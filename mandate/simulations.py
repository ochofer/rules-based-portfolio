"""Simulations on the allocation test's returns: the bootstrap of the test, and the rules on the 1999 to
2025 sample and on resampled paths.

The returns are those of allocation_check.py: monthly, in euro, February 1999 to December 2025, with no
costs. The script writes three tables, which the dashboard draws:

  mandate/simulation_bootstrap.csv  the worst fall of every split from 40/60 to 100/0 over resampled paths of
                                    10 and of 5 years, rebalanced by the band, with no contributions
  mandate/simulation_history.csv    the rules with a starting amount of 100 and a top-up of 5 a month, applied
                                    at each month end of the sample, beside the same split brought back to its
                                    target weights at each month end
  mandate/simulation_paths.csv      the value of the portfolio over resampled paths of 10 years from the first
                                    purchase, with the top-up and the rules, in units of the starting amount

A resampled path joins blocks of 12 consecutive months of the sample. Each block starts at any month and
wraps from December 2025 to February 1999, and one fixed seed draws the blocks, so a run gives the same
tables. The 10-year paths of the bootstrap and the paths of the portfolio's value are the same draws; the
5-year paths are their first 60 months.

Two checks run before anything is written, and the script stops if either fails. Applied to the sample as
it is, the bootstrap's code gives the allocation test's worst fall and growth per year for every split. The
rules without top-ups give the allocation test's path for 70/30.

Usage:   python3 mandate/simulations.py
Requires Python 3.9 or later, pandas and numpy, and the cached sources of allocation_check.py.
"""

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import allocation_check as ac  # noqa: E402

SEED = 20261009
PATHS = 10_000
BLOCK_MONTHS = 12
BLOCK_CHECKS = (6, 24, 36)  # block lengths of the check, for 70/30 over 10 years
HORIZONS = (10, 5)  # years: the main horizon, then the check
TARGET = 0.70
LIMITS = (0.35, 0.40)  # the mandate's test limit and its outer bound
START, TOP_UP = 100.0, 5.0  # units of the starting amount; rule 2 sets the top-up at 5 per cent of it
ORDER_BUDGET = 5  # rule 6
RESULTS = os.path.join(HERE, "allocation_check_results.csv")
OUT = {name: os.path.join(HERE, f"simulation_{name}.csv") for name in ("bootstrap", "history", "paths")}


