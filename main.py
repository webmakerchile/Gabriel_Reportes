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


def run_fastapi(port=8000):
    import uvicorn
    from src.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


def run_streamlit(port=5001):
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/dashboard/app.py",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--server.enableWebsocketCompression=false",
    ])


def run_nginx():
    os.makedirs("/tmp/nginx_client_body", exist_ok=True)
    result = subprocess.run(
        ["nginx", "-t", "-c", NGINX_CONF],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        logger.error(f"Nginx config test failed: {result.stderr}")
        return

    logger.info("Nginx config OK, starting...")
    proc = subprocess.Popen(
        ["nginx", "-g", "daemon off;", "-c", NGINX_CONF],
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
    logger.info("FastAPI iniciando en 127.0.0.1:8000")

    streamlit_thread = threading.Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()
    logger.info("Streamlit iniciando en 127.0.0.1:5001")

    logger.info("Esperando que Streamlit y FastAPI esten listos...")
    if wait_for_port(5001):
        logger.info("Streamlit listo en puerto 5001")
    else:
        logger.error("Streamlit no respondio en 60 segundos")

    if wait_for_port(8000):
        logger.info("FastAPI listo en puerto 8000")
    else:
        logger.error("FastAPI no respondio en 60 segundos")

    logger.info("Nginx reverse proxy iniciando en 0.0.0.0:5000")
    run_nginx()
