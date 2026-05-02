"""Tests del helper de filtros de fecha amigable al planner (Fase 3).

Cubre la equivalencia semantica de los reemplazos:
  - ``func.date(col) >= df AND func.date(col) <= dt`` -> rango sobre col pura.
  - ``extract('year/month', col) == ...`` -> ``col >= start AND col < end_excl``.

Los tests son puros (no tocan DB): validan los timestamps que produce el
helper y la composicion de la lista de filtros que se desempaca con ``*``.
"""
from datetime import date, datetime, timedelta

import pytest

from src.utils.date_filters import (
    date_range_filters,
    to_end_excl_dt,
    to_start_dt,
    year_month_range,
)


# ---------------- to_start_dt ----------------


def test_to_start_dt_date_to_midnight():
    assert to_start_dt(date(2026, 5, 2)) == datetime(2026, 5, 2, 0, 0, 0)


def test_to_start_dt_datetime_passthrough():
    dt = datetime(2026, 5, 2, 14, 30, 15)
    assert to_start_dt(dt) is dt


def test_to_start_dt_none():
    assert to_start_dt(None) is None


# ---------------- to_end_excl_dt ----------------


def test_to_end_excl_dt_date_is_day_after():
    """date inclusivo -> datetime del dia siguiente a 00:00 (borde exclusivo)."""
    assert to_end_excl_dt(date(2026, 5, 2)) == datetime(2026, 5, 3, 0, 0, 0)


def test_to_end_excl_dt_datetime_passthrough():
    """Si el caller ya maneja datetime, NO se le suma un dia."""
    dt = datetime(2026, 5, 2, 23, 59, 59)
    assert to_end_excl_dt(dt) is dt


def test_to_end_excl_dt_none():
    assert to_end_excl_dt(None) is None


def test_to_end_excl_dt_handles_month_boundary():
    """Cruza fin de mes correctamente."""
    assert to_end_excl_dt(date(2026, 1, 31)) == datetime(2026, 2, 1, 0, 0, 0)


def test_to_end_excl_dt_handles_year_boundary():
    """Cruza fin de año correctamente."""
    assert to_end_excl_dt(date(2026, 12, 31)) == datetime(2027, 1, 1, 0, 0, 0)


# ---------------- date_range_filters (composicion) ----------------


class _FakeCol:
    """Stub mínimo: captura las comparaciones >= y < sin tocar SQLAlchemy."""

    def __ge__(self, other):
        return ("ge", other)

    def __lt__(self, other):
        return ("lt", other)


def test_date_range_filters_both_none_returns_empty_list():
    """Sin fechas: lista vacia. query.filter(*[]) es no-op en SQLAlchemy."""
    assert date_range_filters(_FakeCol(), None, None) == []


def test_date_range_filters_only_from():
    conds = date_range_filters(_FakeCol(), date(2026, 1, 1), None)
    assert conds == [("ge", datetime(2026, 1, 1, 0, 0, 0))]


def test_date_range_filters_only_to():
    """Solo date_to: genera 1 cond < day_after_to (incluye date_to completo)."""
    conds = date_range_filters(_FakeCol(), None, date(2026, 1, 31))
    assert conds == [("lt", datetime(2026, 2, 1, 0, 0, 0))]


def test_date_range_filters_both():
    conds = date_range_filters(_FakeCol(), date(2026, 1, 1), date(2026, 1, 31))
    assert conds == [
        ("ge", datetime(2026, 1, 1, 0, 0, 0)),
        ("lt", datetime(2026, 2, 1, 0, 0, 0)),
    ]


def test_date_range_filters_includes_full_last_day():
    """Cualquier hora del ultimo dia debe quedar dentro del rango."""
    _, end_excl = (
        date_range_filters(_FakeCol(), date(2026, 1, 1), date(2026, 1, 31))[0][1],
        date_range_filters(_FakeCol(), date(2026, 1, 1), date(2026, 1, 31))[1][1],
    )
    # Ventas a las 23:59:59 del dia date_to deben pasar el filtro col < end_excl.
    last_second = datetime(2026, 1, 31, 23, 59, 59)
    assert last_second < end_excl


# ---------------- year_month_range ----------------


def test_year_month_range_year_only():
    """Sin mes: rango anual completo."""
    assert year_month_range(2026) == (
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2027, 1, 1, 0, 0, 0),
    )


def test_year_month_range_january():
    assert year_month_range(2026, 1) == (
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2026, 2, 1, 0, 0, 0),
    )


def test_year_month_range_mid_year():
    assert year_month_range(2026, 5) == (
        datetime(2026, 5, 1, 0, 0, 0),
        datetime(2026, 6, 1, 0, 0, 0),
    )


def test_year_month_range_december_crosses_year():
    """Diciembre: end_excl debe ser 1 enero del año siguiente."""
    assert year_month_range(2026, 12) == (
        datetime(2026, 12, 1, 0, 0, 0),
        datetime(2027, 1, 1, 0, 0, 0),
    )


@pytest.mark.parametrize("month", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
def test_year_month_range_end_is_strictly_after_start(month):
    start, end_excl = year_month_range(2026, month)
    assert end_excl > start


def test_year_month_range_covers_full_month_inclusive():
    """Cualquier instante DENTRO del mes pasa el predicado start <= x < end."""
    start, end = year_month_range(2026, 2)
    last_second_of_feb = datetime(2026, 2, 28, 23, 59, 59)
    first_of_march = datetime(2026, 3, 1, 0, 0, 0)
    assert start <= last_second_of_feb < end
    assert not (start <= first_of_march < end)
