"""Net asset values of the two ETFs and the euro reference rate, downloaded into cache/.

Sources, all published by the issuers or by the European Central Bank:
  - iShares: the fund data file of IE00B6R52259 (an XML spreadsheet; its "Historical NAVs" sheet holds
    the daily net asset value in US dollars since 2011-10-21).
  - Vanguard: the daily net asset value of IE00BH04GL39 in euro, from the data service behind
    vanguard.co.uk.
  - ECB: the euro reference rate against the US dollar (dataset EXR), daily, and the euro short-term rate
    (dataset EST), daily, for the savings comparator.
  - HSBC: the daily net asset value of IE000JZ473P7 in US dollars, the fund of the S&P 500 alternative, from
    the price history on its page at assetmanagement.hsbc.co.uk.
  - The comparators' funds (method/comparator_funds.csv), each from its issuer's published series: State
    Street's spreadsheet of net asset values for the SPDR funds, Vanguard's data service for the LifeStrategy
    funds, HANetf's spreadsheet for the Mag7 fund, and the historical data spreadsheet that DWS's product page
    offers for the Nasdaq-100 fund, read after answering the page's entry gate for the Netherlands as a
    non-professional investor.
Files are cached locally, never committed and never redistributed. cache/sources.json records each
download's URL, time and size.
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

USER_AGENT = "rules-based-portfolio/0.1"
ISHARES_DOCUMENT = (
    "https://www.blackrock.com/varnish-api/uk-retail01-product-data/product-data/api/v1/"
    "get-fund-document?appType=PRODUCT_PAGE&appSubType=ISHARES&targetSite=ishares-uk&locale=en_GB"
    "&portfolioId=251850&component={component}&userType=individual"
)
VANGUARD_SERVICE = "https://www.vanguard.co.uk/gpx/graphql"
VANGUARD_PORT_ID = "9591"
ECB_USD_PER_EUR = "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata"
ECB_ESTR = "https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?format=csvdata"
HSBC_SITE = "https://www.assetmanagement.hsbc.co.uk"
HSBC_FUND_PAGE = HSBC_SITE + "/en/individual-investor/funds/{isin}"
HSBC_EXCHANGE = "XLON"  # the listing whose base-currency price history the page shows as the net asset value
HSBC_FEEDS = ("IE000JZ473P7",)  # the HSBC share classes whose price history this module reads
SSGA_NAVHIST = "https://www.ssga.com/library-content/products/fund-data/etfs/emea/navhist-emea-en-{key}-gy.xlsx"
HANETF_NAVHIST = "https://hanetf.com/wp-content/assets/upload/NAV_history-{key}-{isin}-all-all.xlsx"
SSGA_HOLDINGS = "https://www.ssga.com/library-content/products/fund-data/etfs/emea/holdings-daily-emea-en-{key}-gy.xlsx"
VANGUARD_FACTSHEET = "https://fund-docs.vanguard.com/{name}_EU_INT_EN.pdf"
LIFESTRATEGY_FACTSHEETS = {
    "IE00BMVB5P51": "LifeStrategy_60_Equity_UCITS_ETF_EUR_Accumulating_9494",
    "IE00BMVB5R75": "LifeStrategy_80_Equity_UCITS_ETF_EUR_Accumulating_9496",
}
# The published series of each comparator fund: its issuer, the name the issuer's file or service gives it, and
# the currency of its net asset value.
COMPARATOR_FEEDS = {
    "IE00BFY0GT14": ("ssga", "sppw", "USD"),
    "IE00B44Z5B48": ("ssga", "spyy", "USD"),
    "IE00BMVB5P51": ("vanguard", "9494", "EUR"),
    "IE00BMVB5R75": ("vanguard", "9496", "EUR"),
    "IE000NFL4BX4": ("hanetf", "MAGZ", "USD"),
    "IE00BMFKG444": ("dws", "nl-nl", "USD"),
}
DWS_SITE = "https://etf.deutsche-am.com"
# The entry gate of DWS's Dutch site, answered as its product page answers it when a reader picks the
# Netherlands and a non-professional investor and accepts the site's terms: the gate's key for that audience.
DWS_GATE = DWS_SITE + "/EntryGate/Accept?returnUrl={page}&setLanguage={culture}&setDisclaimer=true&setAudience={audience}"
DWS_RETAIL = "7864d84e-9892-4df4-9d1b-0109d415b8ae"
DWS_HISTORY = DWS_SITE + "/api/pdp/{culture}/etf/{isin}/historicaldata/download?startDate={start}&endDate={end}&includeTax=false"

SS = "urn:schemas-microsoft-com:office:spreadsheet"
MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Sept": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def fetch(
    name: str,
    url: str,
    refresh: bool = False,
    payload: dict = None,
    attempts: int = 3,
    cache_dir: Path = config.CACHE_DIR,
) -> Path:
    """The cached file for a source, downloaded when missing or when refresh is set.

    A download is tried three times, 10 seconds apart, and written to a temporary file first, so that an
    interrupted download never leaves a partial file in the cache. payload, when given, is sent as JSON
    in a POST request.
    """
    path = Path(cache_dir) / name
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers.update({"Content-Type": "application/json", "x-consumer-id": "uk0"})
    request = urllib.request.Request(url, data=data, headers=headers)
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            break
        except OSError as error:
            if attempt == attempts:
                raise SystemExit(
                    f"Could not download {url} ({error}). Try again later; the cached copy, if any, "
                    f"is unchanged at {path}."
                )
            time.sleep(10)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, path)
    _log_download(name, url, len(body), Path(cache_dir))
    return path


def _log_download(name: str, url: str, size: int, cache_dir: Path) -> None:
    log = cache_dir / "sources.json"
    entries = json.loads(log.read_text()) if log.exists() else {}
    entries[name] = {
        "url": url,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": size,
    }
    log.write_text(json.dumps(entries, indent=1, sort_keys=True))


def _number(text: str) -> float:
    return float(text.replace(",", "").strip())


def parse_ishares_navs(path: Path) -> pd.Series:
    """The "Historical NAVs" sheet of the iShares fund data file: net asset value by date, in US dollars."""
    root = ET.parse(path).getroot()
    for sheet in root.findall(f"{{{SS}}}Worksheet"):
        if sheet.get(f"{{{SS}}}Name") != "Historical NAVs":
            continue
        values = {}
        for row in sheet.iter(f"{{{SS}}}Row"):
            cells = [c.find(f"{{{SS}}}Data") for c in row.findall(f"{{{SS}}}Cell")]
            texts = [(d.text or "").strip() if d is not None else "" for d in cells]
            if len(texts) < 2:
                continue
            m = re.fullmatch(r"(\d{2})/([A-Za-z]+)/(\d{4})", texts[0])
            if not m or m.group(2) not in MONTHS or not texts[1]:
                continue
            day = pd.Timestamp(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1)))
            values[day] = _number(texts[1])
        if not values:
            raise ValueError(f"{path}: the Historical NAVs sheet has no dated rows")
        return pd.Series(values, name="nav_usd").sort_index()
    raise ValueError(f"{path}: no sheet named Historical NAVs")


def parse_vanguard_navs(path: Path) -> pd.Series:
    """The data service's answer for navPrices: net asset value by date, in euro."""
    answer = json.loads(Path(path).read_text())
    items = answer["data"]["funds"][0]["pricingDetails"]["navPrices"]["items"]
    if any(item["currencyCode"] != "EUR" for item in items):
        raise ValueError(f"{path}: a net asset value is not in euro")
    values = {pd.Timestamp(item["asOfDate"]): float(item["price"]) for item in items}
    return pd.Series(values, name="nav_eur").sort_index()


