"""Every figure the dashboard displays is formatted here, once, from full precision.

Percentages and weights to one decimal, basis points to whole numbers, loadings to two decimals, years
to one decimal; dates as YYYY-MM-DD, and YYYY-MM for months. The page shows these strings in labels,
tooltips, tiles and tables alike, so the same figure never appears with two roundings.
"""

from __future__ import annotations

import math

import pandas as pd

MINUS = "−"  # the typographic minus sign


def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or (x is not None and pd.isna(x))


def pct(x, signed: bool = False) -> str:
    """A share or a return in per cent, one decimal: 0.7012 -> "70.1%"; signed adds a plus to gains."""
    if _missing(x):
        return "n/a"
    value = round(float(x) * 100, 1) + 0.0
    text = f"{value:+.1f}%" if signed and value != 0 else f"{value:.1f}%"
    return text.replace("-", MINUS)


def points(x, signed: bool = True) -> str:
    """Percentage points, one decimal: drift and differences of weights."""
    if _missing(x):
        return "n/a"
    value = round(float(x), 1)
    if value == 0:
        value = 0.0
    return (f"{value:+.1f}" if signed else f"{value:.1f}").replace("-", MINUS) + " points"


def bps(x, signed: bool = True) -> str:
    """Basis points, whole numbers."""
    if _missing(x):
        return "n/a"
    value = int(round(float(x)))
    if value == 0:
        return "0 bp"
    return (f"{value:+d}" if signed else f"{value:d}").replace("-", MINUS) + " bp"


def loading(x) -> str:
    if _missing(x):
        return "n/a"
    value = round(float(x), 2)
    if value == 0:
        value = 0.0
    return f"{value:.2f}".replace("-", MINUS)


def index(x) -> str:
    """A growth index or a value in units of the starting amount, one decimal."""
    if _missing(x):
        return "n/a"
    return f"{round(float(x), 1):.1f}"


def years(x) -> str:
    if _missing(x):
        return "n/a"
    return f"{round(float(x), 1):.1f} years"


def day(x) -> str:
    return "n/a" if _missing(x) else pd.Timestamp(x).strftime("%Y-%m-%d")


def day_words(x) -> str:
    """A date in prose, as in 8 October 2026. Stamps, tables and axes keep the ISO form of day()."""
    return "n/a" if _missing(x) else f"{pd.Timestamp(x).day} {pd.Timestamp(x).strftime('%B %Y')}"


def month(x) -> str:
    return "n/a" if _missing(x) else pd.Timestamp(x).strftime("%Y-%m")


def count(x) -> str:
    return "n/a" if _missing(x) else str(int(x))


def rounded(x, decimals: int = 6):
    """The position of a mark. Labels and tooltips carry the formatted strings above."""
    return None if _missing(x) else round(float(x), max(decimals, 6))
