import asyncio
import logging
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from src.database import SessionLocal
from src.etl.sync_service import SyncService
from src.reports.excel_generator import (
    generate_vendedor_report,
    sync_for_report,
    log_reconciliation_per_vendor,
)
from src.reports.email_service import (
    send_report_email,
    build_report_email_html,
    check_email_config,
    send_admin_alert,
    build_admin_alert_html,
)

logger = logging.getLogger(__name__)

TRACKED_VENDEDOR_IDS = ["28856", "28886", "28887", "28891", "28892"]

# ── FIX 1: Singleton para evitar schedulers duplicados al reiniciar FastAPI ──
_scheduler_instance = None

# Anti-spam para alertas de fallo de sync: ultimo envio por scope.
# Evita inundar la bandeja si Obuma esta caido por horas (1 alerta/scope/hora).
ALERT_COOLDOWN_HOURS = 1.0
_last_alert_sent_at: dict = {}


def _send_sync_failure_alert(scope: str, error: Exception) -> None:
    """Envia correo de alerta a ADMIN_ALERT_EMAILS cuando sync_for_report falla.

    - No-op silencioso si no hay ADMIN_ALERT_EMAILS configurado o si no hay
      proveedor de email (por eso send_admin_alert retorna skipped sin lanzar).
    - Aplica cooldown de ALERT_COOLDOWN_HOURS por scope: si ya se envio una
      alerta para ese flujo dentro de la ventana, se omite (solo log debug).
    - Esta funcion NUNCA debe lanzar excepcion: el flujo de aborto del envio
      ya esta en marcha y romper aqui empeoraria las cosas.
    """
    try:
        now = datetime.now()
        last = _last_alert_sent_at.get(scope)
        if last is not None:
            age_h = (now - last).total_seconds() / 3600.0
            if age_h < ALERT_COOLDOWN_HOURS:
                logger.debug(
                    f"Alerta admin para '{scope}' omitida (cooldown {age_h:.2f}h < "
                    f"{ALERT_COOLDOWN_HOURS}h)"
                )
                return

        subject = f"[ALERTA] {scope} - sync con Obuma fallo, no se envio el reporte"
        body = build_admin_alert_html(
            scope=scope,
            error_text=str(error)[:500],
            occurred_at=now,
            suggestion=(
                "Revisa que la API de Obuma este accesible y que las credenciales "
                "OBUMA_API_KEY / OBUMA_BASE_URL sigan validas. Cuando Obuma este OK, "
                "puedes regenerar y reenviar el reporte manualmente desde el dashboard."
            ),
        )
        result = send_admin_alert(subject, body)
        if result.get("skipped"):
            logger.warning(
                f"Alerta admin para '{scope}' no enviada: {result.get('reason')}. "
                f"Define ADMIN_ALERT_EMAILS para recibirla."
            )
        elif result.get("success"):
            _last_alert_sent_at[scope] = now
            logger.info(
                f"Alerta admin enviada para '{scope}' (cooldown {ALERT_COOLDOWN_HOURS}h activo)"
            )
        else:
            logger.error(
                f"Alerta admin para '{scope}' fallo al enviarse: {result.get('error')}"
            )
    except Exception as alert_err:
        # Nunca propagar — solo loguear.
        logger.error(
            f"Excepcion enviando alerta admin para '{scope}': {alert_err}",
            exc_info=True,
        )


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
        logger.info("Sincronización diaria completada (sin envío de reportes)")

    except Exception as e:
        logger.error(f"Error en tarea programada: {e}", exc_info=True)
    finally:
        db.close()


def weekly_friday_reports():
    """Genera y envia reportes semanales solo los viernes a las 23:00 Chile.
    Sync inmediato + abort-on-failure: si el sync falla NO se envia el correo."""
    logger.info("Ejecutando envio semanal de reportes (viernes 23:00)...")
    db = SessionLocal()
    try:
        today = date.today()
        date_from = date(today.year, 1, 1)
        date_to = today
        _generate_and_send_individual_reports(
            db, date_from, date_to, scope="Reporte Semanal Viernes"
        )
    except Exception as e:
        logger.error(f"Error en envio semanal de reportes: {e}", exc_info=True)
    finally:
        db.close()


def daily_weekday_reports():
    """Reportes diarios automaticos lunes-jueves a las 23:00 Chile (post actividad de Obuma).
    El viernes se omite porque ese dia se envia el reporte semanal a las 23:00.
    Sync inmediato + abort-on-failure: si el sync falla NO se envia el correo."""
    today = date.today()
    # weekday(): lunes=0, martes=1, miercoles=2, jueves=3, viernes=4, sabado=5, domingo=6
    if today.weekday() == 4:
        logger.info("Viernes detectado: omitiendo reporte diario (se enviara el semanal a las 23:00).")
        return
    logger.info(f"Ejecutando envio diario de reportes ({today.strftime('%A')} 23:00)...")
    db = SessionLocal()
    try:
        date_from = date(today.year, 1, 1)
        date_to = today
        _generate_and_send_individual_reports(
            db, date_from, date_to, scope="Reporte Diario Lun-Jue"
        )
    except Exception as e:
        logger.error(f"Error en envio diario de reportes: {e}", exc_info=True)
    finally:
        db.close()


