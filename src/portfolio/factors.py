"""Factor exposures of the equity ETF, charts 18 and 19.

The ETF's weekly return in US dollars, from its net asset values, minus the weekly risk-free rate, is
regressed by ordinary least squares on Kenneth French's developed-market factors: Mkt-RF, SMB, HML, RMW,
CMA (Developed 5 Factors, daily) and WML (Developed Momentum Factor, daily). Fund and factors are in US
dollars, so no exchange rate enters the regression. Weeks run from Wednesday close to Wednesday close,
using the last net asset value on or before each Wednesday, and the factors and the risk-free rate are
compounded from the daily files over the days of the same week. The window is the 36 calendar months to
the last month end both sources cover.

Standard errors are Newey-West with a Bartlett kernel and lag floor(4 (T/100)^(2/9)). The check is the
same regression on daily returns with each factor's return of the same and of the previous day
(Dimson's correction): the loading is the sum of the two coefficients. The fund's valuation point and
the construction of French's daily files do not coincide day by day, so loadings on same-day daily
factors are biased, and weekly returns are the primary estimate.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, prices

FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{name}_CSV.zip"
FILES = {"five": "Developed_5_Factors_Daily", "momentum": "Developed_Mom_Factor_Daily"}


def fetch(refresh: bool, cache_dir: Path = config.CACHE_DIR) -> dict:
    return {
        key: prices.fetch(f"french/{name}_CSV.zip", FRENCH.format(name=name), refresh, cache_dir=cache_dir)
        for key, name in FILES.items()
    }


def parse_french(path: Path) -> tuple:
    """The daily table of a French zip file, in decimals, and the database line of its header."""
    with zipfile.ZipFile(path) as z:
        text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    vintage = next((line.strip() for line in lines if "database" in line), "")
    header = next(i for i, line in enumerate(lines) if line.replace(" ", "").startswith(","))
    body = []
    for line in lines[header + 1 :]:
        first = line.split(",")[0].strip()
        if not (len(first) == 8 and first.isdigit()):
            break
        body.append(line)
    columns = ["date"] + [c.strip() for c in lines[header].split(",")[1:]]
    frame = pd.read_csv(io.StringIO("\n".join(body)), header=None, names=columns)
    frame["date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d")
    frame = frame.set_index("date").astype(float)
    if (frame <= -99.99).any().any():
        raise ValueError(f"{path}: missing values (-99.99)")
    return frame / 100, vintage


def daily_factors(paths: dict) -> tuple:
    five, vintage = parse_french(paths["five"])
    momentum, _ = parse_french(paths["momentum"])
    frame = five.join(momentum, how="inner")
    return frame[list(config.FACTORS) + ["RF"]], vintage


def weekly(nav_usd: pd.Series, factors: pd.DataFrame) -> pd.DataFrame:
    """Weekly fund excess returns and compounded factor returns, Wednesday to Wednesday."""
    first, last = max(nav_usd.index.min(), factors.index.min()), min(nav_usd.index.max(), factors.index.max())
    wednesdays = pd.date_range(first, last, freq="W-WED")
    nav_dates = [nav_usd.index[nav_usd.index <= w].max() for w in wednesdays]
    rows = []
    for (w0, d0), (w1, d1) in zip(zip(wednesdays, nav_dates), zip(wednesdays[1:], nav_dates[1:])):
        days = factors.loc[(factors.index > w0) & (factors.index <= w1)]
        if days.empty or d0 == d1:
            continue
        compounded = (1 + days).prod() - 1
        fund = nav_usd[d1] / nav_usd[d0] - 1
        row = {"week_end": w1, "fund_excess": fund - compounded["RF"]}
        row.update({f: compounded[f] for f in config.FACTORS})
        rows.append(row)
    return pd.DataFrame(rows).set_index("week_end")


def newey_west_lag(t: int) -> int:
    return int(np.floor(4 * (t / 100) ** (2 / 9)))


def ols_newey_west(y: np.ndarray, x: np.ndarray, lag: int) -> dict:
    """OLS with an intercept; Newey-West (Bartlett) covariance without a small-sample factor."""
    t = len(y)
    X = np.column_stack([np.ones(t), x])
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    e = y - X @ beta
    u = X * e[:, None]
    s = u.T @ u
    for lag_j in range(1, lag + 1):
        w = 1 - lag_j / (lag + 1)
        g = u[lag_j:].T @ u[:-lag_j]
        s += w * (g + g.T)
    cov = xtx_inv @ s @ xtx_inv
    r2 = 1 - (e @ e) / np.sum((y - y.mean()) ** 2)
    return {"beta": beta, "cov": cov, "r2": r2, "t": t, "lag": lag}


def window(index: pd.DatetimeIndex, end_month: pd.Period, months: int) -> pd.DatetimeIndex:
    end = end_month.to_timestamp(how="end").normalize()
    start = (end_month - months + 1).to_timestamp(how="start")
    return index[(index >= start) & (index <= end)]


def loadings(nav_usd: pd.Series, factors: pd.DataFrame, end_month: pd.Period) -> pd.DataFrame:
    """Chart 18: weekly loadings over 36 months, and the daily Dimson check over the same months."""
    weeks = weekly(nav_usd, factors)
    w = weeks.loc[window(weeks.index, end_month, config.FACTOR_WINDOW_MONTHS)]
    fit = ols_newey_west(w["fund_excess"].values, w[list(config.FACTORS)].values, newey_west_lag(len(w)))
    rows = []
    for k, factor in enumerate(config.FACTORS, start=1):
        rows.append(_row("weekly", factor, fit["beta"][k], np.sqrt(fit["cov"][k, k]), fit, w.index))
    # The daily check with one lag of each factor.
    fund = nav_usd.pct_change().dropna()
    joined = factors.join(fund.rename("fund"), how="inner")
    joined["fund_excess"] = joined["fund"] - joined["RF"]
    lagged = joined[list(config.FACTORS)].shift(1).add_suffix("_lag")
    data = pd.concat([joined, lagged], axis=1).dropna()
    data = data.loc[window(data.index, end_month, config.FACTOR_WINDOW_MONTHS)]
    names = list(config.FACTORS) + [f"{f}_lag" for f in config.FACTORS]
    fit_d = ols_newey_west(data["fund_excess"].values, data[names].values, newey_west_lag(len(data)))
    n = len(config.FACTORS)
    for k, factor in enumerate(config.FACTORS, start=1):
        b = fit_d["beta"][k] + fit_d["beta"][k + n]
        v = fit_d["cov"][k, k] + fit_d["cov"][k + n, k + n] + 2 * fit_d["cov"][k, k + n]
        rows.append(_row("daily, same and previous day", factor, b, np.sqrt(v), fit_d, data.index))
    return pd.DataFrame(rows)


def _row(method, factor, b, se, fit, index) -> dict:
    return {
        "method": method,
        "factor": factor,
        "factor_name": config.FACTOR_NAME[factor],
        "loading": b,
        "standard_error": se,
        "lower": b - 2 * se,
        "upper": b + 2 * se,
        "intercept": fit["beta"][0],
        "r_squared": fit["r2"],
        "observations": fit["t"],
        "newey_west_lag": fit["lag"],
        "window_start": index.min(),
        "window_end": index.max(),
    }


def rolling(nav_usd: pd.Series, factors: pd.DataFrame, end_month: pd.Period) -> pd.DataFrame:
    """Chart 19: the weekly regression in a 36-month window stepped at each month end."""
    weeks = weekly(nav_usd, factors)
    first = weeks.index.min().to_period("M") + config.FACTOR_WINDOW_MONTHS
    rows = []
    month = first
    while month <= end_month:
        w = weeks.loc[window(weeks.index, month, config.FACTOR_WINDOW_MONTHS)]
        fit = ols_newey_west(w["fund_excess"].values, w[list(config.FACTORS)].values, newey_west_lag(len(w)))
        for k, factor in enumerate(config.FACTORS, start=1):
            se = np.sqrt(fit["cov"][k, k])
            rows.append(
                {
                    "window_end": month.to_timestamp(how="end").normalize(),
                    "factor": factor,
                    "factor_name": config.FACTOR_NAME[factor],
                    "loading": fit["beta"][k],
                    "standard_error": se,
                    "observations": fit["t"],
                }
            )
        month += 1
    return pd.DataFrame(rows)


def last_full_month(factors: pd.DataFrame, nav_usd: pd.Series) -> pd.Period:
    """The last month both the factor files and the fund's values cover to its end."""
    last = min(factors.index.max(), nav_usd.index.max())
    month = last.to_period("M")
    month_end_day = factors.index[factors.index.to_period("M") == month].max()
    complete = last >= month_end_day and (last + pd.offsets.BDay(1)).to_period("M") != month
    return month if complete else month - 1
