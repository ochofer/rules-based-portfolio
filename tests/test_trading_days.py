"""Xetra's calendar and the cycle day of rule 3."""

from datetime import date

from portfolio import trading_days as td


def test_easter():
    assert td.easter_sunday(2026) == date(2026, 4, 5)
    assert td.easter_sunday(2027) == date(2027, 3, 28)
    assert td.easter_sunday(2028) == date(2028, 4, 16)


def test_xetra_holidays_2026_and_2027():
    # Deutsche Boerse's trading calendar: New Year, Good Friday, Easter Monday, 1 May,
    # 24 to 26 and 31 December.
    assert td.xetra_holidays(2026) == {
        date(2026, 1, 1),
        date(2026, 4, 3),
        date(2026, 4, 6),
        date(2026, 5, 1),
        date(2026, 12, 24),
        date(2026, 12, 25),
        date(2026, 12, 26),
        date(2026, 12, 31),
    }
    assert date(2027, 3, 26) in td.xetra_holidays(2027) and date(2027, 3, 29) in td.xetra_holidays(2027)


def test_cycle_days():
    assert td.cycle_day(2026, 11) == date(2026, 11, 5)  # a Thursday
    assert td.cycle_day(2026, 12) == date(2026, 12, 7)  # the 5th is a Saturday
    assert td.cycle_day(2026, 4) == date(2026, 4, 7)  # the 5th is Easter Sunday, the 6th Easter Monday
    assert td.cycle_day(2027, 9) == date(2027, 9, 6)  # the 5th is a Sunday


def test_us_holidays_2026_and_2027():
    # The NYSE's holiday calendar.
    assert td.us_holidays(2026) == {
        date(2026, 1, 1),
        date(2026, 1, 19),
        date(2026, 2, 16),
        date(2026, 4, 3),
        date(2026, 5, 25),
        date(2026, 6, 19),
        date(2026, 7, 3),
        date(2026, 9, 7),
        date(2026, 11, 26),
        date(2026, 12, 25),
    }
    assert td.us_holidays(2027) == {
        date(2027, 1, 1),
        date(2027, 1, 18),
        date(2027, 2, 15),
        date(2027, 3, 26),
        date(2027, 5, 31),
        date(2027, 6, 18),
        date(2027, 7, 5),
        date(2027, 9, 6),
        date(2027, 11, 25),
        date(2027, 12, 24),
    }


def test_cycle_days_with_the_us_market_closed():
    # Rule 3 sets the cycle day by Xetra alone, and two cycle days of 2027 fall on US holidays.
    assert td.cycle_day(2027, 7) == date(2027, 7, 5) and not td.us_market_open(date(2027, 7, 5))
    assert td.cycle_day(2027, 9) == date(2027, 9, 6) and not td.us_market_open(date(2027, 9, 6))
    assert td.us_market_open(date(2026, 11, 5))


def test_previous_trading_day():
    assert td.previous_trading_day(date(2026, 11, 5)) == date(2026, 11, 4)
    assert td.previous_trading_day(date(2026, 12, 7)) == date(2026, 12, 4)
    assert td.previous_trading_day(date(2027, 1, 4)) == date(2026, 12, 30)
