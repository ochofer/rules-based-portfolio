"""The look-through: the holdings of the two ETFs, weighted by each sleeve's weight in the portfolio.

Sources, cached in cache/ and never redistributed:
  - iShares: the holdings file of IE00B6R52259 (CSV), with the issuer's location, GICS sector and market
    currency of each line, as of the date in its first line.
  - Vanguard: the holdings of IE00BH04GL39 from the data service behind vanguard.co.uk, monthly, and the
    fund's monthly factsheet (PDF) for the average duration, the distribution by credit quality and the
    benchmark's one-month return.

Equity: lines that are not equities (cash, money market, futures, currency contracts, collateral) form one
line, "Cash and derivatives". Four lines are other iShares ETFs on single markets (method/funds_held.csv):
their country and currency are those of the market they hold, they are shown as "Single-market ETFs held
by the fund" in the sector view, and they are not companies in the top ten. Countries are the issuer's
location as iShares reports it, regions follow MSCI's market classification (method/msci_regions.csv), and
share classes of one company are summed (method/companies.csv). Currencies are named, largest first, until
the rest is below 10 per cent of the portfolio, at most seven of them, and the rest is shown as Other.

Bonds: the issuing country is the ISIN's country code, or the issuer's name for international (XS)
ISINs. Maturities are measured from the holdings' as-of date. Duration and credit quality are the
factsheet's figures, never computed here.
"""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import config, prices

E, B = config.EQUITY, config.BONDS
CASH_LINE = "Cash and derivatives"
CURRENCY_BARS, CURRENCY_OTHER_BELOW = 8, 0.10  # currencies are named until Other is below 10 per cent
FUNDS_LINE = "Single-market ETFs held by the fund"
FACTSHEET = (
    "https://fund-docs.vanguard.com/"
    "EUR_Eurozone_Government_Bond_UCITS_ETF_EUR_Accumulating_9591_EU_INT_EN.pdf"
)
MATURITY_RANGES = [(0, 1), (1, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, None)]
RATINGS = ("AAA", "AA", "A", "BBB")
SECTOR_NAMES = {"Communication": "Communication Services"}  # the GICS name of iShares' short form
ISIN_COUNTRY = {
    "AT": "Austria", "BE": "Belgium", "CY": "Cyprus", "DE": "Germany", "EE": "Estonia", "ES": "Spain",
    "FI": "Finland", "FR": "France", "GR": "Greece", "HR": "Croatia", "IE": "Ireland", "IT": "Italy",
    "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta", "NL": "Netherlands",
    "PT": "Portugal", "SI": "Slovenia", "SK": "Slovakia",
}  # fmt: skip


def vanguard_holdings_query() -> dict:
    query = (
        'query { borHoldings(portIds: ["%s"]) { holdings(limit: 1500) { totalHoldings items '
        "{ isin issuerName maturityDate couponRate marketValuePercentage effectiveDate securityType } } } }"
        % prices.VANGUARD_PORT_ID
    )
    return {"query": query}


def fetch(refresh: bool, cache_dir: Path = config.CACHE_DIR) -> dict:
    paths = {
        "ishares": prices.fetch(
            "ishares/IE00B6R52259_holdings.csv",
            prices.ISHARES_DOCUMENT.format(component="holdings"),
            refresh,
            cache_dir=cache_dir,
        ),
        "vanguard": prices.fetch(
            "vanguard/IE00BH04GL39_holdings.json",
            prices.VANGUARD_SERVICE,
            refresh,
            payload=vanguard_holdings_query(),
            cache_dir=cache_dir,
        ),
        "factsheet": prices.fetch("vanguard/factsheet_latest.pdf", FACTSHEET, refresh, cache_dir=cache_dir),
    }
    return paths


# Equity --------------------------------------------------------------------------------------------


def parse_ishares_holdings(path: Path) -> tuple:
    """The holdings rows and their as-of date."""
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    m = re.match(r'Fund Holdings as of,"(\d{2})/([A-Za-z]+)/(\d{4})"', lines[0])
    if not m:
        raise ValueError(f"{path}: first line is not 'Fund Holdings as of'")
    as_of = pd.Timestamp(int(m.group(3)), prices.MONTHS[m.group(2)], int(m.group(1)))
    start = next(i for i, line in enumerate(lines) if line.startswith("Ticker,"))
    body = []
    for line in lines[start:]:
        if not line.strip():
            break
        body.append(line)
    rows = list(csv.DictReader(io.StringIO("\n".join(body))))
    frame = pd.DataFrame(rows)
    frame["weight"] = frame["Weight (%)"].str.replace(",", "").astype(float) / 100
    return frame, as_of


def _method(name: str) -> pd.DataFrame:
    return pd.read_csv(config.METHOD_DIR / name, dtype=str, keep_default_na=False)


