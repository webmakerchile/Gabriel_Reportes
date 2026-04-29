"""Tests del monitor interno de salud (`internal_health_check`).

Cubre:
- Estado OK cuando email + scheduler estan configurados.
- Estado degraded con razon correcta cuando falta correo.
- Estado degraded con razon correcta cuando scheduler no corre.
- Multiple razones acumuladas.
- Cooldown: la segunda llamada dentro del cooldown NO envia alerta.
- Tras pasar el cooldown, vuelve a enviar.
- Si check_email_config lanza, lo trata como degraded sin propagar.
- Si get_scheduler_status lanza, lo trata como degraded sin propagar.
- _send_health_degraded_alert hace no-op silencioso si ADMIN_ALERT_EMAILS no esta.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import src.scheduler as sched_mod


def _reset_cooldown():
    sched_mod._last_alert_sent_at.clear()


def test_health_ok_when_email_and_scheduler_configured():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", return_value={"configured": True}), \
         patch.object(sched_mod, "get_scheduler_status", return_value={"running": True, "state": "ok"}), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "ok"
    assert result["reasons"] == []
    mock_alert.assert_not_called()


def test_health_degraded_when_email_not_configured():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", return_value={"configured": False}), \
         patch.object(sched_mod, "get_scheduler_status", return_value={"running": True, "state": "ok"}), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("correo" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_when_scheduler_not_running():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", return_value={"configured": True}), \
         patch.object(sched_mod, "get_scheduler_status", return_value={"running": False, "state": "down"}), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert any("scheduler" in r.lower() for r in result["reasons"])
    mock_alert.assert_called_once()


def test_health_degraded_accumulates_multiple_reasons():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", return_value={"configured": False}), \
         patch.object(sched_mod, "get_scheduler_status", return_value={"running": False, "state": "down"}), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    assert len(result["reasons"]) == 2
    mock_alert.assert_called_once()
    args, _ = mock_alert.call_args
    assert len(args[0]) == 2  # ambas razones pasadas a la alerta


def test_health_check_does_not_propagate_when_email_helper_raises():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", side_effect=RuntimeError("boom")), \
         patch.object(sched_mod, "get_scheduler_status", return_value={"running": True, "state": "ok"}), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        # No debe lanzar
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    mock_alert.assert_called_once()


def test_health_check_does_not_propagate_when_scheduler_helper_raises():
    _reset_cooldown()
    with patch.object(sched_mod, "check_email_config", return_value={"configured": True}), \
         patch.object(sched_mod, "get_scheduler_status", side_effect=RuntimeError("boom")), \
         patch.object(sched_mod, "_send_health_degraded_alert") as mock_alert:
        result = sched_mod.internal_health_check()
    assert result["status"] == "degraded"
    mock_alert.assert_called_once()


def test_alert_cooldown_blocks_second_call_within_window():
    """Dentro de la ventana de cooldown, la segunda llamada NO envia alerta."""
    _reset_cooldown()
    # Simulamos send_admin_alert exitoso para que se setee el cooldown.
    with patch.object(sched_mod, "send_admin_alert", return_value={"success": True}):
        sched_mod._send_health_degraded_alert(["razon test"])
    # Ahora debe haber timestamp registrado
    assert "Salud del Sistema" in sched_mod._last_alert_sent_at

    # Segunda llamada inmediata: debe omitirse (no llama a send_admin_alert)
    with patch.object(sched_mod, "send_admin_alert") as mock_send:
        sched_mod._send_health_degraded_alert(["razon test 2"])
        mock_send.assert_not_called()


def test_alert_cooldown_expires_and_sends_again():
    """Tras pasar el cooldown, vuelve a enviar."""
    _reset_cooldown()
    # Insertar timestamp viejo (mas alla del cooldown)
    old = datetime.now() - timedelta(hours=sched_mod.ALERT_COOLDOWN_HOURS + 0.5)
    sched_mod._last_alert_sent_at["Salud del Sistema"] = old

    with patch.object(sched_mod, "send_admin_alert", return_value={"success": True}) as mock_send:
        sched_mod._send_health_degraded_alert(["razon test"])
        mock_send.assert_called_once()


def test_alert_skipped_silently_when_admin_emails_not_configured():
    """Si ADMIN_ALERT_EMAILS no esta, send_admin_alert retorna skipped y no rompe."""
    _reset_cooldown()
    with patch.object(
        sched_mod,
        "send_admin_alert",
        return_value={"skipped": True, "reason": "ADMIN_ALERT_EMAILS no definida"},
    ):
        # No debe lanzar y NO debe registrar timestamp (porque no se envio)
        sched_mod._send_health_degraded_alert(["razon test"])
    assert "Salud del Sistema" not in sched_mod._last_alert_sent_at


def test_alert_helper_never_propagates_exceptions():
    """Si send_admin_alert lanza, _send_health_degraded_alert NO debe propagar."""
    _reset_cooldown()
    with patch.object(sched_mod, "send_admin_alert", side_effect=RuntimeError("smtp down")):
        # No debe lanzar
        sched_mod._send_health_degraded_alert(["razon test"])
