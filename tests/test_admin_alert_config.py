"""Tests para el helper que reporta el estado de ADMIN_ALERT_EMAILS y el log
de arranque que avisa si las alertas a admin estan sin configurar.

Si manana alguien rompe el parseo de la variable o cambia el mensaje de
arranque, estos tests fallan y obligan a actualizar tambien `replit.md`
y la pestana "Configuracion de Email" del dashboard.
"""
import logging

import pytest

from src.reports.email_service import (
    check_admin_alert_config,
    log_admin_alert_config_status,
)


# ---------------------------------------------------------------------------
# check_admin_alert_config
# ---------------------------------------------------------------------------

def test_check_admin_alert_config_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_ALERT_EMAILS", raising=False)
    cfg = check_admin_alert_config()
    assert cfg["configured"] is False
    assert cfg["emails"] == []
    assert "no esta definida" in cfg["reason"]


def test_check_admin_alert_config_blank(monkeypatch):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "   \n  ")
    cfg = check_admin_alert_config()
    assert cfg["configured"] is False
    assert cfg["emails"] == []


def test_check_admin_alert_config_no_valid_emails(monkeypatch):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "pepe, juanito")
    cfg = check_admin_alert_config()
    assert cfg["configured"] is False
    assert cfg["emails"] == []
    assert "no contiene correos validos" in cfg["reason"]


def test_check_admin_alert_config_single(monkeypatch):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "admin@example.com")
    cfg = check_admin_alert_config()
    assert cfg["configured"] is True
    assert cfg["emails"] == ["admin@example.com"]


def test_check_admin_alert_config_csv_with_noise(monkeypatch):
    # Acepta separador coma y/o newline; descarta espacios y items sin '@'.
    monkeypatch.setenv(
        "ADMIN_ALERT_EMAILS",
        "gabriel@vlsur.cl,\notro@vlsur.cl ,  basura  , ",
    )
    cfg = check_admin_alert_config()
    assert cfg["configured"] is True
    assert cfg["emails"] == ["gabriel@vlsur.cl", "otro@vlsur.cl"]


# ---------------------------------------------------------------------------
# log_admin_alert_config_status
# ---------------------------------------------------------------------------

def test_log_admin_alert_config_status_warns_when_unset(monkeypatch, caplog):
    monkeypatch.delenv("ADMIN_ALERT_EMAILS", raising=False)
    with caplog.at_level(logging.WARNING):
        cfg = log_admin_alert_config_status()
    assert cfg["configured"] is False
    # Debe ser muy explicito: la palabra clave "NO CONFIGURADAS" tiene que aparecer.
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("ALERTAS DE ADMIN: NO CONFIGURADAS" in m for m in warnings), warnings
    assert any("ADMIN_ALERT_EMAILS" in m for m in warnings), warnings


def test_log_admin_alert_config_status_info_when_set(monkeypatch, caplog):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "gabriel@vlsur.cl,otro@vlsur.cl")
    with caplog.at_level(logging.INFO):
        cfg = log_admin_alert_config_status()
    assert cfg["configured"] is True
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    # Debe nombrar a los dos destinatarios y decir "configuradas".
    assert any("ALERTAS DE ADMIN: configuradas" in m for m in infos), infos
    assert any("gabriel@vlsur.cl" in m and "otro@vlsur.cl" in m for m in infos), infos


# ---------------------------------------------------------------------------
# send_admin_alert sigue respetando el helper compartido
# ---------------------------------------------------------------------------

def test_send_admin_alert_skips_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_ALERT_EMAILS", raising=False)
    from src.reports.email_service import send_admin_alert
    res = send_admin_alert("subject", "<p>body</p>")
    assert res["success"] is False
    assert res["skipped"] is True


def test_send_admin_alert_skips_when_no_valid_emails(monkeypatch):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "pepe, juanito")
    from src.reports.email_service import send_admin_alert
    res = send_admin_alert("subject", "<p>body</p>")
    assert res["success"] is False
    assert res["skipped"] is True


def test_send_admin_alert_calls_send_report_email_when_configured(monkeypatch):
    monkeypatch.setenv("ADMIN_ALERT_EMAILS", "admin@example.com,otro@example.com")

    captured = {}

    def fake_send(to_emails, subject, body, attachment_paths=None):
        captured["to"] = to_emails
        captured["subject"] = subject
        captured["attachments"] = attachment_paths
        return {"success": True, "method": "fake", "recipients": to_emails}

    monkeypatch.setattr("src.reports.email_service.send_report_email", fake_send)
    from src.reports.email_service import send_admin_alert
    res = send_admin_alert("subject", "<p>body</p>")
    assert res["success"] is True
    assert captured["to"] == ["admin@example.com", "otro@example.com"]
    assert captured["attachments"] is None
