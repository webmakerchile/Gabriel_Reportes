import asyncio
import logging
from aiohttp import web, ClientSession, WSMsgType, TCPConnector

logger = logging.getLogger(__name__)

STREAMLIT_URL = "http://127.0.0.1:5001"
FASTAPI_URL = "http://127.0.0.1:8000"


def _get_backend(path):
    if path.startswith("/api"):
        return FASTAPI_URL
    return STREAMLIT_URL


def _get_ws_backend(path):
    if path.startswith("/api"):
        return "ws://127.0.0.1:8000"
    return "ws://127.0.0.1:5001"


async def health_check(request):
    return web.Response(text="OK", status=200)


async def handle_websocket(request):
    path = request.path
    qs = request.query_string
    ws_backend_base = _get_ws_backend(path)
    target = f"{ws_backend_base}{path}"
    if qs:
        target += f"?{qs}"

    protocols = request.headers.get("Sec-WebSocket-Protocol", "").split(", ")
    protocols = [p.strip() for p in protocols if p.strip()]
    ws_server = web.WebSocketResponse(protocols=protocols if protocols else None)
    await ws_server.prepare(request)

    ws_headers = {}
    if protocols:
        ws_headers["Sec-WebSocket-Protocol"] = ", ".join(protocols)

    try:
        async with ClientSession() as session:
            async with session.ws_connect(target, protocols=protocols if protocols else None) as ws_client:
                async def pipe_client_to_backend():
                    try:
                        async for msg in ws_server:
                            if msg.type == WSMsgType.TEXT:
                                await ws_client.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await ws_client.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                break
                    except Exception:
                        pass

                async def pipe_backend_to_client():
                    try:
                        async for msg in ws_client:
                            if msg.type == WSMsgType.TEXT:
                                await ws_server.send_str(msg.data)
                            elif msg.type == WSMsgType.BINARY:
                                await ws_server.send_bytes(msg.data)
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                                break
                    except Exception:
                        pass

                await asyncio.gather(
                    pipe_client_to_backend(),
                    pipe_backend_to_client(),
                    return_exceptions=True,
                )
    except Exception as e:
        logger.debug(f"WebSocket proxy error: {e}")

    return ws_server


async def handle_http(request):
    path = request.path
    qs = request.query_string
    backend = _get_backend(path)
    target = f"{backend}{path}"
    if qs:
        target += f"?{qs}"

    headers = {}
    for k, v in request.headers.items():
        if k.lower() not in ("host", "transfer-encoding", "connection", "upgrade"):
            headers[k] = v

    try:
        body = await request.read()
        async with ClientSession(connector=TCPConnector(force_close=True)) as session:
            async with session.request(
                method=request.method,
                url=target,
                headers=headers,
                data=body if body else None,
                allow_redirects=False,
                timeout=None,
            ) as resp:
                resp_headers = {}
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection", "content-encoding"):
                        resp_headers[k] = v

                response_body = await resp.read()
                return web.Response(
                    body=response_body,
                    status=resp.status,
                    headers=resp_headers,
                )
    except Exception as e:
        return web.Response(
            text=f"<html><head><meta http-equiv='refresh' content='3'></head>"
                 f"<body><h2>Servicio iniciando...</h2>"
                 f"<p>Reintentando en 3 segundos.</p></body></html>",
            status=502,
            content_type="text/html",
        )


async def handle_request(request):
    if request.path == "/_health":
        return await health_check(request)

    upgrade = request.headers.get("Upgrade", "").lower()
    if upgrade == "websocket":
        return await handle_websocket(request)

    return await handle_http(request)


def run_proxy(port=5000):
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", handle_request)
    app.router.add_route("*", "/", handle_request)
    logger.info(f"Reverse proxy starting on 0.0.0.0:{port}")
    web.run_app(app, host="0.0.0.0", port=port, print=None)
