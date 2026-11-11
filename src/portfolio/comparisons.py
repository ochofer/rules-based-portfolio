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

The second stage adds 70/30 under the same rules with the first-ranked equity fund, and one fund in place of two:
the S&P 500 alternative, the MSCI World fund, the two LifeStrategy funds, the Nasdaq-100 fund and the Mag7 fund,
each bought with the same contributions on the same days at its net asset value in euro and held. The Mag7 fund's
series starts on 4 November 2026, so its comparison starts at that day's close with the portfolio's value, and
takes the contributions made after it. For a fund X with equity share s, the difference to reference portfolio A is
split through a portfolio P' of the two funds held at the split s without cash: P' minus A gives cash, split and
the dollar by the identity above, and X minus P' gives regions, the sum over the look-through regions of s times the
difference in region weight times the region's return in euro (Brinson and Fachler), the dollar's part of a US
dollar fund, and the rest within each region. For savings, bonds against the rate is split into the rate against
the bonds' yield, the bonds' duration times the change in yield, and the rest of the bond return, from the ECB's
curve at the bond fund's duration.

The benchmark's statistics come from month-end values times the square root of 12, and stay empty until six
month ends exist: a tracking error from fewer monthly differences is not an estimate. Its difference and its
effects wait for the same date. A daily comparator's volatility, correlation, difference and band wait for 20 daily
returns for the same reason.
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
MIN_DAILY_RETURNS = 20  # daily returns before a daily comparator's volatility, correlation, difference and band
REGION_NAMES = ("North America", "Europe and Middle East", "Pacific", "Emerging markets")
CASH_REGION = "Cash"

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
    *((key, name, "splits") for key, name, _ in SPLITS),
    ("first_ranked", "70/30 with the first-ranked funds", "same_rules"),
    ("sp500", "The S&P 500 alternative", "one_fund"),
    ("msci_world", "The MSCI World fund", "one_fund"),
    ("lifestrategy_60", "LifeStrategy 60% Equity", "one_fund"),
    ("lifestrategy_80", "LifeStrategy 80% Equity", "one_fund"),
    ("nasdaq100", "The Nasdaq-100 fund", "one_fund"),
    ("mag7", "The Mag7 fund", "one_fund"),
    ("market_portfolio", "The global market portfolio", "market_portfolio"),
    ("savings", "Savings at the euro short-term rate", "bank"),
    ("bank_offensief", "Rabobank's managed profile Offensief", "managed"),
)
ONE_FUND = tuple(key for key, _, pane in ROWS if pane == "one_fund")
EFFECTS = ("implementation", "drift", "split", "dollar", "cash", "regions", "within_regions", "equity_classes",
           "bond_classes", "rate_against_yield", "change_in_yield", "bonds_rest", "timing", "compounding")  # fmt: skip
BOND_EFFECTS = ("rate_against_yield", "change_in_yield", "bonds_rest")
# The global market portfolio's asset classes, each held through one fund (method/comparator_funds.csv), and those
# of them that count as equity: listed private equity and listed real estate are companies' shares.
MARKET_SLEEVES = ("equities", "aggregate", "private_equity", "real_estate", "em_debt", "inflation_linked", "high_yield")
EQUITY_LIKE = ("equities", "private_equity", "real_estate")


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


def measures(growth: pd.Series, base: pd.Series, periods_per_year: int = TRADING_DAYS, minimum: int = 0) -> dict:
    """The statistics of one series against the portfolio's, both growth indices on the same dates. Below minimum
    returns the volatility, correlation, difference and band are left empty."""
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
    if n < minimum:
        for k in ("volatility", "correlation", "difference", "tracking_error", "band"):
            out[k] = float("nan")
        out["inside_band"] = ""
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


