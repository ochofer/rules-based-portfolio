"""The allocation test reproduces from its script: the global table byte for byte, and the US run beside it,
which has the same columns and chooses nothing."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mandate"))
import allocation_check as ac  # noqa: E402

GLOBAL = ("developed.zip", "emerging.zip", "ecb_usd_per_eur.csv", "ecb_10y.csv", "ecb_7y.csv")


def cached(*names):
    missing = [n for n in names if not (Path(ac.CACHE) / n).exists()]
    if missing:
        pytest.skip("the allocation test's sources are not in cache/: " + ", ".join(missing))


def test_the_global_results_file_reproduces_exactly():
    cached(*GLOBAL)
    returns, _ = ac.monthly_returns()
    rows = ac.split_rows(returns)
    text = ac.csv_text(ac.results_table(rows, ac.largest_within(rows)))
    assert text == (ROOT / "mandate" / "allocation_check_results.csv").read_text(encoding="utf-8")


def test_the_us_run_uses_the_same_bonds_and_months_and_chooses_nothing():
    cached(*GLOBAL, "us_market.zip")
    returns, _ = ac.monthly_returns()
    us, _ = ac.us_returns(returns)
    assert list(us.index) == list(returns.index) and (us["bonds"] == returns["bonds"]).all()
    text = ac.csv_text(ac.results_table(ac.split_rows(us), None))
    assert text == (ROOT / "mandate" / "allocation_check_us_results.csv").read_text(encoding="utf-8")
    header = (ROOT / "mandate" / "allocation_check_results.csv").read_text(encoding="utf-8").splitlines()[0]
    assert text.splitlines()[0] == header
    assert all(line.endswith(",no") for line in text.splitlines()[1:])


def test_the_split_gap_holds_the_two_splits_growth_and_the_bootstrap_of_their_gap():
    gap = pd.read_csv(ROOT / "mandate" / "allocation_check_split_gap.csv").iloc[0]
    results = pd.read_csv(ROOT / "mandate" / "allocation_check_results.csv").set_index("split")
    assert (gap["first_split"], gap["second_split"], gap["months"]) == ("100/0", "40/60", 323)
    assert gap["first_split_growth_per_year"] == pytest.approx(results.loc["100/0", "growth_per_year"], abs=1e-6)
    assert gap["second_split_growth_per_year"] == pytest.approx(results.loc["40/60", "growth_per_year"], abs=1e-6)
    assert gap["gap_per_year"] == pytest.approx(gap["first_split_growth_per_year"] - gap["second_split_growth_per_year"], abs=2e-6)
    assert gap["mean_difference_standard_error_independent_months"] == pytest.approx(
        gap["difference_standard_deviation_per_year"] / (323 / 12) ** 0.5, abs=2e-6)
    assert (gap["block_months"], gap["draws"], gap["seed"]) == (ac.GAP_BLOCK_MONTHS, ac.GAP_DRAWS, ac.GAP_SEED)
    assert gap["gap_lower_95"] < gap["gap_per_year"] < gap["gap_upper_95"]
    assert not {"standard_error", "lower_bound", "upper_bound"} & set(gap.index)


def test_the_split_gap_bootstrap_resamples_paired_months_in_circular_blocks():
    # Two splits on the same returns pair every month with itself: every resample gives a gap of zero, so the
    # standard error is zero and the interval closes on zero. The draws are the same on every run.
    months = pd.period_range("2000-01", periods=60, freq="M")
    rng = np.random.default_rng(3)
    equity = pd.Series(rng.normal(0.006, 0.04, 60), index=months)
    gap = ac.split_gap(pd.DataFrame({"equity": equity, "bonds": equity}), 1.0, 0.0).iloc[0]
    assert gap["gap_standard_error"] == pytest.approx(0.0, abs=1e-12)
    assert gap["gap_lower_95"] == pytest.approx(0.0, abs=1e-12) and gap["gap_upper_95"] == pytest.approx(0.0, abs=1e-12)
    noisy = pd.DataFrame({"equity": equity, "bonds": rng.normal(0.002, 0.01, 60)}, index=months)
    once, again = ac.split_gap(noisy, 1.0, 0.4), ac.split_gap(noisy, 1.0, 0.4)
    assert once["gap_standard_error"].iloc[0] > 0 and once.equals(again)


def test_the_settings_table_holds_the_grid_and_the_shares_for_2002_and_1997():
    table = pd.read_csv(ROOT / "mandate" / "allocation_check_settings.csv")
    results = pd.read_csv(ROOT / "mandate" / "allocation_check_results.csv").set_index("split")
    assert len(table) == 24
    grid = table[table["added_with"] == "grid added after its outcome was known"]
    assert sorted(set(grid["emerging_share"])) == list(ac.SETTINGS_EMERGING_SHARES)
    assert sorted(set(grid["bond_maturity_years"])) == list(ac.SETTINGS_BOND_MATURITIES) and len(grid) == 16
    for year, share in ((2002, ac.SETTINGS_SOURCED_SHARE), (1997, ac.SETTINGS_SOURCED_SHARE_1997)):
        sourced = table[table["added_with"] == f"MSCI's share for {year}"]
        assert set(sourced["emerging_share"]) == {share} and len(sourced) == 4
    # The row at the test's own settings is the test: the same worst falls as the results table.
    own = table[table["test_settings"] == "yes"]
    assert len(own) == 1 and (own["emerging_share"].iloc[0], own["bond_maturity_years"].iloc[0]) == (0.10, 7.0)
    assert own["worst_fall_70_30"].iloc[0] == pytest.approx(results.loc["70/30", "worst_fall"], abs=1e-6)
    assert own["worst_fall_65_35"].iloc[0] == pytest.approx(results.loc["65/35", "worst_fall"], abs=1e-6)
    assert own["largest_split_within_limit"].iloc[0] == "70/30"
    # The largest split within the limit follows from the two worst falls the table gives.
    for _, r in table.iterrows():
        if r["worst_fall_70_30"] <= ac.RISK_LIMIT:
            assert r["largest_split_within_limit"] in ("70/30", "75/25", "80/20")
        elif r["worst_fall_65_35"] <= ac.RISK_LIMIT:
            assert r["largest_split_within_limit"] == "65/35"


def test_the_turning_share_lies_between_the_two_sourced_shares_and_meets_the_limit():
    turning = pd.read_csv(ROOT / "mandate" / "allocation_check_settings_turning.csv").set_index("bond_maturity_years")
    assert list(turning.index) == list(ac.TURNING_MATURITIES)
    for maturity, row in turning.iterrows():
        assert ac.SETTINGS_SOURCED_SHARE < row["turning_share"] <= ac.SETTINGS_SOURCED_SHARE_1997
        assert row["worst_fall_70_30"] == pytest.approx(ac.RISK_LIMIT, abs=1e-5)
    assert turning.loc[7.0, "turning_share"] < turning.loc[6.7, "turning_share"]


def test_the_turning_share_reproduces_exactly_and_brackets_the_limit():
    cached(*GLOBAL)
    text = ac.turning_shares().to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_settings_turning.csv").read_text(encoding="utf-8")
    for maturity, share in zip(ac.TURNING_MATURITIES, ac.turning_shares()["turning_share"]):
        fall = lambda s: ac.worst_fall(ac.band_path(ac.monthly_returns(s, maturity)[0], 0.70))[0]  # noqa: E731
        assert fall(share) <= ac.RISK_LIMIT < fall(share - 2 * ac.TURNING_INTERVAL)


def test_the_mandate_the_readme_and_the_guide_give_the_settings_tables_figures():
    table = pd.read_csv(ROOT / "mandate" / "allocation_check_settings.csv")
    turning = pd.read_csv(ROOT / "mandate" / "allocation_check_settings_turning.csv").set_index("bond_maturity_years")
    late = table[table["added_with"] == "MSCI's share for 2002"].set_index("bond_maturity_years")
    early = table[table["added_with"] == "MSCI's share for 1997"].set_index("bond_maturity_years")
    within = int((table["worst_fall_70_30"] <= ac.RISK_LIMIT).sum())
    mandate = (ROOT / "mandate" / "MANDATE.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "guide" / "source.md").read_text(encoding="utf-8")
    assert set(late.loc[[7.0, 6.7], "largest_split_within_limit"]) == {"65/35"}
    assert set(early.loc[[7.0, 6.7], "largest_split_within_limit"]) == {"70/30"}
    figures = lambda t: f"({t.loc[7.0, 'worst_fall_70_30'] * 100:.2f} and {t.loc[6.7, 'worst_fall_70_30'] * 100:.2f} per cent)"  # noqa: E731
    assert figures(late) in mandate and figures(early) in mandate
    turns = (f"answer turns at a share of {turning.loc[7.0, 'turning_share'] * 100:.1f} per cent at 7 years and "
             f"{turning.loc[6.7, 'turning_share'] * 100:.1f} at 6.7")
    for text in (mandate, readme, guide):
        assert turns in text and "so on MSCI's own figures the test does not decide between 70/30 and 65/35" in text
        assert "The target is 70/30 and has not been amended. A change would be an amendment under rule 9." in text
        assert "At the share of emerging markets MSCI reports for 2002" not in text
    assert f"Over the {len(table)} settings of `mandate/allocation_check_settings.csv`, 70/30 stays within 35 per cent in {within}." in mandate
    assert f"in {within} of the {len(table)}" in mandate
    assert f"from {table['worst_fall_70_30'].min() * 100:.1f} to {table['worst_fall_70_30'].max() * 100:.1f} per cent" in mandate
    assert f"Over the {len(table)} settings of that table 70/30 stays within 35 per cent in {within}." in readme
    assert f"the test at the {len(table)} settings of `mandate/allocation_check_settings.csv`" in guide


def test_the_settings_table_reproduces_exactly():
    cached(*GLOBAL)
    text = ac.settings_grid().to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_settings.csv").read_text(encoding="utf-8")


def test_the_split_gap_file_reproduces_exactly():
    cached(*GLOBAL)
    returns, _ = ac.monthly_returns()
    text = ac.split_gap(returns).to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_split_gap.csv").read_text(encoding="utf-8")
