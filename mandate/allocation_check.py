"""Derive the portfolio's split from the mandate's risk limit.

The mandate sets a risk limit of a worst fall of about one third, which the
test reads as at most 35 per cent. The worst fall is the largest fall in value
from a previous peak to a later low. This script measures, on monthly euro
returns from February 1999 to December 2025, the worst fall of every split from
40/60 to 100/0 in steps of 5 points, each rebalanced by the band of rule 5, and
selects the largest equity target weight whose worst fall stays within the
limit.

In November 2026, after the first cycle day, a second run was added to answer
a question readers ask: the same test with the US stock market in place of the
global equity series, with the same bonds, the same band rule, the same splits
and the same months. The split was set on the global series alone, and the US
run chooses nothing: its table reads no in the column chosen on every row. The
same run gives the cumulative return in US dollars, dividends included, of the
US stock market and of the developed markets outside the United States over
January 2000 to December 2009 and over January 2010 to December 2024, the
figures behind one sentence of the dashboard's Method view.

Data, downloaded at run time and cached in cache/ (never committed):
  - Kenneth French's developed-market and emerging-market factor files (the
    market return is Mkt-RF plus RF, in US dollars).
  - Kenneth French's US research factors, monthly (the US market return is
    Mkt-RF plus RF, in US dollars), for the US run only.
  - Kenneth French's developed-ex-US factor file, monthly (the market return of
    the developed markets outside the United States is Mkt-RF plus RF, in US
    dollars), for the two periods of the US run only.
  - The European Central Bank's euro reference rate against the US dollar,
    daily (dataset EXR).
  - The European Central Bank's euro area yield curve for all government
    bonds, seven-year spot rate, daily from September 2004 (dataset YC).
  - The European Central Bank's euro area ten-year government bond yield,
    monthly averages (dataset IRS), used before the yield curve starts.

Usage:   python3 mandate/allocation_check.py
Output:  mandate/allocation_check_results.md, the same text on screen, and the table of every split in
         mandate/allocation_check_results.csv. The US run writes its table of every split to
         mandate/allocation_check_us_results.csv, the two series' returns over the two periods to
         mandate/allocation_check_us_periods.csv, and its figures to the screen. The history of the comparisons
         writes the split and the dollar effects of 70/30 against 100/0, 60/40 and the US stock market at 70/30 to
         mandate/allocation_check_history.csv (each calendar year, the two periods and the whole test) and
         mandate/allocation_check_history_windows.csv (rolling windows of ten calendar years).
Requires Python 3.9 or later, pandas and numpy.
"""
import io
import math
import os
import re
import time
import urllib.request
import zipfile
from datetime import date

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
OUT = os.path.join(ROOT, "mandate", "allocation_check_results.md")
OUT_CSV = os.path.join(ROOT, "mandate", "allocation_check_results.csv")
OUT_US_CSV = os.path.join(ROOT, "mandate", "allocation_check_us_results.csv")
OUT_US_PERIODS = os.path.join(ROOT, "mandate", "allocation_check_us_periods.csv")
OUT_HISTORY = os.path.join(ROOT, "mandate", "allocation_check_history.csv")
OUT_HISTORY_WINDOWS = os.path.join(ROOT, "mandate", "allocation_check_history_windows.csv")
US_PERIODS = (("2000-01", "2009-12"), ("2010-01", "2024-12"))  # the decade from 2000 and the fifteen years after it

# The mandate's numbers.
RISK_LIMIT = 0.35        # worst fall allowed in the test: one third, rounded up to the next 5 points
BAND_HALF_WIDTH = 0.05   # rule 5: the equity weight may move 5 points either side of its target
EQUITY_GRID = [w / 100 for w in range(40, 101, 5)]
EMERGING_SHARE = 0.10    # emerging markets' approximate share of a global index of developed and emerging markets
BOND_MATURITY = 7.0      # in years, close to the average duration of a euro government bond index
FIRST_MONTH, LAST_MONTH = "1999-01", "2025-12"
# The history of the comparisons: 70/30 against three comparators on the test's own series, by calendar year, over
# the two periods of US_PERIODS and over rolling windows of ten calendar years.
HISTORY_TARGET = 0.70
HISTORY_COMPARATORS = (("100/0", "global", 1.00), ("60/40", "global", 0.60), ("the US stock market at 70/30", "united_states", 0.70))
WINDOW_YEARS = 10

