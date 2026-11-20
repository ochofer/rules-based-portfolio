"""The allocation test reproduces from its script: the global table byte for byte, the US run beside it, which has
the same columns and chooses nothing, the comparison with MSCI's series and the bond's maturities, and the tables of
the test as it stood until 19 November 2026."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mandate"))
import allocation_check as ac  # noqa: E402

ECB = ("ecb_usd_per_eur.csv", "ecb_10y.csv", "ecb_7y.csv")
GLOBAL = ("north_america.zip", "europe.zip", "japan.zip", "asia_pacific_ex_japan.zip", "emerging.zip") + ECB
EARLIER = ("developed.zip", "emerging.zip") + ECB  # the equity series as it stood until 19 November 2026
MSCI = tuple(f"msci_{code}_{variant}.json" for code in ("990200", "990500", "990800", "891800", "892400")
             for variant in ("strd", "netr", "grtr"))


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
    # The row at the earlier test's own settings is that test: 34.7 per cent at 70/30, as rules/RULES.md gives it.
    own = table[table["test_settings"] == "yes"]
    assert len(own) == 1 and (own["emerging_share"].iloc[0], own["bond_maturity_years"].iloc[0]) == (0.10, 7.0)
    assert round(own["worst_fall_70_30"].iloc[0] * 100, 1) == 34.7
    assert own["largest_split_within_limit"].iloc[0] == "70/30"
    assert "70/30" in results.index
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
    cached(*EARLIER)
    text = ac.turning_shares().to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_settings_turning.csv").read_text(encoding="utf-8")
    for maturity, share in zip(ac.TURNING_MATURITIES, ac.turning_shares()["turning_share"]):
        fall = lambda s: ac.worst_fall(ac.band_path(ac.fixed_share_returns(s, maturity)[0], 0.70))[0]  # noqa: E731
        assert fall(share) <= ac.RISK_LIMIT < fall(share - 2 * ac.TURNING_INTERVAL)


def test_the_mandate_the_readme_and_the_guide_give_the_comparison_s_figures():
    comparison = pd.read_csv(ROOT / "mandate" / "allocation_check_comparison.csv")
    maturities = pd.read_csv(ROOT / "mandate" / "allocation_check_maturities.csv").set_index("bond_maturity_years")
    results = pd.read_csv(ROOT / "mandate" / "allocation_check_results.csv").set_index("split")
    deciding = comparison[comparison["role"] == "deciding"].iloc[0]
    net = comparison[(comparison["role"] == "comparison") & comparison["series"].str.startswith("MSCI's")]
    acwi = comparison[comparison["series"].str.startswith("MSCI ACWI")]
    span = lambda rows: f"{rows['worst_fall_70_30'].min() * 100:.2f} to {rows['worst_fall_70_30'].max() * 100:.2f}"  # noqa: E731
    assert deciding["worst_fall_70_30"] == pytest.approx(results.loc["70/30", "worst_fall"], abs=1e-6)
    assert maturities.loc[7.0, "worst_fall_70_30"] == pytest.approx(results.loc["70/30", "worst_fall"], abs=1e-6)
    mandate = (ROOT / "mandate" / "MANDATE.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "guide" / "source.md").read_text(encoding="utf-8")
    assert f"70/30 fell {span(acwi)} per cent, above the test's line of 35" in mandate
    assert f"| {span(net).replace(' to ', '% to ')}% | 65/35 |" in mandate
    assert f"{results.loc['70/30', 'worst_fall'] * 100:.2f} per cent on the deciding series" in readme
    assert f"MSCI's regional net returns at the same weights 70/30 fell {span(net)} per cent" in guide
    figures = ", ".join(f"{maturities.loc[m, 'worst_fall_70_30'] * 100:.2f}" for m in (5.0, 6.7)) + " and "
    assert f"70/30's worst fall is {figures}{maturities.loc[9.0, 'worst_fall_70_30'] * 100:.2f} per cent" in mandate
    gross = comparison[comparison["role"] == "measure of the tax on dividends"]
    assert f"it is {span(gross)} per cent and the test still gives 65/35" in mandate
    assert set(gross["largest_split_within_limit"]) == {"65/35"}
    for text in (mandate, readme, guide):
        assert "so on MSCI's own figures the test does not decide" not in text
        assert "has not been amended" not in text


def test_the_comparison_and_the_maturities_reproduce_exactly_and_choose_nothing():
    cached(*GLOBAL, *MSCI)
    _, french, msci, _ = ac.read_region_weights()
    returns, _ = ac.monthly_returns()
    text = ac.comparison(returns, msci).to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_comparison.csv").read_text(encoding="utf-8")
    text = ac.maturity_table(french).to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_maturities.csv").read_text(encoding="utf-8")
    table = pd.read_csv(ROOT / "mandate" / "allocation_check_comparison.csv")
    assert list(table["role"]).count("deciding") == 1 and len(table) == 7


def test_the_regional_weights_sum_to_one_and_name_what_french_s_lists_leave_out():
    _, french, msci, table = ac.read_region_weights()
    assert french.sum() == pytest.approx(1.0) and msci.sum() == pytest.approx(1.0)
    assert list(french.index) == [name for name, _ in ac.REGIONS]
    left_out = set(table.loc[table["french_region"] == "none", "country"])
    assert left_out == {"Israel", "Russia", "Cash and derivatives"}
    assert table.loc[table["country"] == "Greece", "french_region"].iloc[0] == "Emerging markets"
    assert table["share_of_fund"].sum() == pytest.approx(1.0, abs=1e-5)


def test_run_at_gives_the_test_at_the_committed_weights():
    cached(*GLOBAL, *MSCI)
    table = pd.read_csv(ac.REGION_WEIGHTS, keep_default_na=False)
    row = ac.run_at(table)
    results = pd.read_csv(ROOT / "mandate" / "allocation_check_results.csv").set_index("split")
    assert row["worst_fall_70_30"] == pytest.approx(results.loc["70/30", "worst_fall"], abs=1e-6)
    assert row["largest_split"] == results[results["chosen"] == "yes"].index[0]
    assert row["msci_regions_worst_fall_70_30_low"] < row["msci_regions_worst_fall_70_30_high"]
    assert sum(row[f"weight_{key}"] for _, key in ac.REGIONS) == pytest.approx(1.0)


def test_the_settings_table_reproduces_exactly():
    cached(*EARLIER)
    text = ac.settings_grid().to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_settings.csv").read_text(encoding="utf-8")


def test_the_split_gap_file_reproduces_exactly():
    cached(*GLOBAL)
    returns, _ = ac.monthly_returns()
    text = ac.split_gap(returns).to_csv(index=False, float_format="%.6f", lineterminator="\n")
    assert text == (ROOT / "mandate" / "allocation_check_split_gap.csv").read_text(encoding="utf-8")


def _weights():
    return pd.read_csv(ROOT / "mandate" / "allocation_check_weights.csv", keep_default_na=False)


def test_the_weights_table_holds_its_three_cases():
    w = _weights()
    back, shift, scan = (w[w["case"] == c] for c in ("rolled back", "shift", "North America"))
    assert (len(back), len(shift), len(scan)) == (202, 20, 501)
    assert (back["month_end"].iloc[0], back["month_end"].iloc[-1]) == ("2026-09", ac.ROLLBACK_FROM)
    columns = [f"weight_{key}" for _, key in ac.REGIONS]
    assert np.allclose(w[columns].sum(axis=1), 1.0, atol=1e-5)
    _, french, _, _ = ac.read_region_weights()
    assert np.allclose(back[columns].iloc[0].to_numpy(), french.to_numpy(), atol=1e-6)
    results = pd.read_csv(ROOT / "mandate" / "allocation_check_results.csv").set_index("split")
    assert back["worst_fall_70_30"].iloc[0] == pytest.approx(results.loc["70/30", "worst_fall"], abs=1e-6)
    assert set(back["largest_split_within_limit"]) == {"70/30"} and set(scan["largest_split_within_limit"]) == {"70/30"}
    assert (w["months_back_to_target_70_30"] == w["months_back_to_target_70_30_list"].str.split().str.len()).all()
    changed = shift[shift["largest_split_within_limit"] != "70/30"]
    assert sorted(zip(changed["shift_from"], changed["shift_to"], pd.to_numeric(changed["shift_points"]).round(1))) == [
        ("Emerging markets", "Japan", 4.3), ("Europe", "Japan", 6.9)]
    assert (changed["worst_fall_70_30"] > ac.RISK_LIMIT).all()
    assert set(changed["every_larger_shift_changes_the_split"]) == {"yes", "no"}
    assert set(shift.loc[shift["largest_split_within_limit"] == "70/30", "every_larger_shift_changes_the_split"]) == {""}


def test_the_weights_table_rows_reproduce():
    cached(*GLOBAL)
    w = _weights()
    frame = pd.DataFrame({name: ac.french_market(key)[0] for name, key in ac.REGIONS})
    currency, _ = ac.currency_factor()
    bonds, _, _ = ac.bond_returns(ac.BOND_MATURITY)
    scan = w[w["case"] == "North America"]
    picked = pd.concat([w[w["case"] == "rolled back"].iloc[[1, -1]], w[w["shift_to"] == "Japan"].iloc[[1, 3]],
                        scan[scan["weight_north_america"].round(4).isin([0.6930, 0.6935])]])
    for row in picked.to_dict("records"):
        weights = pd.Series({name: row[f"weight_{key}"] for name, key in ac.REGIONS})
        falls = ac._falls_at(frame, currency, bonds, weights)
        for column in ("worst_fall_65_35", "worst_fall_70_30", "worst_fall_75_25"):
            assert falls[column] == pytest.approx(row[column], abs=2e-6)
        assert (falls["largest_split_within_limit"], falls["months_back_to_target_70_30_list"]) == (
            row["largest_split_within_limit"], row["months_back_to_target_70_30_list"])
    jump = scan.set_index(scan["weight_north_america"].round(4))
    assert (round(jump.loc[0.6930, "worst_fall_70_30"] * 100, 2), round(jump.loc[0.6935, "worst_fall_70_30"] * 100, 2)) == (34.60, 33.73)


def test_the_rules_and_the_mandate_give_the_weights_table_s_figures():
    w = _weights()
    back = w[w["case"] == "rolled back"]
    rules = (ROOT / "rules" / "RULES.md").read_text(encoding="utf-8")
    mandate = (ROOT / "mandate" / "MANDATE.md").read_text(encoding="utf-8")
    low, high = back["worst_fall_70_30"].min() * 100, back["worst_fall_70_30"].max() * 100
    for text in (rules, mandate):
        assert f"give 70/30 at all {len(back)} month ends, with 70/30's worst fall from {low:.2f} to {high:.2f} per cent" in text
        assert "In steps of a tenth of a point, the smallest shift between two regions that gives 65/35 is 4.3 points from emerging markets to Japan" in text
    assert "with North America at 69.30 per cent and the other regions in proportion, 70/30's worst fall is 34.60 per cent, and at 69.35 it is 33.73" in mandate


def test_the_digest_follows_its_recipe():
    values = pd.Series([1.1789, 3.3673445774076236], index=pd.PeriodIndex(["1999-01", "1999-02"], freq="M"))
    text = "1999-01,1.17890000\n1999-02,3.36734458\n"
    assert ac.ecb_digest(values) == __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()


def test_a_changed_value_of_the_ecb_s_series_is_found(monkeypatch):
    cached(*ECB)
    assert ac.ecb_as_committed()
    original = ac.ecb_series

    def altered(month):
        def series(name):
            values = original(name).copy()
            if name == "ecb_10y":
                values.loc[month] = values.loc[month] + 1e-6
            return values
        return series

    monkeypatch.setattr(ac, "ecb_series", altered("2001-06"))  # a month the test reads
    assert not ac.ecb_as_committed()
    monkeypatch.setattr(ac, "ecb_series", altered("2015-06"))  # a month it does not: the spot rate prices the bond then
    assert ac.ecb_as_committed()


def test_the_files_table_holds_french_s_five_files_and_the_ecb_s_three_series():
    files = pd.read_csv(ROOT / "mandate" / "allocation_check_files.csv", dtype=str, keep_default_na=False)
    assert list(files.columns) == ac.FILE_COLUMNS
    assert list(files["source"]) == [ac.FRENCH_SOURCE] * 5 + [ac.ECB_SOURCE] * 3
    ecb = files[files["source"] == ac.ECB_SOURCE].set_index("file")
    assert ecb.loc["EXR/D.USD.EUR.SP00.A", ["values_read", "first_period", "last_period"]].tolist() == ["324", "1999-01", "2025-12"]
    assert all(len(h) == 64 for h in files["sha256"])


def test_the_fund_documents_name_the_two_funds_of_the_fund_check():
    documents = pd.read_csv(ROOT / "mandate" / "allocation_check_fund_documents.csv", dtype=str)
    assert list(documents["isin"]) == ["LU1829220216", "IE00BH04GL39"]
    for row, key in zip(documents.itertuples(), ("equity", "bonds")):
        assert row.isin in ac.FUND_CHECK[key][0] and row.page.isdigit() and len(row.sha256) == 64
        assert row.address.startswith("https://") and pd.Timestamp(row.as_at) <= pd.Timestamp(row.downloaded)
        assert ac.FUND_CHECK[key][0].startswith(row.fund)
    text = (ROOT / "mandate" / "allocation_check_results.md").read_text(encoding="utf-8")
    assert ac.fund_documents_text() in text