def daily_effects(key: str, r: pd.DataFrame, funds: pd.DataFrame, state: dict, ctx: dict = None) -> pd.DataFrame:
    """The daily effects of one comparator's difference to the portfolio, one column per effect.

    r holds the daily returns of the portfolio, A, B and the comparator. state holds the cash weight and the equity
    share of the invested part, at the previous close, of A and of the comparator. ctx, for the second stage, holds
    the regional returns and weights, the one-fund comparators' equity shares and dollar returns, and the bond
    curve."""
    ctx = ctx or {}
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
        invested = 1 - a["cash"]
        bond = ctx.get("bond")
        if bond is not None:
            carry, change = bond["carry"].reindex(r.index), bond["change"].reindex(r.index)
            out["rate_against_yield"] = invested * (rate - carry)
            out["change_in_yield"] = invested * bond["duration"] * change
            out["bonds_rest"] = -invested * (funds["r_b"] - carry + bond["duration"] * change)
        else:
            out["rate_against_yield"] = invested * (rate - funds["r_b"])
        out["cash"] = a["cash"] * rate
        out["split"] = -invested * a["equity"] * (funds["r_d"] - funds["r_b"])
        out["dollar"] = -invested * a["equity"] * (funds["r_e"] - funds["r_d"])
    elif key == "first_ranked":
        a, c = state["reference_a"].shift(1).reindex(r.index), state[key].shift(1).reindex(r.index)
        inv_a = a["equity"] * funds["r_e"] + (1 - a["equity"]) * funds["r_b"]
        tilt = (1 - c["cash"]) * (c["equity"] - a["equity"])
        out["cash"] = (a["cash"] - c["cash"]) * inv_a
        out["split"] = tilt * (funds["r_d"] - funds["r_b"])
        out["dollar"] = tilt * (funds["r_e"] - funds["r_d"])
        weight = (1 - c["cash"]) * c["equity"]
        _fund_part(out, key, weight, r["_first_ranked_fund"] - funds["r_e"], funds, ctx)
    elif key in ONE_FUND:
        a = state["reference_a"].shift(1).reindex(r.index)
        share = ctx[key]["share"]
        inv_a = a["equity"] * funds["r_e"] + (1 - a["equity"]) * funds["r_b"]
        tilt = share - a["equity"]
        out["cash"] = a["cash"] * inv_a
        out["split"] = tilt * (funds["r_d"] - funds["r_b"])
        out["dollar"] = tilt * (funds["r_e"] - funds["r_d"])
        held = share * funds["r_e"] + (1 - share) * funds["r_b"]
        _fund_part(out, key, pd.Series(1.0, index=r.index), r[key] - held, funds, ctx, share)
        if ctx[key].get("bonds_na"):
            out[list(BOND_EFFECTS)] = float("nan")
    elif key == "market_portfolio":
        a = state["reference_a"].shift(1).reindex(r.index)
        own = ctx[key]
        weight = own["weights"].shift(1).reindex(r.index)  # each class's weight at the previous close
        share = weight[list(EQUITY_LIKE)].sum(axis=1)
        inv_a = a["equity"] * funds["r_e"] + (1 - a["equity"]) * funds["r_b"]
        tilt = share - a["equity"]
        out["cash"] = a["cash"] * inv_a
        out["split"] = tilt * (funds["r_d"] - funds["r_b"])
        out["dollar"] = tilt * (funds["r_e"] - funds["r_d"])
        # Each class against the held fund of its kind: the equity-like classes against the equity fund, the bond
        # classes against the bond fund. A dollar fund's conversion to euro goes to the dollar row, less the equity
        # fund's for an equity-like class, whose conversion the split's dollar row already carries.
        held_gap = funds["r_e"] - funds["r_d"]
        for sleeve in MARKET_SLEEVES:
            equity_like = sleeve in EQUITY_LIKE
            gap = weight[sleeve] * (own["r_eur"][sleeve].reindex(r.index) - (funds["r_e"] if equity_like else funds["r_b"]))
            conversion = pd.Series(0.0, index=r.index)
            if own["r_usd"] is not None and sleeve in own["r_usd"] and sleeve != "equities":
                own_gap = (own["r_eur"][sleeve] - own["r_usd"][sleeve]).reindex(r.index)
                conversion = weight[sleeve] * (own_gap - (held_gap if equity_like else 0.0))
            out["dollar"] += conversion
            out["equity_classes" if equity_like else "bond_classes"] += gap - conversion
    # Every effect but implementation starts on the first day on which reference portfolio A held its funds at the
    # previous close. On the first purchase day the comparators and reference portfolio A buy at that day's net asset
    # values, so their returns are zero and the portfolio's difference is implementation alone. A comparator whose
    # series starts later is passed only the days after its base day.
    idle = state["reference_a"].shift(1).reindex(r.index)["cash"] >= 1 - 1e-12
    if idle.any():
        for column in EFFECTS:
            if column != "implementation" and out[column].notna().any():
                out.loc[idle, column] = 0.0
    return out


