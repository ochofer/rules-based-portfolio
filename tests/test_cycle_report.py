"""The cycle report: each rule's line on its own, so that a ledger or a proposal that breaks one rule fails
that line and no other; and the line after the orders.

The ledger here starts with 1,000 on 2026-10-08, invested 700 and 300, and a top-up of 50 is paid on
2026-11-02. The cycle day is Thursday 2026-11-05. The values on the cycle day are given directly.
"""

from datetime import date, datetime

import pandas as pd
import pytest

from conftest import BD, EQ, contribution, order
from portfolio import config, cycle_report as cr, ledger, rules_engine

E, B = config.EQUITY, config.BONDS
DAY = date(2026, 11, 5)
AT = datetime(2026, 11, 5, 15, 30)
VALUES = {E: 690.0, B: 310.0, "cash": 50.0}  # rule 4 buys equity 45 and bonds 5


def start_orders():
    return [
        order("2026-10-08", "16:00:00", EQ, "buy", 70, 10),
        order("2026-10-08", "16:01:00", BD, "buy", 100, 3),
    ]


def contributions(top_up_day="2026-11-02"):
    return [
        contribution("2026-10-08", "before 15:59:00", 1000, "start"),
        contribution(top_up_day, "08:00:00", 50, "top-up"),
    ]


@pytest.fixture
def records(write_ledger):
    def _records(orders=None, top_up_day="2026-11-02"):
        t, c = write_ledger(start_orders() + (orders or []), contributions(top_up_day))
        return ledger.read(t, c)

    return _records


def failed(checks):
    return {c.rule for c in checks if not c.passed}


def plan(values=VALUES):
    return rules_engine.plan(values[E], values[B], values["cash"])


def test_every_line_passes_when_the_proposal_is_the_rules(records):
    checks = cr.before_orders(records(), DAY, AT, VALUES, plan().orders)
    assert failed(checks) == set()
    assert [c.rule for c in checks] == ["2", "3", "4", "4, reading", "5", "6", "7", "10"]


def test_a_late_top_up_fails_rule_2_only(records):
    assert failed(cr.before_orders(records(top_up_day="2026-11-03"), DAY, AT, VALUES, plan().orders)) == {"2"}


def test_a_day_that_is_not_the_cycle_day_fails_rule_3_only(records):
    friday = date(2026, 11, 6)
    checks = cr.before_orders(records(), friday, datetime(2026, 11, 6, 15, 30), VALUES, plan().orders)
    assert failed(checks) == {"3"}


def test_the_cash_into_the_wrong_sleeve_fails_rule_4_only(records):
    wrong = [rules_engine.Order(B, "buy", 50.0, (("4", 50.0),))]
    assert failed(cr.before_orders(records(), DAY, AT, VALUES, wrong)) == {"4"}


def test_an_order_below_one_euro_fails_the_reading_only(records):
    # Bonds are 50 below target and take 50 of the 50.5, which leaves 0.50 for equity: below one euro.
    values = {E: 769.5, B: 280.0, "cash": 50.5}
    rules = plan(values)
    assert len(rules.below_minimum) == 1
    assert failed(cr.before_orders(records(), DAY, AT, values, rules.orders)) == set()
    kept = rules.orders + rules.below_minimum
    assert failed(cr.before_orders(records(), DAY, AT, values, kept)) == {"4, reading"}


def test_a_missing_band_order_fails_rule_5_only(records):
    values = {E: 800.0, B: 200.0, "cash": 50.0}  # 76.2 per cent after the top-up: back to 70/30
    assert plan(values).band_triggered
    top_up_only = [rules_engine.Order(B, "buy", 50.0, (("4", 50.0),))]
    assert failed(cr.before_orders(records(), DAY, AT, values, top_up_only)) == {"5"}
    assert failed(cr.before_orders(records(), DAY, AT, values, plan(values).orders)) == set()


def test_more_orders_than_the_month_has_left_fails_rule_6_only(records):
    earlier = [
        order(d, "15:50:00", EQ, "buy", 0.1, 10)
        for d in ("2026-11-03", "2026-11-03", "2026-11-04", "2026-11-04")
    ]
    assert failed(cr.before_orders(records(earlier), DAY, AT, VALUES, plan().orders)) == {"6"}


def test_the_top_up_that_waits_under_rule_6_passes_rule_4(records):
    earlier = [
        order(d, "15:50:00", EQ, "buy", 0.1, 10)
        for d in ("2026-11-03", "2026-11-03", "2026-11-04", "2026-11-04")
    ]
    waiting = rules_engine.plan(VALUES[E], VALUES[B], VALUES["cash"], orders_used_this_month=4)
    assert waiting.top_up_waits and not waiting.orders
    assert failed(cr.before_orders(records(earlier), DAY, AT, VALUES, waiting.orders)) == set()


def test_a_report_written_after_the_window_fails_rule_7_only(records):
    late = datetime(2026, 11, 5, 17, 20)
    assert failed(cr.before_orders(records(), DAY, late, VALUES, plan().orders)) == {"7"}


def test_an_earlier_sale_without_its_cost_basis_fails_rule_10_only(records):
    sale = [order("2026-10-20", "15:50:00", EQ, "sell", 1, 10, rule="5")]
    assert failed(cr.before_orders(records(sale), DAY, AT, VALUES, plan().orders)) == {"10"}


def test_the_report_carries_no_euro_amount(records):
    text = cr.write_before(records(), DAY, AT, VALUES, plan().orders, "2026-11-04")
    for amount in ("45.00", "45.0 ", "5.00", "50.00", "690", "310", "1000", "1,000"):
        assert amount not in text
    assert "| 1 | Equity | buy | 4.3% | rule 4 |" in text
    assert cr.PENDING in text and cr.written_at(text) == AT


def test_the_line_after_the_orders(records):
    placed = [
        order("2026-11-05", "15:50:00", EQ, "buy", 4.5, 10, rule="4", bid="9.99", ask="10.01"),
        order("2026-11-05", "15:51:00", BD, "buy", 1, 5, rule="4"),
    ]
    line = cr.after_orders(records(placed), DAY, VALUES, plan().orders, AT)
    assert line.startswith(
        "After the orders: 2 placed against 2 proposed, the same sleeves and sides, at 100.0% and 100.0%"
    )
    assert "Inside 15:45 to 17:00: 2 of 2. Bid and ask recorded: 1 of 2. Half-spread 10 bp." in line
    assert line.endswith("The report was written before the first order: yes.")
    text = cr.add_after(cr.write_before(records(), DAY, AT, VALUES, plan().orders, "2026-11-04"), line)
    assert cr.PENDING not in text and line in text


def test_the_proposal_recomputed_from_the_ledger(records):
    navs = pd.DataFrame(
        {E: [10.0, 9.857142857], B: [3.0, 3.1]}, index=pd.to_datetime(["2026-10-08", "2026-11-04"])
    )
    values, rules = cr.proposal_on(records(), navs, DAY)
    assert values == pytest.approx({E: 690.0, B: 310.0, "cash": 50.0}, abs=1e-6)
    assert [(o.sleeve, o.amount_eur) for o in rules.orders] == [(E, 45.0), (B, 5.0)]
