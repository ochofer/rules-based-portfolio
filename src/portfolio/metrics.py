"""Step 3 of the pipeline: values to returns, drawdowns, weights, costs, orders and the monthly table.

Every figure here is in euro or in units until outputs.py turns it into a share, a percentage or basis
points. The time-weighted return treats each contribution as arriving at the end of its day:
r_d = (V_d - C_d) / V_(d-1) - 1. The base is the starting amount before the first order, set at 100 on
the last valuation day before the first purchase, so that the first day's return includes the cost of
the first orders.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from . import config, rules_engine, trading_days
from .ledger import Ledger
from .references import _cycle_days

E, B = config.EQUITY, config.BONDS


def start_amount(ledger: Ledger) -> float:
    return float(ledger.contributions.iloc[0]["amount_eur"])


def base_day(ledger: Ledger, navs_eur: pd.DataFrame) -> pd.Timestamp:
    """The last day with net asset values before the first purchase: the base of every index."""
    first = pd.Timestamp(ledger.contributions.iloc[0]["moment"].date())
    earlier = navs_eur.index[navs_eur.index < first]
    return earlier[-1] if len(earlier) else first - pd.Timedelta(days=1)


def flows_on_days(ledger: Ledger, days: pd.DatetimeIndex) -> pd.Series:
    """Top-ups by valuation day: each is assigned to the first valuation day on or after its date."""
    out = pd.Series(0.0, index=days)
    for c in ledger.contributions.iloc[1:].itertuples():
        later = days[days >= pd.Timestamp(c.moment.date())]
        if len(later):
            out[later[0]] += c.amount_eur
    return out


def growth_index(values: pd.Series, flows: pd.Series, base_value: float, base: pd.Timestamp) -> pd.Series:
    """Growth of 100, time-weighted, from the base."""
    level, previous, out = 100.0, base_value, {base: 100.0}
    for day, value in values.items():
        level *= (value - flows.get(day, 0.0)) / previous
        out[day] = level
        previous = value
    return pd.Series(out, dtype=float)


def drawdown(index: pd.Series) -> pd.Series:
    return index / index.cummax() - 1


def money_weighted(ledger: Ledger, day: pd.Timestamp, value: float) -> float:
    """The internal rate of return of the contributions to day and the value on day, per year."""
    flows = [(c.moment.date(), -c.amount_eur) for c in ledger.contributions.itertuples() if c.moment <= day]
    flows.append((day.date(), value))
    first = flows[0][0]
    t = np.array([(d - first).days / 365.25 for d, _ in flows])
    a = np.array([x for _, x in flows])
    if t[-1] <= 0:
        return float("nan")

    def npv(rate):
        return float(np.sum(a / (1 + rate) ** t))

    low, high = -0.99, 10.0
    for _ in range(200):
        mid = (low + high) / 2
        if npv(mid) > 0:
            low = mid
        else:
            high = mid
    return mid


def _years(ledger: Ledger, day: pd.Timestamp) -> float:
    return (day.date() - ledger.contributions.iloc[0]["moment"].date()).days / 365.25


def daily(
    ledger: Ledger,
    values: pd.DataFrame,
    reference_a: pd.DataFrame,
    reference_b: pd.DataFrame,
    blend: pd.Series,
    base: pd.Timestamp,
) -> pd.DataFrame:
    """One row per valuation day, with the base row first."""
    start = start_amount(ledger)
    flows = flows_on_days(ledger, values.index)
    out = pd.DataFrame({"growth_portfolio": growth_index(values["value_eur"], flows, start, base)})
    for name, ref in (("growth_reference_a", reference_a), ("growth_reference_b", reference_b)):
        if len(ref):
            out[name] = growth_index(ref["value"], flows_on_days(ledger, ref.index), start, base)
        else:
            out[name] = np.nan
    out["growth_index_blend"] = blend.reindex(out.index)
    out["drawdown_portfolio"] = drawdown(out["growth_portfolio"])
    known = out["growth_index_blend"].dropna()
    out["drawdown_index_blend"] = drawdown(known).reindex(out.index)
    for column in ("weight_equity", "weight_bonds", "weight_cash"):
        out[column] = values[column].reindex(out.index)
    out.loc[base, ["weight_equity", "weight_bonds", "weight_cash"]] = [np.nan, np.nan, 1.0]
    out["value_in_units"] = values["value_eur"].reindex(out.index) / start * 100
    out.loc[base, "value_in_units"] = 100.0
    out["contributions_in_units"] = values["contributions_eur"].reindex(out.index) / start * 100
    out.loc[base, "contributions_in_units"] = 100.0
    ref = out["growth_reference_a"]
    out["implementation_cost_bps"] = (out["growth_portfolio"] / ref - 1) * 1e4
    out.index.name = "date"
    return out.sort_index()


def orders(ledger: Ledger) -> pd.DataFrame:
    """The portfolio's orders with what the public record shows of them: no amount and no units."""
    rows = []
    start = start_amount(ledger)
    for o in ledger.orders.itertuples():
        parts = ""
        if o.parts:
            split = dict(p.split(":") for p in o.parts.split("|"))
            total = sum(float(v) for v in split.values())
            parts = ", ".join(f"rule {k}: {float(v) / total:.4f}" for k, v in split.items())
        if o.rule == "start":
            gross = o.gross + o.fee
            produced = "yes" if abs(gross - config.TARGET[o.sleeve] * start) <= 1.0 else "no"
        else:
            produced = ""
        day = o.moment.date()
        start_w, end_w = config.ORDER_WINDOW
        rows.append(
            {
                "date": pd.Timestamp(day),
                "sleeve": o.sleeve,
                "side": o.side,
                "rule": o.rule,
                "parts": parts,
                "produced_by_rules": produced,
                "inside_rule_7_window": "yes" if start_w <= o.moment.time() <= end_w else "no",
                "on_a_trading_day": "yes" if trading_days.is_trading_day(day) else "no",
                "bid_and_ask_recorded": "no" if (pd.isna(o.bid) or pd.isna(o.ask)) else "yes",
                "_fee": o.fee,
                "_half_spread": (
                    np.nan if pd.isna(o.bid) or pd.isna(o.ask) else abs(o.units) * (o.ask - o.bid) / 2
                ),
            }
        )
    return pd.DataFrame(rows)