def _fund_part(out: pd.DataFrame, key: str, weight: pd.Series, gap: pd.Series, funds: pd.DataFrame, ctx: dict,
               share: float = 1.0) -> None:  # fmt: skip
    """Split weight times the fund's return gap into regions, the dollar's part and the rest within each region.

    For a fund in place of the held equity fund, gap is the return of the fund minus the held fund's. For a fund in
    place of the whole portfolio, gap is its return minus that of the two funds held at its equity share, and share
    scales the regions of its equity part."""
    own = ctx[key]
    if ctx.get("region_returns") is not None and own.get("regions") is not None:
        regions = ctx["region_returns"].reindex(gap.index).fillna(0.0)
        weights = by_day(own["regions"], gap.index, regions.columns) - by_day(ctx["held_regions"], gap.index, regions.columns)
        out["regions"] = weight * share * (regions * weights).sum(axis=1)
    dollar = pd.Series(0.0, index=gap.index)
    if own.get("r_usd") is not None:
        dollar = weight * share * ((own["r_eur"] - own["r_usd"]).reindex(gap.index) - (funds["r_e"] - funds["r_d"]))
        out["dollar"] += dollar
    out["within_regions"] = weight * gap - out["regions"] - dollar


def by_day(snapshots: pd.DataFrame, days: pd.DatetimeIndex, regions) -> pd.DataFrame:
    """Region weights on each day: the latest snapshot taken on or before the day, and the first snapshot for the
    days before it. snapshots has one row per snapshot date and one column per region."""
    frame = snapshots.reindex(columns=list(regions)).fillna(0.0).sort_index()
    out = frame.reindex(frame.index.union(days)).ffill().bfill().reindex(days)
    return out.fillna(0.0)


def one_fund(ledger: Ledger, unit_value: pd.Series, days: pd.DatetimeIndex, end, base_day=None,
             base_value: float = None) -> pd.Series:  # fmt: skip
    """Daily values in euro of the contributions bought into one fund at its net asset value and held, on days.

    From the first purchase, the starting amount buys on the day of the first purchase and each top-up on the first
    valuation day on or after its date, as for the S&P 500 alternative. From a later base day, base_value buys at
    that day's close, and only the contributions dated after it follow."""
    if base_day is None:
        return references.sp500_alternative(ledger, unit_value.reindex(days), end)["value"].reindex(days).dropna()
    start = pd.Timestamp(base_day)
    later = days[days > start]
    flows = _flows_after(ledger, days, start)
    units = float(base_value) / unit_value.loc[start]
    values = {start: float(base_value)}
    for day in later:
        units += flows.get(day, 0.0) / unit_value.loc[day]
        values[day] = units * unit_value.loc[day]
    return pd.Series(values, dtype=float)


def _flows_after(ledger: Ledger, days: pd.DatetimeIndex, base_day) -> pd.Series:
    """Top-ups dated after base_day, each on the first valuation day on or after its date."""
    later = days[days > pd.Timestamp(base_day)]
    flows = pd.Series(0.0, index=later)
    for c in ledger.contributions.iloc[1:].itertuples():
        day = pd.Timestamp(c.moment.date())
        if day > pd.Timestamp(base_day) and len(later[later >= day]):
            flows[later[later >= day][0]] += c.amount_eur
    return flows


def market_weights(path=None) -> tuple:
    """The global market portfolio's weights (method/market_portfolio_weights.csv): the dataset's eight asset classes
    summed by the class fund that holds each, in MARKET_SLEEVES' order and scaled to sum to one, and the date they
    describe. The table holds one version of the dataset. A later version moves the comparator on the first cycle
    day after its publication, carried from its own date, and until that move is written the build stops."""
    table = pd.read_csv(path or config.METHOD_DIR / "market_portfolio_weights.csv")
    if table["version"].nunique() != 1:
        raise ValueError("method/market_portfolio_weights.csv holds more than one version of the weights, and the "
                         "move to a later version is not written")
    weights = table.groupby("held_in")["weight"].sum().reindex(list(MARKET_SLEEVES))
    if weights.isna().any():
        raise ValueError("method/market_portfolio_weights.csv: an asset class fund holds no weight")
    return weights / weights.sum(), pd.Timestamp(table["as_of"].iloc[0])


def carried_weights(weights: pd.Series, unit_values: pd.DataFrame, since, until) -> pd.Series:
    """Weights carried from since to until by each class fund's return in euro: each weight times its fund's value
    on until over its value on since, scaled to sum to one. A fund's value on a day is its last net asset value on or
    before it, and every fund must have one on or before since."""
    level = unit_values.reindex(columns=list(weights.index)).sort_index().ffill()
    before = level.loc[:pd.Timestamp(since)]
    if not len(before) or before.iloc[-1].isna().any():
        raise ValueError(f"a class fund has no net asset value on or before {pd.Timestamp(since):%Y-%m-%d}")
    grown = weights * level.loc[:pd.Timestamp(until)].iloc[-1] / before.iloc[-1]
    return grown / grown.sum()