def parse_ecb(path: Path) -> pd.Series:
    """The ECB's euro reference rate: US dollars per euro, by date."""
    frame = pd.read_csv(path, usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
    series = pd.Series(
        frame["OBS_VALUE"].astype(float).values,
        index=pd.to_datetime(frame["TIME_PERIOD"]),
        name="usd_per_eur",
    )
    return series.sort_index()


def parse_estr(path: Path) -> pd.Series:
    """The ECB's euro short-term rate, volume-weighted, in per cent a year, by the day it applies to."""
    frame = pd.read_csv(path, usecols=["TIME_PERIOD", "OBS_VALUE"]).dropna()
    return pd.Series(frame["OBS_VALUE"].astype(float).values, index=pd.to_datetime(frame["TIME_PERIOD"]),
                     name="estr").sort_index()  # fmt: skip


def load_estr(refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> pd.Series:
    """The euro short-term rate, from the cache or freshly downloaded."""
    return parse_estr(fetch("ecb/estr.csv", ECB_ESTR, refresh, cache_dir=cache_dir))


def _hsbc_post(path: str, body, component: str, token: str = None) -> str:
    """One request to the data service behind the fund page, as the page makes it."""
    url = path if path.startswith("http") else HSBC_SITE + path
    headers = {"User-Agent": USER_AGENT, "X-Country": "GB", "X-Language": "EN", "X-Component": component}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode("utf-8") if body is not None else b""
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode("utf-8")


def hsbc_price_history(isin: str) -> bytes:
    """The price history of an HSBC ETF share class, as its fund page requests it: the page names its
    presentation, the presentation names the price chart and the listings, and the chart's series for the
    listing's base currency is the net asset value by date."""
    request = urllib.request.Request(HSBC_FUND_PAGE.format(isin=isin.lower()), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        page = response.read().decode("utf-8", "replace")
    m = re.search(r"presentationUrl:\s*\{\s*'url'\s*:\s*'([^']+)',\s*'id'\s*:\s*'([^']+)'", page)
    if not m:
        raise ValueError(f"{isin}: the fund page names no presentation")
    info = {"country": "GB", "language": "EN", "investorType": "INDV", "shareId": isin}
    token = _hsbc_post("/api/v1/token/issue", None, m.group(2))
    presentation = json.loads(_hsbc_post(m.group(1), {"id": m.group(2), "pageInformation": info}, m.group(2), token))
    chart = next(s for tab in presentation["tabs"] for s in tab.get("sections", []) if s.get("type") == "LineGraph")
    listing = next(e for e in presentation["exchange"]["items"] if e["id"] == HSBC_EXCHANGE)
    base = next(g for g in listing["currency"] if g["name"] == "Base Currency")["options"][0]
    component = chart["requestUrl"]["id"]
    token = _hsbc_post("/api/v1/token/issue", None, component)
    body = dict(chart["payload"], pageInformation=info, exchange=listing["id"], currency=base["id"])
    series = json.loads(_hsbc_post("/api/v1/detail/line-chart-series", body, component, token))
    return json.dumps({"isin": isin, "currency": base["label"], "series": series}).encode("utf-8")


def fetch_hsbc(isin: str, refresh: bool = False, attempts: int = 3, cache_dir: Path = config.CACHE_DIR) -> Path:
    """The cached price history of an HSBC ETF, downloaded when missing or when refresh is set, three tries
    10 seconds apart, through a temporary file."""
    name = f"hsbc/{isin}_nav.json"
    path = Path(cache_dir) / name
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            body = hsbc_price_history(isin)
            break
        except (OSError, ValueError, KeyError, StopIteration) as error:
            if attempt == attempts:
                raise SystemExit(f"Could not download the net asset values of {isin} from HSBC ({error}). Try again "
                                 f"later; the cached copy, if any, is unchanged at {path}.")  # fmt: skip
            time.sleep(10)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, path)
    _log_download(name, HSBC_FUND_PAGE.format(isin=isin.lower()), len(body), Path(cache_dir))
    return path


def parse_hsbc_navs(path: Path) -> pd.Series:
    """The price history of an HSBC ETF: net asset value by date, in US dollars."""
    answer = json.loads(Path(path).read_text())
    if answer["currency"] != "USD":
        raise ValueError(f"{path}: the net asset values are not in US dollars")
    points = next(s for s in answer["series"] if s.get("name") == "Price")["data"]
    values = {pd.Timestamp(p["x"]): float(p["y"]) for p in points if p.get("y") is not None}
    if not values:
        raise ValueError(f"{path}: the price history is empty")
    return pd.Series(values, name="nav_usd").sort_index()


def load_alternative(isin: str, refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> pd.Series:
    """The net asset values in US dollars of the S&P 500 alternative's fund. Its issuer's feed is the one
    written for it, and a fund without one stops the build."""
    if isin not in HSBC_FEEDS:
        raise ValueError(f"no net asset value feed is written for {isin}, the fund the selection picks")
    return parse_hsbc_navs(fetch_hsbc(isin, refresh, cache_dir=cache_dir))


def vanguard_query(start: str = "2019-01-01", end: str = None, port_id: str = VANGUARD_PORT_ID) -> dict:
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    query = (
        "query Q($portIds: [String!]!, $startDate: String!, $endDate: String!) { funds(portIds: $portIds) "
        "{ pricingDetails { navPrices(startDate: $startDate, endDate: $endDate, limit: 0) "
        "{ items { price asOfDate currencyCode } } } } }"
    )
    return {"query": query, "variables": {"portIds": [port_id], "startDate": start, "endDate": end}}


def _sheet_series(path: Path, date_format: str = None, column: int = 1, beside: dict = None) -> tuple:
    """A spreadsheet of net asset values whose table starts at the row whose first cell reads Date: the values by
    date, from the given column, and the currency the sheet states above the table on the first row whose label
    ends in Currency, if it states one. beside maps other columns to the headings they must carry, so that a
    sheet whose columns have moved stops the build."""
    frame = pd.read_excel(path, header=None)
    first = frame[0].astype(str).str.strip()
    starts = first[first == "Date"].index
    if not len(starts):
        raise ValueError(f"{path}: no table headed Date")
    stated = frame[first.str.rstrip(":").str.endswith("Currency")]
    currency = str(stated.iloc[0, 1]).strip() if len(stated) else ""
    heads = [str(h).strip() for h in frame.iloc[starts[0]]]
    for at, heading in (beside or {}).items():
        if at >= len(heads) or heads[at] != heading:
            raise ValueError(f"{path}: column {at + 1} is not headed {heading}")
    body = frame.iloc[starts[0] + 1:, [0, column]]
    body.columns = [0, 1]
    days = pd.to_datetime(body[0], format=date_format, errors="coerce") if date_format else pd.to_datetime(body[0], errors="coerce")
    values = pd.to_numeric(body[1], errors="coerce")
    kept = days.notna() & values.notna()
    series = pd.Series(values[kept].values, index=pd.DatetimeIndex(days[kept]), name="unit_value").sort_index()
    if not len(series):
        raise ValueError(f"{path}: the table holds no dated value")
    return series[~series.index.duplicated(keep="last")], currency


def dws_history(isin: str, culture: str, start: str = "2019-01-01", end: str = None) -> bytes:
    """The historical data spreadsheet of a DWS ETF, as its product page offers it for download: the page's entry
    gate is answered first, for the Netherlands and a non-professional investor, then the spreadsheet is requested
    with the cookies the gate sets."""
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    page = urllib.parse.quote(f"/{culture}/{isin}/", safe="")
    gate = DWS_GATE.format(page=page, culture=culture, audience=DWS_RETAIL)
    request = urllib.request.Request(gate, data=b"continue=", headers={"User-Agent": USER_AGENT}, method="POST")
    with opener.open(request, timeout=120) as response:
        response.read()
    if not any(c.name == f"audiences_{culture}" for c in jar):
        raise ValueError(f"{isin}: DWS's entry gate set no audience")
    url = DWS_HISTORY.format(culture=culture, isin=isin, start=start, end=end)
    with opener.open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=120) as response:
        body = response.read()
    if not body.startswith(b"PK"):
        raise ValueError(f"{isin}: DWS's historical data is not a spreadsheet")
    return body


def fetch_dws(isin: str, refresh: bool = False, attempts: int = 3, cache_dir: Path = config.CACHE_DIR) -> Path:
    """The cached historical data spreadsheet of a DWS ETF, downloaded when missing or when refresh is set, three
    tries 10 seconds apart, through a temporary file."""
    _, culture, _ = COMPARATOR_FEEDS[isin]
    name = f"dws/{isin}_history.xlsx"
    path = Path(cache_dir) / name
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, attempts + 1):
        try:
            body = dws_history(isin, culture)
            break
        except (OSError, ValueError) as error:
            if attempt == attempts:
                raise SystemExit(f"Could not download the net asset values of {isin} from DWS ({error}). Try again "
                                 f"later; the cached copy, if any, is unchanged at {path}.")  # fmt: skip
            time.sleep(10)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(body)
    os.replace(tmp, path)
    _log_download(name, DWS_HISTORY.format(culture=culture, isin=isin, start="{start}", end="{end}"), len(body), Path(cache_dir))
    return path


def load_ssga_holdings(isin: str, refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> tuple:
    """A SPDR fund's daily holdings from State Street's published spreadsheet: each line's country and its share of
    the fund, and the date of the holdings."""
    _, key, _ = COMPARATOR_FEEDS[isin]
    path = fetch(f"ssga/{isin}_holdings.xlsx", SSGA_HOLDINGS.format(key=key), refresh, cache_dir=cache_dir)
    frame = pd.read_excel(path, header=None)
    first = frame[0].astype(str).str.strip()
    head = first[first == "ISIN"].index[0]
    dated = frame[first.str.rstrip(":") == "Holdings As Of"]
    as_of = pd.to_datetime(str(dated.iloc[0, 1]).strip(), format="%d-%b-%Y")
    table = frame.iloc[head + 1:].copy()
    table.columns = [str(c).strip() for c in frame.iloc[head]]
    table = table[pd.to_numeric(table["Percent of Fund"], errors="coerce").notna()]
    country = next(c for c in table.columns if c.endswith("Country Name"))
    out = pd.DataFrame({"country": table[country].fillna("").astype(str).str.strip(),
                        "weight": pd.to_numeric(table["Percent of Fund"]) / 100})  # fmt: skip
    return out.reset_index(drop=True), as_of


def _pdf_text(path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(str(path)) as pdf:
        return "\n".join((page.extract_text() or "") for page in pdf.pages)


def _lifestrategy_text(isin: str, refresh: bool, cache_dir: Path) -> tuple:
    name = LIFESTRATEGY_FACTSHEETS[isin]
    path = fetch(f"vanguard/{isin}_factsheet.pdf", VANGUARD_FACTSHEET.format(name=name), refresh, cache_dir=cache_dir)
    return _pdf_text(path), path


def load_lifestrategy_charges(isin: str, refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> tuple:
    """A LifeStrategy fund's ongoing charges figure from its monthly factsheet, as a fraction a year, and the
    factsheet's date."""
    text, path = _lifestrategy_text(isin, refresh, cache_dir)
    found = re.search(r"Ongoing Charges Figure\W*?\s*(\d+(?:\.\d+)?)\s*%", text)
    if not found:
        raise ValueError(f"{path}: no ongoing charges figure")
    dated = re.search(r"Data as at (\d{1,2} [A-Z][a-z]+ \d{4})", text)
    return float(found.group(1)) / 100, pd.to_datetime(dated.group(1)) if dated else pd.NaT


def load_lifestrategy_allocation(isin: str, refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> tuple:
    """A LifeStrategy fund's allocation to its underlying Vanguard funds, from its monthly factsheet: each fund and
    its share, and the factsheet's date."""
    text, path = _lifestrategy_text(isin, refresh, cache_dir)
    section = re.search(r"Allocation to underlying Vanguard funds\n(.*?)\nTotal", text, flags=re.S)
    if not section:
        raise ValueError(f"{path}: no allocation to underlying funds")
    lines = re.findall(r"^(Vanguard .*?)\s+(\d+(?:\.\d+)?)\s*%?\s*$", section.group(1), flags=re.M)
    dated = re.search(r"Data as at (\d{1,2} [A-Z][a-z]+ \d{4})", text)
    as_of = pd.to_datetime(dated.group(1)) if dated else pd.NaT
    frame = pd.DataFrame([(fund.strip(), float(share) / 100) for fund, share in lines], columns=["fund", "share"])
    return frame.drop_duplicates("fund"), as_of


RABOBANK_COSTS = ("https://media.rabobank.com/asset/10715cd7-c653-494d-b1dd-279bd16c8a48/"
                  "Kostenoverzicht-Rabo-Beheerd-Beleggen-Basis.pdf")  # fmt: skip
DUTCH_MONTHS = {m: i for i, m in enumerate(["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus",
                                             "september", "oktober", "november", "december"], start=1)}  # fmt: skip


def parse_rabobank_costs(text: str) -> dict:
    """Rabobank's published costs of its managed index portfolios (Rabo Beheerd Beleggen Basis), on the first
    100,000 euro invested: the basic service and the portfolio management, each a share a quarter, the funds' own
    costs as a range a year, and the month of the schedule."""
    flat = re.sub(r"\s+", " ", text)
    basic = re.search(r"Basisdienstverlening\b.*?tot € ?100\.000 (\d+,\d+)% per kwartaal", flat)
    managed = re.search(r"Portefeuillebeheer\b.*?tot € ?100\.000 (\d+,\d+)%", flat)
    funds = re.search(r"bedragen deze kosten tussen (\d+(?:,\d+)?) en (\d+(?:,\d+)?)%", flat)
    dated = re.search(r"Kostenoverzicht Rabo Beheerd Beleggen Basis (\w+) (\d{4})", flat)
    if not (basic and managed and funds and dated) or dated.group(1).lower() not in DUTCH_MONTHS:
        raise ValueError("Rabobank's cost overview does not state its costs in the form read")
    number = lambda x: float(x.replace(",", ".")) / 100  # noqa: E731
    return {"basic_a_quarter": number(basic.group(1)), "management_a_quarter": number(managed.group(1)),
            "funds_low": number(funds.group(1)), "funds_high": number(funds.group(2)),
            "dated": pd.Timestamp(int(dated.group(2)), DUTCH_MONTHS[dated.group(1).lower()], 1)}  # fmt: skip


def load_rabobank_costs(refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> dict:
    path = fetch("rabobank/kostenoverzicht_basis.pdf", RABOBANK_COSTS, refresh, cache_dir=cache_dir)
    return parse_rabobank_costs(_pdf_text(path))


ISSUER_NAME = {"ssga": "State Street", "vanguard": "Vanguard", "hanetf": "HANetf", "dws": "DWS"}


def comparator_cache_name(isin: str) -> str:
    """The cache file of a comparator fund's published series."""
    issuer = COMPARATOR_FEEDS[isin][0]
    return {"ssga": f"ssga/{isin}_navhist.xlsx", "hanetf": f"hanetf/{isin}_nav.xlsx", "vanguard": f"vanguard/{isin}_nav.json",
            "dws": f"dws/{isin}_history.xlsx"}[issuer]  # fmt: skip


def load_comparator(isin: str, refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> tuple:
    """The net asset values of a comparator's fund from its issuer's published series, and their currency."""
    if isin not in COMPARATOR_FEEDS:
        raise ValueError(f"no published series is written for {isin}")
    issuer, key, currency = COMPARATOR_FEEDS[isin]
    if issuer == "ssga":
        path = fetch(f"ssga/{isin}_navhist.xlsx", SSGA_NAVHIST.format(key=key), refresh, cache_dir=cache_dir)
        series, stated = _sheet_series(path, "%d-%b-%Y")
        if stated != currency:
            raise ValueError(f"{path}: the net asset values are in {stated}, not {currency}")
    elif issuer == "dws":
        path = fetch_dws(isin, refresh, cache_dir=cache_dir)
        # The third column, between the assets under management and the index level.
        series, stated = _sheet_series(path, "%d.%m.%Y", column=2, beside={1: "Asset Under Management", 3: "Index Level"})
        if stated != currency:
            raise ValueError(f"{path}: the net asset values are in {stated}, not {currency}")
    elif issuer == "hanetf":
        path = fetch(f"hanetf/{isin}_nav.xlsx", HANETF_NAVHIST.format(key=key, isin=isin), refresh, cache_dir=cache_dir)
        series, _ = _sheet_series(path)
    else:
        path = fetch(f"vanguard/{isin}_nav.json", VANGUARD_SERVICE, refresh, payload=vanguard_query(port_id=key),
                     cache_dir=cache_dir)  # fmt: skip
        series = parse_vanguard_navs(path)
    return series.rename("unit_value"), currency


def load(refresh: bool = False, cache_dir: Path = config.CACHE_DIR) -> dict:
    """The three series, from the cache or freshly downloaded."""
    ishares = fetch(
        "ishares/IE00B6R52259_fund.xml",
        ISHARES_DOCUMENT.format(component="fundDownloadV2"),
        refresh,
        cache_dir=cache_dir,
    )
    vanguard = fetch(
        "vanguard/IE00BH04GL39_nav.json",
        VANGUARD_SERVICE,
        refresh,
        payload=vanguard_query(),
        cache_dir=cache_dir,
    )
    ecb = fetch("ecb/usd_per_eur.csv", ECB_USD_PER_EUR, refresh, cache_dir=cache_dir)
    return {
        "equity_usd": parse_ishares_navs(ishares),
        "bonds_eur": parse_vanguard_navs(vanguard),
        "usd_per_eur": parse_ecb(ecb),
    }


def navs_in_euro(series: dict) -> pd.DataFrame:
    """Both net asset values in euro on each day either is published.

    The equity ETF's US-dollar value is divided by the ECB reference rate of the same day; on a day
    without a rate (an ECB holiday) the last rate is carried forward, and the column rate_carried marks
    those days. A day on which one fund publishes and the other does not carries the other's last value.
    """
    usd = series["equity_usd"]
    rate = series["usd_per_eur"]
    days = usd.index.union(series["bonds_eur"].index)
    rate_on_day = rate.reindex(days)
    carried = rate_on_day.isna()
    rate_on_day = rate_on_day.ffill()
    frame = pd.DataFrame(
        {
            config.EQUITY: (usd.reindex(days).ffill() / rate_on_day),
            config.BONDS: series["bonds_eur"].reindex(days).ffill(),
            "usd_per_eur": rate_on_day,
            "rate_carried": carried,
        }
    )
    return frame.dropna(subset=[config.EQUITY, config.BONDS])
