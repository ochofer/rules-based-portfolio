"""Units and cash by day, and their value at the net asset values in euro."""

from datetime import date

import pandas as pd
import pytest

from conftest import BD, EQ, contribution, order
from portfolio import config, ledger, positions, valuations

E, B = config.EQUITY, config.BONDS


def navs(rows):
    frame = pd.DataFrame(rows, columns=["date", E, B]).set_index("date")
    frame.index = pd.to_datetime(frame.index)
    return frame


def test_positions_follow_the_order_dates(start_ledger, write_ledger):
    t, c = start_ledger
    frame = positions.build(ledger.read(t, c), date(2026, 10, 12))
    assert frame.loc["2026-10-08", E] == 7 and frame.loc["2026-10-08", B] == 10
    assert frame.loc["2026-10-12", "cash_eur"] == pytest.approx(0.0)
    assert frame.loc["2026-10-12", "contributions_eur"] == 100


def test_a_top_up_is_cash_until_it_is_invested(write_ledger):
    t, c = write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 7, 10),
            order("2026-10-08", "16:01:00", BD, "buy", 10, 3),
            order("2026-11-05", "16:00:00", EQ, "buy", 0.49, 10, rule="4", fee="0.10"),
        ],
        [
            contribution("2026-10-08", "before 15:59:00", 100, "start"),
            contribution("2026-11-02", "09:00", 5, "top-up"),
        ],
    )
    records = ledger.read(t, c)
    frame = positions.build(records, date(2026, 11, 6))
    assert frame.loc["2026-11-04", "cash_eur"] == pytest.approx(5.0)
    assert frame.loc["2026-11-05", "cash_eur"] == pytest.approx(0.0)
    assert frame.loc["2026-11-05", E] == pytest.approx(7.49)
    assert positions.orders_in_month(records, 2026, 11) == 1
    assert positions.orders_in_month(records, 2026, 10) == 2


def test_valuation_carries_the_last_value_of_a_fund_that_did_not_publish(start_ledger):
    t, c = start_ledger
    held = positions.build(ledger.read(t, c), date(2026, 10, 12))
    values = valuations.build(
        held, navs([("2026-10-08", 10.0, 3.0), ("2026-10-09", 11.0, None), ("2026-10-12", 11.0, 3.3)]).ffill()
    )
    assert values.loc["2026-10-09", "value_eur"] == pytest.approx(7 * 11 + 10 * 3)
    assert values.loc["2026-10-12", "weight_equity"] == pytest.approx(77 / 110)
    assert values["weight_cash"].abs().max() < 1e-9


def test_value_on_a_day_uses_the_last_published_values(start_ledger):
    t, c = start_ledger
    held = positions.build(ledger.read(t, c), date(2026, 10, 12))
    v = valuations.at(
        held, navs([("2026-10-08", 10.0, 3.0), ("2026-10-09", 11.0, 3.1)]), pd.Timestamp("2026-10-12")
    )
    assert (
        v[E] == pytest.approx(77)
        and v[B] == pytest.approx(31)
        and v["nav_date"] == pd.Timestamp("2026-10-09")
    )


def test_value_with_net_asset_values_of_an_earlier_day(start_ledger):
    t, c = start_ledger
    held = positions.build(ledger.read(t, c), date(2026, 10, 12))
    v = valuations.at(
        held,
        navs([("2026-10-08", 10.0, 3.0), ("2026-10-09", 11.0, 3.1)]),
        pd.Timestamp("2026-10-12"),
        nav_day=pd.Timestamp("2026-10-08"),
    )
    assert v[E] == pytest.approx(70) and v["nav_date"] == pd.Timestamp("2026-10-08")


def test_a_day_before_the_start_stops(start_ledger):
    t, c = start_ledger
    with pytest.raises(ledger.LedgerError, match="before the first contribution"):
        positions.build(ledger.read(t, c), date(2026, 10, 7))
