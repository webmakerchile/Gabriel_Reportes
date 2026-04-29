"""Tests para el helper que reporta el estado del proveedor de correo
(Resend / SendGrid / SMTP) y el log de arranque que avisa si esta
sin configurar o si EMAIL_FROM quedo en sandbox.

Si manana alguien rompe el parseo de las variables o cambia el mensaje de
arranque, estos tests fallan y obligan a actualizar tambien `replit.md`.
"""
import logging

import pytest

from src.reports.email_service import (
    check_email_config,
    log_email_config_status,
)


_EMAIL_VARS = (
    "RESEND_API_KEY",
    "SENDGRID_API_KEY",
    "SMTP_HOST",
    "SMTP_USER",
    "SMTP_PASS",
    "SMTP_PORT",
    "EMAIL_FROM",
    "EMAIL_FROM_NAME",
)


@pytest.fixture(autouse=True)
def _clear_email_env(monkeypatch):
    """Cada test arranca con TODAS las vars de email limpias."""
    for var in _EMAIL_VARS:
        monkeypatch.delenv(var, raising=False)
    yield


# ---------------------------------------------------------------------------
# check_email_config
# ---------------------------------------------------------------------------

def test_check_email_config_unset():
    cfg = check_email_config()
    assert cfg["configured"] is False
    assert cfg["method"] is None
    assert cfg["sandbox"] is False
    assert cfg["from_email"] is None


def test_check_email_config_resend_sandbox(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_xxx")
    # EMAIL_FROM no se setea - cae al default sandbox onboarding@resend.dev
    cfg = check_email_config()
    assert cfg["configured"] is True
    assert cfg["method"] == "Resend"
    assert cfg["sandbox"] is True
    assert cfg["from_email"] == "onboarding@resend.dev"


def test_check_email_config_resend_with_verified_domain(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_xxx")
    monkeypatch.setenv("EMAIL_FROM", "reportes@autoreportes.cl")
    cfg = check_email_config()
    assert cfg["configured"] is True
    assert cfg["method"] == "Resend"
    assert cfg["sandbox"] is False
    assert cfg["from_email"] == "reportes@autoreportes.cl"


def test_check_email_config_sendgrid(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "sg_xxx")
    monkeypatch.setenv("EMAIL_FROM", "reportes@autoreportes.cl")
    cfg = check_email_config()
    assert cfg["configured"] is True
    assert cfg["method"] == "SendGrid"
    assert cfg["sandbox"] is False


def test_check_email_config_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "secret")
    monkeypatch.setenv("EMAIL_FROM", "user@example.com")
    cfg = check_email_config()
    assert cfg["configured"] is True
    assert cfg["method"] == "SMTP"
    assert cfg["sandbox"] is False


def test_check_email_config_smtp_missing_pass_is_unconfigured(monkeypatch):
    # send_report_email() exige SMTP_HOST + SMTP_USER + SMTP_PASS para
    # poder mandar; check_email_config() debe reflejar el mismo criterio
    # para que el log de arranque no diga "SMTP OK" cuando en realidad
    # el envio rebotaria por falta de password.
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("EMAIL_FROM", "user@example.com")
    cfg = check_email_config()
    assert cfg["configured"] is False
    assert cfg["method"] is None


# ---------------------------------------------------------------------------
# log_email_config_status
# ---------------------------------------------------------------------------

def test_log_email_config_status_warns_when_unset(caplog):
    with caplog.at_level(logging.WARNING):
        cfg = log_email_config_status()
    assert cfg["configured"] is False
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    # Debe ser muy explicito: la palabra clave "EMAIL: NO CONFIGURADO" tiene
    # que aparecer y debe nombrar las variables a definir.
    assert any("EMAIL: NO CONFIGURADO" in m for m in warnings), warnings
    assert any("RESEND_API_KEY" in m for m in warnings), warnings


def test_log_email_config_status_warns_in_sandbox_mode(monkeypatch, caplog):
    monkeypatch.setenv("RESEND_API_KEY", "re_xxx")
    # EMAIL_FROM cae en default sandbox
    with caplog.at_level(logging.WARNING):
        cfg = log_email_config_status()
    assert cfg["configured"] is True
    assert cfg["sandbox"] is True
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    # Debe decir explicitamente que esta en sandbox y mencionar el remitente.
    assert any("sandbox" in m.lower() for m in warnings), warnings
    assert any("onboarding@resend.dev" in m for m in warnings), warnings
    assert any("Resend" in m for m in warnings), warnings


def test_log_email_config_status_info_when_resend_with_verified_domain(monkeypatch, caplog):
    monkeypatch.setenv("RESEND_API_KEY", "re_xxx")
    monkeypatch.setenv("EMAIL_FROM", "reportes@autoreportes.cl")
    with caplog.at_level(logging.INFO):
        cfg = log_email_config_status()
    assert cfg["configured"] is True
    assert cfg["sandbox"] is False
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    # Debe decir "Resend OK" y nombrar el remitente.
    assert any("EMAIL: Resend OK" in m for m in infos), infos
    assert any("reportes@autoreportes.cl" in m for m in infos), infos
    # Y NO debe haber warning en este caso.
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings == [], warnings


def test_log_email_config_status_info_when_sendgrid(monkeypatch, caplog):
    monkeypatch.setenv("SENDGRID_API_KEY", "sg_xxx")
    monkeypatch.setenv("EMAIL_FROM", "reportes@autoreportes.cl")
    with caplog.at_level(logging.INFO):
        cfg = log_email_config_status()
    assert cfg["configured"] is True
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("EMAIL: SendGrid OK" in m for m in infos), infos


def test_log_email_config_status_info_when_smtp(monkeypatch, caplog):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "secret")
    monkeypatch.setenv("EMAIL_FROM", "user@example.com")
    with caplog.at_level(logging.INFO):
        cfg = log_email_config_status()
    assert cfg["configured"] is True
    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("EMAIL: SMTP OK" in m for m in infos), infos
