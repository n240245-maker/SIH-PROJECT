"""Deterministic prototype geo-evidence calendar and location checks."""

from __future__ import annotations

from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Iterable


def is_working_day(value: date, holidays: Iterable[date] = ()) -> bool:
    """Use the documented prototype calendar: Monday-Friday minus configured holidays."""

    return value.weekday() < 5 and value not in set(holidays)


def add_working_days(start: date, count: int, holidays: Iterable[date] = ()) -> date:
    if count < 0:
        raise ValueError("count must be non-negative")
    # A deadline expressed as N working days after an event starts counting on
    # the following calendar day, not on the event date itself.
    result = start + timedelta(days=1)
    found = 0
    while found < count:
        if is_working_day(result, holidays):
            found += 1
            if found == count:
                return result
        result += timedelta(days=1)
    return result


def first_working_days(year: int, month: int, count: int = 3, holidays: Iterable[date] = ()) -> list[date]:
    cursor = date(year, month, 1)
    values: list[date] = []
    while len(values) < count:
        if is_working_day(cursor, holidays):
            values.append(cursor)
        cursor += timedelta(days=1)
    return values


def monthly_evidence_status(
    *, lifecycle: str, as_of: date, capture_dates: Iterable[date], holidays: Iterable[date] = ()
) -> str:
    """Return the current-month evidence status without treating future duties as failures."""

    if lifecycle != "EXECUTION":
        return "NOT_APPLICABLE"
    window = first_working_days(as_of.year, as_of.month, holidays=holidays)
    current = [value for value in capture_dates if value.year == as_of.year and value.month == as_of.month]
    if current:
        return "RECORDED" if min(current) <= window[-1] else "OVERDUE"
    if as_of < window[0]:
        return "UPCOMING"
    if as_of <= window[-1]:
        return "DUE"
    return "OVERDUE"


def completion_evidence_status(
    *, lifecycle: str, completion_date: date | None, capture_date: date | None,
    as_of: date, holidays: Iterable[date] = (),
) -> str:
    if lifecycle != "COMPLETION" or completion_date is None:
        return "NOT_APPLICABLE"
    deadline = add_working_days(completion_date, 3, holidays)
    if capture_date is not None:
        return "RECORDED" if capture_date <= deadline else "OVERDUE"
    return "DUE" if as_of <= deadline else "OVERDUE"


def haversine_metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def location_status(
    registered_latitude: float | None,
    registered_longitude: float | None,
    capture_latitude: float | None,
    capture_longitude: float | None,
    *,
    threshold_metres: float = 500.0,
) -> tuple[str, float | None]:
    if None in (registered_latitude, registered_longitude, capture_latitude, capture_longitude):
        return "COMPARISON_UNAVAILABLE", None
    distance = haversine_metres(
        float(registered_latitude), float(registered_longitude),
        float(capture_latitude), float(capture_longitude),
    )
    return ("LOCATION_CONSISTENT" if distance <= threshold_metres else "LOCATION_REQUIRES_REVIEW", distance)
