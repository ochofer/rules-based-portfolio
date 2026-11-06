"""Net asset values of the two ETFs and the euro reference rate, downloaded into cache/.

Sources, all published by the issuers or by the European Central Bank:
  - iShares: the fund data file of IE00B6R52259 (an XML spreadsheet; its "Historical NAVs" sheet holds
    the daily net asset value in US dollars since 2011-10-21).
  - Vanguard: the daily net asset value of IE00BH04GL39 in euro, from the data service behind
    vanguard.co.uk.
  - ECB: the euro reference rate against the US dollar (dataset EXR), daily.
  - HSBC: the daily net asset value of IE000JZ473P7 in US dollars, the fund of the S&P 500 alternative, from
    the price history on its page at assetmanagement.hsbc.co.uk.
Files are cached locally, never committed and never redistributed. cache/sources.json records each
download's URL, time and size.
"""

from __future__ import annotations

import json
import os
import re
import time
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
HSBC_SITE = "https://www.assetmanagement.hsbc.co.uk"
HSBC_FUND_PAGE = HSBC_SITE + "/en/individual-investor/funds/{isin}"
HSBC_EXCHANGE = "XLON"  # the listing whose base-currency price history the page shows as the net asset value
HSBC_FEEDS = ("IE000JZ473P7",)  # the HSBC share classes whose price history this module reads

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


def vanguard_query(start: str = "2019-01-01", end: str = None) -> dict:
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    query = (
        "query Q($portIds: [String!]!, $startDate: String!, $endDate: String!) { funds(portIds: $portIds) "
        "{ pricingDetails { navPrices(startDate: $startDate, endDate: $endDate, limit: 0) "
        "{ items { price asOfDate currencyCode } } } } }"
    )
    return {"query": query, "variables": {"portIds": [VANGUARD_PORT_ID], "startDate": start, "endDate": end}}


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
