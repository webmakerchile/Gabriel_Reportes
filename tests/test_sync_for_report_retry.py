"""Regression tests para el reintento-unico ante cortes de conexion DB en
sync_for_report.

Contexto (14/07/2026): el Reporte Diario no llego a NADIE porque, tras ~9 min
descargando paginas del API de Obuma, la primera query de
sync_ventas_items_incremental encontro la conexion a Postgres muerta
("SSL connection has been closed unexpectedly") y el abort-on-failure cancelo
el envio completo. Un corte transitorio de conexion NO debe costar el envio
del dia: ahora cada paso se reintenta UNA vez (rollback + re-ejecucion del
paso completo, que es idempotente) antes de rendirse.

Cubre:
  1. Un OperationalError transitorio en un paso => rollback + reintento y el
     sync completa OK (el reporte se envia).
  2. OperationalError persistente (falla tambien el reintento) => la
     excepcion se propaga (abort-on-failure intacto: 0 correos).
  3. Errores que NO son de conexion (p.ej. ValueError) NO se reintentan.

Ningun test requiere conexion real a Obuma ni a Postgres.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError, InterfaceError, OperationalError


def _make_operational_error(msg="SSL connection has been closed unexpectedly"):
    return OperationalError("SELECT 1", {}, Exception(msg))


class _AsyncReturn:
    """Funcion mock async que devuelve un valor fijo."""

    def __init__(self, value):
        self._value = value
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        value = self._value

        async def _coro():
            return value

        return _coro()


class _AsyncFlaky:
    """Funcion mock async que falla las primeras `fail_times` llamadas con
    `exc` y despues devuelve `value`."""

    def __init__(self, value, exc, fail_times=1):
        self._value = value
        self._exc = exc
        self._fail_times = fail_times
        self.calls = 0

    def __call__(self, *_args, **_kwargs):
        self.calls += 1
        should_fail = self.calls <= self._fail_times
        value = self._value
        exc = self._exc

        async def _coro():
            if should_fail:
                raise exc
            return value

        return _coro()


def _make_svc(items_behavior):
    svc = MagicMock()
    svc.sync_clientes = _AsyncReturn({"synced": 10})
    svc.sync_ventas = _AsyncReturn({"synced": 20})
    svc.sync_ventas_items_incremental = items_behavior
    svc.sync_ventas_cobros = _AsyncReturn({"synced": 40})
    return svc


def test_transient_disconnect_is_retried_and_sync_completes():
    """Corte transitorio en ventas_items: el paso se reintenta 1 vez, el sync
    completa y se hizo rollback antes del reintento."""
    from src.reports import excel_generator

    flaky = _AsyncFlaky({"synced": 30}, _make_operational_error(), fail_times=1)
    svc = _make_svc(flaky)
    db = MagicMock()
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        result = excel_generator.sync_for_report(db=db, scope="test-retry")

    assert flaky.calls == 2, "el paso debe re-ejecutarse exactamente una vez mas"
    assert result["ventas_items"]["synced"] == 30
    assert db.rollback.called, "debe hacerse rollback antes del reintento"
    # Los demas pasos NO se re-ejecutan.
    assert svc.sync_clientes.calls == 1
    assert svc.sync_ventas.calls == 1
    assert svc.sync_ventas_cobros.calls == 1


def test_persistent_disconnect_still_aborts():
    """Si el reintento tambien falla, la excepcion se propaga y el flujo
    llamador aborta el envio (garantia abort-on-failure intacta)."""
    from src.reports import excel_generator

    flaky = _AsyncFlaky({"synced": 30}, _make_operational_error(), fail_times=2)
    svc = _make_svc(flaky)
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(OperationalError):
            excel_generator.sync_for_report(db=MagicMock(), scope="test-retry")

    assert flaky.calls == 2, "exactamente 1 intento + 1 reintento, no mas"


def test_interface_error_is_also_retried():
    """InterfaceError ('connection already closed') es otra cara del mismo
    corte de conexion y tambien debe reintentarse."""
    from src.reports import excel_generator

    exc = InterfaceError("SELECT 1", {}, Exception("connection already closed"))
    flaky = _AsyncFlaky({"synced": 30}, exc, fail_times=1)
    svc = _make_svc(flaky)
    db = MagicMock()
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        result = excel_generator.sync_for_report(db=db, scope="test-retry")

    assert flaky.calls == 2
    assert result["ventas_items"]["synced"] == 30


def test_integrity_error_is_not_retried():
    """IntegrityError es un error de DATOS (DBAPIError pero no de conexion):
    reintentarlo repetiria el mismo choque. Debe propagarse al primer intento."""
    from src.reports import excel_generator

    exc = IntegrityError("INSERT ...", {}, Exception("unique violation"))
    exc.connection_invalidated = False
    flaky = _AsyncFlaky({"synced": 30}, exc, fail_times=1)
    svc = _make_svc(flaky)
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(IntegrityError):
            excel_generator.sync_for_report(db=MagicMock(), scope="test-retry")

    assert flaky.calls == 1, "sin reintento para errores de integridad de datos"


def test_non_connection_errors_are_not_retried():
    """Un error de logica (no de conexion) NO debe reintentarse: se propaga
    al primer intento."""
    from src.reports import excel_generator

    flaky = _AsyncFlaky({"synced": 30}, ValueError("bug de datos"), fail_times=1)
    svc = _make_svc(flaky)
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(ValueError):
            excel_generator.sync_for_report(db=MagicMock(), scope="test-retry")

    assert flaky.calls == 1, "sin reintento para errores no-OperationalError"


def test_lock_released_after_persistent_failure():
    """El candado _sync_report_lock debe quedar libre aunque el sync falle
    (si quedara tomado, TODOS los reportes posteriores se colgarian)."""
    from src.reports import excel_generator

    flaky = _AsyncFlaky({"synced": 30}, _make_operational_error(), fail_times=2)
    svc = _make_svc(flaky)
    with patch("src.etl.sync_service.SyncService", return_value=svc):
        with pytest.raises(OperationalError):
            excel_generator.sync_for_report(db=MagicMock(), scope="test-lock")

    acquired = excel_generator._sync_report_lock.acquire(blocking=False)
    assert acquired, "el lock debe quedar liberado tras el fallo"
    excel_generator._sync_report_lock.release()
