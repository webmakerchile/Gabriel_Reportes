import asyncio
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from src.database import SessionLocal
from src.etl.sync_service import SyncService
from src.reports.excel_generator import generate_all_vendedor_reports

logger = logging.getLogger(__name__)


def scheduled_sync_and_report():
    logger.info("Ejecutando sincronización y generación de reportes programados...")
    db = SessionLocal()
    try:
        service = SyncService(db)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(service.sync_all())
        loop.close()
        logger.info(f"Sincronización completada: {results}")

        filepaths = generate_all_vendedor_reports(db, date.today().year)
        logger.info(f"Reportes por vendedor generados: {len(filepaths)} archivos")
        for fp in filepaths:
            logger.info(f"  -> {fp}")
    except Exception as e:
        logger.error(f"Error en tarea programada: {e}")
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler(timezone="America/Santiago")
    scheduler.add_job(
        scheduled_sync_and_report,
        CronTrigger(hour=23, minute=50, timezone="America/Santiago"),
        id="daily_sync_report",
        name="Sincronización y Reporte Diario 23:50 Chile",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado - Reporte diario programado para 23:50 hora Chile")
    return scheduler