def weekend_morning_reports():
    """Reportes de fin de semana sabado y domingo a las 09:00 Chile.
    A esa hora la actividad del dia anterior en Obuma ya esta cerrada y
    cualquier movimiento posterior se reflejara en el envio del lunes 23:00.
    Sync inmediato + abort-on-failure: si el sync falla NO se envia el correo."""
    today = date.today()
    logger.info(f"Ejecutando envio de fin de semana ({today.strftime('%A')} 09:00)...")
    db = SessionLocal()
    try:
        date_from = date(today.year, 1, 1)
        date_to = today
        _generate_and_send_individual_reports(
            db, date_from, date_to, scope="Reporte Fin de Semana"
        )
    except Exception as e:
        logger.error(f"Error en envio de fin de semana: {e}", exc_info=True)
    finally:
        db.close()


def _generate_and_send_individual_reports(db, date_from, date_to, scope: str = "Reporte"):
    """Genera reportes y envia cada uno SOLO a los emails del vendedor correspondiente.

    Sync inmediato + abort-on-failure: ANTES de generar cualquier Excel ejecuta
    sync_for_report (clientes + ventas + items + cobros). Si falla, NO se envia
    NINGUN correo y se loguea el error claramente. Esto garantiza que Gabriel
    nunca recibe datos incompletos disfrazados de buenos.
    """
    from src.models.models import ReporteProgramado, Empleado

    # 1) Sync inmediato. Si falla, ABORTAMOS sin enviar nada y notificamos
    #    al admin (correo a ADMIN_ALERT_EMAILS, con cooldown de 1h por scope).
    try:
        sync_for_report(db, scope=scope)
    except Exception as sync_err:
        logger.error(
            f"{scope}: sync inmediato FALLO -- NO se envia ningun correo. Causa: {sync_err}",
            exc_info=True,
        )
        _send_sync_failure_alert(scope, sync_err)
        return

    # 2) Reconciliacion post-sync (no bloqueante, solo audit log).
    try:
        log_reconciliation_per_vendor(db, date.today(), scope=scope)
    except Exception as recon_err:
        logger.warning(f"{scope}: reconciliacion fallo (no bloqueante): {recon_err}")

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

        # Pre-check: ¿hay algun reporte realmente listo para ejecutar?
        # Solo en ese caso justificamos pagar el costo del sync inmediato.
        due_schedules = [s for s in schedules if _should_execute(s, now)]
        if not due_schedules:
            return

        # Sync inmediato + abort-on-failure UNA SOLA VEZ por tick (todos los
        # schedules due en este tick comparten los mismos datos frescos).
        # Si falla, alertamos al admin (con cooldown) ademas del log.
        try:
            sync_for_report(db, scope="Reportes Programados")
        except Exception as sync_err:
            logger.error(
                f"Reportes Programados: sync inmediato FALLO -- NO se envia "
                f"ningun reporte programado. {len(due_schedules)} schedule(s) "
                f"omitidos en este tick. Causa: {sync_err}",
                exc_info=True,
            )
            _send_sync_failure_alert("Reportes Programados", sync_err)
            return

        # Reconciliacion post-sync (no bloqueante).
        try:
            log_reconciliation_per_vendor(
                db, date.today(), scope="Reportes Programados"
            )
        except Exception as recon_err:
            logger.warning(
                f"Reportes Programados: reconciliacion fallo (no bloqueante): {recon_err}"
            )

        for sched in due_schedules:
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
        id="daily_sync",
        name="Sincronización Diaria 18:30 Chile (sin envío)",
        replace_existing=True,
    )
    scheduler.add_job(
        daily_weekday_reports,
        CronTrigger(day_of_week="mon-thu", hour=23, minute=0, timezone="America/Santiago"),
        id="daily_weekday_reports",
        name="Envio Diario de Reportes - Lun-Jue 23:00 Chile",
        replace_existing=True,
    )
    scheduler.add_job(
        weekly_friday_reports,
        CronTrigger(day_of_week="fri", hour=23, minute=0, timezone="America/Santiago"),
        id="weekly_friday_reports",
        name="Envio Semanal de Reportes - Viernes 23:00 Chile",
        replace_existing=True,
    )
    scheduler.add_job(
        weekend_morning_reports,
        CronTrigger(day_of_week="sat,sun", hour=9, minute=0, timezone="America/Santiago"),
        id="weekend_morning_reports",
        name="Envio Reportes Fin de Semana - Sab-Dom 09:00 Chile",
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
        "Scheduler iniciado - Sync ligero diario 18:30 + "
        "Reportes Lun-Jue 23:00 + Reporte Semanal viernes 23:00 + "
        "Reportes Sab-Dom 09:00 + Verificacion programados cada 15 min "
        "(todos con sync inmediato + abort-on-failure)"
    )
    return scheduler
