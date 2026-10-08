"""The factor regressions, on simulated returns with known loadings."""

import numpy as np
import pandas as pd
import pytest

from portfolio import config, factors


def simulated(n_days=2400, lag_share=0.0, seed=3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2017-01-02", periods=n_days)
    f = pd.DataFrame(rng.normal(0, 0.006, size=(n_days, 6)), index=days, columns=list(config.FACTORS))
    f["RF"] = 0.0001
    true = np.array([1.0, -0.1, 0.05, 0.1, -0.05, 0.08])
    common = f[list(config.FACTORS)].values @ true
    lagged = np.concatenate([[0.0], common[:-1]])
    fund = f["RF"].values + (1 - lag_share) * common + lag_share * lagged + rng.normal(0, 0.002, n_days)
    fund_value = pd.Series(100 * np.cumprod(1 + fund), index=days)
    return fund_value, f, true


def test_weekly_regression_recovers_known_loadings():
    fund_value, f, true = simulated()
    end = (f.index.max() - pd.offsets.MonthEnd(1)).to_period("M")
    table = factors.loadings(fund_value, f, end)
    weekly = table[table["method"] == "weekly"].set_index("factor").loc[list(config.FACTORS)]
    assert np.all(np.abs(weekly["loading"].values - true) <= 2.5 * weekly["standard_error"].values)
    assert int(weekly["observations"].iloc[0]) in range(150, 160)
    assert int(weekly["newey_west_lag"].iloc[0]) == 4


def test_weekly_factor_returns_compound_the_days_of_the_week():
    fund_value, f, _ = simulated(n_days=60)
    weeks = factors.weekly(fund_value, f)
    w0, w1 = weeks.index[0] - pd.Timedelta(days=7), weeks.index[0]
    days = f.loc[(f.index > w0) & (f.index <= w1), "SMB"]
    assert weeks["SMB"].iloc[0] == pytest.approx(np.prod(1 + days.values) - 1, abs=1e-15)


def test_dimson_recovers_a_loading_that_arrives_a_day_late():
    fund_value, f, true = simulated(lag_share=0.4)
    end = (f.index.max() - pd.offsets.MonthEnd(1)).to_period("M")
    table = factors.loadings(fund_value, f, end)
    daily = table[table["method"] != "weekly"].set_index("factor").loc["Mkt-RF"]
    assert abs(daily["loading"] - 1.0) <= 2.5 * daily["standard_error"]
    fund = (fund_value.pct_change() - f["RF"]).dropna()
    same_day = np.polyfit(f.loc[fund.index, "Mkt-RF"], fund, 1)[0]
    assert same_day < 0.8


def test_newey_west_equals_a_reference_implementation():
    # Reference: statsmodels OLS(...).fit(cov_type="HAC", cov_kwds={"maxlags": 4, "use_correction": False}).
    rng = np.random.default_rng(7)
    x = rng.normal(0, 0.02, size=(156, 3))
    e = rng.normal(0, 0.005, size=156)
    e[1:] += 0.5 * e[:-1]
    y = 0.001 + x @ np.array([1.0, -0.2, 0.3]) + e
    fit = factors.ols_newey_west(y, x, 4)
    assert fit["beta"] == pytest.approx(
        [-4.46605700e-04, 9.94916490e-01, -2.10485224e-01, 3.16887079e-01], abs=1e-9
    )
    assert np.sqrt(np.diag(fit["cov"])) == pytest.approx(
        [0.00054489, 0.0230844, 0.01929391, 0.02123018], abs=1e-8
    )


def test_lag_rule():
    assert factors.newey_west_lag(156) == 4 and factors.newey_west_lag(756) == 6
