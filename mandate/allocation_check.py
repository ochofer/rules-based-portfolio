"""Derive the portfolio's split from the mandate's risk limit.

The mandate sets a risk limit of a worst fall of about one third, which the
test reads as at most 35 per cent. The worst fall is the largest fall in value
from a previous peak to a later low. This script measures, on monthly euro
returns from February 1999 to December 2025, the worst fall of every split from
40/60 to 100/0 in steps of 5 points, each rebalanced by the band of rule 5, and
selects the largest equity target weight whose worst fall stays within the
limit.

Data, downloaded at run time and cached in cache/ (never committed):
  - Kenneth French's developed-market and emerging-market factor files (the
    market return is Mkt-RF plus RF, in US dollars).
  - The European Central Bank's euro reference rate against the US dollar,
    daily (dataset EXR).
  - The European Central Bank's euro area yield curve for all government
    bonds, seven-year spot rate, daily from September 2004 (dataset YC).
  - The European Central Bank's euro area ten-year government bond yield,
    monthly averages (dataset IRS), used before the yield curve starts.

Usage:   python3 mandate/allocation_check.py
Output:  mandate/allocation_check_results.md, and the same text on screen.
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

# The mandate's numbers.
RISK_LIMIT = 0.35        # worst fall allowed in the test: one third, rounded up to the next 5 points
BAND_HALF_WIDTH = 0.05   # rule 5: the equity weight may move 5 points either side of its target
EQUITY_GRID = [w / 100 for w in range(40, 101, 5)]
EMERGING_SHARE = 0.10    # emerging markets' approximate share of a global index of developed and emerging markets
BOND_MATURITY = 7.0      # in years, close to the average duration of a euro government bond index
FIRST_MONTH, LAST_MONTH = "1999-01", "2025-12"

SOURCES = {
    "developed": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_3_Factors_CSV.zip",
    "emerging": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Emerging_5_Factors_CSV.zip",
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


def monthly_returns():
    """Monthly euro returns of the equity and bond sleeves, February 1999 to December 2025."""
    developed, header_dev = french_market("developed")
    emerging, header_em = french_market("emerging")
    daily_rate = ecb_series("ecb_usd_per_eur")
    daily_rate.index = pd.to_datetime(daily_rate.index)
    usd_per_eur = month_end(daily_rate)
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


def main():
    returns, vintages = monthly_returns()
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
    within = [r for r in rows if r[3] <= RISK_LIMIT]
    chosen = max(within, key=lambda r: r[0]) if within else None

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
    text = "\n".join(out) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
