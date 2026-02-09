import subprocess
import sys
import os
import threading
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def seed_database():
    from src.database import SessionLocal, engine, Base
    from src.etl.api_catalog_seed import seed_api_catalog
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_api_catalog(db)
    finally:
        db.close()


def run_fastapi():
    import uvicorn
    from src.api.main import app
    from src.scheduler import start_scheduler

    seed_database()
    start_scheduler()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


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
    fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
    fastapi_thread.start()
    logger.info("FastAPI iniciado en puerto 8000")

    logger.info("Iniciando Streamlit en puerto 5000")
    run_streamlit()
