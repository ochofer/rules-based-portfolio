"""The look-through's risk: the exact long-only solver, the frontier, the risk contributions, the component
weights, the episodes, the record of the estimate, the forecast's calibration, the key information documents
and the difference to the index blend in three parts. The last tests read the committed tables."""

import itertools

import numpy as np
import pandas as pd
import pytest

from portfolio import config, metrics, risk

E, B = config.EQUITY, config.BONDS
NAMES = list(risk.COMPONENTS)


def sample(seed=7, months=120):
    """Monthly returns of seven components with a realistic spread of volatilities and correlations."""
    rng = np.random.default_rng(seed)
    vols = np.array([0.045, 0.040, 0.036, 0.044, 0.006, 0.016, 0.040])
    base = rng.standard_normal((months, 2))
    noise = rng.standard_normal((months, 7))
    loads = np.array([[0.9, 0.1], [0.85, 0.1], [0.8, 0.1], [0.8, 0.1], [0.0, 0.7], [0.0, 0.9], [0.0, 0.95]])
    shocks = base @ loads.T + noise * np.sqrt(1 - (loads**2).sum(axis=1))
    drift = np.array([0.010, 0.007, 0.006, 0.007, 0.000, -0.001, -0.002])
    index = pd.period_range("2016-10", periods=months, freq="M")
    return pd.DataFrame(drift + shocks * vols, index=index, columns=NAMES)


@pytest.fixture
def moments():
    return risk.moments(sample())


def test_minimum_variance_has_no_lower_variance_neighbour_on_a_grid(moments):
    _, cov = moments
    w = risk.minimum_variance(cov).values
    best = w @ cov.values @ w
    for i, j in itertools.permutations(range(len(w)), 2):
        for step in (0.001, 0.01, 0.05):
            if w[i] >= step:
                v = w.copy()
                v[i] -= step
                v[j] += step
                assert v @ cov.values @ v >= best - 1e-14
    # And no point of a coarse grid of the whole set of long-only, fully invested portfolios lies lower.
    grid = np.array(list(compositions(10, len(w)))) / 10
    assert np.einsum("ij,jk,ik->i", grid, cov.values, grid).min() >= best - 1e-14


def compositions(total, parts):
    """Every way to write total as an ordered sum of parts whole numbers from zero."""
    if parts == 1:
        yield (total,)
        return
    for first in range(total + 1):
        for rest in compositions(total - first, parts - 1):
            yield (first,) + rest


def test_frontier_weights_are_long_only_fully_invested_and_meet_the_target(moments):
    mean, cov = moments
    f = risk.frontier(mean, cov)
    weights = f[[c for c in f.columns if c.startswith("weight_")]].values
    assert len(f) == risk.FRONTIER_POINTS and (weights >= 0).all()
    assert np.allclose(weights.sum(axis=1), 1, atol=1e-12)
    targets = np.linspace(f["estimated_return"].iloc[0], mean.max(), risk.FRONTIER_POINTS)
    assert np.allclose(f["estimated_return"], targets, atol=1e-12)
    assert np.allclose(np.sqrt(np.einsum("ij,jk,ik->i", weights, cov.values, weights)), f["estimated_volatility"])
    assert (np.diff(f["estimated_volatility"]) > -1e-12).all()
    assert f.loc[0, "estimated_volatility"] == pytest.approx(np.sqrt(risk.minimum_variance(cov) @ cov @ risk.minimum_variance(cov)))


def test_the_solver_agrees_with_slsqp(moments):
    optimize = pytest.importorskip("scipy.optimize")
    mean, cov = moments
    exact = risk.frontier(mean, cov)
    sigma, mu, n = cov.values, mean.values, len(mean)
    for _, row in exact.iloc[[0, 6, 12, 18, 23]].iterrows():
        target = row["estimated_return"]
        found = optimize.minimize(lambda w: w @ sigma @ w, np.full(n, 1 / n), jac=lambda w: 2 * sigma @ w, method="SLSQP",
                                  bounds=[(0, 1)] * n, options={"ftol": 1e-15, "maxiter": 500},
                                  constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1},
                                               {"type": "eq", "fun": lambda w, t=target: w @ mu - t}])  # fmt: skip
        assert found.success
        assert np.sqrt(found.fun) >= row["estimated_volatility"] - 1e-7
        assert np.sqrt(found.fun) == pytest.approx(row["estimated_volatility"], abs=1e-6)


def test_risk_contributions_sum_to_one_and_cash_carries_none(moments):
    _, cov = moments
    weights = pd.Series([0.47, 0.09, 0.05, 0.08, 0.13, 0.09, 0.08, 0.01], index=NAMES + [risk.CASH])
    shares = risk.risk_contributions(weights, cov)
    assert shares.sum() == pytest.approx(1, abs=1e-12) and shares[risk.CASH] == 0
    w = weights[NAMES].values
    assert risk.volatility(weights, cov) == pytest.approx(np.sqrt(w @ cov.values @ w))