def circular_draws(rng, months_in_sample, paths, months, block):
    """Indices of resampled paths: blocks of consecutive months, each starting at any month and wrapping
    around the end of the sample."""
    blocks = -(-months // block)
    starts = rng.integers(0, months_in_sample, size=(paths, blocks))
    index = (starts[:, :, None] + np.arange(block)) % months_in_sample
    return index.reshape(paths, blocks * block)[:, :months]


def band_paths(equity_returns, bond_returns, w):
    """Month-end values of portfolios started at 1 at the target weights and rebalanced by the band of
    rule 5, one row per path: the allocation test's band_path, for many paths at once."""
    equity, bonds = np.full(equity_returns.shape[0], w), np.full(equity_returns.shape[0], 1.0 - w)
    values = np.empty(equity_returns.shape)
    for m in range(equity_returns.shape[1]):
        equity = equity * (1 + equity_returns[:, m])
        bonds = bonds * (1 + bond_returns[:, m])
        total = equity + bonds
        outside = np.abs(equity / total - w) > ac.BAND_HALF_WIDTH
        equity = np.where(outside, w * total, equity)
        bonds = np.where(outside, (1 - w) * total, bonds)
        values[:, m] = total
    return values


def worst_falls(values, start=1.0):
    """The largest fall from a previous peak to a later month end, the starting value counted as a peak."""
    with_start = np.concatenate([np.full((values.shape[0], 1), start), values], axis=1)
    return -(with_start / np.maximum.accumulate(with_start, axis=1) - 1).min(axis=1)


def rules_paths(equity_returns, bond_returns, top_up):
    """The rules on many paths at once. The portfolio starts at 100 at the target weights. At each month end
    the top-up buys the sleeve furthest below its target weight up to that weight and the remainder buys the
    other sleeve (rule 4); then, if the equity weight is outside the band, the portfolio goes back to its
    target weights (rule 5), a band purchase and a top-up purchase of one sleeve being one order. Returns,
    per path and month end: the value before the top-up, the equity weight before the top-up and after the
    cycle, the orders and whether the band called for an order."""
    paths, months = equity_returns.shape
    equity, bonds = np.full(paths, START * TARGET), np.full(paths, START * (1 - TARGET))
    out = {key: np.empty((paths, months)) for key in ("value", "weight_before", "weight_after", "orders")}
    band = np.zeros((paths, months), dtype=bool)
    for m in range(months):
        equity = equity * (1 + equity_returns[:, m])
        bonds = bonds * (1 + bond_returns[:, m])
        out["value"][:, m] = equity + bonds
        out["weight_before"][:, m] = equity / (equity + bonds)
        total = equity + bonds + top_up
        buy_equity = np.clip(TARGET * total - equity, 0.0, top_up)
        buy_bonds = top_up - buy_equity
        orders = (buy_equity > 0).astype(int) + (buy_bonds > 0).astype(int)
        equity, bonds = equity + buy_equity, bonds + buy_bonds
        outside = np.abs(equity / (equity + bonds) - TARGET) > ac.BAND_HALF_WIDTH
        total = equity + bonds
        equity = np.where(outside, TARGET * total, equity)
        bonds = np.where(outside, (1 - TARGET) * total, bonds)
        out["orders"][:, m] = np.where(outside, 2, orders)
        out["weight_after"][:, m] = equity / (equity + bonds)
        band[:, m] = outside
    out["band"] = band
    return out


def every_cycle_day(equity_returns, bond_returns, top_up):
    """The same split brought back to its target weights at each month end, after the top-up: the rule of
    reference portfolio B. Returns the value before the top-up at each month end."""
    value, values = START, []
    for r_equity, r_bonds in zip(equity_returns, bond_returns):
        value = value * (TARGET * (1 + r_equity) + (1 - TARGET) * (1 + r_bonds))
        values.append(value)
        value = value + top_up
    return np.array(values)


def growth_of_100(before_top_up, top_up):
    """Time-weighted growth of 100 from month-end values taken before each top-up."""
    previous = np.concatenate([[START], before_top_up[:-1] + top_up])
    return 100 * np.cumprod(before_top_up / previous)


def check_against_the_allocation_test(returns):
    """Stop unless the code reproduces the allocation test on the sample as it is."""
    results = pd.read_csv(RESULTS)
    equity_returns = returns["equity"].values[None, :]
    bond_returns = returns["bonds"].values[None, :]
    years = len(returns) / 12
    for row in results.itertuples():
        values = band_paths(equity_returns, bond_returns, row.equity_weight)
        fall = worst_falls(values)[0]
        growth = values[0, -1] ** (1 / years) - 1
        if abs(fall - row.worst_fall) > 5e-7 or abs(growth - row.growth_per_year) > 5e-7:
            raise SystemExit(
                f"The bootstrap's code does not reproduce the allocation test for {row.split}: worst fall "
                f"{fall:.6f} against {row.worst_fall:.6f}, growth per year {growth:.6f} against "
                f"{row.growth_per_year:.6f}. Nothing was written."
            )
    test_path = ac.band_path(returns, TARGET).values
    no_top_up = rules_paths(equity_returns, bond_returns, 0.0)
    band = band_paths(equity_returns, bond_returns, TARGET)[0]
    if not (
        np.allclose(no_top_up["value"][0] / START, test_path, rtol=1e-12, atol=0)
        and np.allclose(band, test_path, rtol=1e-12, atol=0)
    ):
        raise SystemExit(
            "The rules without top-ups do not give the allocation test's path for 70/30. Nothing was written."
        )


def bootstrap_table(returns, main_draws, rng):
    equity, bonds = returns["equity"].values, returns["bonds"].values
    one_path = {}
    for w in ac.EQUITY_GRID:
        one_path[w] = worst_falls(band_paths(equity[None, :], bonds[None, :], w))[0]
    rows = []

    def row(horizon, block, w, falls):
        return {
            "horizon_years": horizon,
            "block_months": block,
            "paths": len(falls),
            "split": f"{round(w * 100)}/{round((1 - w) * 100)}",
            "equity_weight": w,
            "worst_fall_one_path": one_path[w],
            "median_worst_fall": float(np.median(falls)),
            "p95_worst_fall": float(np.quantile(falls, 0.95)),
            "share_above_35": float(np.mean(falls > LIMITS[0])),
            "share_above_40": float(np.mean(falls > LIMITS[1])),
        }

    for horizon in HORIZONS:
        draws = main_draws[:, : horizon * 12]
        for w in ac.EQUITY_GRID:
            rows.append(
                row(horizon, BLOCK_MONTHS, w, worst_falls(band_paths(equity[draws], bonds[draws], w)))
            )
    for block in BLOCK_CHECKS:
        draws = circular_draws(rng, len(returns), PATHS, HORIZONS[0] * 12, block)
        rows.append(
            row(HORIZONS[0], block, TARGET, worst_falls(band_paths(equity[draws], bonds[draws], TARGET)))
        )
    return pd.DataFrame(rows)


def history_table(returns):
    equity, bonds = returns["equity"].values, returns["bonds"].values
    rules = rules_paths(equity[None, :], bonds[None, :], TOP_UP)
    growth = growth_of_100(rules["value"][0], TOP_UP)
    calendar = growth_of_100(every_cycle_day(equity, bonds, TOP_UP), TOP_UP)
    start = pd.DataFrame(
        [
            {
                "month": str(returns.index[0] - 1),
                "equity_weight_before_top_up": TARGET,
                "equity_weight_after_cycle": TARGET,
                "orders": np.nan,
                "band_order": "",
                "growth_rules": 100.0,
                "drawdown_rules": 0.0,
                "growth_every_cycle_day": 100.0,
                "drawdown_every_cycle_day": 0.0,
            }
        ]
    )
    frame = pd.DataFrame(
        {
            "month": [str(p) for p in returns.index],
            "equity_weight_before_top_up": rules["weight_before"][0],
            "equity_weight_after_cycle": rules["weight_after"][0],
            "orders": rules["orders"][0],
            "band_order": np.where(rules["band"][0], "yes", "no"),
            "growth_rules": growth,
            "drawdown_rules": growth / np.maximum.accumulate(np.concatenate([[100.0], growth]))[1:] - 1,
            "growth_every_cycle_day": calendar,
            "drawdown_every_cycle_day": calendar
            / np.maximum.accumulate(np.concatenate([[100.0], calendar]))[1:]
            - 1,
        }
    )
    frame = pd.concat([start, frame], ignore_index=True)
    if frame["orders"].max() > ORDER_BUDGET:
        raise SystemExit(
            "A cycle day needs more orders than the budget of rule 6; the simulation does not model the wait."
        )
    return frame


def paths_table(returns, main_draws):
    equity, bonds = returns["equity"].values, returns["bonds"].values
    draws = main_draws[:, : HORIZONS[0] * 12]
    values = rules_paths(equity[draws], bonds[draws], TOP_UP)["value"]
    values = np.concatenate([np.full((values.shape[0], 1), START), values], axis=1)
    months = np.arange(values.shape[1])
    quantiles = np.quantile(values, [0.05, 0.25, 0.5, 0.75, 0.95], axis=0)
    return pd.DataFrame(
        {
            "month": months,
            "years": months / 12,
            "paid_in": START + TOP_UP * np.maximum(months - 1, 0),
            "p05": quantiles[0],
            "p25": quantiles[1],
            "p50": quantiles[2],
            "p75": quantiles[3],
            "p95": quantiles[4],
        }
    )


def write(frame, path, decimals):
    frame = frame.copy()
    for column in frame.columns:
        if pd.api.types.is_float_dtype(frame[column]):
            frame[column] = frame[column].round(decimals) + 0.0
    frame.to_csv(path, index=False, float_format="%.10g", lineterminator="\n")


def main():
    returns, _ = ac.monthly_returns()
    check_against_the_allocation_test(returns)
    rng = np.random.default_rng(SEED)
    main_draws = circular_draws(rng, len(returns), PATHS, max(HORIZONS) * 12, BLOCK_MONTHS)
    bootstrap = bootstrap_table(returns, main_draws, rng)
    history = history_table(returns)
    paths = paths_table(returns, main_draws)
    write(bootstrap, OUT["bootstrap"], 6)
    write(history, OUT["history"], 6)
    write(paths, OUT["paths"], 4)
    main_row = bootstrap[(bootstrap["horizon_years"] == 10) & (bootstrap["block_months"] == BLOCK_MONTHS)
                         & (bootstrap["split"] == "70/30")].iloc[0]  # fmt: skip
    print(
        f"Checks passed: the code reproduces the allocation test. {PATHS} paths, blocks of {BLOCK_MONTHS} months, seed {SEED}."
    )
    print(
        f"70/30 over 10 years: median worst fall {main_row.median_worst_fall:.1%}, 95th percentile "
        f"{main_row.p95_worst_fall:.1%}, above 35% {main_row.share_above_35:.1%}, above 40% {main_row.share_above_40:.1%}."
    )
    print(
        f"Mechanics on the sample: {int((history['band_order'] == 'yes').sum())} band orders in {len(history) - 1} cycle days."
    )
    print("Written: " + ", ".join(os.path.relpath(p, os.path.dirname(HERE)) for p in OUT.values()))


if __name__ == "__main__":
    main()
