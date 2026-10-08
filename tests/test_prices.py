"""Parsing the three sources and converting the equity ETF's net asset value to euro.

The files are synthetic, written in each source's format with invented values.
"""

import json

import pandas as pd
import pytest

from portfolio import config, prices


def row(*cells):
    """One row of an XML spreadsheet, from (type, text) pairs."""
    data = "".join(f'<ss:Cell><ss:Data ss:Type="{kind}">{text}</ss:Data></ss:Cell>' for kind, text in cells)
    return f"<ss:Row>{data}</ss:Row>"


ROWS = [
    row(("String", "As Of"), ("String", "Value per share")),
    row(("String", "02/Oct/2026"), ("Number", "101.50")),
    row(("String", "01/Oct/2026"), ("Number", "101.00")),
    row(("String", "30/Sept/2026"), ("Number", "1,100.25")),
    row(("String", "29/Sep/2026"), ("String", "")),
]
SPREADSHEET = (
    '<?xml version="1.0"?>\n'
    '<ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n'
    f'<ss:Worksheet ss:Name="Overview"><ss:Table>{row(("String", "x"))}</ss:Table></ss:Worksheet>\n'
    '<ss:Worksheet ss:Name="Historical NAVs"><ss:Table>\n'
    + "\n".join(ROWS)
    + "\n</ss:Table></ss:Worksheet>\n</ss:Workbook>\n"
)


def test_ishares_sheet_with_both_spellings_of_september(tmp_path):
    path = tmp_path / "fund.xml"
    path.write_text(SPREADSHEET)
    series = prices.parse_ishares_navs(path)
    assert list(series.index) == [
        pd.Timestamp("2026-09-30"),
        pd.Timestamp("2026-10-01"),
        pd.Timestamp("2026-10-02"),
    ]
    assert series.iloc[0] == 1100.25 and series.iloc[-1] == 101.50


def test_ishares_file_without_the_sheet_stops(tmp_path):
    path = tmp_path / "fund.xml"
    path.write_text(SPREADSHEET.replace("Historical NAVs", "Holdings"))
    with pytest.raises(ValueError, match="no sheet named"):
        prices.parse_ishares_navs(path)


def vanguard_answer(items):
    return {"data": {"funds": [{"pricingDetails": {"navPrices": {"items": items}}}]}}


def test_vanguard_answer(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            vanguard_answer(
                [
                    {"price": 23.20, "asOfDate": "2026-10-02", "currencyCode": "EUR"},
                    {"price": 23.10, "asOfDate": "2026-10-01", "currencyCode": "EUR"},
                ]
            )
        )
    )
    series = prices.parse_vanguard_navs(path)
    assert list(series.values) == [23.10, 23.20]


def test_vanguard_value_in_another_currency_stops(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(vanguard_answer([{"price": 1, "asOfDate": "2026-10-01", "currencyCode": "GBP"}]))
    )
    with pytest.raises(ValueError, match="not in euro"):
        prices.parse_vanguard_navs(path)


def test_ecb_rates(tmp_path):
    path = tmp_path / "rates.csv"
    path.write_text("KEY,FREQ,TIME_PERIOD,OBS_VALUE\nEXR.D,D,2026-10-01,1.1000\nEXR.D,D,2026-10-02,1.1200\n")
    assert prices.parse_ecb(path).to_dict() == {
        pd.Timestamp("2026-10-01"): 1.10,
        pd.Timestamp("2026-10-02"): 1.12,
    }


def test_conversion_to_euro_carries_the_last_rate_and_the_last_value():
    days = pd.to_datetime(["2026-10-01", "2026-10-02", "2026-10-05"])
    series = {
        "equity_usd": pd.Series([110.0, 112.0], index=days[:2]),  # no value published on the 5th
        "bonds_eur": pd.Series([23.0, 23.1, 23.2], index=days),
        "usd_per_eur": pd.Series([1.10, 1.12], index=days[[0, 2]]),  # no rate on the 2nd
    }
    frame = prices.navs_in_euro(series)
    assert frame.loc["2026-10-01", config.EQUITY] == pytest.approx(100.0)
    assert frame.loc["2026-10-02", config.EQUITY] == pytest.approx(112.0 / 1.10)
    assert bool(frame.loc["2026-10-02", "rate_carried"]) and not bool(frame.loc["2026-10-05", "rate_carried"])
    assert frame.loc["2026-10-05", config.EQUITY] == pytest.approx(112.0 / 1.12)
    assert frame.loc["2026-10-05", config.BONDS] == 23.2


def test_cached_file_is_used_without_a_download(tmp_path, monkeypatch):
    cached = tmp_path / "ecb" / "rates.csv"
    cached.parent.mkdir()
    cached.write_text("x")
    monkeypatch.setattr(prices.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    assert prices.fetch("ecb/rates.csv", "https://example.org", cache_dir=tmp_path) == cached
