"""The orders rules 4 to 6 produce on a cycle day.

Rule 4: the cash not yet invested (the top-up and anything left from earlier orders) buys the sleeve
furthest below its target weight, up to its target weight, and the rest buys the other sleeve up to its
target weight. With two sleeves the two amounts add up to the cash, so the portfolio reaches 70/30
whenever both sleeves are below their targets. When one sleeve is above its target, all the cash buys
the other.

Rule 5: if the equity weight is then below 65 or above 75 per cent, the portfolio is brought back to
exactly 70/30 by selling the sleeve above its target weight and buying the other. A top-up purchase and
a band purchase of the same sleeve are one order with two parts.

Rule 6: at most five orders a month. If the rules call for more than the month has left, the band orders
come first and the top-up waits for the next cycle day.

Amounts are in euro, rounded down to the cent so that purchases never exceed the cash. An order below
the broker's minimum of one euro is not placed, and its cash waits for the next cycle day.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import config

E, B = config.EQUITY, config.BONDS


class BudgetError(RuntimeError):
    """Rule 6 cannot be met: fewer orders are left in the month than the band orders need."""


@dataclass(frozen=True)
class Order:
    sleeve: str
    side: str  # "buy" or "sell"
    amount_eur: float  # positive, in euro, to the cent
    parts: tuple  # ((rule, signed euro amount), ...), purchases positive, sales negative


@dataclass
class Plan:
    before: dict  # euro values of each sleeve and of cash before the orders
    orders: list
    after: dict  # euro values after the orders
    band_triggered: bool = False
    top_up_waits: bool = False
    notes: list = field(default_factory=list)

    def weights(self, which: str) -> dict:
        values = self.before if which == "before" else self.after
        total = sum(values.values())
        return {k: v / total for k, v in values.items()}


def _cents_down(x: float) -> float:
    return math.floor(round(x * 100, 6)) / 100


def rule_4(values: dict, cash: float) -> dict:
    """Purchases with the cash, by sleeve, in euro (before rounding)."""
    total = values[E] + values[B] + cash
    shortfall = {s: config.TARGET[s] * total - values[s] for s in config.SLEEVES}
    buys = {s: 0.0 for s in config.SLEEVES}
    remaining = cash
    for sleeve in sorted(config.SLEEVES, key=lambda s: shortfall[s], reverse=True):
        x = min(remaining, max(shortfall[sleeve], 0.0))
        buys[sleeve] += x
        remaining -= x
    return buys


def rule_5(values: dict, cash: float, invest_cash: bool = True) -> dict:
    """Band orders by sleeve, in euro (purchases positive, sales negative), or zeros inside the band.

    The equity weight counts the cash not yet invested in the value of the portfolio, as RULES.md defines
    a weight. When the top-up waits under rule 6 (invest_cash False), the band orders bring the two ETFs
    to 70/30 of their combined value and the cash stays for the next cycle day.
    """
    total = values[E] + values[B] + cash
    weight = values[E] / total
    low, high = config.BAND
    if low <= weight <= high:
        return {s: 0.0 for s in config.SLEEVES}
    base = total if invest_cash else values[E] + values[B]
    return {s: config.TARGET[s] * base - values[s] for s in config.SLEEVES}


def _orders(top_up: dict, band: dict, cash: float) -> list:
    """One order per sleeve, sales first. Each amount is rounded down to the cent, the purchases are cut
    by the cent if needed so that they never exceed the cash plus the proceeds of the sales, and the
    parts of an order add up to its amount exactly."""
    net = {s: top_up[s] + band[s] for s in config.SLEEVES}
    amount = {s: _cents_down(abs(net[s])) for s in config.SLEEVES}
    sales = sum(amount[s] for s in config.SLEEVES if net[s] < 0)
    excess = sum(amount[s] for s in config.SLEEVES if net[s] > 0) - (cash + sales)
    if excess > 1e-9:
        largest = max((s for s in config.SLEEVES if net[s] > 0), key=lambda s: amount[s])
        amount[largest] = round(amount[largest] - math.ceil(round(excess * 100, 6)) / 100, 2)
    orders = []
    for sleeve in sorted(config.SLEEVES, key=lambda s: net[s] > 0):
        if amount[sleeve] < 0.005:
            continue
        signed = amount[sleeve] if net[sleeve] > 0 else -amount[sleeve]
        if abs(top_up[sleeve]) >= 0.005 and abs(band[sleeve]) >= 0.005:
            first = _cents_down(top_up[sleeve])
            parts = (("4", first), ("5", round(signed - first, 2)))
        else:
            parts = (("4" if abs(top_up[sleeve]) >= 0.005 else "5", signed),)
        orders.append(Order(sleeve, "buy" if signed > 0 else "sell", amount[sleeve], parts))
    return orders


def plan(equity_eur: float, bonds_eur: float, cash_eur: float, orders_used_this_month: int = 0) -> Plan:
    """The cycle day's orders from the values at the last net asset values and the cash not yet invested."""
    before = {E: equity_eur, B: bonds_eur, "cash": cash_eur}
    values = {E: equity_eur, B: bonds_eur}
    top_up = rule_4(values, cash_eur)
    after_4 = {s: values[s] + top_up[s] for s in config.SLEEVES}
    band = rule_5(after_4, cash_eur - sum(top_up.values()))
    notes = []
    orders = _orders(top_up, band, cash_eur)
    small = [o for o in orders if o.amount_eur < config.MIN_ORDER_EUR]
    if small:
        notes.append(
            "Orders below one euro are not placed; their cash waits for the next cycle day: "
            + ", ".join(f"{o.side} {o.sleeve} {o.amount_eur:.2f}" for o in small)
        )
        orders = [o for o in orders if o.amount_eur >= config.MIN_ORDER_EUR]
    left = config.ORDERS_PER_MONTH - orders_used_this_month
    top_up_waits = False
    if len(orders) > left:
        top_up_waits = True
        band_only = rule_5(values, cash_eur, invest_cash=False)
        orders = [
            o
            for o in _orders({s: 0.0 for s in config.SLEEVES}, band_only, 0.0)
            if o.amount_eur >= config.MIN_ORDER_EUR
        ]
        notes.append(f"Rule 6: {left} orders left this month; the top-up waits for the next cycle day.")
        if len(orders) > left:
            raise BudgetError(
                f"Rule 6: the band orders need {len(orders)} orders and the month has {left} left. "
                "Run the cycle as written as far as possible and record the doubt in the monthly log."
            )
    after = dict(before)
    for o in orders:
        signed = o.amount_eur if o.side == "buy" else -o.amount_eur
        after[o.sleeve] += signed
        after["cash"] -= signed
    triggered = any(abs(a) >= 0.005 for a in (band_only if top_up_waits else band).values())
    return Plan(
        before=before,
        orders=orders,
        after=after,
        band_triggered=triggered,
        top_up_waits=top_up_waits,
        notes=notes,
    )
