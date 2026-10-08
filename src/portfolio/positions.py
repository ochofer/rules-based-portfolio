"""Step 1 of the pipeline: the ledger to units and cash at the end of each day.

Units change on the date of the order, ahead of settlement, so the weights follow the
exposure the order creates. Cash is every contribution minus every purchase plus every sale, fees
included; it is part of the portfolio until rule 4 invests it.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from . import config
from .ledger import Ledger, LedgerError


def build(ledger: Ledger, end: date) -> pd.DataFrame:
    """One row per calendar day from the first contribution to end: units of each sleeve, cash in euro and
    contributions to date in euro."""
    contributions = ledger.contributions
    first = contributions["moment"].min().date()
    if end < first:
        raise LedgerError(f"{end} is before the first contribution, on {first}")
    days = pd.date_range(first, end, freq="D")
    frame = pd.DataFrame(0.0, index=days, columns=[*config.SLEEVES, "cash_eur", "contributions_eur"])
    for c in contributions.itertuples():
        frame.loc[pd.Timestamp(c.moment.date()) :, ["cash_eur", "contributions_eur"]] += c.amount_eur
    for o in ledger.orders.itertuples():
        day = pd.Timestamp(o.moment.date())
        if day > days[-1]:
            continue
        frame.loc[day:, o.sleeve] += o.units
        frame.loc[day:, "cash_eur"] += o.cash_change
    frame.index.name = "date"
    return frame


def orders_in_month(ledger: Ledger, year: int, month: int) -> int:
    """Orders placed in a calendar month, the count rule 6 limits to five."""
    moments = ledger.orders["moment"]
    return int(((moments.dt.year == year) & (moments.dt.month == month)).sum())
