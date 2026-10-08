"""Step 2 of the pipeline: units, cash and net asset values to values and weights.

The portfolio is valued at the ETFs' net asset values in euro, the price series the reference portfolios
use, so that the difference between them measures the cost of implementation alone. A day is valued when
at least one fund publishes a net asset value, and the other fund's last value is carried forward.
"""

from __future__ import annotations

import pandas as pd

from . import config


def build(positions: pd.DataFrame, navs_eur: pd.DataFrame) -> pd.DataFrame:
    """Values in euro of each sleeve, of cash and of the portfolio, and the weights, on each valuation day
    from the first day with positions."""
    days = navs_eur.index[(navs_eur.index >= positions.index[0]) & (navs_eur.index <= positions.index[-1])]
    held = positions.reindex(days, method="ffill")
    out = pd.DataFrame(index=days)
    for sleeve in config.SLEEVES:
        out[f"nav_{sleeve}_eur"] = navs_eur.loc[days, sleeve]
        out[f"value_{sleeve}_eur"] = held[sleeve] * navs_eur.loc[days, sleeve]
    out["cash_eur"] = held["cash_eur"]
    out["value_eur"] = out[[f"value_{s}_eur" for s in config.SLEEVES]].sum(axis=1) + out["cash_eur"]
    for sleeve in config.SLEEVES:
        out[f"weight_{sleeve}"] = out[f"value_{sleeve}_eur"] / out["value_eur"]
    out["weight_cash"] = out["cash_eur"] / out["value_eur"]
    out["contributions_eur"] = held["contributions_eur"]
    out.index.name = "date"
    return out


def at(
    positions: pd.DataFrame, navs_eur: pd.DataFrame, day: pd.Timestamp, nav_day: pd.Timestamp = None
) -> dict:
    """Values in euro of the units and cash held at the end of day, at the last net asset values published
    on or before nav_day (by default day itself)."""
    navs = navs_eur.loc[: (day if nav_day is None else nav_day)].iloc[-1]
    held = positions.loc[:day].iloc[-1]
    values = {s: float(held[s] * navs[s]) for s in config.SLEEVES}
    values["cash"] = float(held["cash_eur"])
    values["nav_date"] = navs.name
    values["navs"] = {s: float(navs[s]) for s in config.SLEEVES}
    return values
