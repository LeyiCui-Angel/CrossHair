import datetime

import pytest

pytest.importorskip("dateutil")

from dateutil.relativedelta import FR, MO, relativedelta  # noqa: E402

from crosshair.core import proxy_for_type  # noqa: E402
from crosshair.statespace import EXEC_ERR, POST_FAIL, StateSpace  # noqa: E402
from crosshair.test_util import check_states  # noqa: E402
from crosshair.tracers import NoTracing, ResumedTracing  # noqa: E402


def test_add_months_clamps_day(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        result = d + relativedelta(months=1)
        assert space.is_possible(result.day == 28)
        assert space.is_possible(result.day == 31)
        assert not space.is_possible(result.day > d.day)
        assert not space.is_possible((result.month - d.month) % 12 != 1)


def test_symbolic_month_count_stays_symbolic(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    n = proxy_for_type(int, "n")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        space.add(1 <= n)
        space.add(n <= 11)
        result = d + relativedelta(months=n)
        assert space.is_possible(result.month == 2)
        assert space.is_possible(result.month == 11)
        assert space.is_possible(result.year == d.year + 1)
        assert not space.is_possible(result.year > d.year + 1)


def test_add_year_from_leap_day(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        result = d + relativedelta(years=1)
        space.add(d.month == 2)
        space.add(d.day == 29)
        assert not space.is_possible(result.day != 28)
        assert not space.is_possible(result.month != 2)


def test_days_only_offset_stays_ordinal_backed(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        with NoTracing():
            assert d._ord is None
        result = d + relativedelta(weeks=2, days=3)
        with NoTracing():
            assert d._ord is not None
            assert result._ymd is None
            assert result._ord is not None
        assert not space.is_possible((result - d).days != 17)


def test_month_offset_stays_field_backed(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        result = d + relativedelta(months=1)
        with NoTracing():
            assert d._ord is None
            assert result._ymd is not None
            assert result._ord is None
        assert not space.is_possible(result <= d)
        with NoTracing():
            assert d._ord is None
            assert result._ord is None


def test_subtract_years_and_months(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        result = d - relativedelta(years=1, months=1)
        space.add(d.month == 3)
        space.add(d.day == 31)
        assert not space.is_possible(result.month != 2)
        assert space.is_possible(result.day == 28)
        assert space.is_possible(result.day == 29)
        assert not space.is_possible(result.day > 29)


def test_weekday_targeting(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        forward = d + relativedelta(weekday=FR(+2))
        backward = d + relativedelta(weekday=MO(-1))
        assert not space.is_possible(forward.weekday() != 4)
        assert not space.is_possible(backward.weekday() != 0)
        assert space.is_possible((forward - d).days == 7)
        assert space.is_possible((forward - d).days == 13)
        assert not space.is_possible((forward - d).days > 13)
        assert not space.is_possible((d - backward).days > 6)


def test_absolute_day_replacement(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        end_of_month = d + relativedelta(day=31)
        assert not space.is_possible(end_of_month.month != d.month)
        assert space.is_possible(end_of_month.day == 30)
        assert not space.is_possible(end_of_month.day < 28)


def test_datetime_with_time_offsets(space: StateSpace) -> None:
    dt = proxy_for_type(datetime.datetime, "dt")
    with ResumedTracing():
        space.add(1000 < dt.year)
        space.add(dt.year < 9000)
        result = dt + relativedelta(months=1, hours=3)
        assert not space.is_possible((result.hour - dt.hour) % 24 != 3)
        assert not space.is_possible(result.tzinfo != dt.tzinfo)


def test_date_promoted_to_datetime_for_time_offsets(space: StateSpace) -> None:
    d = proxy_for_type(datetime.date, "d")
    with ResumedTracing():
        space.add(1000 < d.year)
        space.add(d.year < 9000)
        result = d + relativedelta(hours=25)
        assert isinstance(result, datetime.datetime)
        assert not space.is_possible(result.hour != 1)
        assert not space.is_possible((result.date() - d).days != 1)


def test_relativedelta_operands_use_dateutil(space: StateSpace) -> None:
    with ResumedTracing():
        combined = relativedelta(months=1) + relativedelta(months=1)
        assert combined == relativedelta(months=2)
        with_days = relativedelta(months=1) + datetime.timedelta(days=1)
        assert with_days == relativedelta(months=1, days=1)


def test_symbolic_relativedelta_argument() -> None:
    def f(rd: relativedelta):
        """
        raises: ValueError, OverflowError
        post: _ != datetime.date(2024, 2, 29)
        """
        return datetime.date(2024, 1, 31) + rd

    check_states(f, POST_FAIL)


def test_year_out_of_range_raises() -> None:
    def f(d: datetime.date):
        """post: _.year == d.year + 1"""
        return d + relativedelta(years=1)

    check_states(f, EXEC_ERR)


def test_month_clamp_counterexample() -> None:
    def f(d: datetime.date):
        """
        raises: ValueError
        post: _.day == d.day
        """
        return d + relativedelta(months=1)

    check_states(f, POST_FAIL)


def test_month_addition_is_not_associative() -> None:
    def f(d: datetime.date):
        """
        raises: ValueError
        post: _ == d + relativedelta(months=2)
        """
        return d + relativedelta(months=1) + relativedelta(months=1)

    check_states(f, POST_FAIL)