# Two expectations for the US run, written on 5 November 2026 before it ran and kept as written. The run
# reports whether each is met, and nothing is tuned to meet them.
# E8: the worst fall of the US series at 70/30 exceeds 35 per cent, since the dollar fell against the euro from
#     2001 to 2003 while the US market fell further than the global series.
# E9: the largest US split whose worst fall is within 35 per cent is 65/35 or lower.
E8_US_FALL_AT_70_ABOVE = 0.35
E9_US_LARGEST_SPLIT_AT_MOST = 0.65

SOURCES = {
    "developed": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_3_Factors_CSV.zip",
    "emerging": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Emerging_5_Factors_CSV.zip",
    "us_market": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
    "developed_ex_us": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_ex_US_3_Factors_CSV.zip",
    "ecb_usd_per_eur": "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata",
    "ecb_10y": "https://data-api.ecb.europa.eu/service/data/IRS/M.U2.L.L40.CI.0000.EUR.N.Z?format=csvdata",
    "ecb_7y": "https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_C.SV_C_YM.SR_7Y?format=csvdata",
}

# Calendar-year returns in euro, in per cent, of two funds that track the same
# markets, as their issuers publish them. The comparison shows how closely the
# constructed returns follow returns an investor in euro received.
FUND_CHECK = {
    "equity": ("Amundi MSCI All Country World UCITS ETF EUR Acc (LU1829220216)",
               "an MSCI ACWI fund that reports its returns in euro",
               {2021: 27.33, 2022: -13.15, 2023: 17.91, 2024: 25.19, 2025: 7.68}),
    "bonds": ("Vanguard EUR Eurozone Government Bond UCITS ETF (EUR) Accumulating (IE00BH04GL39)",
              "the bond ETF the portfolio holds",
              {2021: -3.54, 2022: -18.45, 2023: 7.15, 2024: 1.77, 2025: 0.57}),
}
FACTSHEET_DATE = "31 August 2026"


def fetch(name, attempts=3):
    """Return the bytes of a source file, downloading it once into cache/.

    A download is tried three times, 10 seconds apart, and written to a
    temporary file first, so that an interrupted download never leaves a
    partial file in the cache.
    """
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name + (".zip" if SOURCES[name].endswith(".zip") else ".csv"))
    if not os.path.exists(path):
        request = urllib.request.Request(SOURCES[name], headers={"User-Agent": "allocation-check/1.0", "Accept": "*/*"})
        for attempt in range(1, attempts + 1):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read()
                break
            except OSError as error:
                if attempt == attempts:
                    raise SystemExit(f"Could not download {SOURCES[name]} ({error}). Download it in a browser, "
                                     f"save it as {path}, and run the script again.")
                time.sleep(10)
        with open(path + ".part", "wb") as f:
            f.write(data)
        os.replace(path + ".part", path)
    with open(path, "rb") as f:
        return f.read()


def french_market(name):
    """Monthly market return in US dollars (Mkt-RF plus RF, as a fraction) and the file's header line."""
    archive = zipfile.ZipFile(io.BytesIO(fetch(name)))
    lines = archive.read(archive.namelist()[0]).decode("latin1").splitlines()
    header = next(line for line in lines if "Mkt-RF" in line).split(",")
    rows = []
    for line in lines:
        m = re.match(r"^\s*(\d{6})\s*,(.*)$", line)
        if m:
            rows.append([m.group(1)] + [float(x) for x in m.group(2).split(",")])
        elif rows and not line.strip():
            break  # the monthly table ends at the first blank line, and annual tables follow
    table = pd.DataFrame(rows, columns=["month"] + [h.strip() for h in header[1:]])
    table.index = pd.PeriodIndex(table.pop("month"), freq="M")
    return (table["Mkt-RF"] + table["RF"]) / 100, lines[0].strip()


def ecb_series(name):
    """An ECB data portal series as a pandas Series indexed by its period, missing values dropped."""
    frame = pd.read_csv(io.BytesIO(fetch(name)), usecols=["TIME_PERIOD", "OBS_VALUE"])
    return frame.dropna().set_index("TIME_PERIOD")["OBS_VALUE"]


def month_end(series):
    """The last observation in each calendar month."""
    return series.groupby(series.index.to_period("M")).last()