def market_portfolio(ledger: Ledger, unit_values: pd.DataFrame, weights: pd.Series, days: pd.DatetimeIndex,
                     moves: tuple = ()) -> tuple:  # fmt: skip
    """Daily values in euro of the contributions held in the asset classes' funds as the market holds them, on days
    from the first purchase.

    The starting amount buys the weights at the net asset values of the first day. The weights then move with the
    funds' prices, with no rebalancing, and each top-up buys every fund in proportion to its value in the comparator on
    the first day on or after its date, so a top-up leaves the weights as they were. moves holds a later weight set as
    (day, weights): on that day the comparator sells and buys to the new set at the day's net asset values. Returns the
    value and each class's weight at each close, and each move's day with its turnover, half the sum of the weight
    changes."""
    names = list(weights.index)
    prices = unit_values.reindex(columns=names).reindex(days).ffill()
    contributions = ledger.contributions
    start = days[0]
    units = weights / weights.sum() * float(contributions.iloc[0]["amount_eur"]) / prices.loc[start]
    flows = [(pd.Timestamp(c.moment.date()), float(c.amount_eur)) for c in contributions.iloc[1:].itertuples()]
    moves = {pd.Timestamp(day): w / w.sum() for day, w in moves}
    rows, turnover, previous = [], [], None
    for day in days:
        price = prices.loc[day]
        paid = sum(a for d, a in flows if (previous is None or d > previous) and d <= day)
        held = units * price
        if paid:
            units = units + paid * (held / held.sum()) / price
            held = units * price
        if day in moves:
            total = held.sum()
            turnover.append((day, 0.5 * float((moves[day] - held / total).abs().sum())))
            units = moves[day] * total / price
            held = units * price
        rows.append({"date": day, "value": float(held.sum()), **(held / held.sum()).to_dict()})
        previous = day
    return pd.DataFrame(rows).set_index("date"), turnover


def region_shares(weights: pd.Series) -> pd.Series:
    """Weights by region scaled to sum to one over the four regions, so that the regions effect is Brinson and
    Fachler's allocation term: the weight differences sum to zero."""
    w = weights.reindex(list(REGION_NAMES)).fillna(0.0)
    return w / w.sum() if w.sum() > 0 else w


# Other names of a country in issuers' holdings files, and the name method/msci_regions.csv gives it.
COUNTRY_NAMES = {"South Korea": "Korea (South)", "Republic Of Korea": "Korea (South)", "Korea": "Korea (South)",
                 "Russia": "Russian Federation", "Czechia": "Czech Republic", "Turkiye": "Turkey"}  # fmt: skip


def by_country(holdings: pd.DataFrame, regions_table: pd.DataFrame) -> pd.Series:
    """A fund's weights by region from its holdings by country, through method/msci_regions.csv. Lines without a
    country (cash) are left out; a country the table does not name stops the build."""
    region_of = dict(zip(regions_table["country"], regions_table["region"]))
    country = holdings["country"].fillna("").astype(str).str.strip().replace(COUNTRY_NAMES)
    region = country.map(region_of)
    unknown = sorted(set(country[region.isna() & (country != "") & (holdings["weight"] != 0)]))
    if unknown:
        raise ValueError(f"method/msci_regions.csv does not name {', '.join(unknown)}")
    mapped = holdings.assign(region=region).dropna(subset=["region"])
    return region_shares(mapped.groupby("region")["weight"].sum())


def mixed_regions(allocation: pd.DataFrame, mapping: pd.DataFrame, held: pd.Series, msci_world: pd.Series) -> tuple:
    """A LifeStrategy fund's equity share and the regions of its equity part, from its allocation to underlying
    funds (method/lifestrategy_underlying.csv): a single-region fund counts in its region, a FTSE All-World fund
    takes the held fund's look-through regions and a FTSE Developed World fund the MSCI World comparator's. An
    underlying fund the table does not name stops the build."""
    weights, equity = pd.Series(0.0, index=list(REGION_NAMES)), 0.0
    for line in allocation.itertuples():
        found = [m for m in mapping.itertuples() if m.name_contains in line.fund]
        if not found:
            raise ValueError(f"method/lifestrategy_underlying.csv does not name {line.fund}")
        rule = found[0]
        if rule.sleeve != "equity":
            continue
        equity += line.share
        source = {"held": held, "msci_world": msci_world}.get(rule.regions_from)
        if source is None:
            weights[rule.regions_from] += line.share
        else:
            weights += line.share * region_shares(source)
    return equity, region_shares(weights)


