"""The orders of rules 4 to 6.

Amounts are in euro with a starting amount of 1,000 and a top-up of 50 (5 per cent of it), except the
example from RULES.md, which uses 100 and 5 as the rule does. The scale matters only for the minimum
order of one euro.
"""

import itertools

import pytest

from portfolio import config, rules_engine as re_

E, B = config.EQUITY, config.BONDS


def by_sleeve(plan):
    return {o.sleeve: (o.side, o.amount_eur, dict(o.parts)) for o in plan.orders}


def test_example_of_rule_4():
    # RULES.md, rule 4: equity 68 and bonds 32 before a top-up of 5; all 5 buy equity; 68.0 to 69.5 per cent.
    plan = re_.plan(68, 32, 5)
    assert by_sleeve(plan) == {E: ("buy", 5.0, {"4": 5.0})}
    assert round(100 * plan.weights("after")[E], 1) == 69.5
    assert not plan.band_triggered


def test_top_up_large_enough_reaches_70_30_exactly():
    # Both sleeves below their targets of 735 and 315: equity takes 45, bonds the remaining 5.
    plan = re_.plan(690, 310, 50)
    assert by_sleeve(plan) == {E: ("buy", 45.0, {"4": 45.0}), B: ("buy", 5.0, {"4": 5.0})}
    assert plan.weights("after")[E] == pytest.approx(0.70, abs=1e-6)
    assert plan.after["cash"] == pytest.approx(0.0, abs=1e-9)


def test_one_sleeve_above_target_gets_nothing():
    plan = re_.plan(760, 240, 50)
    assert by_sleeve(plan) == {B: ("buy", 50.0, {"4": 50.0})}
    assert plan.weights("after")[E] == pytest.approx(760 / 1050)


def test_band_purchase_merges_with_the_top_up_into_one_order():
    # After the top-up, equity is 800 of 1,050 (76.2 per cent): back to 735 and 315.
    plan = re_.plan(800, 200, 50)
    orders = by_sleeve(plan)
    assert plan.band_triggered and len(plan.orders) == 2
    assert orders[E] == ("sell", 65.0, {"5": -65.0})
    assert orders[B] == ("buy", 115.0, {"4": 50.0, "5": 65.0})
    assert plan.weights("after")[E] == pytest.approx(0.70, abs=1e-6)


def test_band_below_65():
    plan = re_.plan(600, 400, 50)  # all 50 buy equity: 650 of 1,050 is 61.9 per cent, below the band
    orders = by_sleeve(plan)
    assert plan.band_triggered
    assert orders[E] == ("buy", 135.0, {"4": 50.0, "5": 85.0})
    assert orders[B] == ("sell", 85.0, {"5": -85.0})
    assert plan.weights("after")[E] == pytest.approx(0.70, abs=1e-6)


def test_never_more_than_two_orders_and_the_cash_is_never_overspent():
    for e, b, c in itertools.product(range(400, 1001, 30), range(0, 601, 30), (0, 10, 50, 250)):
        if e + b == 0:
            continue
        plan = re_.plan(float(e), float(b), float(c))
        assert len(plan.orders) <= 2
        assert plan.after["cash"] >= -1e-9
        assert (
            sum(o.amount_eur for o in plan.orders if o.side == "buy")
            <= c + sum(o.amount_eur for o in plan.orders if o.side == "sell") + 1e-9
        )
        w = plan.weights("after")[E]
        before = plan.weights("before")[E]
        if plan.band_triggered:
            assert w == pytest.approx(0.70, abs=1e-3)
        else:
            assert config.BAND[0] - 1e-9 <= w <= config.BAND[1] + 1e-9 or abs(w - 0.70) <= abs(before - 0.70)


def test_nothing_is_sold_inside_the_band():
    for e, b in itertools.product(range(650, 751, 10), range(250, 351, 10)):
        plan = re_.plan(float(e), float(b), 50.0)
        if not plan.band_triggered:
            assert all(o.side == "buy" for o in plan.orders)


def test_top_up_waits_when_the_month_has_too_few_orders_left():
    plan = re_.plan(690, 310, 50, orders_used_this_month=4)  # two orders needed, one left, no band
    assert plan.top_up_waits and plan.orders == []
    assert plan.after["cash"] == 50


def test_band_orders_come_first_and_stop_when_they_cannot_be_placed():
    plan = re_.plan(800, 200, 50, orders_used_this_month=3)  # two orders, two left: placed
    assert len(plan.orders) == 2 and not plan.top_up_waits
    with pytest.raises(re_.BudgetError):
        re_.plan(800, 200, 50, orders_used_this_month=4)  # the band needs two orders, one left


def test_a_top_up_of_one_order_is_placed_with_one_order_left():
    plan = re_.plan(760, 240, 50, orders_used_this_month=4)  # equity above target: one purchase of bonds
    assert by_sleeve(plan) == {B: ("buy", 50.0, {"4": 50.0})} and not plan.top_up_waits


def test_orders_below_one_euro_are_not_placed():
    plan = re_.plan(700, 300, 0.5)
    assert plan.orders == [] and "below one euro" in plan.notes[0]
    assert plan.after["cash"] == 0.5


def test_no_cash_inside_the_band_means_no_order():
    assert re_.plan(720, 280, 0).orders == []


def test_amounts_are_to_the_cent_and_the_parts_add_up():
    for e, b, c in itertools.product(
        (640.137, 812.5551, 700.0), (190.3333, 301.019, 355.7), (50.137, 0.0, 49.999)
    ):
        plan = re_.plan(e, b, c)
        for o in plan.orders:
            assert round(o.amount_eur, 2) == o.amount_eur
            signed = o.amount_eur if o.side == "buy" else -o.amount_eur
            assert sum(a for _, a in o.parts) == pytest.approx(signed, abs=1e-9)
        buys = sum(o.amount_eur for o in plan.orders if o.side == "buy")
        sales = sum(o.amount_eur for o in plan.orders if o.side == "sell")
        assert buys <= c + sales + 1e-9


def test_a_sale_is_listed_before_the_purchase():
    assert [o.side for o in re_.plan(800, 200, 50).orders] == ["sell", "buy"]
    assert [o.side for o in re_.plan(600, 400, 50).orders] == ["sell", "buy"]