def ecb_seven_year():
    """Month-end seven-year spot rate of the ECB all-government curve, as a fraction."""
    daily = ecb_series("ecb_7y")
    daily.index = pd.to_datetime(daily.index)
    return month_end(daily) / 100


def usd_per_eur_month_end():
    """The ECB euro reference rate against the US dollar at each month end."""
    daily_rate = ecb_series("ecb_usd_per_eur")
    daily_rate.index = pd.to_datetime(daily_rate.index)
    return month_end(daily_rate)


def monthly_returns():
    """Monthly euro returns of the equity and bond sleeves, February 1999 to December 2025."""
    developed, header_dev = french_market("developed")
    emerging, header_em = french_market("emerging")
    usd_per_eur = usd_per_eur_month_end()
    # An investor in euro gains when the dollar rises against the euro, so the
    # dollar return is multiplied by last month's rate over this month's rate.
    currency = usd_per_eur.shift(1) / usd_per_eur
    equity = (1 + (1 - EMERGING_SHARE) * developed + EMERGING_SHARE * emerging) * currency - 1

    # Bonds from October 2004: a seven-year zero-coupon bond priced from the
    # month-end spot rate (continuous compounding), held for one month, so that
    # its maturity shortens by one month while it is held.
    spot = ecb_seven_year()
    ecb_bond = np.exp(-spot * (BOND_MATURITY - 1 / 12)) / np.exp(-spot.shift(1) * BOND_MATURITY) - 1
    # Before October 2004: the ten-year yield, a monthly average, priced as a
    # bond with a duration of seven years: one month of yield, minus duration
    # times the change in yield, plus the second-order term of the price change.
    ten_year = ecb_series("ecb_10y")
    ten_year.index = pd.PeriodIndex(ten_year.index, freq="M")
    ten_year = ten_year / 100
    change = ten_year.diff()
    early_bond = ten_year.shift(1) / 12 - BOND_MATURITY * change + 0.5 * (BOND_MATURITY ** 2 + BOND_MATURITY) * change ** 2
    bonds = ecb_bond.combine_first(early_bond)

    returns = pd.DataFrame({"equity": equity, "bonds": bonds}).loc[FIRST_MONTH:LAST_MONTH].dropna()
    vintages = {
        "Kenneth French, developed markets": f'file header "{header_dev}"',
        "Kenneth French, emerging markets": f'file header "{header_em}"',
        "ECB euro reference rate against the US dollar": "last observation " + str(usd_per_eur.index[-1]),
        "ECB seven-year spot rate": "last observation " + str(spot.index[-1]),
        "ECB ten-year government bond yield": "last observation " + str(ten_year.index[-1]),
    }
    return returns, vintages


def us_returns(returns):
    """The test's returns with the US stock market in place of the global equity series: French's US market
    return in US dollars, converted to euro with the same rate as the global series, beside the same bonds, over
    the same months. Returns the frame and the US file's header line."""
    us, header = french_market("us_market")
    usd_per_eur = usd_per_eur_month_end()
    currency = usd_per_eur.shift(1) / usd_per_eur
    equity = ((1 + us) * currency - 1).reindex(returns.index)
    frame = pd.DataFrame({"equity": equity, "bonds": returns["bonds"]})
    if frame.isna().any().any():
        raise SystemExit("The US series has a missing month inside the test's months.")
    return frame, header


def band_path(returns, equity_target):
    """Value of a portfolio started at 1 and rebalanced by the band of rule 5, checked at each month end."""
    equity, bonds = equity_target, 1 - equity_target
    values = []
    for r_equity, r_bonds in zip(returns["equity"].values, returns["bonds"].values):
        equity *= 1 + r_equity
        bonds *= 1 + r_bonds
        total = equity + bonds
        if abs(equity / total - equity_target) > BAND_HALF_WIDTH:
            equity, bonds = equity_target * total, (1 - equity_target) * total
        values.append(total)
    return pd.Series(values, index=returns.index)


def worst_fall(values, start=None, end=None):
    """Largest fall from a previous peak to a later low, with its peak and low months."""
    fall = values / values.cummax() - 1
    window = fall.loc[start:end]
    low = window.idxmin()
    peak = values.loc[:low].idxmax()
    return -window.min(), peak, low


def sleeve_return(returns, sleeve, peak, low):
    """Compound return of one sleeve over the months after the peak, up to and including the low."""
    return (1 + returns[sleeve].loc[peak + 1:low]).prod() - 1


