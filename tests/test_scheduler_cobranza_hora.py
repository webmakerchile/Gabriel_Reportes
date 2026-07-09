"""Blinda el horario del reporte de cobranza del lunes.

El cliente exige que el correo LLEGUE ANTES de las 09:00. El cron corre a las
05:30 (America/Santiago) para dejar colchon de sobra. Si alguien mueve la hora
sin querer, este test falla.
"""
from unittest.mock import patch

from apscheduler.schedulers.background import BackgroundScheduler


def test_cobranza_lunes_registrada_a_las_0530():
    from src import scheduler as sched_mod

    old_instance = sched_mod._scheduler_instance
    sched_mod._scheduler_instance = None
    try:
        # start() parcheado: no levanta threads, pero los jobs quedan pendientes
        # y son inspeccionables via get_job().
        with patch.object(BackgroundScheduler, "start"):
            s = sched_mod.start_scheduler()

        job = s.get_job("weekly_monday_cobranza_reports")
        assert job is not None, "el job de cobranza del lunes debe existir"
        trigger = str(job.trigger)
        assert "day_of_week='mon'" in trigger
        assert "hour='5'" in trigger, f"cobranza debe correr a las 05:30, trigger={trigger}"
        assert "minute='30'" in trigger

        # El diario sigue a las 06:30 (no debe haberse movido).
        daily = s.get_job("daily_weekday_reports")
        assert daily is not None
        daily_trigger = str(daily.trigger)
        assert "hour='6'" in daily_trigger and "minute='30'" in daily_trigger
    finally:
        sched_mod._scheduler_instance = old_instance
