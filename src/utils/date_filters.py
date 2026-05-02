"""Helpers para filtros de fecha amigables al planner de Postgres.

Predicados como ``extract('year', col) == y`` o ``func.date(col) >= d`` aplican
una funcion sobre la columna y por eso el planner ignora los indices btree
existentes (p.ej. ``ix_ventas_vendedor_fecha``). Los helpers aqui devuelven
predicados sobre la columna pura para que el indice se aproveche.

Semantica preservada: ``func.date(col) <= date_to`` se traduce a
``col < day_after_date_to`` para incluir todo el dia ``date_to`` (00:00:00 a
23:59:59) cuando la columna almacena un DateTime con hora.
"""
from datetime import date as date_cls, datetime, time, timedelta
from typing import List, Optional, Tuple, Union


def to_start_dt(d: Union[date_cls, datetime, None]) -> Optional[datetime]:
    """Convierte un date a datetime al inicio del dia (00:00:00).

    Si ``d`` ya es ``datetime`` lo devuelve tal cual. ``None`` propaga ``None``.
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, time.min)


def to_end_excl_dt(d: Union[date_cls, datetime, None]) -> Optional[datetime]:
    """Convierte un date inclusivo a datetime exclusivo del dia siguiente.

    Semantica:
      - Si ``d`` es ``date``: devuelve ``datetime(d + 1 dia, 00:00:00)`` para
        que ``col < retorno`` incluya todo el dia ``d`` (00:00 a 23:59:59).
      - Si ``d`` es ``datetime``: devuelve el mismo instante (es decir, se
        trata como borde EXCLUSIVO exacto, NO como "dia completo"). Esto es
        intencional para callers que ya manejan datetimes con hora propia.
      - ``None`` propaga ``None``.
    """
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    return datetime.combine(d + timedelta(days=1), time.min)


def date_range_filters(col, date_from=None, date_to=None) -> List:
    """Genera la lista de filtros de rango sobre una columna ``DateTime``.

    Equivalente semantico a:
        ``func.date(col) >= date_from AND func.date(col) <= date_to``
    pero sobre la columna pura, asi el planner aprovecha el btree de fecha.

    Uso (con desempaque):
        ``query.filter(*date_range_filters(col, df, dt))``
    """
    conds = []
    start = to_start_dt(date_from)
    end_excl = to_end_excl_dt(date_to)
    if start is not None:
        conds.append(col >= start)
    if end_excl is not None:
        conds.append(col < end_excl)
    return conds


def year_month_range(year: int, month: Optional[int] = None) -> Tuple[datetime, datetime]:
    """Devuelve ``(start_dt, end_dt_excl)`` para un ``year`` o un ``(year, month)``.

    Equivalente semantico a:
        ``extract('year', col) == year`` (y opcional ``extract('month', col) == month``)
    pero permite filtrar como ``col >= start AND col < end_excl`` aprovechando
    el btree de fecha.
    """
    if month is None:
        return (datetime(year, 1, 1), datetime(year + 1, 1, 1))
    if month == 12:
        return (datetime(year, 12, 1), datetime(year + 1, 1, 1))
    return (datetime(year, month, 1), datetime(year, month + 1, 1))
