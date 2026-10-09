"""Returns, drawdowns and the reference portfolios, on invented net asset values."""

from datetime import date

import pandas as pd
import pytest

from conftest import BD, EQ, contribution, order
from portfolio import ledger, metrics, positions, references, rules_engine, trading_days, valuations


def navs(days, equity, bonds):
    frame = pd.DataFrame({"equity": equity, "bonds": bonds}, index=pd.to_datetime(days))
    frame["usd_per_eur"], frame["rate_carried"] = 1.1, False
    return frame


def test_time_weighted_return_by_hand():
    # Day 1: 1,000 grows to 1,010 (+1%). Day 2: a contribution of 100 arrives and the value is 1,120.
    # The return of day 2 is (1,120 - 100) / 1,010 - 1 = 0.99%; the index ends at 100 x 1.01 x 1.0099.
    values = pd.Series([1010.0, 1120.0], index=pd.to_datetime(["2026-10-09", "2026-10-12"]))
    flows = pd.Series([0.0, 100.0], index=values.index)
    index = metrics.growth_index(values, flows, 1000.0, pd.Timestamp("2026-10-08"))
    assert index.iloc[0] == 100 and index.iloc[-1] == pytest.approx(100 * 1.01 * (1020 / 1010))


def test_drawdown_on_a_known_path():
    index = pd.Series([100, 110, 99, 105, 121])
    assert list(metrics.drawdown(index).round(4)) == [0, 0, -0.1, round(105 / 110 - 1, 4), 0]


def test_money_weighted_return_of_a_single_contribution_is_the_simple_return():
    records = type("L", (), {})()
    records.contributions = pd.DataFrame({"moment": [pd.Timestamp("2026-01-01")], "amount_eur": [1000.0]})
    rate = metrics.money_weighted(records, pd.Timestamp("2027-01-01"), 1100.0)
    assert rate == pytest.approx(0.10, abs=1e-3)


def money_weighted_cumulative(contributions, day, value):
    records = type("L", (), {})()
    records.contributions = pd.DataFrame(
        {"moment": [pd.Timestamp(m) for m, _ in contributions], "amount_eur": [a for _, a in contributions]}
    )
    return metrics.money_weighted_cumulative(records, pd.Timestamp(day), value)


def test_money_weighted_cumulative_on_the_first_days():
    # On the day of the first purchase it is the value over the contributions; one day later a 1 per cent
    # gain is 1 per cent, a rate of about 3,700 per cent a year.
    start = [("2026-10-08 09:32", 1000.0)]
    assert money_weighted_cumulative(start, "2026-10-08", 1001.0) == pytest.approx(0.001)
    assert money_weighted_cumulative(start, "2026-10-09", 1010.0) == pytest.approx(0.01)
    assert money_weighted_cumulative(start, "2026-10-09", 990.0) == pytest.approx(-0.01)


def test_a_contribution_made_on_the_valuation_day_counts():
    flows = [("2026-10-08 09:32", 1000.0), ("2026-11-02 10:15", 100.0)]
    assert money_weighted_cumulative(flows, "2026-11-02", 1100.0) == pytest.approx(0.0, abs=1e-9)


def test_reference_a_equals_the_portfolio_without_costs(write_ledger):
    # The portfolio buys 70/30 at the net asset value and, on the cycle day of 5 November, places the orders
    # the rules give at the previous day's values, executed at the day's net asset value: no cost at all.
    days = ["2026-10-08", "2026-10-09", "2026-11-04", "2026-11-05", "2026-11-06"]
    frame = navs(days, [10.0, 10.2, 10.4, 10.3, 10.5], [3.0, 3.0, 2.95, 2.96, 2.97])
    start, top_up = 1000.0, 50.0
    rows = [order("2026-10-08", "16:00:00", EQ, "buy", f"{700 / 10.0:.10f}", "10.0"),
            order("2026-10-08", "16:01:00", BD, "buy", f"{300 / 3.0:.10f}", "3.0")]  # fmt: skip
    before = {"equity": 70.0 * 10.4, "bonds": 100.0 * 2.95}
    plan = rules_engine.plan(before["equity"], before["bonds"], top_up)
    for k, o in enumerate(plan.orders):
        price = 10.3 if o.sleeve == "equity" else 2.96
        isin = EQ if o.sleeve == "equity" else BD
        rows.append(
            order(
                "2026-11-05",
                f"16:0{k}:00",
                isin,
                o.side,
                f"{o.amount_eur / price:.10f}",
                str(price),
                rule="4",
            )
        )
    t, c = write_ledger(rows, [contribution("2026-10-08", "before 15:59:00", start, "start"),
                               contribution("2026-11-02", "09:00", top_up, "top-up")])  # fmt: skip
    records = ledger.read(t, c)
    held = positions.build(records, date(2026, 11, 6))
    values = valuations.build(held, frame)
    ref = references.simulate(records, frame, date(2026, 11, 6), "rules")
    assert ref["value"].values == pytest.approx(values["value_eur"].values, abs=0.02)
    base = metrics.base_day(records, frame)
    table = metrics.daily(records, values, ref, ref, pd.Series(dtype=float), base)
    assert table["implementation_cost_bps"].abs().max() < 0.5


