import subprocess
import sys
import os
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

IS_DEPLOYMENT = os.environ.get("REPL_DEPLOYMENT", "") == "1"


def run_fastapi(port=8000):
    import uvicorn
    from src.api.main import app
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def run_streamlit():
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        "src/dashboard/app.py",
        "--server.port=5000",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
    ])


if __name__ == "__main__":
    if IS_DEPLOYMENT:
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Modo producción: FastAPI en puerto {port}")
        run_fastapi(port=port)
    else:
        fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
        fastapi_thread.start()
        logger.info("FastAPI iniciado en puerto 8000")

        logger.info("Iniciando Streamlit en puerto 5000")
        run_streamlit()