def test_component_weights_group_the_look_through_and_keep_cash_apart():
    regions = pd.DataFrame({"region": ["North America", "Europe and Middle East", "Pacific", "Emerging markets",
                                       "Cash and derivatives"],
                            "share_of_portfolio": [0.47, 0.09, 0.05, 0.08, 0.003]})  # fmt: skip
    maturities = pd.DataFrame({"maturity": ["1 to 3 years", "3 to 5 years", "5 to 7 years", "7 to 10 years",
                                            "10 to 15 years", "Over 15 years", "Cash and derivatives"],
                               "share_of_portfolio": [0.07, 0.06, 0.04, 0.05, 0.03, 0.045, 0.002]})  # fmt: skip
    w = risk.component_weights(regions, maturities, cash_weight=0.0)
    assert w["Bonds, short"] == pytest.approx(0.13) and w["Bonds, medium"] == pytest.approx(0.09)
    assert w["Bonds, long"] == pytest.approx(0.075) and w[risk.CASH] == pytest.approx(0.005)
    assert w.sum() == pytest.approx(regions["share_of_portfolio"].sum() + maturities["share_of_portfolio"].sum())
    with pytest.raises(ValueError, match="not a component"):
        risk.component_weights(pd.DataFrame({"region": ["Antarctica"], "share_of_portfolio": [1.0]}), maturities, 0.0)


def test_a_maturity_group_is_a_zero_coupon_bond_at_its_midpoint():
    months = pd.period_range("2020-01", periods=4, freq="M")
    flat = pd.DataFrame({g[0]: [0.02] * 4 for g in risk.MATURITY_GROUPS}, index=months)
    assert np.allclose(risk.group_returns(flat), np.exp(0.02 / 12) - 1)
    up = flat.copy()
    up.iloc[2:] = 0.03  # a rise of one point in month three costs about the duration in per cent
    r = risk.group_returns(up).iloc[1]
    for name, _, _, maturity, _ in risk.MATURITY_GROUPS:
        assert r[name] == pytest.approx(np.exp(-0.03 * (maturity - 1 / 12) + 0.02 * maturity) - 1)
        assert r[name] < 0


def test_stress_holds_todays_weights_and_fills_a_short_series_from_the_allocation_test():
    months = pd.period_range("1999-01", "2023-12", freq="M")
    components = pd.DataFrame(0.01, index=months, columns=NAMES)
    components.loc[: pd.Period("2004-09", "M"), [n for n in NAMES if risk.SLEEVE_OF[n] == B]] = np.nan
    test = pd.DataFrame({"equity": -0.02, "bonds": 0.005}, index=months)
    weights = pd.Series([0.4, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05, 0.05], index=NAMES + [risk.CASH])
    episodes = risk.stress(components, test, weights).set_index("episode")
    first = episodes.loc["2000 to 2003"]  # 31 months, bonds from the allocation test
    assert first["equity_contribution"] == pytest.approx(0.7 * (1.01**31 - 1))
    assert first["bond_contribution"] == pytest.approx(0.25 * (1.005**31 - 1))
    assert first["series"] == "the components, and the allocation test's series for the bond sleeve"
    crisis = episodes.loc["2007 to 2009"]  # 16 months, all components
    assert crisis["total"] == pytest.approx(0.95 * (1.01**16 - 1))
    assert crisis["series"] == "the components"
    assert (episodes["total"] == episodes["equity_contribution"] + episodes["bond_contribution"]).all()


def test_the_record_of_the_estimate_is_written_once_and_never_rewritten():
    first = risk.record_estimate(pd.DataFrame(), pd.Period("2026-09", "M"), 0.10, pd.Period("2016-10", "M"), "2026-10-08")
    assert len(first) == 0  # before the month of the first purchase
    record = risk.record_estimate(first, pd.Period("2026-10", "M"), 0.10, pd.Period("2016-11", "M"), "2026-10-08")
    again = risk.record_estimate(record, pd.Period("2026-10", "M"), 0.20, pd.Period("2016-11", "M"), "2026-10-08")
    later = risk.record_estimate(again, pd.Period("2026-11", "M"), 0.11, pd.Period("2016-12", "M"), "2026-10-08")
    assert list(later["month_end"]) == ["2026-10", "2026-11"] and list(later["estimated_volatility"]) == [0.10, 0.11]


def test_the_forecasts_calibration_is_the_spread_of_returns_over_their_forecasts():
    history = pd.DataFrame({"month_end": [str(p) for p in pd.period_range("2026-10", periods=14, freq="M")],
                            "estimated_volatility": np.linspace(0.08, 0.12, 14)})  # fmt: skip
    z = np.array([1.2, -0.8, 0.3, -1.5, 2.0, 0.1, -0.4, 0.9, -1.1, 0.6, -0.2, 1.4, -0.7])
    months = pd.period_range("2026-11", periods=len(z), freq="M")
    forecast = history["estimated_volatility"].values[: len(z)] / np.sqrt(12)
    monthly = pd.DataFrame({"month": [str(m) for m in months], "complete": "yes", "return_month": z * forecast})
    value, count = risk.calibration(history, monthly)
    assert count == 13 and value == pytest.approx(np.std(z, ddof=1))
    early, count = risk.calibration(history, monthly.iloc[:11])
    assert np.isnan(early) and count == 11
    to_date = monthly.assign(complete=["yes"] * 12 + ["to date"])
    assert risk.calibration(history, to_date)[1] == 12


