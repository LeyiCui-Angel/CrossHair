import operator
import sys
from datetime import date, datetime
from typing import Optional

import pytest  # type: ignore

pytest.importorskip("dateutil")

from dateutil.relativedelta import FR, relativedelta  # noqa: E402

from crosshair.behavior_compare import ResultComparison, compare_results  # noqa: E402
from crosshair.core_and_libs import (  # noqa: E402
    MessageType,
    analyze_function,
    run_checkables,
)

# crosshair: max_uninteresting_iterations=10


def _add_months_and_days(d, months, days, day):
    return d + relativedelta(months=months, days=days, day=day)


def _subtract_years(dt, years, hours):
    return dt - relativedelta(years=years, hours=hours)


def _nth_friday(d, n):
    return d + relativedelta(weekday=FR(n))


def check_relativedelta_add_months_and_days(
    d: date, months: int, days: int, day: Optional[int]
) -> ResultComparison:
    """
    pre: -30 <= months <= 30
    pre: -100 <= days <= 100
    pre: day is None or 1 <= day <= 31
    post: _
    """
    return compare_results(_add_months_and_days, d, months, days, day)


def check_relativedelta_subtract_years_from_datetime(
    dt: datetime, years: int, hours: int
) -> ResultComparison:
    """
    pre: -10 <= years <= 10
    pre: -50 <= hours <= 50
    post: _
    """
    return compare_results(_subtract_years, dt, years, hours)


def check_relativedelta_weekday(d: date, n: int) -> ResultComparison:
    """
    pre: -3 <= n <= 3 and n != 0
    post: _
    """
    return compare_results(_nth_friday, d, n)


def check_relativedelta_symbolic_argument(d: date, rd: relativedelta) -> ResultComparison:
    """post: _"""
    return compare_results(operator.add, d, rd)


def check_relativedelta_between_dates(a: date, b: date) -> ResultComparison:
    """post: _"""
    return compare_results(relativedelta, a, b)


# This is the only real test definition.
# It runs crosshair on each of the "check" functions defined above.
@pytest.mark.parametrize("fn_name", [fn for fn in dir() if fn.startswith("check_")])
def test_builtin(fn_name: str) -> None:
    this_module = sys.modules[__name__]
    messages = run_checkables(analyze_function(getattr(this_module, fn_name)))
    errors = [m for m in messages if m.state > MessageType.PRE_UNSAT]
    assert errors == [], [(m.state, m.message) for m in errors]