def equity_lines(frame: pd.DataFrame) -> pd.DataFrame:
    """One row per line with its country, region, sector, currency and company, weights in the fund."""
    regions = _method("msci_regions.csv").set_index("country")
    funds = _method("funds_held.csv").set_index("ticker")
    companies = _method("companies.csv").set_index("name_in_file")["company"]
    out = []
    for row in frame.to_dict("records"):
        record = {"weight": row["weight"], "name": row["Name"]}
        if row["Asset Class"] != "Equity":
            record.update(kind="cash", country=CASH_LINE, sector=CASH_LINE, currency=row["Market Currency"])
        elif row["Ticker"] in funds.index:
            fund = funds.loc[row["Ticker"]]
            record.update(kind="fund", country=fund["country"], sector=FUNDS_LINE, currency=fund["currency"])
        else:
            record.update(
                kind="equity",
                country=row["Location"],
                sector=SECTOR_NAMES.get(row["Sector"], row["Sector"]),
                currency=row["Market Currency"],
            )
        record["company"] = (
            companies.get(row["Name"], row["Name"].title()) if record["kind"] == "equity" else None
        )
        out.append(record)
    lines = pd.DataFrame(out)
    known = set(regions.index) | {CASH_LINE}
    unknown = sorted(set(lines["country"]) - known)
    if unknown:
        raise ValueError(f"method/msci_regions.csv has no region for {unknown}")
    lines["region"] = [CASH_LINE if c == CASH_LINE else regions.loc[c, "region"] for c in lines["country"]]
    lines["country"] = [c if c == CASH_LINE else regions.loc[c, "display"] for c in lines["country"]]
    return lines


# Bonds ---------------------------------------------------------------------------------------------


def parse_vanguard_holdings(path: Path) -> tuple:
    answer = json.loads(Path(path).read_text())
    items = answer["data"]["borHoldings"][0]["holdings"]["items"]
    frame = pd.DataFrame(items)
    dates = set(frame["effectiveDate"].dropna())
    if len(dates) != 1:
        raise ValueError(f"{path}: holdings carry {len(dates)} as-of dates")
    frame["weight"] = frame["marketValuePercentage"].astype(float) / 100
    return frame, pd.Timestamp(dates.pop())


def _issuer_country(isin, issuer) -> str:
    if not isin:
        return CASH_LINE
    if isin[:2] in ISIN_COUNTRY:
        return ISIN_COUNTRY[isin[:2]]
    m = re.match(r"(\w+) Government", issuer or "")
    if isin[:2] == "XS" and m:
        return m.group(1)
    raise ValueError(f"no country for bond {isin} ({issuer})")


def _range_label(low, high) -> str:
    if low == 0:
        return f"Under {high} year"
    return f"Over {low} years" if high is None else f"{low} to {high} years"


def _maturity_range(years: float) -> str:
    for low, high in MATURITY_RANGES:
        if high is None or years < high:
            return _range_label(low, high)