def calendar_years(monthly):
    """Calendar-year returns compounded from monthly returns."""
    return (1 + monthly).groupby(monthly.index.year).prod() - 1


def signed(x):
    """A difference in percentage points with its sign, and 0.00 when it rounds to zero."""
    text = f"{x:+.2f}"
    return "0.00" if text in ("+0.00", "-0.00") else text


def split_rows(returns):
    """Every split on the grid under the band rule: growth per year, volatility, the worst fall with its peak and
    low months, and the fall in each named period."""
    years = len(returns) / 12
    rows = []
    for w in EQUITY_GRID:
        values = band_path(returns, w)
        growth = values.iloc[-1] ** (1 / years) - 1
        volatility = values.pct_change().std() * math.sqrt(12)
        fall, peak, low = worst_fall(values)
        fall_2000, _, _ = worst_fall(values, "1999-01", "2004-12")
        fall_2008, _, _ = worst_fall(values, "2007-01", "2010-12")
        fall_2022, _, _ = worst_fall(values, "2021-12", "2022-12")
        rows.append((w, growth, volatility, fall, peak, low, fall_2000, fall_2008, fall_2022))
    return rows


def largest_within(rows):
    """The row of the largest equity target weight whose worst fall is within the limit, or None."""
    within = [r for r in rows if r[3] <= RISK_LIMIT]
    return max(within, key=lambda r: r[0]) if within else None


def results_table(rows, chosen):
    """The table of every split, as written to the results files. chosen is the row held, or None."""
    table = pd.DataFrame(rows, columns=["equity_weight", "growth_per_year", "volatility", "worst_fall", "peak", "low",
                                        "fall_1999_2004", "fall_2007_2010", "fall_2022"])
    table.insert(0, "split", [f"{round(w * 100)}/{round((1 - w) * 100)}" for w in table["equity_weight"]])
    table["within_limit"] = ["yes" if f <= RISK_LIMIT else "no" for f in table["worst_fall"]]
    table["chosen"] = ["yes" if chosen and w == chosen[0] else "no" for w in table["equity_weight"]]
    return table


def us_periods():
    """The cumulative return in US dollars, dividends included, of French's US market and of his developed markets
    outside the United States over each period of US_PERIODS, as a fraction. A period with a missing month stops."""
    series = (("US stock market", french_market("us_market")[0]),
              ("Developed markets outside the United States", french_market("developed_ex_us")[0]))
    rows = []
    for first, last in US_PERIODS:
        months = len(pd.period_range(first, last, freq="M"))
        for name, returns in series:
            r = returns.loc[first:last]
            if len(r) != months or (r <= -0.9999).any():
                raise SystemExit(f"{name}: a month is missing between {first} and {last}.")
            rows.append({"series": name, "first_month": first, "last_month": last, "months": months,
                         "cumulative_return_usd": float(np.prod(1 + r.to_numpy()) - 1)})
    return pd.DataFrame(rows)


def band_weights(returns, equity_target):
    """The band path of band_path with the equity weight held at the start of each month, after any rebalancing at
    the month end before it: the value at each month end and that weight."""
    equity, bonds = equity_target, 1 - equity_target
    values, weights = [], []
    for r_equity, r_bonds in zip(returns["equity"].values, returns["bonds"].values):
        weights.append(equity / (equity + bonds))
        equity *= 1 + r_equity
        bonds *= 1 + r_bonds
        total = equity + bonds
        if abs(equity / total - equity_target) > BAND_HALF_WIDTH:
            equity, bonds = equity_target * total, (1 - equity_target) * total
        values.append(total)
    return pd.Series(values, index=returns.index), pd.Series(weights, index=returns.index)


def global_dollar_returns(index):
    """The global equity series in US dollars, before its conversion to euro: French's developed and emerging
    markets at the test's shares."""
    developed, _ = french_market("developed")
    emerging, _ = french_market("emerging")
    return ((1 - EMERGING_SHARE) * developed + EMERGING_SHARE * emerging).reindex(index)