def keep_snapshots(previous: pd.DataFrame, current: pd.DataFrame, today) -> pd.DataFrame:
    """The region weights kept: for each comparator, the last snapshot of each month that has ended, and the latest.

    Both frames have the columns comparator, snapshot (the date of the weights), region and weight."""
    frames = [f for f in (previous, current) if f is not None and len(f)]
    if not frames:
        return pd.DataFrame(columns=["comparator", "snapshot", "region", "weight"])
    both = pd.concat(frames, ignore_index=True)
    both["snapshot"] = pd.to_datetime(both["snapshot"])
    both = both.drop_duplicates(["comparator", "snapshot", "region"], keep="last")
    month_now = pd.Timestamp(today).to_period("M")
    kept = []
    for key, own in both.groupby("comparator", sort=False):
        dates = sorted(own["snapshot"].unique())
        keep = {dates[-1]}
        for month, group in pd.Series(dates, index=pd.DatetimeIndex(dates)).groupby(pd.DatetimeIndex(dates).to_period("M")):
            if month < month_now:
                keep.add(group.iloc[-1])
        kept.append(own[own["snapshot"].isin(keep)])
    out = pd.concat(kept, ignore_index=True).sort_values(["comparator", "snapshot", "region"])
    return out.reset_index(drop=True)


def _snapshots(table: pd.DataFrame, key: str) -> pd.DataFrame:
    own = table[table["comparator"] == key]
    return own.pivot(index="snapshot", columns="region", values="weight").sort_index()


def _month(index) -> list:
    return [pd.Timestamp(d).strftime("%Y-%m") for d in index]


def simulations(ledger: Ledger, navs: pd.DataFrame, values: pd.DataFrame, table: pd.DataFrame, ref_a: pd.DataFrame,
                ref_b: pd.DataFrame, rate: pd.Series, end, extra: dict = None) -> tuple:  # fmt: skip
    """Each daily comparator's simulation, and the euro value and growth of 100 of the portfolio and of each, on the
    days of the record with its base day first. A comparator whose series starts after the first purchase has its
    base day in windows, and one whose series could not be read has its reason in missing."""
    extra = extra or {}
    days = table.index
    base = days[0]
    start = metrics.start_amount(ledger)
    sims = {"reference_a": ref_a, "reference_b": ref_b}
    for key, _, equity in SPLITS:
        sims[key] = references.simulate(ledger, navs, end, "rules", split_target(equity), split_band(equity))
    first = extra.get("first_ranked")
    if first is not None and first.get("eur") is not None:
        sims["first_ranked"] = references.simulate(ledger, _with_equity(navs, first["eur"]), end, "rules")
    sims["savings"] = savings(ledger, rate, days[1:])
    values_eur = {"portfolio": values["value_eur"]}
    growth = {"portfolio": table["growth_portfolio"]}
    for key, sim in sims.items():
        held = sim.reindex(days[1:])["value"]
        values_eur[key] = held
        growth[key] = metrics.growth_index(held, metrics.flows_on_days(ledger, held.index), start, base).reindex(days)
    windows, missing = {}, dict(extra.get("unavailable", {}))
    if first is not None and first.get("eur") is None:
        missing["first_ranked"] = first.get("status", "")
    for key, spec in extra.get("one_fund", {}).items():
        if spec.get("eur") is None:
            missing[key] = spec.get("status", "")
            continue
        unit_value = spec["eur"].reindex(days)
        if spec.get("from") is None:
            held = one_fund(ledger, unit_value, days, end).reindex(days[1:])
            values_eur[key] = held
            growth[key] = metrics.growth_index(held, metrics.flows_on_days(ledger, held.index), start, base).reindex(days)
            continue
        later = days[days >= pd.Timestamp(spec["from"])]
        if len(later) < 2:
            missing[key] = spec.get("status") or f"series from {pd.Timestamp(spec['from']):%Y-%m-%d}"
            continue
        day = later[0]
        base_value = float(values_eur["portfolio"].loc[day])
        held = one_fund(ledger, unit_value, days, end, day, base_value)
        values_eur[key] = held
        growth[key] = metrics.growth_index(held.iloc[1:], _flows_after(ledger, days, day), base_value, day).reindex(days)
        windows[key] = day
    market = extra.get("market_portfolio")
    if market is not None and market.get("eur") is None:
        missing["market_portfolio"] = market.get("status", "")
    elif market is not None:
        # The published weights describe the market at their date: carried to the base day by the class funds'
        # returns, they are the market's weights as the comparator starts.
        market["carried"] = carried_weights(market["weights"], market["eur"], market["as_of"], base)
        market["start_as_of"] = base
        market["held"], market["turnover"] = market_portfolio(ledger, market["eur"], market["carried"], days[1:],
                                                              market.get("moves", ()))  # fmt: skip
        held = market["held"]["value"]
        values_eur["market_portfolio"] = held
        growth["market_portfolio"] = metrics.growth_index(held, metrics.flows_on_days(ledger, held.index), start,
                                                          base).reindex(days)  # fmt: skip
    return sims, values_eur, growth, windows, missing


