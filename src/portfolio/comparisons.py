"""The comparisons: the record beside comparators that receive the same contributions on the same days.

The comparators of the first stage are the benchmark (the index blend, which has values at month ends only),
reference portfolios A and B, the same two ETFs at 100/0, 90/10, 80/20 and 60/40 under the same rules with the
band of rule 5 at five points either side of each target, and savings at the euro short-term rate. Each is
valued in euro at the issuers' net asset values or at the published rate, without costs.

For the portfolio and each comparator the module measures the return since the first purchase, time-weighted
and money-weighted and not annualised; the volatility of daily returns times the square root of 252; the worst
fall with its dates; the correlation of daily returns with the portfolio's; the difference of time-weighted
return to the portfolio's; and the band chance alone produces over the same span, plus or minus two tracking
errors times the square root of the years, where the tracking error is the standard deviation of the daily
differences times the square root of 252. The band ignores compounding and treats the daily differences as
independent.

Each difference is split into effects computed day by day, summed by month and then over the months. For a
comparator C that holds the same two funds at net asset value, and reference portfolio A, with cash weight c,
the equity share of the invested part e (both at the previous close), the equity fund's return in euro r_e and
in US dollars r_d, and the bond fund's return r_b, the identity

    r_C - r_A = (c_A - c_C) * r_inv_A + (1 - c_C) * (e_C - e_A) * (r_e - r_b)

is exact on each day, where r_inv_A is the return of A's invested part. Cash is its first term. Split is the
second term with the dollar return r_d in place of r_e, and the dollar is the rest, (1 - c_C) * (e_C - e_A) *
(r_e - r_d): the fund's other currencies stay inside r_d. Implementation is r_A minus the portfolio's return,
and drift, for reference portfolio B, is r_B - r_A. For savings, at the rate r_s,

    r_s - r_A = (1 - c_A) * (r_s - r_b) + c_A * r_s - (1 - c_A) * e_A * (r_e - r_b),

so the bonds against the rate, cash, split and the dollar sum to it exactly. Over the record, the compounding
residual is the difference of the cumulative returns minus the sum of the daily effects, and timing is the
comparator's money-weighted minus time-weighted return, less the portfolio's.

The benchmark's statistics come from month-end values times the square root of 12, and stay empty until six
month ends exist: a tracking error from fewer monthly differences is not an estimate. Its difference and its
effects wait for the same date.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config, metrics, references
from .ledger import Ledger

E, B = config.EQUITY, config.BONDS
TRADING_DAYS = 252
BAND_HALF_WIDTH = 0.05  # rule 5's band, five points either side of the target
BENCHMARK_MONTH_ENDS = 6  # month ends before the benchmark's statistics, difference and effects are shown

# Key, name and equity target of each split. 70/30 is reference portfolio A.
SPLITS = (
    ("split_100_0", "100/0", 1.00),
    ("split_90_10", "90/10", 0.90),
    ("split_80_20", "80/20", 0.80),
    ("split_60_40", "60/40", 0.60),
)
# Key, name and pane of every row of the summary table, in its order. The portfolio is the base row.
ROWS = (
    ("portfolio", "The portfolio", None),
    ("benchmark", "The benchmark, the index blend", "same_rules"),
    ("reference_a", "Reference portfolio A", "same_rules"),
    ("reference_b", "Reference portfolio B", "same_rules"),
    *((key, name, "other_funds_or_splits") for key, name, _ in SPLITS),
    ("savings", "Savings at the euro short-term rate", "bank"),
)
EFFECTS = ("implementation", "drift", "split", "dollar", "cash", "bonds_against_rate", "timing", "compounding")


def split_target(equity: float) -> dict:
    return {E: equity, B: round(1 - equity, 10)}


def split_band(equity: float) -> tuple:
    """Rule 5's band around another target, within 0 and 1. For 100/0 it never binds."""
    return (max(0.0, round(equity - BAND_HALF_WIDTH, 10)), min(1.0, round(equity + BAND_HALF_WIDTH, 10)))


