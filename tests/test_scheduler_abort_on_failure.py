"""Regression tests para la garantia "fallo de sync de Obuma => 0 correos enviados".

Estos tests blindan la conducta abort-on-failure del scheduler. Si alguien
manana cambia algo y deja pasar un correo con datos viejos, estos tests
deben fallar inmediatamente.

Cubre:
  1. sync_for_report levanta RuntimeError si sync_clientes falla.
  2. sync_for_report levanta RuntimeError si sync_ventas falla.
  3. sync_for_report levanta RuntimeError si sync_ventas_items_incremental falla.
  4. sync_for_report levanta RuntimeError si sync_ventas_cobros falla.
     [NOTA: la spec original de la tarea decia "cobros es non-blocking", pero
     el codigo actual lo trata como BLOQUEANTE (excel_generator.py linea 1191-1198)
     porque sin cobros frescos los saldos POR PAGAR de cartera y los KPIs de
     cobranza serian erroneos. El test refleja la conducta REAL del codigo,
     que es la deseada por el equipo. Si en el futuro se decide volver
     cobros a non-blocking, este test debe actualizarse a la par.]
  5. _generate_and_send_individual_reports con sync mockeado a fallar:
     send_report_email se llamo 0 veces.
  6. process_scheduled_reports con 5 schedules due y sync mockeado a fallar:
     send_report_email se llamo 0 veces.

Ningun test requiere conexion real a Obuma ni a Resend.
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _AsyncReturn:
    """Coroutine-like object: una funcion mock async que devuelve un valor fijo."""

    def __init__(self, value):
        self._value = value

    def __call__(self, *_args, **_kwargs):
        async def _coro():
            return self._value

        return _coro()


def _make_sync_service_mock(
    clientes=None,
    ventas=None,
    ventas_items=None,
    ventas_cobros=None,
):
    """Crea un mock de SyncService con metodos async configurables."""
    svc = MagicMock()
    svc.sync_clientes = _AsyncReturn(clientes if clientes is not None else {"synced": 10})
    svc.sync_ventas = _AsyncReturn(ventas if ventas is not None else {"synced": 20})
    svc.sync_ventas_items_incremental = _AsyncReturn(
        ventas_items if ventas_items is not None else {"synced": 30}
    )
    svc.sync_ventas_cobros = _AsyncReturn(
        ventas_cobros if ventas_cobros is not None else {"synced": 40}
    )
    return svc


def _make_schedule(idx, vendedor_id="28856"):
    """Construye un mock de ReporteProgramado due."""
    sched = MagicMock()
    sched.id = idx
    sched.nombre = f"Schedule {idx}"
    sched.activo = True
    sched.vendedor_obuma_id = vendedor_id
    sched.tipo_reporte = "individual"
    sched.emails_destino = "test@example.com"
    sched.frecuencia = "diario"
    sched.hora = 8
    sched.minuto = 0
    sched.dia_semana = 0
    sched.dia_mes = 1
    sched.filtro_fecha_tipo = "ano_actual"
    sched.filtro_fecha_desde = None
    sched.filtro_fecha_hasta = None
    sched.ultima_ejecucion = None
    sched.proxima_ejecucion = datetime.now() - timedelta(hours=1)
    sched.total_enviados = 0
    return sched


# ---------------------------------------------------------------------------
# 1-4: sync_for_report y propagacion de fallos
# ---------------------------------------------------------------------------

def test_sync_for_report_raises_when_sync_clientes_fails():
    from src.reports import excel_generator

    svc = _make_sync_service_mock(clientes={"error": "boom-clientes"})
    with patch.object(excel_generator, "SyncService", return_value=svc, create=True):
        # SyncService se importa adentro de la funcion -> patch del modulo origen.
        with patch("src.etl.sync_service.SyncService", return_value=svc):
            with pytest.raises(RuntimeError, match="sync_clientes"):
                excel_generator.sync_for_report(db=MagicMock(), scope="test")


def test_sync_for_report_raises_when_sync_ventas_fails():
    from src.reports import excel_generator

    svc = _make_sync_service_mock(ventas={"error": "boom-ventas"})
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(RuntimeError, match="sync_ventas"):
            excel_generator.sync_for_report(db=MagicMock(), scope="test")


def test_sync_for_report_raises_when_sync_ventas_items_fails():
    from src.reports import excel_generator

    svc = _make_sync_service_mock(ventas_items={"error": "boom-items"})
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(RuntimeError, match="sync_ventas_items_incremental"):
            excel_generator.sync_for_report(db=MagicMock(), scope="test")


def test_sync_for_report_raises_when_sync_ventas_cobros_fails():
    """Cobros es BLOQUEANTE (ver docstring del modulo). Cambio: la spec original
    de la tarea pedia que cobros fuese non-blocking; el codigo de produccion
    decidio hacerlo blocking porque sin cobros frescos los saldos POR PAGAR de
    cartera y los KPIs de cobranza serian erroneos. Este test refleja la
    conducta real y deseada del codigo actual."""
    from src.reports import excel_generator

    svc = _make_sync_service_mock(ventas_cobros={"error": "boom-cobros"})
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(RuntimeError, match="sync_ventas_cobros"):
            excel_generator.sync_for_report(db=MagicMock(), scope="test")


def test_sync_for_report_returns_dict_when_all_ok():
    """Sanity check: si los 4 syncs van OK, sync_for_report retorna el dict
    completo y no levanta. Asegura que las assertions de fallo no son triviales."""
    from src.reports import excel_generator

    svc = _make_sync_service_mock()
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        result = excel_generator.sync_for_report(db=MagicMock(), scope="test-ok")
    assert set(result.keys()) == {"clientes", "ventas", "ventas_items", "ventas_cobros"}
    assert result["clientes"]["synced"] == 10
    assert result["ventas_cobros"]["synced"] == 40


# ---------------------------------------------------------------------------
# 5: _generate_and_send_individual_reports => 0 emails si sync falla
# ---------------------------------------------------------------------------

def test_generate_and_send_individual_reports_does_not_send_email_when_sync_fails():
    from src import scheduler

    db = MagicMock()
    with patch.object(
        scheduler,
        "sync_for_report",
        side_effect=RuntimeError("sync_clientes fallo: boom"),
    ) as mock_sync, patch.object(
        scheduler, "send_report_email"
    ) as mock_send, patch.object(
        scheduler, "generate_vendedor_report"
    ) as mock_gen, patch.object(
        scheduler, "log_reconciliation_per_vendor"
    ) as mock_recon, patch.object(
        scheduler, "check_email_config", return_value={"configured": True}
    ):
        scheduler._generate_and_send_individual_reports(
            db, date(2026, 1, 1), date(2026, 4, 29), scope="UnitTest"
        )

    mock_sync.assert_called_once()
    # GARANTIA CRITICA: 0 correos enviados.
    assert mock_send.call_count == 0, (
        f"send_report_email NO debe llamarse cuando sync falla; "
        f"se llamo {mock_send.call_count} veces"
    )
    # Y tampoco se generan Excels (porque abortamos antes).
    assert mock_gen.call_count == 0
    # Reconciliacion tampoco corre porque retornamos antes.
    assert mock_recon.call_count == 0


# ---------------------------------------------------------------------------
# 6: process_scheduled_reports con 5 schedules due => 0 emails si sync falla
# ---------------------------------------------------------------------------

def test_process_scheduled_reports_does_not_send_any_email_when_sync_fails():
    from src import scheduler

    schedules = [_make_schedule(i) for i in range(1, 6)]  # 5 schedules due

    # Mock de la query: db.query(...).filter(...).all() -> schedules
    fake_query = MagicMock()
    fake_query.filter.return_value.all.return_value = schedules

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with patch.object(scheduler, "SessionLocal", return_value=fake_db), patch.object(
        scheduler,
        "sync_for_report",
        side_effect=RuntimeError("sync_ventas fallo: timeout Obuma"),
    ) as mock_sync, patch.object(
        scheduler, "send_report_email"
    ) as mock_send, patch.object(
        scheduler, "generate_vendedor_report"
    ) as mock_gen, patch.object(
        scheduler, "log_reconciliation_per_vendor"
    ), patch.object(
        scheduler, "_should_execute", return_value=True
    ):
        scheduler.process_scheduled_reports()

    # Sync se intento UNA SOLA vez (todos los schedules comparten el sync del tick).
    mock_sync.assert_called_once()
    # GARANTIA CRITICA: ningun reporte de los 5 schedules due se envia.
    assert mock_send.call_count == 0, (
        f"send_report_email NO debe llamarse cuando sync falla; "
        f"se llamo {mock_send.call_count} veces para {len(schedules)} schedules due"
    )
    # Tampoco se generan Excels.
    assert mock_gen.call_count == 0


def test_process_scheduled_reports_no_sync_if_no_schedules_due():
    """Sanity: si no hay schedules due, sync_for_report NO se llama y por
    transitividad tampoco hay correos. Asegura que la logica no llama sync
    inutilmente."""
    from src import scheduler

    schedules = [_make_schedule(i) for i in range(1, 4)]
    fake_query = MagicMock()
    fake_query.filter.return_value.all.return_value = schedules

    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with patch.object(scheduler, "SessionLocal", return_value=fake_db), patch.object(
        scheduler, "sync_for_report"
    ) as mock_sync, patch.object(
        scheduler, "send_report_email"
    ) as mock_send, patch.object(
        scheduler, "_should_execute", return_value=False
    ):
        scheduler.process_scheduled_reports()

    assert mock_sync.call_count == 0
    assert mock_send.call_count == 0