def _with_equity(navs: pd.DataFrame, equity_eur: pd.Series) -> pd.DataFrame:
    """The net asset values with another equity fund's, in euro, in place of the held one's."""
    out = navs.copy()
    out[E] = equity_eur.reindex(navs.index)
    return out


def _empty_row(key: str, name: str, pane: str, status: str) -> dict:
    row = {"comparator": key, "name": name, "pane": pane or "", "basis": "daily", "first_day": None, "last_day": None,
           "periods": 0, "return_money_weighted": float("nan"), "inside_band": "", "status": status,
           "worst_fall_peak": None, "worst_fall_low": None}  # fmt: skip
    for k in ("return_time_weighted", "volatility", "worst_fall", "correlation", "difference", "tracking_error", "band"):
        row[k] = float("nan")
    return row


def _context(extra: dict, days: pd.DatetimeIndex, sims: dict, navs: pd.DataFrame) -> dict:
    """The second stage's inputs to the daily effects: regional returns and weights, each one-fund comparator's
    equity share and returns in euro and in dollars, the first-ranked fund's, and the bond curve."""
    ctx = {}
    levels = extra.get("region_levels")
    if levels is not None and len(levels):
        on_days = levels.reindex(levels.index.union(days)).ffill().reindex(days)
        ctx["region_returns"] = (on_days / on_days.shift(1) - 1).iloc[1:].reindex(columns=list(REGION_NAMES))
    table = extra.get("regions")
    if table is not None and len(table):
        ctx["held_regions"] = _snapshots(table, "held")
    for key, spec in [*extra.get("one_fund", {}).items(), ("first_ranked", extra.get("first_ranked"))]:
        if spec is None or spec.get("eur") is None:
            continue
        eur = spec["eur"].reindex(days)
        own = {"share": spec.get("share", 1.0), "bonds_na": spec.get("bonds_na", False),
               "r_eur": (eur / eur.shift(1) - 1).iloc[1:], "r_usd": None,
               "regions": _snapshots(table, key) if table is not None and key in set(table["comparator"]) else None}  # fmt: skip
        if spec.get("usd") is not None:
            usd = spec["usd"].reindex(spec["usd"].index.union(days)).ffill().reindex(days)
            own["r_usd"] = (usd / usd.shift(1) - 1).iloc[1:]
        ctx[key] = own
    market = extra.get("market_portfolio")
    if market is not None and market.get("held") is not None:
        eur = market["eur"].reindex(columns=list(MARKET_SLEEVES))
        eur = eur.reindex(eur.index.union(days)).ffill().reindex(days)
        usd = market.get("usd")
        if usd is not None:
            usd = usd.reindex(usd.index.union(days)).ffill().reindex(days)
        ctx["market_portfolio"] = {"weights": market["held"].reindex(columns=list(MARKET_SLEEVES)),
                                   "r_eur": (eur / eur.shift(1) - 1).iloc[1:],
                                   "r_usd": None if usd is None else (usd / usd.shift(1) - 1).iloc[1:]}  # fmt: skip
    bond = extra.get("bond")
    if bond is not None:
        spot = bond["spot"].reindex(bond["spot"].index.union(days)).ffill().reindex(days)
        years = pd.Series(days, index=days).diff().dt.days / 365
        ctx["bond"] = {"carry": (spot.shift(1) * years).iloc[1:], "change": spot.diff().iloc[1:],
                       "duration": float(bond["duration"])}  # fmt: skip
    return ctx


