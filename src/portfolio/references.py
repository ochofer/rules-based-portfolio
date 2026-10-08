"""The reference portfolios and the index blend.

Reference portfolio A receives the same contributions on the same days as the portfolio and applies the
same rules on the same cycle days: the orders come from the rules engine on the net asset values of the
last trading day before the cycle day, as for the portfolio, and execute at the net asset value of the
cycle day, in fractional units and without costs. Reference portfolio B receives the same contributions
and goes back to 70/30 on every cycle day. Both invest the starting amount at 70/30 at the net asset
value of the day of the first purchase.

The index blend is 70 per cent MSCI ACWI net total return in euro and 30 per cent the Bloomberg
Euro-Aggregate Treasury index, rebalanced at each month end. Bloomberg publishes no public series, so the
bond part is the benchmark's one-month return in Vanguard's monthly factsheet, and the blend is monthly.
It starts at the first month end after the first purchase, at the portfolio's level on that day.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from . import config, prices, rules_engine, trading_days
from .ledger import Ledger

E, B = config.EQUITY, config.BONDS

MSCI_LEVELS = (
    "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph?currency_symbol=EUR"
    "&index_variant=NETR&start_date={start}&end_date={end}&data_frequency=DAILY&index_codes=892400"
)


def _execution_day(navs_eur: pd.DataFrame, day: pd.Timestamp):
    """The first day on or after day with a net asset value, or None if none is published yet."""
    later = navs_eur.index[navs_eur.index >= day]
    return later[0] if len(later) else None


def _cycle_days(first: date, last: date) -> list:
    """Cycle days of rule 3 after the first purchase and up to last."""
    out, year, month = [], first.year, first.month
    while (year, month) <= (last.year, last.month):
        day = trading_days.cycle_day(year, month)
        if first < day <= last:
            out.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def simulate(ledger: Ledger, navs_eur: pd.DataFrame, end: date, mode: str) -> pd.DataFrame:
    """Daily values in euro of a reference portfolio: mode "rules" for A, "calendar" for B.

    Returns one row per valuation day from the first purchase: units of each sleeve, cash and value.
    """
    if mode not in ("rules", "calendar"):
        raise ValueError(mode)
    contributions = ledger.contributions
    start = contributions.iloc[0]
    start_day = _execution_day(navs_eur, pd.Timestamp(start["moment"].date()))
    if start_day is None:
        return pd.DataFrame(columns=[E, B, "cash", "value"])
    days = navs_eur.index[(navs_eur.index >= start_day) & (navs_eur.index <= pd.Timestamp(end))]
    unit_value = navs_eur.loc[days, [E, B]]
    units = {E: 0.0, B: 0.0}
    cash = 0.0
    flows = [(pd.Timestamp(c.moment.date()), c.amount_eur) for c in contributions.iloc[1:].itertuples()]
    cycles = []
    for c in _cycle_days(start["moment"].date(), end):
        execution = _execution_day(navs_eur, pd.Timestamp(c))
        if execution is not None and execution <= pd.Timestamp(end):
            cycles.append((pd.Timestamp(c), execution))
    rows, previous = [], None
    for day in days:
        if previous is None:
            amount = float(start["amount_eur"])
            for sleeve in (E, B):
                units[sleeve] += amount * config.TARGET[sleeve] / unit_value.loc[day, sleeve]
        cash += sum(a for d, a in flows if (previous is None or d > previous) and d <= day)
        for cycle, execution in cycles:
            if execution != day:
                continue
            last_close = pd.Timestamp(trading_days.previous_trading_day(cycle.date()))
            before = navs_eur.loc[:last_close, [E, B]].iloc[-1]
            values = {s: units[s] * before[s] for s in (E, B)}
            if mode == "rules":
                plan = rules_engine.plan(values[E], values[B], cash)
                signed = {o.sleeve: (o.amount_eur if o.side == "buy" else -o.amount_eur) for o in plan.orders}
            else:
                total = values[E] + values[B] + cash
                signed = {s: config.TARGET[s] * total - values[s] for s in (E, B)}
            for sleeve, amount in signed.items():
                units[sleeve] += amount / unit_value.loc[day, sleeve]
                cash -= amount
        value = units[E] * unit_value.loc[day, E] + units[B] * unit_value.loc[day, B] + cash
        rows.append({"date": day, E: units[E], B: units[B], "cash": cash, "value": value})
        previous = day
    return pd.DataFrame(rows).set_index("date")


def fetch_msci(refresh: bool, cache_dir: Path, start: date, end: date) -> Path:
    url = MSCI_LEVELS.format(start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    return prices.fetch("msci/acwi_netr_eur.json", url, refresh, cache_dir=cache_dir)


def parse_msci(path: Path) -> pd.Series:
    """MSCI ACWI net total return in euro, end-of-day levels by date."""
    answer = json.loads(Path(path).read_text())
    if answer.get("ISO_currency_symbol") != "EUR" or answer.get("index_variant_type") != "NETR":
        raise ValueError(f"{path}: not the net total return index in euro")
    levels = answer["indexes"]["INDEX_LEVELS"]
    values = {pd.Timestamp(str(x["calc_date"])): float(x["level_eod"]) for x in levels}
    return pd.Series(values, name="msci_acwi_netr_eur").sort_index()


def index_blend(growth: pd.Series, msci: pd.Series, bond_month: pd.Series, today: date) -> pd.Series:
    """The index blend at each completed month end, starting at the portfolio's level on the first.

    growth: the portfolio's growth of 100 by valuation day. msci: index levels by day. bond_month: the
    bond benchmark's return by month, indexed by monthly periods. The blend stops at the first month for
    which either return is not yet published.
    """
    empty = pd.Series(dtype=float, name="index_blend")
    if growth.empty or msci.empty:
        return empty
    current = pd.Timestamp(today).to_period("M")
    month_of = growth.index.to_period("M")
    complete = sorted(m for m in set(month_of) if m < current)
    if not complete:
        return empty
    last_day = {m: growth.index[month_of == m].max() for m in complete}
    level = msci.groupby(msci.index.to_period("M")).last()
    out = {complete[0]: float(growth.loc[last_day[complete[0]]])}
    for previous, month in zip(complete, complete[1:]):
        if month not in level.index or previous not in level.index or month not in bond_month.index:
            break
        equity = level[month] / level[previous] - 1
        blend = config.TARGET[E] * equity + config.TARGET[B] * float(bond_month[month])
        out[month] = out[previous] * (1 + blend)
    return pd.Series({last_day[m]: v for m, v in out.items()}, name="index_blend", dtype=float)
