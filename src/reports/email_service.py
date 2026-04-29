import os
import logging
import smtplib
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

logger = logging.getLogger(__name__)


def send_report_email(to_emails: list, subject: str, body_html: str, attachment_paths: list = None) -> dict:
    resend_key = os.environ.get("RESEND_API_KEY")
    sendgrid_key = os.environ.get("SENDGRID_API_KEY")
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    from_email = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
    from_name = os.environ.get("EMAIL_FROM_NAME", "BI Platform - VLSur")

    if resend_key:
        return _send_via_resend(resend_key, from_email, from_name, to_emails, subject, body_html, attachment_paths)
    elif sendgrid_key:
        return _send_via_sendgrid(sendgrid_key, from_email, from_name, to_emails, subject, body_html, attachment_paths)
    elif smtp_host and smtp_user and smtp_pass:
        return _send_via_smtp(smtp_host, smtp_port, smtp_user, smtp_pass, from_email, from_name, to_emails, subject, body_html, attachment_paths)
    else:
        logger.warning("No email service configured")
        return {"success": False, "error": "No email service configured."}


def _send_via_resend(api_key, from_email, from_name, to_emails, subject, body_html, attachment_paths):
    try:
        import httpx

        attachments_data = []
        if attachment_paths:
            for fpath in attachment_paths:
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        file_data = base64.b64encode(f.read()).decode()
                    attachments_data.append({
                        "filename": os.path.basename(fpath),
                        "content": file_data,
                    })

        payload = {
            "from": f"{from_name} <{from_email}>",
            "to": to_emails,
            "subject": subject,
            "html": body_html,
        }
        if attachments_data:
            payload["attachments"] = attachments_data

        resp = httpx.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if resp.status_code in (200, 201, 202):
            logger.info(f"Email sent via Resend to {to_emails}")
            return {"success": True, "method": "resend", "recipients": to_emails}
        else:
            logger.error(f"Resend error {resp.status_code}: {resp.text}")
            return {"success": False, "error": f"Resend error: {resp.status_code} - {resp.text}"}

    except Exception as e:
        logger.error(f"Resend exception: {e}")
        return {"success": False, "error": str(e)}


def _send_via_sendgrid(api_key, from_email, from_name, to_emails, subject, body_html, attachment_paths):
    try:
        import httpx

        attachments_data = []
        if attachment_paths:
            for fpath in attachment_paths:
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        file_data = base64.b64encode(f.read()).decode()
                    attachments_data.append({
                        "content": file_data,
                        "filename": os.path.basename(fpath),
                        "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "disposition": "attachment"
                    })

        payload = {
            "personalizations": [{"to": [{"email": e.strip()} for e in to_emails]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": [{"type": "text/html", "value": body_html}],
        }
        if attachments_data:
            payload["attachments"] = attachments_data

        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if resp.status_code in (200, 201, 202):
            logger.info(f"Email sent via SendGrid to {to_emails}")
            return {"success": True, "method": "sendgrid", "recipients": to_emails}
        else:
            logger.error(f"SendGrid error {resp.status_code}: {resp.text}")
            return {"success": False, "error": f"SendGrid error: {resp.status_code} - {resp.text}"}

    except Exception as e:
        logger.error(f"SendGrid exception: {e}")
        return {"success": False, "error": str(e)}


def _send_via_smtp(host, port, user, password, from_email, from_name, to_emails, subject, body_html, attachment_paths):
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = ", ".join(to_emails)
        msg["Subject"] = subject
        msg.attach(MIMEText(body_html, "html"))

        if attachment_paths:
            for fpath in attachment_paths:
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(fpath)}")
                    msg.attach(part)

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_email, to_emails, msg.as_string())

        logger.info(f"Email sent via SMTP to {to_emails}")
        return {"success": True, "method": "smtp", "recipients": to_emails}

    except Exception as e:
        logger.error(f"SMTP exception: {e}")
        return {"success": False, "error": str(e)}


