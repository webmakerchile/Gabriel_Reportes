import asyncio
import logging
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.database import SessionLocal
from src.etl.sync_service import SyncService
from src.reports.excel_generator import generate_vendedor_report
from src.reports.email_service import (
    send_report_email,
    build_report_email_html,
    check_email_config,
)

logger = logging.getLogger(__name__)

TRACKED_VENDEDOR_IDS = ["28856", "28886", "28887", "28891", "28892"]

# ── FIX 1: Singleton para evitar schedulers duplicados al reiniciar FastAPI ──
_scheduler_instance = None


def scheduled_sync_and_report():
    logger.info("Ejecutando sincronización diaria (ligera)...")
    db = SessionLocal()
    try:
        service = SyncService(db)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        results = {}
        results["clientes"] = loop.run_until_complete(service.sync_clientes())
        logger.info(f"Clientes sync: {results['clientes'].get('synced', '?')}")
        results["ventas"] = loop.run_until_complete(service.sync_ventas())
        logger.info(f"Ventas sync: {results['ventas'].get('synced', '?')}")

        # ── FIX 2: Sync items desde inicio del año, no solo 45 días ──
        # Esto asegura que el reporte anual tenga datos completos de items
        # para clasificar Maquinaria vs Repuestos en todos los meses.
        today = date.today()
        fecha_desde = date(today.year, 1, 1).strftime("%Y-%m-%d")
        fecha_hasta = today.strftime("%Y-%m-%d")
        results["ventas_items"] = loop.run_until_complete(
            service.sync_ventas_items_incremental(fecha_desde, fecha_hasta)
        )
        logger.info(
            f"Ventas items sync (año completo): {results['ventas_items'].get('synced', '?')}"
        )

        results["ventas_cobros"] = loop.run_until_complete(service.sync_ventas_cobros())
        results["empleados"] = loop.run_until_complete(service.sync_empleados())
        results["productos"] = loop.run_until_complete(service.sync_productos())

        loop.close()
        logger.info("Sincronización diaria completada")

        date_from = date(today.year, 1, 1)
        date_to = today
        _generate_and_send_individual_reports(db, date_from, date_to)

    except Exception as e:
        logger.error(f"Error en tarea programada: {e}", exc_info=True)
    finally:
        db.close()


def _generate_and_send_individual_reports(db, date_from, date_to):
    """Genera reportes y envía cada uno SOLO a los emails del vendedor correspondiente."""
    from src.models.models import ReporteProgramado, Empleado

    email_config = check_email_config()
    if not email_config["configured"]:
        logger.warning(
            "Email no configurado (RESEND_API_KEY). Generando reportes sin enviar."
        )

    date_range_str = (
        f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"
    )

    schedules = (
        db.query(ReporteProgramado).filter(ReporteProgramado.activo == True).all()
    )
    sched_by_vendedor = {}
    for s in schedules:
        if s.vendedor_obuma_id:
            sched_by_vendedor[str(s.vendedor_obuma_id)] = s

    all_filepaths = []
    for vid in TRACKED_VENDEDOR_IDS:
        try:
            fp = generate_vendedor_report(db, vid, date_from, date_to)
            if not fp:
                continue
            all_filepaths.append(fp)
            logger.info(f"Reporte generado: {fp}")

            if not email_config["configured"]:
                continue

            sched = sched_by_vendedor.get(vid)
            if not sched or not sched.emails_destino:
                logger.warning(f"Vendedor {vid}: sin emails configurados, reporte no enviado")
                continue

            emails = [
                e.strip()
                for e in sched.emails_destino.replace("\n", ",").split(",")
                if e.strip() and "@" in e.strip()
            ]
            if not emails:
                continue

            emp = (
                db.query(Empleado)
                .filter(Empleado.obuma_id == vid)
                .first()
            )
            vname = emp.nombre if emp else f"Vendedor {vid}"

            subject = f"Reporte {vname} - {date_range_str}"
            body = build_report_email_html(
                vname,
                "Reporte Diario Automático",
                date_range_str,
                {
                    "Vendedor": vname,
                    "Periodo": date_range_str,
                    "Generado": datetime.now().strftime("%d/%m/%Y %H:%M"),
                },
            )

            result = send_report_email(emails, subject, body, [fp])
            if result["success"]:
                logger.info(f"Reporte {vname} enviado a: {emails}")
            else:
                logger.error(f"Error enviando reporte {vname}: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error generando/enviando reporte vendedor {vid}: {e}", exc_info=True)

    logger.info(f"Reportes generados: {len(all_filepaths)} archivos")