def history_months(returns, us, dollar, us_dollar):
    """Month by month, for each comparator against 70/30 on the global series: both returns and the effects.

    With e the equity weight of 70/30 and e_c the comparator's at the previous month end, r_e and r_d the global
    equity series in euro and in dollars and r_b the bonds: split is (e_c - e)(r_d - r_b) and the dollar
    (e_c - e)(r_e - r_d). For the US stock market at 70/30, the US stock market in dollars is
    e_c (r_us,d - r_d), and its conversion cross term, e_c ((r_us - r_us,d) - (r_e - r_d)), joins the dollar.
    The effects sum to the month's difference exactly."""
    base_values, base_weight = band_weights(returns, HISTORY_TARGET)
    base = base_values / base_values.shift(1, fill_value=1.0) - 1
    frames = {}
    for name, series, target in HISTORY_COMPARATORS:
        own = us if series == "united_states" else returns
        values, weight = band_weights(own, target)
        mine = values / values.shift(1, fill_value=1.0) - 1
        tilt = weight - base_weight
        frame = pd.DataFrame({"comparator": mine, "base": base, "split": tilt * (dollar - returns["bonds"]),
                              "dollar": tilt * (returns["equity"] - dollar), "us_stock_market": 0.0}, index=returns.index)
        if series == "united_states":
            frame["dollar"] += weight * ((us["equity"] - us_dollar) - (returns["equity"] - dollar))
            frame["us_stock_market"] = weight * (us_dollar - dollar)
        gap = frame["comparator"] - frame["base"]
        if (frame[["split", "dollar", "us_stock_market"]].sum(axis=1) - gap).abs().max() > 1e-12:
            raise SystemExit(f"The effects of {name} do not sum to its difference.")
        frame["values"] = values
        frames[name] = frame
    return frames


def _fall_within(values, months):
    """The worst fall of a path within the months, from the level before the first of them: the fall, the peak
    month and the low month."""
    first = values.index.get_loc(months[0])
    start = values.iloc[first - 1] if first > 0 else 1.0
    start_month = months[0] - 1
    path = pd.concat([pd.Series([start], index=[start_month]), values.loc[months]])
    fall = path / path.cummax() - 1
    low = fall.idxmin()
    if fall.min() >= 0:
        return 0.0, "", ""
    return float(-fall.min()), str(path.loc[:low].idxmax()), str(low)


def history_row(name, frame, months, label, kind, tracking_error):
    """One span of one comparator. A calendar year is cumulative, in points; a longer span is per year, in points a
    year: the difference of the two growth rates per year and each effect as its monthly sum over the years. The
    band is two tracking errors (of the whole test) times the square root of the years for a calendar year and
    divided by it for a longer span."""
    part = frame.loc[months]
    years = len(part) / 12
    mine, base = (1 + part["comparator"]).prod(), (1 + part["base"]).prod()
    effects = part[["split", "dollar", "us_stock_market"]].sum()
    if kind == "year":
        difference, unit, band = mine - base, "points", 2 * tracking_error * math.sqrt(years)
    else:
        difference = mine ** (1 / years) - base ** (1 / years)
        effects = effects / years
        unit, band = "points a year", 2 * tracking_error / math.sqrt(years)
    fall, peak, low = _fall_within(frame["values"], months)
    united_states = name == HISTORY_COMPARATORS[2][0]
    return {"comparator": name, "span": label, "kind": kind, "first_month": str(months[0]), "last_month": str(months[-1]),
            "months": len(part), "unit": unit, "difference": difference, "split": effects["split"],
            "dollar": effects["dollar"], "us_stock_market": effects["us_stock_market"] if united_states else float("nan"),
            "compounding": difference - effects.sum(), "volatility": part["comparator"].std() * math.sqrt(12),
            "worst_fall": fall, "worst_fall_peak": peak, "worst_fall_low": low, "tracking_error": tracking_error,
            "band": band, "inside_band": "yes" if abs(difference) <= band else "no"}