def bond_lines(frame: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    out = []
    for row in frame.itertuples(index=False):
        country = _issuer_country(row.isin, row.issuerName)
        if country == CASH_LINE:
            out.append({"weight": row.weight, "country": CASH_LINE, "maturity": CASH_LINE})
            continue
        years = (pd.Timestamp(row.maturityDate) - as_of).days / 365.25
        out.append({"weight": row.weight, "country": country, "maturity": _maturity_range(years)})
    return pd.DataFrame(out)


def maturity_labels() -> list:
    return [_range_label(low, high) for low, high in MATURITY_RANGES]


# Factsheet -----------------------------------------------------------------------------------------


def parse_factsheet(path: Path) -> dict:
    """Average duration, credit quality, the benchmark's one-month return and the as-at date."""
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    return parse_factsheet_text(text, str(path))


def parse_factsheet_text(text: str, path: str = "factsheet") -> dict:
    m = re.search(r"Performance and Data is calculated on closing .{1,40}? as at (\d{1,2} \w+ \d{4})", text)
    if not m:
        raise ValueError(f"{path}: no as-at date")
    as_at = pd.Timestamp(datetime.strptime(m.group(1), "%d %B %Y"))
    duration = re.search(r"^Average duration ([\d.]+) years", text, flags=re.M)
    ratings = {}
    for rating in RATINGS + ("Not Rated",):
        r = re.search(rf"^{rating} ([\d.]+)%?\s*$", text, flags=re.M)
        if not r:
            raise ValueError(f"{path}: no figure for {rating}")
        ratings[rating] = float(r.group(1)) / 100
    block = text[text.index("Annualised performance") :]
    bench = re.search(r"^Benchmark (-?[\d.]+)%", block, flags=re.M)
    if not (duration and bench):
        raise ValueError(f"{path}: duration or benchmark return missing")
    return {
        "as_at": as_at,
        "duration_years": float(duration.group(1)),
        "benchmark_1m": float(bench.group(1)) / 100,
        **{f"rating_{k.lower().replace(' ', '_')}": v for k, v in ratings.items()},
    }


def factsheet_history(latest: Path, cache_dir: Path = config.CACHE_DIR) -> pd.DataFrame:
    """Every factsheet downloaded so far, one row per as-at date. The issuer's URL holds only the latest
    month, so each new one is kept in cache/vanguard/factsheets/."""
    store = Path(cache_dir) / "vanguard" / "factsheets"
    store.mkdir(parents=True, exist_ok=True)
    parsed = parse_factsheet(latest)
    target = store / f"factsheet_{parsed['as_at']:%Y-%m-%d}.pdf"
    if not target.exists():
        shutil.copyfile(latest, target)
    rows = [parse_factsheet(p) for p in sorted(store.glob("factsheet_*.pdf"))]
    return pd.DataFrame(rows).set_index("as_at").sort_index()


# The tables ----------------------------------------------------------------------------------------


def _shares(lines: pd.DataFrame, key: str, sleeve_weight: float) -> pd.DataFrame:
    grouped = lines.groupby(key)["weight"].sum()
    grouped = grouped[grouped.abs() >= 5e-5]  # lines the issuer reports at 0.00 per cent
    frame = pd.DataFrame({"share_of_sleeve": grouped, "share_of_portfolio": grouped * sleeve_weight})
    return frame.sort_values("share_of_sleeve", ascending=False)


def _top_and_other(table: pd.DataFrame, n: int, keep_last: tuple = (CASH_LINE,)) -> pd.DataFrame:
    main = table[~table.index.isin(keep_last)]
    rest = table[table.index.isin(keep_last)]
    head, tail = main.iloc[:n], main.iloc[n:]
    if len(tail):
        head = pd.concat([head, pd.DataFrame([tail.sum()], index=["Other"])])
    return pd.concat([head, rest])


def tables(equity: pd.DataFrame, bonds: pd.DataFrame, factsheet: pd.Series, weights: dict) -> dict:
    """Every look-through table, each with shares of the sleeve and of the whole portfolio."""
    we, wb, wc = weights[E], weights[B], weights["cash"]
    out = {
        "equity_region": _shares(equity, "region", we),
        "equity_country": _top_and_other(_shares(equity, "country", we), 10),
        "equity_sector": _shares(equity, "sector", we),
        "bonds_country": _top_and_other(_shares(bonds, "country", wb), 10),
    }
    companies = equity[equity["kind"] == "equity"].groupby("company")["weight"].sum()
    companies = companies.sort_values(ascending=False).iloc[:10]
    out["top10"] = pd.DataFrame({"share_of_sleeve": companies, "share_of_portfolio": companies * we})
    maturity = _shares(bonds, "maturity", wb).reindex(maturity_labels() + [CASH_LINE]).fillna(0.0)
    keep = [label != maturity_labels()[0] and label != CASH_LINE for label in maturity.index]
    out["bonds_maturity"] = maturity[[k or v != 0 for k, v in zip(keep, maturity["share_of_sleeve"])]]
    by_sleeve = pd.DataFrame({"from_equity_sleeve": equity.groupby("currency")["weight"].sum() * we})
    by_sleeve = by_sleeve.reindex(by_sleeve.index.union(["EUR"])).fillna(0.0)
    by_sleeve["from_bond_sleeve"] = 0.0
    by_sleeve["from_cash"] = 0.0
    by_sleeve.loc["EUR", ["from_bond_sleeve", "from_cash"]] = [wb, wc]
    total = by_sleeve.sum(axis=1).sort_values(ascending=False)
    named = CURRENCY_BARS - 1
    for n in range(1, CURRENCY_BARS):
        if total.iloc[n:].sum() < CURRENCY_OTHER_BELOW:
            named = n
            break
    shown = by_sleeve.loc[total.index[:named]]
    rest = by_sleeve.loc[total.index[named:]].sum()
    if rest.sum() > 0:
        shown = pd.concat([shown, pd.DataFrame([rest], index=["Other"])])
    shown.insert(0, "share_of_portfolio", shown.sum(axis=1))
    out["currency"] = shown
    out["bonds_rating"] = pd.DataFrame(
        {"share_of_sleeve": [factsheet[f"rating_{r.lower()}"] for r in RATINGS]}, index=list(RATINGS)
    )
    out["bonds_rating"]["share_of_portfolio"] = out["bonds_rating"]["share_of_sleeve"] * wb
    out["bonds_duration"] = pd.DataFrame(
        {
            "duration_years": [factsheet["duration_years"]],
            "portfolio_duration_years": [factsheet["duration_years"] * wb],
        }
    )
    return out