def process_scheduled_reports():
    from src.models.models import ReporteProgramado, Empleado

    logger.info("Verificando reportes programados...")
    db = SessionLocal()
    try:
        now = datetime.now()
        schedules = (
            db.query(ReporteProgramado).filter(ReporteProgramado.activo == True).all()
        )

        for sched in schedules:
            if not _should_execute(sched, now):
                continue

            logger.info(f"Ejecutando reporte programado: {sched.nombre}")
            try:
                date_from, date_to = _resolve_schedule_dates(sched)

                filepaths = []
                vendedor_names = []

                if sched.tipo_reporte == "individual" and sched.vendedor_obuma_id:
                    fp = generate_vendedor_report(
                        db, sched.vendedor_obuma_id, date_from, date_to
                    )
                    if fp:
                        filepaths.append(fp)
                    emp = (
                        db.query(Empleado)
                        .filter(Empleado.obuma_id == sched.vendedor_obuma_id)
                        .first()
                    )
                    vendedor_names.append(
                        emp.nombre if emp else sched.vendedor_obuma_id
                    )
                else:
                    for vid in TRACKED_VENDEDOR_IDS:
                        fp = generate_vendedor_report(db, vid, date_from, date_to)
                        if fp:
                            filepaths.append(fp)
                    vendedor_names.append("Todos los Vendedores")

                if filepaths:
                    email_config = check_email_config()
                    if email_config["configured"]:
                        emails = [
                            e.strip()
                            for e in sched.emails_destino.replace("\n", ",").split(",")
                            if e.strip()
                        ]
                        if emails:
                            vname = ", ".join(vendedor_names)
                            date_range_str = f"{date_from.strftime('%d/%m/%Y')} - {date_to.strftime('%d/%m/%Y')}"
                            subject = f"Reporte {sched.nombre} - {date_range_str}"
                            body = build_report_email_html(
                                vname,
                                sched.nombre,
                                date_range_str,
                                {
                                    "Archivos generados": len(filepaths),
                                    "Periodo": date_range_str,
                                },
                            )
                            result = send_report_email(emails, subject, body, filepaths)
                            if result["success"]:
                                logger.info(
                                    f"Email enviado para '{sched.nombre}' a {emails}"
                                )
                            else:
                                logger.error(
                                    f"Error enviando email para '{sched.nombre}': {result.get('error')}"
                                )
                    else:
                        logger.warning(
                            f"Email no configurado, reportes generados pero no enviados para '{sched.nombre}'"
                        )

                sched.ultima_ejecucion = now
                sched.total_enviados = (sched.total_enviados or 0) + 1
                sched.proxima_ejecucion = _calc_next_execution(sched, now)
                db.commit()
                logger.info(
                    f"Reporte programado '{sched.nombre}' completado, proxima ejecucion: {sched.proxima_ejecucion}"
                )

            except Exception as e:
                logger.error(
                    f"Error procesando reporte programado '{sched.nombre}': {e}",
                    exc_info=True,
                )

    except Exception as e:
        logger.error(f"Error general en process_scheduled_reports: {e}", exc_info=True)
    finally:
        db.close()


def _should_execute(sched, now):
    if sched.ultima_ejecucion:
        diff = (now - sched.ultima_ejecucion).total_seconds()
        if diff < 3600:
            return False

    if sched.proxima_ejecucion:
        return now >= sched.proxima_ejecucion

    sched.proxima_ejecucion = _calc_next_execution(sched, now)
    return now >= sched.proxima_ejecucion


def _resolve_schedule_dates(sched):
    today = date.today()

    if sched.filtro_fecha_tipo == "mes_actual":
        return date(today.year, today.month, 1), today
    elif sched.filtro_fecha_tipo == "mes_anterior":
        first_this = date(today.year, today.month, 1)
        last_prev = first_this - timedelta(days=1)
        first_prev = date(last_prev.year, last_prev.month, 1)
        return first_prev, last_prev
    elif sched.filtro_fecha_tipo == "ultimo_trimestre":
        return today - timedelta(days=90), today
    elif sched.filtro_fecha_tipo == "ano_actual":
        return date(today.year, 1, 1), today
    elif sched.filtro_fecha_tipo == "personalizado":
        return sched.filtro_fecha_desde or date(
            today.year, 1, 1
        ), sched.filtro_fecha_hasta or today
    else:
        return date(today.year, today.month, 1), today


def _calc_next_execution(sched, now):
    hour = sched.hora or 8
    minute = sched.minuto or 0

    freq = (sched.frecuencia or "").lower()

    if freq == "diario":
        nxt = (now + timedelta(days=1)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    elif freq == "semanal":
        days_ahead = (sched.dia_semana or 0) - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        nxt = (now + timedelta(days=days_ahead)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    elif freq == "quincenal":
        nxt = (now + timedelta(days=14)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    elif freq == "mensual":
        day = sched.dia_mes or 1
        if now.month == 12:
            nxt = datetime(now.year + 1, 1, min(day, 28), hour, minute)
        else:
            nxt = datetime(now.year, now.month + 1, min(day, 28), hour, minute)
    else:
        nxt = now + timedelta(days=1)

    return nxt


def start_scheduler():
    # ── FIX 1: Singleton — evita crear múltiples schedulers al reiniciar FastAPI ──
    global _scheduler_instance
    if _scheduler_instance is not None:
        try:
            if _scheduler_instance.running:
                logger.info("Scheduler ya está corriendo, omitiendo reinicio.")
                return _scheduler_instance
        except Exception:
            pass

    scheduler = BackgroundScheduler(timezone="America/Santiago")
    scheduler.add_job(
        scheduled_sync_and_report,
        CronTrigger(hour=18, minute=30, timezone="America/Santiago"),
        id="daily_sync_report",
        name="Sincronización y Reporte Diario 18:30 Chile",
        replace_existing=True,
    )
    scheduler.add_job(
        process_scheduled_reports,
        IntervalTrigger(minutes=15, timezone="America/Santiago"),
        id="check_scheduled_reports",
        name="Verificar Reportes Programados (cada 15 min)",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler_instance = scheduler
    logger.info(
        "Scheduler iniciado - Sync diario 18:30 + Verificacion programados cada 15 min"
    )
    return scheduler
