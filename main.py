import subprocess
import sys
import os
import threading
import time
import socket
import logging
import signal

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

FASTAPI_PORT = 8000
STREAMLIT_PORT = 5000

procs = []
_procs_lock = threading.Lock()


def cleanup(sig=None, frame=None):
    with _procs_lock:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)


def _register_proc(proc):
    """Registra un proceso nuevo y limpia los muertos."""
    with _procs_lock:
        # Limpiar procesos que ya terminaron para evitar memory leak
        procs[:] = [p for p in procs if p.poll() is None]
        procs.append(proc)


def run_fastapi():
    while True:
        logger.info("FastAPI iniciando en puerto %d...", FASTAPI_PORT)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import uvicorn; from src.api.main import app; uvicorn.run(app, host='0.0.0.0', port={FASTAPI_PORT}, log_level='info')",
            ]
        )
        _register_proc(proc)
        proc.wait()
        logger.warning("FastAPI se detuvo, reiniciando en 3s...")
        time.sleep(3)


def run_streamlit():
    while True:
        logger.info("Streamlit iniciando en puerto %d...", STREAMLIT_PORT)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "src/dashboard/app.py",
                f"--server.port={STREAMLIT_PORT}",
                "--server.address=0.0.0.0",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
                "--server.enableCORS=false",
                "--server.enableXsrfProtection=false",
                "--server.enableWebsocketCompression=false",
            ]
        )
        _register_proc(proc)
        proc.wait()
        logger.warning("Streamlit se detuvo, reiniciando en 3s...")
        time.sleep(3)


if __name__ == "__main__":
    threading.Thread(target=run_fastapi, daemon=True).start()

    run_streamlit()
