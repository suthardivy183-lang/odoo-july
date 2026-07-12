"""Timezone (Asia/Kolkata) and fiscal-year (Apr-Mar) helpers.

All DB timestamps are stored UTC; business-day logic (deadlines, leaderboard
windows, score periods) is evaluated in IST.
"""

import datetime as dt
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_ist() -> dt.datetime:
    return dt.datetime.now(IST)


def today_ist() -> dt.date:
    return now_ist().date()


def fiscal_year_bounds(d: dt.date | None = None) -> tuple[dt.date, dt.date]:
    d = d or today_ist()
    start_year = d.year if d.month >= 4 else d.year - 1
    return dt.date(start_year, 4, 1), dt.date(start_year + 1, 3, 31)


def fiscal_quarter_bounds(d: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """FY-aligned quarter (Apr-Jun, Jul-Sep, Oct-Dec, Jan-Mar)."""
    d = d or today_ist()
    fy_start, _ = fiscal_year_bounds(d)
    q_index = ((d.year - fy_start.year) * 12 + d.month - fy_start.month) // 3
    q_start_month = fy_start.month + q_index * 3
    year = fy_start.year + (q_start_month - 1) // 12
    month = (q_start_month - 1) % 12 + 1
    start = dt.date(year, month, 1)
    if month + 3 > 12:
        end = dt.date(year + 1, (month + 3) % 12, 1) - dt.timedelta(days=1)
    else:
        end = dt.date(year, month + 3, 1) - dt.timedelta(days=1)
    return start, end


def month_bounds(d: dt.date | None = None) -> tuple[dt.date, dt.date]:
    d = d or today_ist()
    start = d.replace(day=1)
    if d.month == 12:
        end = dt.date(d.year, 12, 31)
    else:
        end = dt.date(d.year, d.month + 1, 1) - dt.timedelta(days=1)
    return start, end


def week_bounds(d: dt.date | None = None) -> tuple[dt.date, dt.date]:
    """IST calendar week, Monday-Sunday."""
    d = d or today_ist()
    start = d - dt.timedelta(days=d.weekday())
    return start, start + dt.timedelta(days=6)


ALL_TIME_START = dt.date(2000, 1, 1)


def resolve_period(
    period: str | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> tuple[dt.date, dt.date]:
    """Resolve a score/report period to inclusive [start, end] dates.

    period: one of 'month' | 'quarter' | 'fy' (default) | 'all'.
    Explicit date_from/date_to override the named period.
    """
    if date_from or date_to:
        return date_from or ALL_TIME_START, date_to or today_ist()
    period = (period or "fy").lower()
    if period == "month":
        return month_bounds()
    if period == "quarter":
        return fiscal_quarter_bounds()
    if period == "all":
        return ALL_TIME_START, today_ist()
    return fiscal_year_bounds()


def date_to_utc_range(start: dt.date, end: dt.date) -> tuple[dt.datetime, dt.datetime]:
    """Convert an inclusive IST date range to a UTC datetime half-open range."""
    start_dt = dt.datetime.combine(start, dt.time.min, tzinfo=IST)
    end_dt = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, tzinfo=IST)
    return start_dt.astimezone(dt.timezone.utc), end_dt.astimezone(dt.timezone.utc)