def build_report_email_html(vendedor_name: str, report_type: str, date_range: str, summary: dict = None) -> str:
    summary_rows = ""
    if summary:
        for key, val in summary.items():
            summary_rows += f'<tr><td style="padding:8px 12px;border-bottom:1px solid #eee;color:#555;">{key}</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:600;color:#1a1f2e;">{val}</td></tr>'

    return f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <div style="background:linear-gradient(135deg,#2F5496,#1a3a7a);padding:24px 30px;">
            <h1 style="color:#fff;margin:0;font-size:20px;">BI Platform - VLSur</h1>
            <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px;">Reporte Automatico</p>
        </div>
        <div style="padding:24px 30px;">
            <h2 style="color:#1a1f2e;margin:0 0 8px;font-size:18px;">{report_type}</h2>
            <p style="color:#666;margin:0 0 4px;font-size:14px;">Vendedor: <strong>{vendedor_name}</strong></p>
            <p style="color:#666;margin:0 0 20px;font-size:14px;">Periodo: <strong>{date_range}</strong></p>
            <p style="color:#666;margin:0 0 16px;font-size:14px;">Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            {"<table style='width:100%;border-collapse:collapse;margin:16px 0;'>" + summary_rows + "</table>" if summary_rows else ""}
            <p style="color:#888;font-size:12px;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
                El archivo Excel se encuentra adjunto a este correo.<br>
                Este es un reporte automatico generado por BI Platform.
            </p>
        </div>
    </div>
    """


def check_email_config() -> dict:
    resend_key = os.environ.get("RESEND_API_KEY")
    sendgrid_key = os.environ.get("SENDGRID_API_KEY")
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    from_email = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")

    if resend_key:
        sandbox = from_email == "onboarding@resend.dev"
        return {
            "configured": True,
            "method": "Resend",
            "detail": "API Key configurada",
            "sandbox": sandbox,
            "from_email": from_email,
        }
    elif sendgrid_key:
        return {"configured": True, "method": "SendGrid", "detail": "API Key configurada", "sandbox": False, "from_email": from_email}
    elif smtp_host and smtp_user:
        return {"configured": True, "method": "SMTP", "detail": f"Servidor: {smtp_host}", "sandbox": False, "from_email": from_email}
    else:
        return {"configured": False, "method": None, "detail": "Sin configurar.", "sandbox": False, "from_email": None}


def check_admin_alert_config() -> dict:
    """Devuelve el estado de la configuracion de alertas a admin.

    Lee `ADMIN_ALERT_EMAILS` (CSV) y reporta si esta configurada con uno o
    mas correos validos. Es usada al arrancar el servidor (para loguear el
    estado) y por el dashboard (para mostrar el indicador ON/OFF).

    Retorna un dict con:
      - configured (bool): True si hay al menos un correo valido.
      - emails (list[str]): lista de correos parseados (puede estar vacia).
      - raw (str): valor crudo de la variable (para diagnostico).
      - reason (str): explicacion corta cuando configured=False.
    """
    raw = os.environ.get("ADMIN_ALERT_EMAILS", "")
    raw_stripped = raw.strip()
    if not raw_stripped:
        return {
            "configured": False,
            "emails": [],
            "raw": raw,
            "reason": "ADMIN_ALERT_EMAILS no esta definida",
        }
    emails = [
        e.strip()
        for e in raw_stripped.replace("\n", ",").split(",")
        if e.strip() and "@" in e.strip()
    ]
    if not emails:
        return {
            "configured": False,
            "emails": [],
            "raw": raw,
            "reason": "ADMIN_ALERT_EMAILS no contiene correos validos",
        }
    return {
        "configured": True,
        "emails": emails,
        "raw": raw,
        "reason": "",
    }


def log_admin_alert_config_status(logger_obj=None) -> dict:
    """Imprime en logs un mensaje explicito sobre el estado de ADMIN_ALERT_EMAILS.

    Pensada para llamarse al arrancar el servidor (FastAPI startup) para que
    quede MUY visible si nadie va a recibir alertas cuando un envio se aborte.
    Devuelve el mismo dict que `check_admin_alert_config()` por conveniencia.
    """
    log = logger_obj if logger_obj is not None else logger
    cfg = check_admin_alert_config()
    if cfg["configured"]:
        emails_str = ", ".join(cfg["emails"])
        log.info(
            "ALERTAS DE ADMIN: configuradas para %s (%d destinatario%s)",
            emails_str,
            len(cfg["emails"]),
            "" if len(cfg["emails"]) == 1 else "s",
        )
    else:
        log.warning(
            "ALERTAS DE ADMIN: NO CONFIGURADAS (%s) - define ADMIN_ALERT_EMAILS "
            "(CSV de correos) para recibir avisos cuando un reporte automatico "
            "no se envie por fallo de sync con Obuma.",
            cfg["reason"],
        )
    return cfg


def send_admin_alert(subject: str, body_html: str) -> dict:
    """Envia un correo corto de ALERTA a la lista de admins definida en
    la variable de entorno ADMIN_ALERT_EMAILS (separada por coma).

    No lleva attachments y NO depende de ningun dato de Obuma — esta
    pensada para avisar fallos del propio sistema (p.ej. un sync abortado).

    Retorna {"success": bool, ...}. Si no hay ADMIN_ALERT_EMAILS configurado
    o no hay servicio de email, retorna {"success": False, "skipped": True}
    sin levantar excepcion (no debe romper nunca el flujo llamador).
    """
    cfg = check_admin_alert_config()
    if not cfg["configured"]:
        return {"success": False, "skipped": True, "reason": cfg["reason"]}
    admin_emails = cfg["emails"]

    try:
        # Reusa send_report_email sin attachments. Esa funcion ya selecciona
        # Resend/SendGrid/SMTP segun lo que este configurado.
        return send_report_email(admin_emails, subject, body_html, attachment_paths=None)
    except Exception as e:
        logger.error(f"send_admin_alert exception: {e}")
        return {"success": False, "error": str(e)}


def build_admin_alert_html(scope: str, error_text: str, occurred_at: datetime, suggestion: str = None) -> str:
    """Construye el cuerpo HTML del correo de alerta de fallo de sync.

    Escapa scope/error_text/suggestion para que mensajes de error con HTML/`<`/`&`
    no rompan el formato ni inyecten markup en la bandeja del admin.
    """
    import html as _html
    scope_safe = _html.escape(str(scope))
    error_safe = _html.escape(str(error_text))
    suggestion_html = ""
    if suggestion:
        suggestion_html = (
            f'<p style="color:#444;margin:12px 0 0;font-size:14px;">'
            f'<strong>Que hacer:</strong> {_html.escape(str(suggestion))}</p>'
        )
    return f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <div style="background:linear-gradient(135deg,#c0392b,#922b21);padding:24px 30px;">
            <h1 style="color:#fff;margin:0;font-size:20px;">ALERTA - BI Platform VLSur</h1>
            <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">Envio automatico abortado</p>
        </div>
        <div style="padding:24px 30px;">
            <h2 style="color:#1a1f2e;margin:0 0 12px;font-size:17px;">No se envio el reporte</h2>
            <p style="color:#444;margin:0 0 12px;font-size:14px;">
                La sincronizacion con Obuma fallo y, para evitar mandar datos
                desactualizados, el sistema decidio NO enviar el correo
                programado. Ningun vendedor recibio reporte en este turno.
            </p>
            <table style="width:100%;border-collapse:collapse;margin:12px 0;">
                <tr><td style="padding:8px 12px;border-bottom:1px solid #eee;color:#555;width:160px;">Flujo afectado</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:600;color:#1a1f2e;">{scope_safe}</td></tr>
                <tr><td style="padding:8px 12px;border-bottom:1px solid #eee;color:#555;">Fecha y hora</td><td style="padding:8px 12px;border-bottom:1px solid #eee;font-weight:600;color:#1a1f2e;">{occurred_at.strftime('%d/%m/%Y %H:%M')}</td></tr>
                <tr><td style="padding:8px 12px;border-bottom:1px solid #eee;color:#555;vertical-align:top;">Detalle tecnico</td><td style="padding:8px 12px;border-bottom:1px solid #eee;color:#1a1f2e;font-family:monospace;font-size:12px;">{error_safe}</td></tr>
            </table>
            {suggestion_html}
            <p style="color:#888;font-size:12px;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
                Esta alerta se envia con cooldown de 1 hora por flujo para no inundar la bandeja si Obuma esta caido.
            </p>
        </div>
    </div>
    """