def build(ledger: Ledger, navs: pd.DataFrame, values: pd.DataFrame, table: pd.DataFrame, ref_a: pd.DataFrame,
          ref_b: pd.DataFrame, blend: pd.Series, rate: pd.Series, end, extra: dict = None) -> dict:  # fmt: skip
    """The public tables of the comparisons: one row per comparator, the growth of 100 of each by day, the effects by
    comparator and month with the record's totals, and the region weights kept.

    extra holds the second stage's inputs: one_fund, each fund's net asset values in euro on the record's days (and
    in US dollars for a dollar fund), its equity share, whether its bond rows are left empty and the day its series
    starts; first_ranked, the first-ranked equity fund's; regions, the region weights kept; region_levels, the four
    regional indices' daily levels in euro; and bond, the ECB spot rate at the bond fund's duration, with the
    duration. A comparator without its inputs is left out."""
    extra = extra or {}
    days = table.index  # the base day first, then every valuation day of the record
    base = days[0]
    sims, values_eur, growth, windows, missing = simulations(ledger, navs, values, table, ref_a, ref_b, rate, end, extra)
    last = days[-1]
    portfolio_mw = {}

    rows = []
    for key, name, pane in ROWS:
        if key == "benchmark":
            rows.append(_benchmark_row(name, pane, blend, growth["portfolio"]))
            continue
        if key in missing:
            rows.append(_empty_row(key, name, pane, missing[key]))
            continue
        if key not in growth:
            continue
        mine, own = growth[key], growth["portfolio"]
        first_day = days[1] if len(days) > 1 else base
        if key in windows:
            first_day = windows[key]
            mine, own = mine.loc[first_day:], own.loc[first_day:] / own.loc[first_day] * 100
        row = {"comparator": key, "name": name, "pane": pane or "", "basis": "daily", "first_day": first_day, "last_day": last,
               **measures(mine, own, minimum=0 if key == "portfolio" else MIN_DAILY_RETURNS), "status": ""}  # fmt: skip
        if key in windows:
            start_value = float(values_eur["portfolio"].loc[first_day])
            row["return_money_weighted"] = metrics.money_weighted_between(ledger, first_day, start_value, last,
                                                                          float(values_eur[key].loc[last]))  # fmt: skip
            mw = metrics.money_weighted_between(ledger, first_day, start_value, last, float(values_eur["portfolio"].loc[last]))
            portfolio_mw[key] = (mw, float(own.iloc[-1] / 100 - 1))
        else:
            row["return_money_weighted"] = metrics.money_weighted_cumulative(ledger, last, float(values_eur[key].loc[last]))
        if key == "portfolio":
            for k in ("correlation", "difference", "tracking_error", "band"):
                row[k] = float("nan")
            row["inside_band"] = ""
        if key == "savings":
            row["correlation"] = float("nan")  # the rate barely moves from day to day
        if key in extra.get("one_fund", {}):
            row["equity_share"] = float(extra["one_fund"][key].get("share", 1.0))
        rows.append(row)
    summary = pd.DataFrame(rows)

    r = pd.DataFrame({k: _returns(g) for k, g in growth.items()})
    funds = _fund_returns(navs, days)
    state = {k: _state(sims[k], navs, days) for k in ["reference_a", *(s[0] for s in SPLITS)]}
    if "first_ranked" in sims:
        navs_f = _with_equity(navs, extra["first_ranked"]["eur"])
        state["first_ranked"] = _state(sims["first_ranked"], navs_f, days)
        r["_first_ranked_fund"] = _fund_returns(navs_f, days)["r_e"]
    ctx = _context(extra, days, sims, navs)
    effects = []
    by_key = summary.set_index("comparator")
    for key in by_key.index:
        if key in ("portfolio", "benchmark") or pd.isna(by_key.loc[key, "difference"]):
            continue
        window = r.index if key not in windows else r.index[r.index > windows[key]]
        daily = daily_effects(key, r.loc[window], funds.loc[window], state, ctx)
        monthly = daily.groupby(_month(daily.index)).sum(min_count=1)
        for month, line in monthly.iterrows():
            effects += [{"comparator": key, "period": month, "effect": e, "value": float(line[e])} for e in EFFECTS]
        total = monthly.sum(min_count=1)
        row = by_key.loc[key]
        total["compounding"] = row["difference"] - total.drop("compounding").sum()
        timing_own = by_key.loc["portfolio", "return_money_weighted"] - by_key.loc["portfolio", "return_time_weighted"]
        if key in portfolio_mw:
            timing_own = portfolio_mw[key][0] - portfolio_mw[key][1]
        total["timing"] = row["return_money_weighted"] - row["return_time_weighted"] - timing_own
        effects += [{"comparator": key, "period": "record", "effect": e, "value": float(total[e])} for e in EFFECTS]
    effects += _benchmark_effects(by_key.loc["benchmark"], blend, r, funds, state, sims["reference_b"], navs, days)

    daily_table = pd.DataFrame({f"growth_{k}": g for k, g in growth.items()})
    daily_table.index.name = "date"
    regions = extra.get("regions")
    return {"summary": summary, "daily": daily_table.reset_index(),
            "effects": pd.DataFrame(effects, columns=["comparator", "period", "effect", "value"]),
            "regions": regions if regions is not None else pd.DataFrame(columns=["comparator", "snapshot", "region", "weight"]),
            "market": market_table(extra.get("market_portfolio"))}  # fmt: skip


