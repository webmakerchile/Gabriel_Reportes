import subprocess
import sys
import os
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def run_fastapi(port=8000):
    import uvicorn
    from src.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


def run_streamlit(port=5000):
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/dashboard/app.py",
        f"--server.port={port}",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--server.enableWebsocketCompression=false",
    ])


if __name__ == "__main__":
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info("FastAPI iniciado en puerto 8000 (interno)")

    logger.info("Iniciando Streamlit en puerto 5000")
    run_streamlit(port=5000)
