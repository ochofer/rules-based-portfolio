"""The look-through's risk, estimated on index returns: the components, their correlations and their
shares of the portfolio's estimated variance, the efficient frontier of the components, the estimated
volatility and its record, and the portfolio's estimated return over five historical episodes.

The components are the four equity regions of the look-through (method/msci_regions.csv) and the bond
sleeve's maturity ladder in three maturity groups. A region's monthly return in euro is MSCI's published
month-end level of its regional index, net total return, from the public tool that gives the index blend.
MSCI publishes no series for Europe and the Middle East together, so that region is priced by MSCI Europe,
and Israel goes with it. A maturity group's monthly return is a zero-coupon euro area government bond at
the group's midpoint, priced from the ECB's curve for all euro area government bonds, as the allocation
test prices its seven-year bond. The series start in January 2001 (MSCI) and October 2004 (ECB).

The window is the last 120 complete months, rolled at each month end, and the 120 months before it serve
the earlier frontier only. The weights are the latest look-through weights. Cash, the uninvested part of the
portfolio and the cash lines of both ETFs, is a component with no return, so the weights sum to one.

The frontier is solved exactly: every set of components that may hold a positive weight is tried, the
equality-constrained problem on that set is a linear system, and the one solution that satisfies the
conditions of optimality (no negative weight, and no excluded component that would lower the variance)
is the answer. The result is the same on every machine, and no optimiser is needed.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, prices

WINDOW_MONTHS = 120
FRONTIER_POINTS = 25
MSCI_MONTHLY = (
    "https://app2.msci.com/products/service/index/indexmaster/getLevelDataForGraph?currency_symbol=EUR"
    "&index_variant=NETR&start_date={start}&end_date={end}&data_frequency=END_OF_MONTH&index_codes={code}"
)
REGIONS = (
    ("North America", "990200", "MSCI North America"),
    ("Europe and Middle East", "990500", "MSCI Europe"),
    ("Pacific", "990800", "MSCI Pacific"),
    ("Emerging markets", "891800", "MSCI Emerging Markets"),
)
ECB_SPOT = (
    "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_{maturity}"
    "?format=csvdata&startPeriod=2004-09-01"
)
# name, lower and upper bound of the ladder in years, the midpoint priced, and the ECB series of that maturity.
# The bond index holds no bond with less than a year to run, so the short group starts at one year.
MATURITY_GROUPS = (
    ("Bonds, short", 1, 5, 3.0, "3Y"),
    ("Bonds, medium", 5, 10, 7.5, "7Y6M"),
    ("Bonds, long", 10, None, 20.0, "20Y"),
)
COMPONENTS = tuple(r[0] for r in REGIONS) + tuple(g[0] for g in MATURITY_GROUPS)
SLEEVE_OF = {**{r[0]: config.EQUITY for r in REGIONS}, **{g[0]: config.BONDS for g in MATURITY_GROUPS}}
CASH = "Cash"
CASH_LINES = ("Cash and derivatives", "Not in the index")
# Each episode runs from the end of its first month to the end of its last.
EPISODES = (
    ("2000 to 2003", "2000-08", "2003-03"),
    ("2007 to 2009", "2007-10", "2009-02"),
    ("Euro crisis of 2011", "2011-04", "2011-09"),
    ("February to March 2020", "2020-01", "2020-03"),
    ("2022", "2021-12", "2022-12"),
)
CALIBRATION_FROM = 12  # months of the record before the forecast's calibration is shown


# Sources -------------------------------------------------------------------------------------------


def parse_msci_monthly(path: Path) -> pd.Series:
    """Month-end levels of one MSCI index, by month."""
    levels = json.loads(Path(path).read_text())["indexes"]["INDEX_LEVELS"]
    series = pd.Series(
        {pd.Period(str(x["calc_date"])[:6], "M"): float(x["level_eod"]) for x in levels}, dtype=float
    )
    return series.sort_index()


def fetch_regions(refresh: bool, today, cache_dir: Path = config.CACHE_DIR) -> pd.DataFrame:
    """Month-end levels of the four regional indices, one column each."""
    end = pd.Timestamp(today).strftime("%Y%m%d")
    columns, days = {}, []
    for name, code, _ in REGIONS:
        url = MSCI_MONTHLY.format(start="19981231", end=end, code=code)
        path = prices.fetch(f"msci/region_{code}_netr_eur_monthly.json", url, refresh, cache_dir=cache_dir)
        columns[name] = parse_msci_monthly(path)
        last = max(str(x["calc_date"]) for x in json.loads(Path(path).read_text())["indexes"]["INDEX_LEVELS"])
        days.append(pd.Timestamp(last))
    frame = pd.DataFrame(columns)
    frame.attrs["last_day"] = min(days)
    return frame


def fetch_curve(refresh: bool, cache_dir: Path = config.CACHE_DIR) -> pd.DataFrame:
    """Month-end spot rates of the ECB curve at the three midpoints, as fractions."""
    columns, days = {}, []
    for name, _, _, _, maturity in MATURITY_GROUPS:
        url = ECB_SPOT.format(maturity=maturity)
        path = prices.fetch(f"ecb/curve_spot_{maturity}.csv", url, refresh, cache_dir=cache_dir)
        frame = pd.read_csv(path, usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
        daily = pd.Series(frame["OBS_VALUE"].astype(float).values / 100, index=pd.to_datetime(frame["TIME_PERIOD"]))
        columns[name] = daily.groupby(daily.index.to_period("M")).last()
        days.append(daily.index.max())
    frame = pd.DataFrame(columns).sort_index()
    frame.attrs["last_day"] = min(days)
    return frame


def group_returns(spot: pd.DataFrame) -> pd.DataFrame:
    """Monthly returns of a zero-coupon bond held for a month at each group's midpoint maturity."""
    out = {}
    for name, _, _, maturity, _ in MATURITY_GROUPS:
        y = spot[name]
        out[name] = np.exp(-y * (maturity - 1 / 12)) / np.exp(-y.shift(1) * maturity) - 1
    return pd.DataFrame(out).iloc[1:]