def savings(ledger: Ledger, rate: pd.Series, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily values in euro of the contributions held at the euro short-term rate.

    The starting amount is deposited on the first day of days, the day of the first purchase, and each top-up on
    the first day on or after its date, as for the S&P 500 alternative. Interest accrues on every calendar day at
    the rate of that day, or of the last day before it with a rate, over 360, and is compounded daily.
    """
    if not len(days):
        return pd.DataFrame(columns=["value"])
    rate = rate.sort_index()
    flows = metrics.flows_on_days(ledger, days)
    value, rows, previous = metrics.start_amount(ledger), [], None
    for day in days:
        if previous is not None:
            for d in pd.date_range(previous, day - pd.Timedelta(days=1), freq="D"):
                known = rate.loc[:d]
                value *= 1 + (float(known.iloc[-1]) if len(known) else 0.0) / 100 / 360
            value += flows.get(day, 0.0)
        rows.append({"date": day, "value": value})
        previous = day
    return pd.DataFrame(rows).set_index("date")


def _returns(growth: pd.Series) -> pd.Series:
    return (growth / growth.shift(1) - 1).iloc[1:]


def _worst_fall(growth: pd.Series) -> tuple:
    """The deepest fall below a previous peak, as a positive share, with the peak's and the low's dates."""
    fall = metrics.drawdown(growth)
    if not len(fall) or fall.min() >= 0:
        return 0.0, None, None
    low = fall.idxmin()
    peak = growth.loc[:low].idxmax()
    return float(-fall.min()), peak, low


def measures(growth: pd.Series, base: pd.Series, periods_per_year: int = TRADING_DAYS) -> dict:
    """The statistics of one series against the portfolio's, both growth indices on the same dates."""
    r, rp = _returns(growth), _returns(base)
    n = len(r)
    fall, peak, low = _worst_fall(growth)
    out = {
        "periods": n,
        "return_time_weighted": float(growth.iloc[-1] / growth.iloc[0] - 1),
        "volatility": float(r.std(ddof=1) * math.sqrt(periods_per_year)) if n > 1 else float("nan"),
        "worst_fall": fall, "worst_fall_peak": peak, "worst_fall_low": low,
        "correlation": float(r.corr(rp)) if n > 2 and r.std() > 0 and rp.std() > 0 else float("nan"),
        "difference": float(growth.iloc[-1] / growth.iloc[0] - base.iloc[-1] / base.iloc[0]),
    }  # fmt: skip
    gap = r - rp
    tracking = float(gap.std(ddof=1) * math.sqrt(periods_per_year)) if n > 1 else float("nan")
    out["tracking_error"] = tracking
    out["band"] = 2 * tracking * math.sqrt(n / periods_per_year) if n > 1 else float("nan")
    out["inside_band"] = "" if math.isnan(out["band"]) else ("yes" if abs(out["difference"]) <= out["band"] else "no")
    return out


def _state(sim: pd.DataFrame, navs: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    """Cash weight and the equity share of the invested part at each close, all cash before the first purchase."""
    unit_value = navs[[E, B]].reindex(days)
    held = sim.reindex(days)
    equity = held[E] * unit_value[E]
    invested = equity + held[B] * unit_value[B]
    out = pd.DataFrame({"cash": held["cash"] / held["value"], "equity": (equity / invested).where(invested > 0, 0.0)})
    return out.fillna({"cash": 1.0, "equity": 0.0})


def _fund_returns(navs: pd.DataFrame, days: pd.DatetimeIndex) -> pd.DataFrame:
    values = navs.reindex(days)
    usd = values[E] * values["usd_per_eur"]
    out = pd.DataFrame({"r_e": values[E] / values[E].shift(1) - 1, "r_d": usd / usd.shift(1) - 1,
                        "r_b": values[B] / values[B].shift(1) - 1})  # fmt: skip
    return out.iloc[1:]


def daily_effects(key: str, r: pd.DataFrame, funds: pd.DataFrame, state: dict) -> pd.DataFrame:
    """The daily effects of one comparator's difference to the portfolio, one column per effect.

    r holds the daily returns of the portfolio, A, B and the comparator; state holds the cash weight and the equity
    share of the invested part, at the previous close, of A and of the comparator."""
    out = pd.DataFrame(0.0, index=r.index, columns=list(EFFECTS))
    out["implementation"] = r["reference_a"] - r["portfolio"]
    if key == "reference_b":
        out["drift"] = r["reference_b"] - r["reference_a"]
    elif key.startswith("split_"):
        a, c = state["reference_a"].shift(1).reindex(r.index), state[key].shift(1).reindex(r.index)
        inv_a = a["equity"] * funds["r_e"] + (1 - a["equity"]) * funds["r_b"]
        tilt = (1 - c["cash"]) * (c["equity"] - a["equity"])
        out["cash"] = (a["cash"] - c["cash"]) * inv_a
        out["split"] = tilt * (funds["r_d"] - funds["r_b"])
        out["dollar"] = tilt * (funds["r_e"] - funds["r_d"])
    elif key == "savings":
        a = state["reference_a"].shift(1).reindex(r.index)
        rate = r["savings"]
        out["bonds_against_rate"] = (1 - a["cash"]) * (rate - funds["r_b"])
        out["cash"] = a["cash"] * rate
        out["split"] = -(1 - a["cash"]) * a["equity"] * (funds["r_d"] - funds["r_b"])
        out["dollar"] = -(1 - a["cash"]) * a["equity"] * (funds["r_e"] - funds["r_d"])
    return out


def _month(index) -> list:
    return [pd.Timestamp(d).strftime("%Y-%m") for d in index]


def simulations(ledger: Ledger, navs: pd.DataFrame, values: pd.DataFrame, table: pd.DataFrame, ref_a: pd.DataFrame,
                ref_b: pd.DataFrame, rate: pd.Series, end) -> tuple:  # fmt: skip
    """Each daily comparator's simulation, and the euro value and growth of 100 of the portfolio and of each, on the
    days of the record with its base day first."""
    days = table.index
    base = days[0]
    start = metrics.start_amount(ledger)
    sims = {"reference_a": ref_a, "reference_b": ref_b}
    for key, _, equity in SPLITS:
        sims[key] = references.simulate(ledger, navs, end, "rules", split_target(equity), split_band(equity))
    sims["savings"] = savings(ledger, rate, days[1:])
    values_eur = {"portfolio": values["value_eur"]}
    growth = {"portfolio": table["growth_portfolio"]}
    for key, sim in sims.items():
        held = sim.reindex(days[1:])["value"]
        values_eur[key] = held
        growth[key] = metrics.growth_index(held, metrics.flows_on_days(ledger, held.index), start, base).reindex(days)
    return sims, values_eur, growth


def build(ledger: Ledger, navs: pd.DataFrame, values: pd.DataFrame, table: pd.DataFrame, ref_a: pd.DataFrame,
          ref_b: pd.DataFrame, blend: pd.Series, rate: pd.Series, end) -> dict:  # fmt: skip
    """The three public tables of the comparisons: one row per comparator, the growth of 100 of each by day, and the
    effects by comparator and month, with the record's totals."""
    days = table.index  # the base day first, then every valuation day of the record
    base = days[0]
    sims, values_eur, growth = simulations(ledger, navs, values, table, ref_a, ref_b, rate, end)
    last = days[-1]

    rows = []
    for key, name, pane in ROWS:
        if key == "benchmark":
            rows.append(_benchmark_row(name, pane, blend, growth["portfolio"]))
            continue
        row = {"comparator": key, "name": name, "pane": pane or "", "basis": "daily", "first_day": days[1] if len(days) > 1 else base,
               "last_day": last, **measures(growth[key], growth["portfolio"])}  # fmt: skip
        row["return_money_weighted"] = metrics.money_weighted_cumulative(ledger, last, float(values_eur[key].loc[last]))
        if key == "portfolio":
            for k in ("correlation", "difference", "tracking_error", "band"):
                row[k] = float("nan")
            row["inside_band"] = ""
        if key == "savings":
            row["correlation"] = float("nan")  # the rate barely moves from day to day
        rows.append(row)
    summary = pd.DataFrame(rows)

    r = pd.DataFrame({k: _returns(g) for k, g in growth.items()})
    funds = _fund_returns(navs, days)
    state = {k: _state(sims[k], navs, days) for k in ["reference_a", *(s[0] for s in SPLITS)]}
    effects = []
    by_key = summary.set_index("comparator")
    for key, _, _ in ROWS:
        if key in ("portfolio", "benchmark"):
            continue
        daily = daily_effects(key, r, funds, state)
        monthly = daily.groupby(_month(daily.index)).sum()
        for month, line in monthly.iterrows():
            effects += [{"comparator": key, "period": month, "effect": e, "value": float(line[e])} for e in EFFECTS]
        total = monthly.sum()
        row = by_key.loc[key]
        total["compounding"] = row["difference"] - total.sum()
        mine = row["return_money_weighted"] - row["return_time_weighted"]
        own = by_key.loc["portfolio", "return_money_weighted"] - by_key.loc["portfolio", "return_time_weighted"]
        total["timing"] = mine - own
        effects += [{"comparator": key, "period": "record", "effect": e, "value": float(total[e])} for e in EFFECTS]
    effects += _benchmark_effects(by_key.loc["benchmark"], blend, r, funds, state, sims["reference_b"], navs, days)

    daily_table = pd.DataFrame({f"growth_{k}": g for k, g in growth.items()})
    daily_table.index.name = "date"
    return {"summary": summary, "daily": daily_table.reset_index(), "effects": pd.DataFrame(effects, columns=["comparator", "period", "effect", "value"])}


def _benchmark_row(name: str, pane: str, blend: pd.Series, portfolio: pd.Series) -> dict:
    """The benchmark against the portfolio at the month ends where both exist. Its return needs two month ends,
    and its statistics, difference and band need six."""
    blend = blend.dropna()
    row = {"comparator": "benchmark", "name": name, "pane": pane, "basis": "monthly",
           "first_day": blend.index[0] if len(blend) else None, "last_day": blend.index[-1] if len(blend) else None,
           "periods": max(len(blend) - 1, 0), "return_money_weighted": float("nan"), "inside_band": ""}  # fmt: skip
    for k in ("return_time_weighted", "volatility", "worst_fall", "correlation", "difference", "tracking_error", "band"):
        row[k] = float("nan")
    row["worst_fall_peak"] = row["worst_fall_low"] = None
    if len(blend) >= 2:
        row["return_time_weighted"] = float(blend.iloc[-1] / blend.iloc[0] - 1)
    if len(blend) >= BENCHMARK_MONTH_ENDS:
        stats = measures(blend, portfolio.reindex(blend.index), periods_per_year=12)
        row.update({k: stats[k] for k in ("volatility", "worst_fall", "worst_fall_peak", "worst_fall_low", "correlation",
                                          "difference", "tracking_error", "band", "inside_band")})  # fmt: skip
    return row


def _benchmark_effects(row, blend, r, funds, state, ref_b, navs, days) -> list:
    """The benchmark's effects by month once its difference is shown: implementation and drift summed by day,
    split, the dollar and cash from reference portfolio B's weights at each month start against 70/30, and the
    funds' costs and tracking differences in the residual until the fund-cost effect is built."""
    blend = blend.dropna()
    if len(blend) < BENCHMARK_MONTH_ENDS:
        return []
    b_state = _state(ref_b, navs, days)
    fund_level = (1 + funds).cumprod()
    out, total = [], pd.Series(0.0, index=list(EFFECTS))
    for previous, end in zip(blend.index, blend.index[1:]):
        window = r.index[(r.index > previous) & (r.index <= end)]
        line = pd.Series(0.0, index=list(EFFECTS))
        line["implementation"] = (r.loc[window, "reference_a"] - r.loc[window, "portfolio"]).sum()
        line["drift"] = (r.loc[window, "reference_b"] - r.loc[window, "reference_a"]).sum()
        growth = fund_level.loc[end] / fund_level.loc[previous] - 1
        w = b_state.loc[previous]
        tilt = config.TARGET[E] - w["equity"]
        line["split"] = tilt * (growth["r_d"] - growth["r_b"])
        line["dollar"] = tilt * (growth["r_e"] - growth["r_d"])
        line["cash"] = w["cash"] * (w["equity"] * growth["r_e"] + (1 - w["equity"]) * growth["r_b"])
        total += line
        out += [{"comparator": "benchmark", "period": pd.Timestamp(end).strftime("%Y-%m"), "effect": e,
                 "value": float(line[e])} for e in EFFECTS]  # fmt: skip
    total["compounding"] = row["difference"] - total.sum()
    out += [{"comparator": "benchmark", "period": "record", "effect": e, "value": float(total[e])} for e in EFFECTS]
    return out
