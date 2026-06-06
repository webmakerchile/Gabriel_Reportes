from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.scheduler import _is_cron_managed_weekly, TRACKED_VENDEDOR_IDS


def _sched(**kw):
    base = dict(
        frecuencia="semanal",
        tipo_reporte="individual",
        dia_semana=5,
        vendedor_obuma_id=TRACKED_VENDEDOR_IDS[0],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_seeded_saturday_weekly_is_suppressed():
    # Las 5 filas semilla (semanal/individual/sabado/vendedor trackeado) las
    # envia el cron weekly_saturday_reports, asi que process_scheduled_reports
    # debe excluirlas para no duplicar el correo.
    for vid in TRACKED_VENDEDOR_IDS:
        assert _is_cron_managed_weekly(_sched(vendedor_obuma_id=vid)) is True


def test_user_weekday_weekly_is_not_suppressed():
    # La UI solo permite dia_semana 0-4; una programacion del usuario nunca cae
    # en sabado, por lo que jamas se suprime.
    for dia in range(0, 5):
        assert _is_cron_managed_weekly(_sched(dia_semana=dia)) is False


def test_non_tracked_vendor_is_not_suppressed():
    assert _is_cron_managed_weekly(_sched(vendedor_obuma_id="99999")) is False


def test_non_weekly_or_non_individual_is_not_suppressed():
    assert _is_cron_managed_weekly(_sched(frecuencia="diario")) is False
    assert _is_cron_managed_weekly(_sched(frecuencia="mensual")) is False
    assert _is_cron_managed_weekly(_sched(tipo_reporte="todos")) is False


def _seed_row(idx, vendedor_id):
    """Mock de una fila semilla del semanal de sabado, marcada como 'due'."""
    s = MagicMock()
    s.id = idx
    s.nombre = f"Reporte Semanal - {vendedor_id}"
    s.activo = True
    s.vendedor_obuma_id = vendedor_id
    s.tipo_reporte = "individual"
    s.frecuencia = "semanal"
    s.dia_semana = 5
    s.hora = 6
    s.minuto = 30
    s.emails_destino = "test@example.com"
    s.ultima_ejecucion = None
    s.proxima_ejecucion = datetime.now() - timedelta(hours=1)  # due
    s.total_enviados = 0
    return s


def test_process_scheduled_reports_skips_saturday_seeds_no_sync_no_send():
    """Si SOLO hay filas semilla del semanal de sabado due, el cron las cubre,
    asi que process_scheduled_reports NO debe sincronizar ni enviar (evita el
    correo semanal duplicado). Se usa el _should_execute real (las filas estan
    due) para verificar que el filtro _is_cron_managed_weekly es quien las
    excluye."""
    from src import scheduler

    schedules = [_seed_row(i, vid) for i, vid in enumerate(TRACKED_VENDEDOR_IDS, 1)]
    fake_query = MagicMock()
    fake_query.filter.return_value.all.return_value = schedules
    fake_db = MagicMock()
    fake_db.query.return_value = fake_query

    with patch.object(scheduler, "SessionLocal", return_value=fake_db), patch.object(
        scheduler, "sync_for_report"
    ) as mock_sync, patch.object(
        scheduler, "send_report_email"
    ) as mock_send, patch.object(
        scheduler, "generate_vendedor_report"
    ) as mock_gen:
        scheduler.process_scheduled_reports()

    # El cron weekly_saturday_reports es el unico emisor: aqui no se sincroniza
    # ni se envia nada.
    assert mock_sync.call_count == 0
    assert mock_send.call_count == 0
    assert mock_gen.call_count == 0
