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