def _state_before(ledger: Ledger, day: date) -> dict:
    """Units and cash after every contribution to the end of day and every order before day."""
    units = {E: 0.0, B: 0.0}
    cash = sum(c.amount_eur for c in ledger.contributions.itertuples() if c.moment.date() <= day)
    for o in ledger.orders.itertuples():
        if o.moment.date() < day:
            units[o.sleeve] += o.units
            cash += o.cash_change
    return {"units": units, "cash": cash}


def compliance(ledger: Ledger, navs_eur: pd.DataFrame, today: date) -> tuple:
    """Band events and every departure from the rules, one row each, without amounts."""
    first = ledger.contributions.iloc[0]["moment"].date()
    events, issues = [], []
    placed = orders(ledger)
    for o in placed.itertuples():
        if o.inside_rule_7_window == "no":
            issues.append(
                {"date": o.date, "sleeve": o.sleeve, "side": o.side, "issue": "outside the rule 7 window"}
            )
        if o.on_a_trading_day == "no":
            issues.append(
                {"date": o.date, "sleeve": o.sleeve, "side": o.side, "issue": "on a day Xetra is closed"}
            )
    cycle_days = set(_cycle_days(first, today))
    for day in sorted(cycle_days):
        last_close = pd.Timestamp(trading_days.previous_trading_day(day))
        if last_close < navs_eur.index.min():
            continue
        state = _state_before(ledger, day)
        unit_value = navs_eur.loc[:last_close].iloc[-1]
        values = {s: state["units"][s] * unit_value[s] for s in (E, B)}
        used = int((placed["date"].dt.to_period("M") == pd.Period(day, "M")).sum() if len(placed) else 0)
        used -= int(((placed["date"] == pd.Timestamp(day))).sum() if len(placed) else 0)
        plan = rules_engine.plan(values[E], values[B], state["cash"], orders_used_this_month=used)
        on_day = placed[placed["date"] == pd.Timestamp(day)] if len(placed) else placed
        done = {(o.sleeve, o.side) for o in on_day.itertuples()}
        wanted = {(o.sleeve, o.side) for o in plan.orders}
        for sleeve, side in sorted(wanted - done):
            issues.append({"date": pd.Timestamp(day), "sleeve": sleeve, "side": side,
                           "issue": "called for by the rules and not placed"})  # fmt: skip
        for sleeve, side in sorted(done - wanted):
            issues.append({"date": pd.Timestamp(day), "sleeve": sleeve, "side": side,
                           "issue": "placed without the rules calling for it"})  # fmt: skip
        if plan.band_triggered:
            events.append(
                {
                    "date": pd.Timestamp(day),
                    "equity_weight_before": plan.weights("before")[E],
                    "band_orders_placed": "yes" if wanted <= done else "no",
                }
            )
    for o in placed.itertuples():
        if o.rule in ("4", "5", "4+5") and o.date.date() not in cycle_days:
            issues.append({"date": o.date, "sleeve": o.sleeve, "side": o.side,
                           "issue": "placed on a day that is not a cycle day"})  # fmt: skip
    columns = ["date", "sleeve", "side", "issue"]
    band = pd.DataFrame(events, columns=["date", "equity_weight_before", "band_orders_placed"])
    return band, pd.DataFrame(issues, columns=columns).sort_values("date", kind="stable")


