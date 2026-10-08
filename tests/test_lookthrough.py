"""The look-through tables, on invented holdings."""

import pandas as pd
import pytest

from portfolio import lookthrough as lt

FACTSHEET_TEXT = """Characteristics Fund Benchmark
Average duration 6.8 years 6.8 years
Distribution by credit quality (% of fund)
AAA 23.3%
AA 6.7
A 47.1
BBB 22.9
Not Rated 0.0
Annualised performance** 1 month Quarter
Fund (Net of expenses) -0.63% -1.94%
Benchmark -0.62% -1.92%
Performance and Data is calculated on closing net asset value as at 31 August 2026.
"""


def equity_frame():
    rows = [
        ("NVDA", "NVIDIA", "Information Technology", "Equity", "United States", "USD", 0.30),
        ("GOOGL", "ALPHABET CLASS A", "Communication", "Equity", "United States", "USD", 0.10),
        ("GOOG", "ALPHABET CLASS C", "Communication", "Equity", "United States", "USD", 0.08),
        ("7203", "TOYOTA MOTOR CORP", "Consumer Discretionary", "Equity", "Japan", "JPY", 0.12),
        ("NDIA", "ISHARES MSCI INDIA UCITS ETF", "Financials", "Equity", "Ireland", "USD", 0.05),
        ("SAP", "SAP", "Information Technology", "Equity", "Germany", "EUR", 0.34),
        ("USD", "USD CASH", "Cash and/or Derivatives", "Cash", "United States", "USD", 0.01),
    ]
    frame = pd.DataFrame(
        rows, columns=["Ticker", "Name", "Sector", "Asset Class", "Location", "Market Currency", "weight"]
    )
    return frame


def bond_frame():
    return pd.DataFrame(
        {
            "isin": ["FR0000000001", "IT0000000002", "XS0000000003", None],
            "issuerName": ["French Republic", "Italy Buoni", "Croatia Government International Bond", None],
            "maturityDate": ["2028-08-31", "2045-01-01", "2031-06-30", None],
            "weight": [0.5, 0.3, 0.19, 0.01],
        }
    )


@pytest.fixture
def tables():
    equity = lt.equity_lines(equity_frame())
    bonds = lt.bond_lines(bond_frame(), pd.Timestamp("2026-08-31"))
    sheet = pd.Series(lt.parse_factsheet_text(FACTSHEET_TEXT))
    return lt.tables(equity, bonds, sheet, {"equity": 0.7, "bonds": 0.29, "cash": 0.01}), equity


def test_shares_sum_to_the_sleeve_weights(tables):
    t, _ = tables
    for key, weight in (("equity_region", 0.7), ("equity_country", 0.7), ("equity_sector", 0.7),
                        ("bonds_country", 0.29), ("bonds_maturity", 0.29)):  # fmt: skip
        assert t[key]["share_of_portfolio"].sum() == pytest.approx(weight, abs=0.0005), key
    assert t["currency"]["share_of_portfolio"].sum() == pytest.approx(1.0)


def test_a_fund_held_counts_under_its_market_and_is_not_a_company(tables):
    t, equity = tables
    assert t["equity_country"].loc["India", "share_of_sleeve"] == pytest.approx(0.05)
    assert "Ireland" not in t["equity_country"].index
    assert t["equity_sector"].loc[lt.FUNDS_LINE, "share_of_sleeve"] == pytest.approx(0.05)
    assert "Ishares Msci India Ucits Etf" not in t["top10"].index


def test_share_classes_are_summed_and_sectors_carry_their_gics_names(tables):
    t, _ = tables
    assert t["top10"].loc["Alphabet", "share_of_sleeve"] == pytest.approx(0.18)
    assert "Communication Services" in t["equity_sector"].index


def test_bonds_by_country_and_maturity(tables):
    t, _ = tables
    assert t["bonds_country"].loc["Croatia", "share_of_sleeve"] == pytest.approx(0.19)
    assert t["bonds_maturity"].loc["1 to 3 years", "share_of_sleeve"] == pytest.approx(0.5)
    assert t["bonds_maturity"].loc["Over 15 years", "share_of_sleeve"] == pytest.approx(0.3)


def test_factsheet_figures():
    sheet = lt.parse_factsheet_text(FACTSHEET_TEXT)
    assert sheet["duration_years"] == 6.8 and sheet["benchmark_1m"] == pytest.approx(-0.0062)
    assert sheet["rating_a"] == pytest.approx(0.471) and sheet["as_at"] == pd.Timestamp("2026-08-31")


def test_currencies_are_named_until_other_is_below_ten_per_cent(tables):
    t, _ = tables
    currency = t["currency"]["share_of_portfolio"]
    assert len(currency) <= lt.CURRENCY_BARS
    if "Other" in currency.index:
        assert currency["Other"] < lt.CURRENCY_OTHER_BELOW or len(currency) == lt.CURRENCY_BARS


def test_currency_exposure_shows_where_each_currency_comes_from(tables):
    t, _ = tables
    currency = t["currency"]
    parts = currency[["from_equity_sleeve", "from_bond_sleeve", "from_cash"]].sum(axis=1)
    assert parts.values == pytest.approx(currency["share_of_portfolio"].values)
    assert currency["from_bond_sleeve"].sum() == pytest.approx(0.29)
    assert currency.loc["EUR", "from_cash"] == pytest.approx(0.01)


def test_a_line_without_an_isin_is_cash_whatever_pandas_reads_it_as():
    for missing in (None, "", float("nan")):
        assert lt._issuer_country(missing, float("nan")) == lt.CASH_LINE
