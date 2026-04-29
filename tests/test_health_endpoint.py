"""Tests del endpoint GET /api/health (Task #15).

Cubre:
- Forma del JSON: contiene 'status', 'email', 'admin_alerts', 'scheduler', 'timestamp'.
- Privacidad: NUNCA expone correos individuales de ADMIN_ALERT_EMAILS, solo cantidad.
- status = "ok" cuando email configurado + scheduler corriendo.
- status = "degraded" si email NO configurado (sin proveedor).
- status = "degraded" si scheduler NO corriendo (down).
- admin_alerts.recipients_count refleja la cantidad real (1, varios, 0).
- Endpoint siempre responde 200 (los clientes deben mirar 'status').
"""
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Importar dentro del fixture para que parches sobre src.scheduler /
    # src.reports.email_service no se queden cacheados entre tests.
    from src.api import main as api_main
    return TestClient(api_main.app)


def _patch_email(configured=True, sandbox=False):
    return patch(
        "src.api.main.check_email_config",
        return_value={
            "configured": configured,
            "method": "Resend" if configured else None,
            "detail": "API Key configurada" if configured else "Sin configurar.",
            "sandbox": sandbox,
            "from_email": "reportes@autoreportes.cl" if configured else None,
        },
    )


def _patch_scheduler(running=True, jobs_count=5):
    jobs = [
        {"id": f"j{i}", "name": f"Job {i}", "next_run": "2026-04-30T09:00:00-04:00"}
        for i in range(jobs_count)
    ] if running else []
    return patch(
        "src.api.main.get_scheduler_status",
        return_value={
            "running": running,
            "state": "ok" if running else "down",
            "jobs_count": len(jobs),
            "jobs": jobs,
        },
    )


def _patch_alerts(emails):
    return patch(
        "src.api.main.check_admin_alert_config",
        return_value={
            "configured": bool(emails),
            "emails": list(emails),
            "raw": ",".join(emails),
            "reason": "" if emails else "ADMIN_ALERT_EMAILS no esta definida",
        },
    )


def test_health_returns_expected_shape(client):
    with _patch_email(), _patch_scheduler(), _patch_alerts(["gabriel@vlsur.cl"]):
        r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"status", "timestamp", "email", "admin_alerts", "scheduler", "scheduler_detail"}
    assert "configured" in body["email"]
    assert "recipients_count" in body["admin_alerts"]
    # scheduler es string segun el contrato del spec; el detalle va aparte.
    assert isinstance(body["scheduler"], str)
    assert body["scheduler"] in ("ok", "down")
    assert "running" in body["scheduler_detail"]
    assert "jobs" in body["scheduler_detail"]


def test_health_status_ok_when_email_and_scheduler_ok(client):
    with _patch_email(configured=True), _patch_scheduler(running=True), _patch_alerts([]):
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_status_degraded_when_email_not_configured(client):
    with _patch_email(configured=False), _patch_scheduler(running=True), _patch_alerts(["x@y.cl"]):
        r = client.get("/api/health")
    assert r.json()["status"] == "degraded"


def test_health_status_degraded_when_scheduler_down(client):
    with _patch_email(configured=True), _patch_scheduler(running=False), _patch_alerts(["x@y.cl"]):
        r = client.get("/api/health")
    body = r.json()
    assert body["status"] == "degraded"
    assert body["scheduler"] == "down"
    assert body["scheduler_detail"]["running"] is False
    assert body["scheduler_detail"]["jobs_count"] == 0


def test_health_does_not_leak_admin_alert_emails(client):
    """CRITICO de privacidad: nunca exponer las direcciones individuales."""
    secret_emails = ["gabriel.secreto@vlsur.cl", "admin.privado@vlsur.cl"]
    with _patch_email(), _patch_scheduler(), _patch_alerts(secret_emails):
        r = client.get("/api/health")
    body_str = r.text
    for em in secret_emails:
        assert em not in body_str, f"Filtracion: {em} aparecio en el JSON publico"
    # Pero la cantidad si debe estar
    assert r.json()["admin_alerts"]["recipients_count"] == 2
    assert r.json()["admin_alerts"]["configured"] is True


def test_health_admin_alerts_zero_when_not_configured(client):
    with _patch_email(), _patch_scheduler(), _patch_alerts([]):
        r = client.get("/api/health")
    body = r.json()
    assert body["admin_alerts"]["configured"] is False
    assert body["admin_alerts"]["recipients_count"] == 0
    assert body["admin_alerts"]["reason"]  # texto no vacio


def test_health_scheduler_jobs_have_next_run(client):
    with _patch_email(), _patch_scheduler(running=True, jobs_count=3), _patch_alerts([]):
        r = client.get("/api/health")
    body = r.json()
    assert body["scheduler"] == "ok"
    jobs = body["scheduler_detail"]["jobs"]
    assert len(jobs) == 3
    for j in jobs:
        assert "id" in j and "name" in j and "next_run" in j


def test_health_returns_200_even_when_everything_is_down(client):
    """El endpoint siempre debe responder 200 — el cliente mira 'status'."""
    with _patch_email(configured=False), _patch_scheduler(running=False), _patch_alerts([]):
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "degraded"
