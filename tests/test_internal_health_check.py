"""Tests del monitor interno de salud (`internal_health_check`).

El monitor sondea el endpoint HTTP `/api/health` con timeout. Cubre:
- HTTP 200 + status="ok" → OK, sin alerta.
- HTTP 200 + status="degraded" + email no configurado → razón email.
- HTTP 200 + status="degraded" + scheduler down → razón scheduler.
- HTTP 200 + status="degraded" + ambos componentes mal → 2 razones.
- HTTP 200 + status="degraded" pero componentes OK → razón fallback.
- HTTP 200 + JSON sin "status" → razón "JSON sin status".
- HTTP 200 + body no-JSON → razón "no-JSON".
- HTTP 500 → razón "respondió HTTP 500".
- httpx.TimeoutException → razón "no respondió en 10s".
- httpx.ConnectError → razón "no responde".
- Excepción genérica del request → razón "Error consultando".
- Cooldown: la segunda llamada dentro de 1h NO envia alerta.
- Cooldown expira y vuelve a enviar.
- Sin ADMIN_ALERT_EMAILS: send_admin_alert retorna skipped, no rompe.
- send_admin_alert lanzando excepción NO se propaga.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import httpx
import pytest

import src.scheduler as sched_mod


def _reset_cooldown():
    sched_mod._last_alert_sent_at.clear()


def _mock_response(status_code: int = 200, json_data: dict = None, raise_json: bool = False):
    """Helper para construir un mock de httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    if raise_json:
        resp.json.side_effect = ValueError("not json")
    else:
        resp.json.return_value = json_data or {}
    return resp


# ─────────── Estado OK ───────────

def test_health_ok_when_endpoint_returns_status_ok():
    _reset_cooldown()
    resp = _mock_response(200, {
        "status": "ok",
        "email": {"configured": True},
        "scheduler": "ok",
    })
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "ok"
    assert result["reasons"] == []
    mock_alert.assert_not_called()


# ─────────── Razones derivadas del JSON ───────────

def test_health_degraded_when_json_says_email_not_configured():
    _reset_cooldown()
    resp = _mock_response(200, {
        "status": "degraded",
        "email": {"configured": False},
        "scheduler": "ok",
    })
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("correo" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_json_says_scheduler_down():
    _reset_cooldown()
    resp = _mock_response(200, {
        "status": "degraded",
        "email": {"configured": True},
        "scheduler": "down",
    })
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("scheduler" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_accumulates_multiple_reasons():
    _reset_cooldown()
    resp = _mock_response(200, {
        "status": "degraded",
        "email": {"configured": False},
        "scheduler": "down",
    })
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert len(result["reasons"]) == 2
    mock_alert.assert_called_once()
    args, _ = mock_alert.call_args
    assert len(args[0]) == 2


def test_health_degraded_fallback_when_components_ok_but_status_degraded():
    """Si JSON dice degraded pero email+scheduler aparecen OK, igual alertamos."""
    _reset_cooldown()
    resp = _mock_response(200, {
        "status": "degraded",
        "email": {"configured": True},
        "scheduler": "ok",
    })
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("sin componente identificable" in r for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_json_missing_status_field():
    _reset_cooldown()
    resp = _mock_response(200, {"email": {"configured": True}, "scheduler": "ok"})
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("sin campo" in r.lower() or "status" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


# ─────────── Errores HTTP / red ───────────

def test_health_degraded_when_endpoint_returns_non_200():
    _reset_cooldown()
    resp = _mock_response(500, None)
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("HTTP 500" in r for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_endpoint_returns_non_json_body():
    _reset_cooldown()
    resp = _mock_response(200, raise_json=True)
    with patch("httpx.get", return_value=resp), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("no-JSON" in r for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_request_times_out():
    _reset_cooldown()
    with patch("httpx.get", side_effect=httpx.TimeoutException("timeout!")), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("timeout" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_connection_refused():
    _reset_cooldown()
    with patch("httpx.get", side_effect=httpx.ConnectError("conn refused")), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("connection error" in r.lower() or "no responde" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_on_unexpected_exception_does_not_propagate():
    _reset_cooldown()
    with patch("httpx.get", side_effect=RuntimeError("boom inesperado")), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        # No debe lanzar
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("error consultando" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


# ─────────── Cooldown del helper ───────────

def test_alert_cooldown_blocks_second_call_within_window():
    _reset_cooldown()
    with patch.object(sched_mod, "send_admin_alert", return_value={"success": True}):
        sched_mod._send_health_degraded_alert(["razon test"])
    assert "Salud del Sistema" in sched_mod._last_alert_sent_at

    with patch.object(sched_mod, "send_admin_alert") as mock_send:
        sched_mod._send_health_degraded_alert(["razon test 2"])
        mock_send.assert_not_called()


def test_alert_cooldown_expires_and_sends_again():
    _reset_cooldown()
    old = datetime.now() - timedelta(hours=sched_mod.ALERT_COOLDOWN_HOURS + 0.5)
    sched_mod._last_alert_sent_at["Salud del Sistema"] = old

    with patch.object(sched_mod, "send_admin_alert", return_value={"success": True}) as mock_send:
        sched_mod._send_health_degraded_alert(["razon test"])
        mock_send.assert_called_once()


def test_alert_skipped_silently_when_admin_emails_not_configured():
    _reset_cooldown()
    with patch.object(
        sched_mod,
        "send_admin_alert",
        return_value={"skipped": True, "reason": "ADMIN_ALERT_EMAILS no definida"},
    ):
        sched_mod._send_health_degraded_alert(["razon test"])
    assert "Salud del Sistema" not in sched_mod._last_alert_sent_at


def test_alert_helper_never_propagates_exceptions():
    _reset_cooldown()
    with patch.object(sched_mod, "send_admin_alert", side_effect=RuntimeError("smtp down")):
        # No debe lanzar
        sched_mod._send_health_degraded_alert(["razon test"])
