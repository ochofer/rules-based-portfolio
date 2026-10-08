"""Xetra's trading days, the cycle day of rule 3, and the days the US equity market is closed.

Xetra is closed on weekends and on New Year's Day, Good Friday, Easter Monday, 1 May, 24, 25 and 26
December and 31 December, as in Deutsche Boerse's trading calendar. The NYSE's regular holidays follow
its published rules; unscheduled closures are not covered. The dates for 2026 and 2027 are in
tests/test_trading_days.py.
"""

from __future__ import annotations

from datetime import date, timedelta

from . import config


def easter_sunday(year: int) -> date:
    """Easter Sunday in the Gregorian calendar (the anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def xetra_holidays(year: int) -> set:
    """Weekdays and weekend days on which Xetra does not open, for one year."""
    easter = easter_sunday(year)
    return {
        date(year, 1, 1),
        easter - timedelta(days=2),
        easter + timedelta(days=1),
        date(year, 5, 1),
        date(year, 12, 24),
        date(year, 12, 25),
        date(year, 12, 26),
        date(year, 12, 31),
    }


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The n-th given weekday of a month (Monday is 0). n = -1 gives the last."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """A holiday on a Saturday is observed on the Friday before, one on a Sunday on the Monday after."""
    return day + timedelta(days={5: -1, 6: 1}.get(day.weekday(), 0))


def us_holidays(year: int) -> set:
    """The NYSE's regular full-day holidays. New Year's Day on a Saturday is not observed."""
    new_year = date(year, 1, 1)
    days = {
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        easter_sunday(year) - timedelta(days=2),  # Good Friday
        _nth_weekday(year, 5, 0, -1),  # Memorial Day
        _observed(date(year, 7, 4)),  # Independence Day
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed(date(year, 12, 25)),  # Christmas
    }
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # Juneteenth
    if new_year.weekday() != 5:
        days.add(_observed(new_year))
    return days


def us_market_open(day: date) -> bool:
    return day.weekday() < 5 and day not in us_holidays(day.year)


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in xetra_holidays(day.year)


def cycle_day(year: int, month: int) -> date:
    """Rule 3: the 5th of the month, or the first trading day after it when the 5th is not one."""
    day = date(year, month, config.CYCLE_DAY_OF_MONTH)
    while not is_trading_day(day):
        day += timedelta(days=1)
    return day


def previous_trading_day(day: date) -> date:
    day -= timedelta(days=1)
    while not is_trading_day(day):
        day -= timedelta(days=1)
    return day