def build_health_degraded_alert_html(reasons: list, occurred_at: datetime, health_url: str = None) -> str:
    """Construye el cuerpo HTML para una alerta de salud degradada del sistema.

    A diferencia de la alerta de fallo de sync (rojo), esta usa naranja
    porque el sistema sigue arriba — sólo hay componentes en mal estado
    (correo sin configurar, scheduler caído, etc.).
    """
    import html as _html
    reasons_html = "".join(
        f'<li style="margin:4px 0;color:#1a1f2e;">{_html.escape(str(r))}</li>'
        for r in reasons
    ) or '<li style="color:#888;">(sin detalle)</li>'
    url_html = ""
    if health_url:
        url_html = (
            f'<p style="color:#444;font-size:13px;margin:12px 0 0;">'
            f'Endpoint consultado: <a href="{_html.escape(health_url)}" style="color:#0a66c2;">'
            f'{_html.escape(health_url)}</a></p>'
        )
    return f"""
    <div style="font-family:'Inter',Arial,sans-serif;max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
        <div style="background:linear-gradient(135deg,#e67e22,#ca6f1e);padding:24px 30px;">
            <h1 style="color:#fff;margin:0;font-size:20px;">SALUD DEL SISTEMA - BI Platform VLSur</h1>
            <p style="color:rgba(255,255,255,0.9);margin:6px 0 0;font-size:13px;">Estado degradado detectado</p>
        </div>
        <div style="padding:24px 30px;">
            <h2 style="color:#1a1f2e;margin:0 0 12px;font-size:17px;">El sistema sigue funcionando, pero hay componentes con problemas</h2>
            <p style="color:#444;margin:0 0 12px;font-size:14px;">
                El monitor interno revisó <code>/api/health</code> y detectó
                que el sistema está en estado <strong>degraded</strong>.
                Los reportes pueden no enviarse correctamente hasta que
                esto se solucione.
            </p>
            <p style="color:#1a1f2e;margin:16px 0 6px;font-size:14px;font-weight:600;">Componentes en mal estado:</p>
            <ul style="margin:0 0 8px 18px;padding:0;font-size:14px;">{reasons_html}</ul>
            <p style="color:#444;margin:14px 0 0;font-size:14px;">
                <strong>Hora de la detección:</strong> {occurred_at.strftime('%d/%m/%Y %H:%M')}
            </p>
            {url_html}
            <p style="color:#888;font-size:12px;margin-top:20px;padding-top:16px;border-top:1px solid #eee;">
                Esta alerta se envía con cooldown de 1 hora para no inundar la bandeja
                si el componente queda mal por un rato. Si recibes 2 correos seguidos,
                pasaron al menos 60 minutos entre ellos.
            </p>
        </div>
    </div>
    """


