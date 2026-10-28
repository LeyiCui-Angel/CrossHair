"""
Symbolic support for ``dateutil.relativedelta`` applied to dates and datetimes.

Year/month offsets and absolute field replacements are applied to the
calendar fields with a branch-free day clamp; the remaining day offset is then
added through ``date.__add__``, which steps the calendar fields one day at a
time.
"""

from calendar import IllegalMonthError
from datetime import date as real_date
from datetime import datetime as real_datetime
from datetime import timedelta as real_timedelta
from typing import Any, Optional

from crosshair import realize, register_patch, register_type
from crosshair.core import SymbolicFactory
from crosshair.libimpl import datetimelib
from crosshair.libimpl.datetimelib import (
    MAXYEAR,
    MINYEAR,
    _check_time_fields,
    _date_skip_construct,
    _datetime_skip_construct,
    _days_in_month_int,
    _is_leap_int,
)
from crosshair.tracers import NoTracing, ResumedTracing

_DATE_TYPES = (datetimelib.date, datetimelib.datetime, real_date, real_datetime)
_DATETIME_TYPES = (datetimelib.datetime, real_datetime)


def _shift_month(year, month, months):
    """Add a month offset, carrying into the year; the result month is 1..12."""
    total_months = year * 12 + (month - 1) + months
    year = total_months // 12
    return year, total_months - year * 12 + 1


def _calendar_fields(delta: Any, year, month, day):
    """Return the (year, month, day) that ``delta`` moves the given fields to."""
    if delta.year:
        year = delta.year
    year = year + delta.years
    if delta.month:
        month = delta.month
        if delta.months:
            month += delta.months
            if month > 12:
                year += 1
                month -= 12
            elif month < 1:
                year -= 1
                month += 12
        if not (1 <= month <= 12):
            raise IllegalMonthError(realize(month))
    else:
        year, month = _shift_month(year, month, delta.months)
    if delta.day:
        day = delta.day
    days_in_month = _days_in_month_int(year, month)
    day = day - (day > days_in_month) * (day - days_in_month)
    if not ((MINYEAR <= year) & (year <= MAXYEAR)):
        raise ValueError("year must be in %d..%d" % (MINYEAR, MAXYEAR))
    if day < 1:
        raise ValueError("day is out of range for month")
    return year, month, day


def _weekday_jump(current_weekday, target: Any):
    weekday, nth = target.weekday, target.n or 1
    jumpdays = (abs(nth) - 1) * 7
    if nth > 0:
        jumpdays += (7 - current_weekday + weekday) % 7
    else:
        jumpdays += (current_weekday - weekday) % 7
        jumpdays *= -1
    return jumpdays


def _add_relativedelta(delta: Any, other: Any):
    with NoTracing():
        other_type = type(other)
        is_datetime = other_type in _DATETIME_TYPES
    if delta._has_time and not is_datetime:
        other = _datetime_skip_construct(
            other.year, other.month, other.day, 0, 0, 0, 0, None
        )
        is_datetime = True

    changes_calendar_fields = (delta.years != 0) | (delta.months != 0)
    if delta.year or delta.month or delta.day:
        changes_calendar_fields = True

    if is_datetime:
        hour = other.hour if delta.hour is None else delta.hour
        minute = other.minute if delta.minute is None else delta.minute
        second = other.second if delta.second is None else delta.second
        microsecond = (
            other.microsecond if delta.microsecond is None else delta.microsecond
        )
        replaces_time_fields = (
            delta.hour is not None
            or delta.minute is not None
            or delta.second is not None
            or delta.microsecond is not None
        )
        changes_calendar_fields |= replaces_time_fields

    if changes_calendar_fields:
        year, month, day = _calendar_fields(delta, other.year, other.month, other.day)
        if is_datetime:
            if replaces_time_fields:
                _check_time_fields(hour, minute, second, microsecond, other.fold)
            result = _datetime_skip_construct(
                year, month, day, hour, minute, second, microsecond, other.tzinfo
            )
            result._fold = other.fold
        else:
            result = _date_skip_construct(year, month, day)
    else:
        year, month = other.year, other.month
        result = other

    days = delta.days
    if delta.leapdays:
        days = days + delta.leapdays * (month > 2) * _is_leap_int(year)

    with NoTracing():
        offset_parts = (
            days,
            delta.hours,
            delta.minutes,
            delta.seconds,
            delta.microseconds,
        )
        has_offset = any(type(part) is not int or part != 0 for part in offset_parts)
    if has_offset:
        result = result + real_timedelta(
            days=days,
            hours=delta.hours,
            minutes=delta.minutes,
            seconds=delta.seconds,
            microseconds=delta.microseconds,
        )
    if delta.weekday:
        result = result + real_timedelta(
            days=_weekday_jump(result.weekday(), delta.weekday)
        )
    return result


def make_registrations() -> None:
    try:
        from dateutil.relativedelta import relativedelta  # type: ignore
    except ImportError:
        return

    original_add = relativedelta.__add__

    def relativedelta_add(self, other):
        with NoTracing():
            is_supported_operand = type(other) in _DATE_TYPES
        if not is_supported_operand:
            return original_add(self, other)
        return _add_relativedelta(self, other)

    register_patch(relativedelta.__add__, relativedelta_add)

    def make_relativedelta(p: SymbolicFactory) -> relativedelta:
        years, months, days = p(int, "_years"), p(int, "_months"), p(int, "_days")
        day = p(Optional[int], "_day")
        with ResumedTracing():
            return relativedelta(years=years, months=months, days=days, day=day)

    register_type(relativedelta, make_relativedelta)