def history_tables(frames):
    """The two committed tables of the history: every span of every comparator, ordered by comparator with the
    whole test first, then the two periods, then each calendar year; and the rolling windows of ten calendar
    years, from the first full year."""
    rows, windows = [], []
    for name, frame in frames.items():
        index = frame.index
        tracking_error = (frame["comparator"] - frame["base"]).std() * math.sqrt(12)
        spans = [(f"{index[0]} to {index[-1]}", "whole", index)]
        spans += [(f"{a} to {b}", "period", index[(index >= pd.Period(a, "M")) & (index <= pd.Period(b, "M"))])
                  for a, b in US_PERIODS]
        spans += [(str(y), "year", index[index.year == y]) for y in sorted(set(index.year))]
        rows += [history_row(name, frame, months, label, kind, tracking_error) for label, kind, months in spans]
        full = [y for y in sorted(set(index.year)) if (index.year == y).sum() == 12]
        for first in full[: len(full) - WINDOW_YEARS + 1]:
            months = index[(index.year >= first) & (index.year < first + WINDOW_YEARS)]
            row = history_row(name, frame, months, f"{first} to {first + WINDOW_YEARS - 1}", "window", tracking_error)
            windows.append({"first_year": first, "last_year": first + WINDOW_YEARS - 1, **row})
    columns = ["comparator", "span", "kind", "first_month", "last_month", "months", "unit", "difference", "split",
               "dollar", "us_stock_market", "compounding", "volatility", "worst_fall", "worst_fall_peak", "worst_fall_low",
               "tracking_error", "band", "inside_band"]
    window_columns = ["comparator", "first_year", "last_year", "months", "unit", "difference", "split", "dollar",
                      "us_stock_market", "compounding", "volatility", "worst_fall", "worst_fall_peak", "worst_fall_low",
                      "tracking_error", "band", "inside_band"]
    return pd.DataFrame(rows)[columns], pd.DataFrame(windows)[window_columns]


def csv_text(table):
    """The results table as the text of its file."""
    return table.to_csv(index=False, float_format="%.6f", lineterminator="\n")


def us_summary(rows, header):
    """The US run's figures and the two expectations set before it, for the screen."""
    largest = largest_within(rows)
    at_70 = next(r for r in rows if round(r[0] * 100) == 70)
    split = f"{round(largest[0] * 100)}/{round((1 - largest[0]) * 100)}" if largest else "none"
    e8 = at_70[3] > E8_US_FALL_AT_70_ABOVE
    e9 = largest is None or largest[0] <= E9_US_LARGEST_SPLIT_AT_MOST
    return "\n".join([
        "## The US run",
        "",
        f'Kenneth French, US research factors: file header "{header}".',
        f"Largest split within {RISK_LIMIT * 100:.0f} per cent: {split}.",
        f"Worst fall at 70/30: {at_70[3] * 100:.1f} per cent, from {at_70[4]} to {at_70[5]}.",
        f"E8, the worst fall at 70/30 exceeds 35 per cent: {'met' if e8 else 'not met'}.",
        f"E9, the largest split within 35 per cent is 65/35 or lower: {'met' if e9 else 'not met'}.",
    ])