ISHARES = (
    "This document is dated 03 September 2026.\nOngoing costs taken each year\nManagement fees and 0.20% of the value "
    "of your investment per year. This is based on a combination of estimated 20 USD\nother administrative or operating "
    "costs\nTransaction costs 0.01% of the value of your investment per year. This is an estimate of the costs incurred"
)
VANGUARD = (
    "This Key Information Document is dated 29/09/2026.\nManagement fees and other 0.07% of the value of your investment "
    "p.a. This is an estimate based on actual costs\nEUR 7\nadministrative or operating costs over the last year\n0.00% "
    "of the value of your investment per year. This is an estimate of the costs\nTransaction costs incurred"
)


@pytest.mark.parametrize(
    "text, fees, transaction, day",
    [(ISHARES, 0.0020, 0.0001, "2026-09-03"), (VANGUARD, 0.0007, 0.0, "2026-09-29")],
)
def test_the_key_information_documents_read_in_both_forms(text, fees, transaction, day):
    k = risk.parse_kid_text(text)
    assert k["management_fees"] == pytest.approx(fees) and k["transaction_costs"] == pytest.approx(transaction)
    assert k["document_date"] == pd.Timestamp(day)
    with pytest.raises(ValueError):
        risk.parse_kid_text(text.replace("dated", "issued"))


def daily(days):
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2026-10-08", periods=days)
    paths = {c: 100 * np.cumprod(1 + rng.normal(0.0003, 0.006, days)) for c in
             ("growth_portfolio", "growth_reference_a", "growth_reference_b", "growth_index_blend")}  # fmt: skip
    return pd.DataFrame({"date": dates, **paths})


def test_the_three_parts_sum_to_the_difference_to_the_index_blend():
    assert metrics.attribution(daily(240)).empty  # October 2026 to August 2027: fewer than twelve months
    frame = daily(290)  # to 2027-11-17: month ends from October 2026 to October 2027
    out = metrics.attribution(frame).iloc[0]
    assert out["period_start"] == pd.Timestamp("2026-10-30") and out["period_end"] == pd.Timestamp("2027-10-29")
    assert out["months"] == 12
    parts = out["implementation_cost"] + out["drift_effect"] + out["tracking_difference"]
    assert parts == pytest.approx(out["total"], abs=1e-14)
    rows = frame.set_index("date")
    total = rows.loc["2027-10-29", "growth_portfolio"] / rows.loc["2026-10-30", "growth_portfolio"] - (
        rows.loc["2027-10-29", "growth_index_blend"] / rows.loc["2026-10-30", "growth_index_blend"]
    )
    assert out["total"] == pytest.approx(total)


# The committed tables -----------------------------------------------------------------------------


def committed(name):
    path = config.OUTPUTS_DIR / name
    if not path.exists():
        pytest.skip(f"outputs/{name} is not built")
    return pd.read_csv(path)


def test_the_committed_weights_match_the_look_through_tables_and_the_shares_sum_to_one():
    components = committed("risk_components.csv").set_index("component")
    regions = committed("lookthrough_equity_region.csv")
    maturities = committed("lookthrough_bonds_maturity.csv")
    cash = committed("allocation_now.csv").iloc[0]["weight_cash"]
    expected = risk.component_weights(regions, maturities, cash)
    assert np.allclose(components.loc[expected.index, "weight"], expected, atol=1e-9)
    assert components["weight"].sum() == pytest.approx(1, abs=1e-6)  # the issuers' holdings files round their weights
    assert components["risk_contribution"].sum() == pytest.approx(1, abs=1e-8)


def test_the_committed_portfolio_point_reproduces_from_the_look_through_weights():
    components = committed("risk_components.csv").set_index("component")
    pairs = committed("risk_correlation.csv")
    summary = committed("risk_summary.csv").iloc[0]
    names = [c for c in components.index if c != risk.CASH]
    rho = pairs.pivot(index="component_a", columns="component_b", values="correlation").loc[names, names].values
    vol = components.loc[names, "estimated_volatility"].values
    w = components.loc[names, "weight"].values
    assert np.sqrt(w @ (rho * np.outer(vol, vol)) @ w) == pytest.approx(summary["estimated_volatility"], abs=1e-8)
    assert w @ components.loc[names, "estimated_return"].values == pytest.approx(summary["estimated_return"], abs=1e-8)
    frontier = committed("risk_frontier.csv")
    current = frontier[frontier["window"] == "current"]
    assert current["estimated_volatility"].iloc[0] == pytest.approx(summary["minimum_variance_volatility"], abs=1e-8)