def component_returns(levels: pd.DataFrame, spot: pd.DataFrame) -> pd.DataFrame:
    regions = levels.pct_change().iloc[1:]
    return pd.concat([regions, group_returns(spot)], axis=1)[list(COMPONENTS)]


def allocation_test_returns() -> pd.DataFrame:
    """The allocation test's two monthly series, equity and bonds, from mandate/allocation_check.py."""
    spec = importlib.util.spec_from_file_location("allocation_check", config.ROOT / "mandate" / "allocation_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    returns, _ = module.monthly_returns()
    return returns


def parse_kid_text(text: str) -> dict:
    """The ongoing costs and the date of a key information document, from its text."""
    flat = re.sub(r"\s+", " ", text)
    fees = re.search(r"Management fees and (?:other )?.{0,120}?(\d+\.\d+)% of the value of your investment", flat)
    transaction = re.search(
        r"(\d+\.\d+)% of the value of your investment (?:per year|p\.a\.)\. This is an estimate of the costs", flat
    )
    dated = re.search(r"is dated (\d{1,2} [A-Z][a-z]+ \d{4}|\d{2}/\d{2}/\d{4})", flat)
    if not (fees and transaction and dated):
        raise ValueError("the key information document has no ongoing costs or no date in the expected form")
    day = pd.to_datetime(dated.group(1), dayfirst=True)
    return {
        "management_fees": float(fees.group(1)) / 100,
        "transaction_costs": float(transaction.group(1)) / 100,
        "document_date": day.normalize(),
    }


KIDS = {
    config.EQUITY: (
        "ishares/IE00B6R52259_kid_en.pdf",
        "https://www.blackrock.com/nl/particuliere-beleggers/literature/kiid/"
        "eu-priips-ishares-msci-acwi-ucits-etf-usd-acc-ie00b6r52259-en.pdf",
    ),
    config.BONDS: ("vanguard/IE00BH04GL39_kid_en.pdf", "https://fund-docs.vanguard.com/ie00bh04gl39_priipskid_en.pdf"),
}


def fetch_kids(refresh: bool, cache_dir: Path = config.CACHE_DIR) -> dict:
    import pdfplumber

    out = {}
    for sleeve, (name, url) in KIDS.items():
        path = prices.fetch(name, url, refresh, cache_dir=cache_dir)
        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        out[sleeve] = parse_kid_text(text)
    return out


# Weights -------------------------------------------------------------------------------------------


def _group_of(label: str) -> str:
    """The maturity group of a rung of the ladder, by its upper bound in years ("Over 15 years" has none)."""
    numbers = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", label)]
    upper = numbers[-1] if numbers and not label.lower().startswith("over") else None
    for name, low, high, _, _ in MATURITY_GROUPS:
        if high is None or (upper is not None and upper <= high):
            return name
    raise ValueError(label)


def component_weights(regions: pd.DataFrame, maturities: pd.DataFrame, cash_weight: float) -> pd.Series:
    """The look-through weights of the components, in shares of the portfolio, with cash last."""
    weights = pd.Series(0.0, index=list(COMPONENTS) + [CASH])
    for _, r in regions.iterrows():
        key = CASH if r["region"] in CASH_LINES else r["region"]
        if key not in weights.index:
            raise ValueError(f"the look-through region {r['region']!r} is not a component")
        weights[key] += r["share_of_portfolio"]
    for _, r in maturities.iterrows():
        key = CASH if r["maturity"] in CASH_LINES else _group_of(r["maturity"])
        weights[key] += r["share_of_portfolio"]
    weights[CASH] += cash_weight
    return weights


# Estimates -----------------------------------------------------------------------------------------


def window(returns: pd.DataFrame, end: pd.Period, months: int = WINDOW_MONTHS) -> pd.DataFrame:
    frame = returns.loc[:end].dropna()
    frame = frame.iloc[-months:]
    if len(frame) < months or frame.index[-1] != end:
        raise ValueError(f"the components have {len(frame)} complete months to {end}, and the window needs {months}")
    return frame


def last_complete_month(returns: pd.DataFrame, today) -> pd.Period:
    complete = returns.dropna()
    complete = complete[complete.index < pd.Period(pd.Timestamp(today), "M")]
    return complete.index[-1]


def moments(frame: pd.DataFrame) -> tuple:
    """Annualised mean returns and covariance of the window's monthly returns."""
    return frame.mean() * 12, frame.cov() * 12


def with_cash(cov: pd.DataFrame) -> pd.DataFrame:
    names = list(cov.index) + [CASH]
    return cov.reindex(index=names, columns=names).fillna(0.0)


def volatility(weights: pd.Series, cov: pd.DataFrame) -> float:
    full = with_cash(cov)
    w = weights.reindex(full.index).fillna(0.0).values
    return float(np.sqrt(w @ full.values @ w))


def risk_contributions(weights: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Each component's share of the portfolio's estimated variance: its weight times its covariance with the
    portfolio, over the portfolio's variance."""
    full = with_cash(cov)
    w = weights.reindex(full.index).fillna(0.0).values
    marginal = full.values @ w
    return pd.Series(w * marginal / (w @ marginal), index=full.index)


def _kkt(cov: np.ndarray, constraints: np.ndarray, targets: np.ndarray, support: tuple):
    n, m = len(support), constraints.shape[0]
    s = list(support)
    system = np.zeros((n + m, n + m))
    system[:n, :n] = 2 * cov[np.ix_(s, s)]
    system[:n, n:] = constraints[:, s].T
    system[n:, :n] = constraints[:, s]
    if np.linalg.cond(system) > 1e12:
        return None
    solution = np.linalg.solve(system, np.concatenate([np.zeros(n), targets]))
    weights = np.zeros(cov.shape[0])
    weights[s] = solution[:n]
    return weights, solution[n:]


def solve(cov: np.ndarray, constraints: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """The long-only weights of least variance under constraints @ w = targets, solved exactly."""
    count, best = cov.shape[0], None
    scale = float(np.abs(cov).max())
    for size in range(1, count + 1):
        for support in itertools.combinations(range(count), size):
            found = _kkt(cov, constraints, targets, support)
            if found is None:
                continue
            weights, multipliers = found
            if (weights < -1e-12).any() or np.abs(constraints @ weights - targets).max() > 1e-9:
                continue
            # The multiplier of each excluded component's bound, which must not be negative.
            bound = 2 * cov @ weights + constraints.T @ multipliers
            outside = [j for j in range(count) if j not in support]
            if outside and (bound[outside] < -1e-10 * max(scale, 1e-12)).any():
                continue
            variance = weights @ cov @ weights
            if best is None or variance < best[0] - 1e-15:
                best = (variance, np.clip(weights, 0.0, None))
    if best is None:
        raise ValueError("no long-only portfolio meets the constraints")
    return best[1] / best[1].sum()


def minimum_variance(cov: pd.DataFrame) -> pd.Series:
    w = solve(cov.values, np.ones((1, len(cov))), np.array([1.0]))
    return pd.Series(w, index=cov.index)


def frontier(mean: pd.Series, cov: pd.DataFrame, points: int = FRONTIER_POINTS) -> pd.DataFrame:
    """The long-only, fully invested portfolios of least variance at evenly spaced target returns, from the
    minimum-variance portfolio's return to the highest component mean."""
    start = minimum_variance(cov)
    low, high = float(mean @ start), float(mean.max())
    rows = []
    for k, target in enumerate(np.linspace(low, high, points)):
        if k == 0:
            w = start.values
        else:
            constraints = np.vstack([np.ones(len(mean)), mean.values])
            w = solve(cov.values, constraints, np.array([1.0, target]))
        rows.append({"point": k, "estimated_return": float(mean.values @ w),
                     "estimated_volatility": float(np.sqrt(w @ cov.values @ w)),
                     **{f"weight_{_slug(c)}": float(x) for c, x in zip(mean.index, w)}})  # fmt: skip
    return pd.DataFrame(rows)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z]+", "_", name.lower()).strip("_")


# Episodes and calibration --------------------------------------------------------------------------


def stress(components: pd.DataFrame, test: pd.DataFrame, weights: pd.Series) -> pd.DataFrame:
    """The portfolio's estimated return over each episode, held at today's weights through it, with the equity
    and bond contributions apart. A sleeve whose components do not cover the episode takes the allocation
    test's series for that sleeve."""
    rows = []
    for name, first, last in EPISODES:
        start, end = pd.Period(first, "M"), pd.Period(last, "M")
        months = pd.period_range(start + 1, end, freq="M")
        contribution, basis = {}, []
        for sleeve in config.SLEEVES:
            names = [c for c in COMPONENTS if SLEEVE_OF[c] == sleeve]
            covered = components.reindex(months)[names].notna().all().all()
            if covered:
                growth = (1 + components.loc[months, names]).prod() - 1
                contribution[sleeve] = float((weights[names] * growth).sum())
            else:
                column = "equity" if sleeve == config.EQUITY else "bonds"
                growth = float((1 + test.reindex(months)[column]).prod() - 1)
                contribution[sleeve] = float(weights[names].sum() * growth)
                basis.append(sleeve)
        rows.append({"episode": name, "from_month_end": str(start), "to_month_end": str(end),
                     "equity_contribution": contribution[config.EQUITY], "bond_contribution": contribution[config.BONDS],
                     "total": contribution[config.EQUITY] + contribution[config.BONDS],
                     "series": _series_text(basis)})  # fmt: skip
    return pd.DataFrame(rows)


def _series_text(from_test: list) -> str:
    if len(from_test) == len(config.SLEEVES):
        return "the allocation test's two series"
    if not from_test:
        return "the components"
    return f"the components, and the allocation test's series for the {'equity' if from_test[0] == config.EQUITY else 'bond'} sleeve"


def record_estimate(history: pd.DataFrame, month_end: pd.Period, value: float, start: pd.Period, first_purchase) -> pd.DataFrame:
    """The record of the estimated volatility at each month end, kept as it was first written: a month end is
    added once, at the first build after it, and never rewritten."""
    columns = ["month_end", "estimated_volatility", "window_start", "window_end"]
    history = history[columns] if len(history) else pd.DataFrame(columns=columns)
    if month_end >= pd.Period(pd.Timestamp(first_purchase), "M") and str(month_end) not in set(history["month_end"].astype(str)):
        row = {"month_end": str(month_end), "estimated_volatility": value, "window_start": str(start), "window_end": str(month_end)}
        history = pd.concat([history, pd.DataFrame([row])], ignore_index=True) if len(history) else pd.DataFrame([row])
    history = history.reset_index(drop=True)
    history["estimated_volatility"] = history["estimated_volatility"].astype(float)
    for column in ("month_end", "window_start", "window_end"):
        history[column] = history[column].astype(str)
    return history


def calibration(history: pd.DataFrame, monthly: pd.DataFrame) -> tuple:
    """The forecast's calibration, as the B-P study measures it: the standard deviation of each month's return
    divided by the forecast for that month (the volatility estimated at the month end before, over the square
    root of twelve). 1 for a calibrated forecast, above 1 for a forecast that was too low. Returns the value and
    the number of months, or NaN while fewer than twelve months have a forecast."""
    if not len(history) or not len(monthly):
        return float("nan"), 0
    forecast = {pd.Period(m, "M") + 1: v / np.sqrt(12) for m, v in zip(history["month_end"], history["estimated_volatility"])}
    done = monthly[monthly["complete"] == "yes"]
    ratios = [r / forecast[pd.Period(m, "M")] for m, r in zip(done["month"], done["return_month"]) if pd.Period(m, "M") in forecast]
    if len(ratios) < CALIBRATION_FROM:
        return float("nan"), len(ratios)
    return float(np.std(ratios, ddof=1)), len(ratios)
