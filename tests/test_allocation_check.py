"""The allocation test reproduces from its script: the global table byte for byte, and the US run beside it,
which has the same columns and chooses nothing."""

import sys
from pathlib import Path

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
