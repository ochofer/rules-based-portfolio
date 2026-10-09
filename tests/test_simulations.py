"""The simulations of mandate/simulations.py, on simulated returns: the same engine as the allocation test and
as the program's rules engine."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mandate"))
import allocation_check as ac  # noqa: E402
import simulations as sim  # noqa: E402

from portfolio import rules_engine  # noqa: E402


def simulated_returns(months=120, seed=1):
    rng = np.random.default_rng(seed)
    index = pd.period_range("2000-01", periods=months, freq="M")
    return pd.DataFrame(
        {"equity": rng.normal(0.006, 0.05, months), "bonds": rng.normal(0.003, 0.015, months)}, index=index
    )


def test_a_block_wraps_around_the_end_of_the_sample():
    draws = sim.circular_draws(np.random.default_rng(0), 7, paths=200, months=9, block=3)
    assert draws.shape == (200, 9)
    for row in draws:
        for start in range(0, 9, 3):
            block = row[start : start + 3]
            assert list(block) == [(block[0] + k) % 7 for k in range(3)]
    assert (draws[:, 0] == 6).any()


def test_the_band_engine_is_the_allocation_test_on_one_path():
    returns = simulated_returns()
    for w in (0.4, 0.7, 1.0):
        values = sim.band_paths(returns["equity"].values[None, :], returns["bonds"].values[None, :], w)[0]
        assert np.allclose(values, ac.band_path(returns, w).values, rtol=1e-12, atol=0)


def test_the_worst_fall_counts_the_starting_value_as_a_peak():
    assert sim.worst_falls(np.array([[0.8, 0.9, 1.1, 0.99]]))[0] == pytest.approx(0.2)


def test_the_rules_without_top_ups_follow_the_band_engine():
    returns = simulated_returns()
    e, b = returns["equity"].values[None, :], returns["bonds"].values[None, :]
    rules = sim.rules_paths(e, b, 0.0)
    assert np.allclose(rules["value"][0] / sim.START, sim.band_paths(e, b, sim.TARGET)[0], rtol=1e-12, atol=0)


def test_the_rules_with_top_ups_give_the_orders_of_the_rules_engine():
    # The program's rules engine works in euro and rounds to cents, so the comparison runs at a scale where
    # the cents do not matter.
    returns = simulated_returns(months=60, seed=3)
    rules = sim.rules_paths(returns["equity"].values[None, :], returns["bonds"].values[None, :], sim.TOP_UP)
    scale = 1000.0
    equity, bonds, cash = sim.START * sim.TARGET * scale, sim.START * (1 - sim.TARGET) * scale, 0.0
    for m, (r_equity, r_bonds) in enumerate(zip(returns["equity"], returns["bonds"])):
        equity, bonds = equity * (1 + r_equity), bonds * (1 + r_bonds)
        plan = rules_engine.plan(equity, bonds, cash + sim.TOP_UP * scale)
        assert len(plan.orders) == rules["orders"][0, m]
        assert plan.band_triggered == rules["band"][0, m]
        equity, bonds, cash = plan.after["equity"], plan.after["bonds"], plan.after["cash"]
        assert equity / (equity + bonds) == pytest.approx(rules["weight_after"][0, m], abs=1e-6)


def test_growth_of_100_removes_the_top_ups():
    before = np.array([110.0, 120.0])  # 100 grows 10 per cent, a top-up of 5 makes 115, which grows to 120
    assert sim.growth_of_100(before, 5.0)[-1] == pytest.approx(100 * 1.10 * 120 / 115)