def main():
    returns, vintages = monthly_returns()
    rows = split_rows(returns)
    chosen = largest_within(rows)

    out = []
    out.append("# Allocation check: results")
    out.append("")
    out.append(f"Generated by `mandate/allocation_check.py` on {date.today().isoformat()}. "
               f"The returns are monthly, in euro, from {returns.index[0]} to {returns.index[-1]}, {len(returns)} months, "
               f"measured at month ends with no costs and no taxes.")
    out.append("")
    out.append("A split is the pair of target weights, written equity/bonds. Each split starts at its target weights and is "
               "rebalanced by its band, the interval of 5 points either side of the equity target weight: when the equity weight "
               "leaves it at a month end, the portfolio goes back to the target weights. The worst fall is the largest fall in value "
               "from a previous peak to a later low, and a fall in a named period runs from the highest earlier value to the lowest month end "
               "in that period. Growth per year is the compound annual return, and "
               "volatility is the standard deviation of the monthly returns times the square root of 12.")
    out.append("")
    out.append("| Split | Growth per year | Volatility | Worst fall | Peak | Low | Fall 1999-2004 | Fall 2007-2010 | Fall 2022 | Within 35% |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for w, growth, vol, fall, peak, low, f00, f08, f22 in rows:
        split = f"{round(w * 100)}/{round((1 - w) * 100)}"
        out.append(f"| {split} | {growth * 100:.1f}% | {vol * 100:.1f}% | {fall * 100:.1f}% | {peak} | {low} | "
                   f"{f00 * 100:.1f}% | {f08 * 100:.1f}% | {f22 * 100:.1f}% | {'yes' if fall <= RISK_LIMIT else 'no'} |")
    out.append("")
    if chosen:
        out.append(f"The largest equity target weight whose worst fall is within {RISK_LIMIT * 100:.0f} per cent is "
                   f"{round(chosen[0] * 100)} per cent, a split of {round(chosen[0] * 100)}/{round((1 - chosen[0]) * 100)}, "
                   f"with a worst fall of {chosen[3] * 100:.1f} per cent from {chosen[4]} to {chosen[5]}.")
    else:
        out.append(f"No split on the grid has a worst fall within {RISK_LIMIT * 100:.0f} per cent.")
    if chosen:
        split = f"{round(chosen[0] * 100)}/{round((1 - chosen[0]) * 100)}"
        values = band_path(returns, chosen[0])
        out.append("")
        out.append(f"## {split} in the two falls")
        out.append("")
        out.append(f"The table gives, for {split}, the fall in each period and the return of each sleeve, the part of the portfolio held in one ETF, "
                   f"over the months from the peak to the low, in per cent.")
        out.append("")
        out.append("| Period | Peak | Low | Fall | Equity return | Bond return |")
        out.append("|---|---|---|---|---|---|")
        for label, start, end in (("1999-2004", "1999-01", "2004-12"), ("2007-2010", "2007-01", "2010-12")):
            fall, peak, low = worst_fall(values, start, end)
            out.append(f"| {label} | {peak} | {low} | {fall * 100:.1f} | {sleeve_return(returns, 'equity', peak, low) * 100:+.1f} | "
                       f"{sleeve_return(returns, 'bonds', peak, low) * 100:+.1f} |")
    out.append("")
    out.append("## How closely the constructed returns follow two funds")
    out.append("")
    (equity_fund, equity_role, equity_published), (bond_fund, bond_role, bond_published) = FUND_CHECK["equity"], FUND_CHECK["bonds"]
    out.append(f"The table gives calendar-year returns in euro, in per cent, of the constructed series and of a fund that tracks the same market. "
               f"The equity fund is {equity_fund}, {equity_role}, and the bond fund is {bond_fund}, {bond_role}. "
               f"The fund returns are from the issuers' factsheets of {FACTSHEET_DATE}. "
               f"The difference is the constructed return minus the fund's, in percentage points.")
    out.append("")
    out.append("| Year | Equity, constructed | Equity fund | Difference | Bonds, constructed | Bond fund | Difference |")
    out.append("|---|---|---|---|---|---|---|")
    built_equity, built_bonds = calendar_years(returns["equity"]) * 100, calendar_years(returns["bonds"]) * 100
    for y in sorted(equity_published):
        out.append(f"| {y} | {built_equity.loc[y]:.2f} | {equity_published[y]:.2f} | {signed(built_equity.loc[y] - equity_published[y])} | "
                   f"{built_bonds.loc[y]:.2f} | {bond_published[y]:.2f} | {signed(built_bonds.loc[y] - bond_published[y])} |")
    out.append("")
    out.append("## Data used")
    out.append("")
    for source, note in vintages.items():
        out.append(f"- {source}: {note}")
    table = results_table(rows, chosen)
    table.to_csv(OUT_CSV, index=False, float_format="%.6f", lineterminator="\n")
    text = "\n".join(out) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)

    # The US run: the same test with the US market in place of the global series. Nothing is chosen from it.
    us, us_header = us_returns(returns)
    us_rows = split_rows(us)
    results_table(us_rows, None).to_csv(OUT_US_CSV, index=False, float_format="%.6f", lineterminator="\n")
    print(us_summary(us_rows, us_header))
    periods = us_periods()
    periods.to_csv(OUT_US_PERIODS, index=False, float_format="%.6f", lineterminator="\n")

    # The history of the comparisons: the split and the dollar effects of 70/30 against three comparators.
    us_dollar = french_market("us_market")[0].reindex(returns.index)
    frames = history_months(returns, us, global_dollar_returns(returns.index), us_dollar)
    history, windows = history_tables(frames)
    history.to_csv(OUT_HISTORY, index=False, float_format="%.6f", lineterminator="\n")
    windows.to_csv(OUT_HISTORY_WINDOWS, index=False, float_format="%.6f", lineterminator="\n")
    print("")
    for r in periods.itertuples():
        print(f"{r.series}, {r.first_month} to {r.last_month}: {r.cumulative_return_usd * 100:.1f} per cent in US dollars, "
              "dividends included.")


if __name__ == "__main__":
    main()