def market_table(market: dict) -> pd.DataFrame:
    """The global market portfolio's weights by asset class fund: as published at their date, carried to the
    comparator's start, and at the last close, with the day of each."""
    columns = ["sleeve", "published", "published_as_of", "start", "start_as_of", "current", "current_as_of"]
    if not market or market.get("held") is None:
        return pd.DataFrame(columns=columns)
    held = market["held"]
    current = held.iloc[-1].reindex(list(MARKET_SLEEVES))
    out = pd.DataFrame({"sleeve": list(MARKET_SLEEVES), "published": market["weights"].reindex(list(MARKET_SLEEVES)).values,
                        "published_as_of": pd.Timestamp(market["as_of"]), "start": market["carried"].reindex(list(MARKET_SLEEVES)).values,
                        "start_as_of": pd.Timestamp(market["start_as_of"]), "current": current.values,
                        "current_as_of": held.index[-1]})  # fmt: skip
    return out[columns]


def market_fees(funds: pd.DataFrame, weights: pd.Series) -> list:
    """The global market portfolio's costs: each class fund's TER a year, from its factsheet as the ranking records
    it, and the TERs weighted by the published weights, with a class held in its parent's fund weighted with the
    parent. funds has one row per class: fund, ter_per_cent and factsheet_date."""
    rows = []
    for _, fund in funds.drop_duplicates("isin").iterrows():
        rows.append(("market_portfolio", f"TER of {fund['fund']}", float(fund["ter_per_cent"]) * 100, None, "a year",
                     "The fund's factsheet, method/selection_market_portfolio.csv", fund["factsheet_date"]))  # fmt: skip
    ter = funds["ter_per_cent"].astype(float).reindex(weights.index)
    rows.append(("market_portfolio", "TERs weighted by the published weights", float((ter * weights).sum()) * 100, None,
                 "a year", "method/market_portfolio_weights.csv", pd.to_datetime(funds["factsheet_date"]).max()))  # fmt: skip
    return rows


def fees(ownership: pd.DataFrame, implementation: pd.Series, charges: dict, bank: dict, market: list = ()) -> pd.DataFrame:
    """The costs beside the comparisons, in basis points: the portfolio's ongoing costs a year at its weights and its
    implementation cost since the first purchase, the LifeStrategy funds' ongoing charges, the published costs of the
    bank's managed profile on the first 100,000 euro invested and the market portfolio's funds' TERs, each with its
    source and date."""
    rows = []
    if len(ownership):
        weighted = ownership[ownership["sleeve"] == "portfolio"].iloc[0]
        dated = pd.to_datetime(ownership["document_date"], errors="coerce").max()
        rows.append(("portfolio", "Ongoing costs of the two ETFs at the portfolio's weights", weighted["ongoing_costs"] * 1e4, None,
                     "a year", "The ETFs' key information documents", dated))  # fmt: skip
    if len(implementation.dropna()):
        last = implementation.dropna()
        rows.append(("portfolio", "Implementation cost, cumulative", float(last.iloc[-1]), None, "since the first purchase",
                     "The record, outputs/implementation_cost.csv", last.index[-1]))  # fmt: skip
    for key, (charge, dated) in charges.items():
        rows.append((key, "Ongoing charges figure", charge * 1e4, None, "a year", "Vanguard's monthly factsheet", dated))
    if bank:
        basic, managed = 4 * bank["basic_a_quarter"] * 1e4, 4 * bank["management_a_quarter"] * 1e4
        low, high = bank["funds_low"] * 1e4, bank["funds_high"] * 1e4
        source, per = "Rabobank's cost overview of Rabo Beheerd Beleggen Basis", "a year, on the first 100,000 euro invested"
        rows += [("bank_offensief", "Basic service, four quarters", basic, None, per, source, bank["dated"]),
                 ("bank_offensief", "Portfolio management, four quarters", managed, None, per, source, bank["dated"]),
                 ("bank_offensief", "The funds' own costs", low, high, "a year", source, bank["dated"]),
                 ("bank_offensief", "All in", basic + managed + low, basic + managed + high, per, source, bank["dated"])]  # fmt: skip
    rows += list(market)
    out = pd.DataFrame(rows, columns=["comparator", "item", "bps_low", "bps_high", "per", "source", "dated"])
    out["bps_high"] = out["bps_high"].fillna(out["bps_low"]).astype(float)
    out["dated"] = pd.to_datetime(out["dated"])
    return out


def _benchmark_row(name: str, pane: str, blend: pd.Series, portfolio: pd.Series) -> dict:
    """The benchmark against the portfolio at the month ends where both exist. Its return needs two month ends,
    and its statistics, difference and band need six."""
    blend = blend.dropna()
    row = {"comparator": "benchmark", "name": name, "pane": pane, "basis": "monthly",
           "first_day": blend.index[0] if len(blend) else None, "last_day": blend.index[-1] if len(blend) else None,
           "periods": max(len(blend) - 1, 0), "return_money_weighted": float("nan"), "inside_band": "", "status": ""}  # fmt: skip
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
