import subprocess
import sys
import os
import threading
import time
import socket
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NGINX_CONF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nginx.conf")

STREAMLIT_PORT = 8501
FASTAPI_PORT = 8000
NGINX_PORT = 5000


def wait_for_port(port, host="127.0.0.1", timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.create_connection((host, port), timeout=1)
            s.close()
            return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


def run_fastapi():
    import uvicorn
    from src.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=FASTAPI_PORT, log_level="info")


def run_streamlit():
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/dashboard/app.py",
        f"--server.port={STREAMLIT_PORT}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--server.enableWebsocketCompression=false",
    ])


def setup_tmp_dirs():
    for d in ["client_temp", "proxy_temp", "fastcgi_temp", "uwsgi_temp", "scgi_temp", "nginx_client_body"]:
        os.makedirs(f"/tmp/{d}", exist_ok=True)


def run_nginx():
    setup_tmp_dirs()

    result = subprocess.run(
        ["nginx", "-t", "-c", NGINX_CONF],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.error(f"Nginx config test failed: {result.stderr}")
        return

    logger.info("Nginx config OK, starting...")
    proc = subprocess.Popen(
        ["nginx", "-g", "daemon off;", "-c", NGINX_CONF, "-e", "/tmp/nginx_error.log"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    def log_nginx_stderr():
        for line in proc.stderr:
            logger.info(f"NGINX: {line.decode().strip()}")

    threading.Thread(target=log_nginx_stderr, daemon=True).start()
    proc.wait()


if __name__ == "__main__":
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info(f"FastAPI iniciando en 127.0.0.1:{FASTAPI_PORT}")

    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()
    logger.info(f"Streamlit iniciando en 127.0.0.1:{STREAMLIT_PORT}")

    logger.info("Esperando que Streamlit y FastAPI esten listos...")
    if wait_for_port(STREAMLIT_PORT):
        logger.info(f"Streamlit listo en puerto {STREAMLIT_PORT}")
    else:
        logger.error(f"Streamlit no respondio en 60 segundos (puerto {STREAMLIT_PORT})")

    if wait_for_port(FASTAPI_PORT):
        logger.info(f"FastAPI listo en puerto {FASTAPI_PORT}")
    else:
        logger.error(f"FastAPI no respondio en 60 segundos (puerto {FASTAPI_PORT})")

    logger.info(f"Nginx reverse proxy iniciando en 0.0.0.0:{NGINX_PORT}")
    run_nginx()