def test_reference_b_goes_back_to_70_30_on_every_cycle_day(write_ledger):
    days = ["2026-10-08", "2026-11-04", "2026-11-05"]
    frame = navs(days, [10.0, 11.0, 11.0], [3.0, 3.0, 3.0])
    t, c = write_ledger([order("2026-10-08", "16:00:00", EQ, "buy", "70", "10.0"),
                         order("2026-10-08", "16:01:00", BD, "buy", "100", "3.0")],
                        [contribution("2026-10-08", "before 15:59:00", 1000, "start")])  # fmt: skip
    ref = references.simulate(ledger.read(t, c), frame, date(2026, 11, 5), "calendar")
    last = ref.iloc[-1]
    assert last["equity"] * 11.0 / last["value"] == pytest.approx(0.70)


def test_index_blend_starts_at_the_first_month_end_and_moves_monthly():
    growth = pd.Series(
        [100.0, 101.0, 102.0], index=pd.to_datetime(["2026-10-30", "2026-11-30", "2026-12-01"])
    )
    msci = pd.Series([500.0, 510.0], index=pd.to_datetime(["2026-10-30", "2026-11-30"]))
    bonds = pd.Series([0.01], index=pd.PeriodIndex(["2026-11"], freq="M"))
    blend = references.index_blend(growth, msci, bonds, date(2026, 12, 2))
    assert blend.iloc[0] == 100.0
    assert blend.iloc[1] == pytest.approx(100 * (1 + 0.7 * 0.02 + 0.3 * 0.01))


def test_cycle_days_after_the_first_purchase():
    assert references._cycle_days(date(2026, 10, 8), date(2026, 12, 31)) == [
        date(2026, 11, 5),
        date(2026, 12, 7),
    ]
    assert trading_days.cycle_day(2026, 11) == date(2026, 11, 5)


def test_the_cost_sources_of_a_month_add_up_to_its_implementation_cost(write_ledger):
    # Equity is bought 1 per cent above the net asset value with a fee of 1 euro. The commission and the gap
    # between the price paid and the net asset value add up to the month's implementation cost.
    days = ["2026-10-07", "2026-10-08", "2026-10-09", "2026-10-12"]
    frame = navs(days, [10.0, 10.0, 10.1, 10.2], [3.0, 3.0, 3.0, 3.01])
    rows = [order("2026-10-08", "16:00:00", EQ, "buy", f"{699 / 10.1:.10f}", "10.1", fee="1.00"),
            order("2026-10-08", "16:01:00", BD, "buy", f"{300 / 3.0:.10f}", "3.0")]  # fmt: skip
    t, c = write_ledger(rows, [contribution("2026-10-08", "before 15:59:00", 1000, "start")])
    records = ledger.read(t, c)
    held = positions.build(records, date(2026, 10, 12))
    values = valuations.build(held, frame)
    ref = references.simulate(records, frame, date(2026, 10, 12), "rules")
    base = metrics.base_day(records, frame)
    table = metrics.daily(records, values, ref, ref, pd.Series(dtype=float), base)
    month = metrics.monthly(records, table, values, metrics.orders(records), date(2026, 10, 12)).iloc[0]
    itemised = (
        month["commissions_bps"] + month["currency_conversion_bps"] + month["execution_against_nav_bps"]
    )
    assert itemised == pytest.approx(month["implementation_cost_month_bps"])
    assert month["implementation_cost_month_bps"] == pytest.approx(-table["implementation_cost_bps"].iloc[-1])
    assert month["execution_against_nav_bps"] > 0 and month["orders_without_bid_and_ask"] == 2