def test_email_delivery(to_email: str) -> dict:
    """Send a real test email and return success/error info."""
    resend_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("EMAIL_FROM", "onboarding@resend.dev")
    from_name = os.environ.get("EMAIL_FROM_NAME", "BI Platform - VLSur")

    if not resend_key:
        return {"success": False, "error": "No hay servicio de email configurado."}

    try:
        import httpx
        payload = {
            "from": f"{from_name} <{from_email}>",
            "to": [to_email],
            "subject": "Prueba de entrega - BI Platform VLSur",
            "html": f"""
            <div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;padding:24px;border:1px solid #eee;border-radius:8px;">
                <h2 style="color:#2F5496;margin:0 0 16px;">BI Platform - VLSur</h2>
                <p style="color:#333;">Este es un correo de prueba enviado desde el sistema de reportes.</p>
                <p style="color:#333;">Si recibiste este mensaje, el envio de reportes automaticos esta funcionando correctamente.</p>
                <hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
                <p style="color:#999;font-size:12px;">Enviado: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            </div>
            """
        }
        resp = httpx.post(
            "https://api.resend.com/emails",
            json=payload,
            headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
            timeout=15
        )
        if resp.status_code in (200, 201, 202):
            return {"success": True, "method": "resend", "recipient": to_email}
        else:
            data = resp.json() if resp.content else {}
            msg = data.get("message", resp.text)
            if "own email address" in msg:
                account_email = msg.split("(")[-1].split(")")[0] if "(" in msg else "tu cuenta"
                return {
                    "success": False,
                    "sandbox": True,
                    "error": f"Resend en modo sandbox: solo puede enviar a {account_email}. Debes verificar el dominio vlsur.cl en resend.com/domains y configurar EMAIL_FROM."
                }
            return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}
