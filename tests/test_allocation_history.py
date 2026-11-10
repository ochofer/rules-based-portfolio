"""The history of the comparisons on invented monthly series: the effects sum to each month's difference, the
spans are in their units, and every band comes from one tracking error per comparator."""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mandate"))
import allocation_check as ac  # noqa: E402


@pytest.fixture
def series():
    index = pd.period_range("1999-02", "2025-12", freq="M")
    rng = np.random.default_rng(11)
    dollar = pd.Series(rng.normal(0.006, 0.045, len(index)), index=index)
    us_dollar = pd.Series(rng.normal(0.007, 0.045, len(index)), index=index)
    currency = pd.Series(1 + rng.normal(0, 0.02, len(index)), index=index)
    bonds = pd.Series(rng.normal(0.003, 0.012, len(index)), index=index)
    returns = pd.DataFrame({"equity": (1 + dollar) * currency - 1, "bonds": bonds})
    us = pd.DataFrame({"equity": (1 + us_dollar) * currency - 1, "bonds": bonds})
    return returns, us, dollar, us_dollar


def test_the_weights_follow_the_band_path_of_the_test(series):
    returns = series[0]
    values, weights = ac.band_weights(returns, 0.7)
    pd.testing.assert_series_equal(values, ac.band_path(returns, 0.7))
    assert weights.iloc[0] == 0.7 and (weights.sub(0.7).abs() <= ac.BAND_HALF_WIDTH + 1e-12).all()


def test_the_effects_sum_to_each_months_difference(series):
    frames = ac.history_months(*series)
    for name, frame in frames.items():
        gap = frame["comparator"] - frame["base"]
        assert np.abs(frame[["split", "dollar", "us_stock_market"]].sum(axis=1) - gap).max() < 1e-12, name
    us = frames["the US stock market at 70/30"]
    assert us["us_stock_market"].abs().sum() > 0
    assert (frames["100/0"]["us_stock_market"] == 0).all()


def test_the_spans_their_order_units_and_bands(series):
    history, windows = ac.history_tables(ac.history_months(*series))
    assert len(history) == 90 and len(windows) == 51
    first = history[history["comparator"] == "100/0"]
    assert list(first["span"][:4]) == ["1999-02 to 2025-12", "2000-01 to 2009-12", "2010-01 to 2024-12", "1999"]
    assert list(first["span"][-1:]) == ["2025"] and first["months"].iloc[3] == 11
    frame = ac.history_months(*series)["100/0"]
    tracking = (frame["comparator"] - frame["base"]).std() * math.sqrt(12)
    year = first[first["span"] == "2008"].iloc[0]
    part = frame.loc["2008"]
    assert year["unit"] == "points"
    assert year["difference"] == pytest.approx((1 + part["comparator"]).prod() - (1 + part["base"]).prod())
    assert year["band"] == pytest.approx(2 * tracking) and year["tracking_error"] == pytest.approx(tracking)
    assert year["compounding"] == pytest.approx(year["difference"] - part[["split", "dollar"]].sum().sum())
    period = first[first["span"] == "2010-01 to 2024-12"].iloc[0]
    part = frame.loc["2010-01":"2024-12"]
    growth = (1 + part["comparator"]).prod() ** (1 / 15) - (1 + part["base"]).prod() ** (1 / 15)
    assert period["unit"] == "points a year" and period["difference"] == pytest.approx(growth)
    assert period["split"] == pytest.approx(part["split"].sum() / 15)
    assert period["band"] == pytest.approx(2 * tracking / math.sqrt(15))
    assert history.loc[history["comparator"] == "60/40", "us_stock_market"].isna().all()
    assert list(windows["first_year"].unique()) == list(range(2000, 2017)) and (windows["months"] == 120).all()
    assert set(history["inside_band"]) <= {"yes", "no"}