def _value_on(values: pd.DataFrame, day) -> float:
    """The portfolio's value at the close of day, or of the first valuation day after it."""
    later = values.index[values.index >= pd.Timestamp(day)]
    return float(values.loc[later[0] if len(later) else values.index[-1], "value_eur"])


def monthly(
    ledger: Ledger, table: pd.DataFrame, values: pd.DataFrame, placed: pd.DataFrame, today: date
) -> pd.DataFrame:
    """The monthly table: one row per month since the first purchase, the current month to date."""
    rows = []
    start = start_amount(ledger)
    days = table.index[1:]
    if len(days) == 0:
        return pd.DataFrame()
    base = table.index[0]
    current = pd.Timestamp(today).to_period("M")
    months = sorted(set(days.to_period("M")))
    previous_day = base
    flows = flows_on_days(ledger, values.index)
    for month in months:
        in_month = days[days.to_period("M") == month]
        last = in_month.max()
        value_end = float(values.loc[last, "value_eur"])
        value_start = start if previous_day == base else float(values.loc[previous_day, "value_eur"])
        flow = float(flows.loc[in_month].sum())
        month_orders = placed[placed["date"].dt.to_period("M") == month] if len(placed) else placed
        # Costs in basis points of the portfolio's value at the close of each order's day, the unit of the
        # implementation cost, so that the sources of a month add up to the month's implementation cost.
        value_on = [_value_on(values, d) for d in month_orders["date"]] if len(month_orders) else []
        fees = sum(f / v for f, v in zip(month_orders["_fee"], value_on)) if len(month_orders) else 0.0
        measured = [h / v for h, v in zip(month_orders["_half_spread"], value_on) if not pd.isna(h)]
        not_measured = int(month_orders["_half_spread"].isna().sum()) if len(month_orders) else 0
        mwr = money_weighted(ledger, last, value_end)
        years = _years(ledger, last)
        row = {
            "month": str(month),
            "last_day": last,
            "complete": "yes" if month < current else "to date",
            "return_month": table.loc[last, "growth_portfolio"] / table.loc[previous_day, "growth_portfolio"]
            - 1,
            "return_since_start": table.loc[last, "growth_portfolio"] / 100 - 1,
            "money_weighted_since_start": (1 + mwr) ** years - 1 if years < 1 else np.nan,
            "money_weighted_per_year": mwr if years >= 1 else np.nan,
            "weight_equity": table.loc[last, "weight_equity"],
            "weight_bonds": table.loc[last, "weight_bonds"],
            "weight_cash": table.loc[last, "weight_cash"],
            "drift_points": (table.loc[last, "weight_equity"] - config.TARGET[E]) * 100,
            "drawdown": table.loc[last, "drawdown_portfolio"],
            "worst_fall_to_date": -table.loc[:last, "drawdown_portfolio"].min(),
            "orders": len(month_orders),
            "contributions_in_units": flow / start * 100 + (100.0 if previous_day == base else 0.0),
            "value_in_units": value_end / start * 100,
            "market_effect": (value_end - value_start - flow) / value_start,
            "contribution_effect": flow / value_start,
            "commissions_bps": fees * 1e4,
            "half_spread_bps": sum(measured) * 1e4 if measured else np.nan,
            "orders_without_bid_and_ask": not_measured,
            "currency_conversion_bps": 0.0,
            "implementation_cost_bps": table.loc[last, "implementation_cost_bps"],
        }
        # The month's implementation cost is the fall in the cumulative one over the month. What the
        # commissions, the measured half-spread and the conversion leave of it is the execution price
        # against the day's net asset value (an unmeasured half-spread included), so the four sum to it.
        before = table.loc[previous_day, "implementation_cost_bps"]
        row["implementation_cost_month_bps"] = -(
            row["implementation_cost_bps"] - (0.0 if pd.isna(before) else before)
        )
        itemised = row["commissions_bps"] + (
            0.0 if pd.isna(row["half_spread_bps"]) else row["half_spread_bps"]
        )
        row["execution_against_nav_bps"] = (
            row["implementation_cost_month_bps"] - itemised - row["currency_conversion_bps"]
        )
        rows.append(row)
        previous_day = last
    frame = pd.DataFrame(rows)
    frame["volatility_12m"] = np.nan
    if len(frame) >= 12:
        r = frame["return_month"]
        frame["volatility_12m"] = r.rolling(12).std(ddof=1) * np.sqrt(12)
    return frame
