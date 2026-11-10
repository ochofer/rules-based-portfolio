"""The comparisons, on invented net asset values and an invented rate."""

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from conftest import BD, EQ, contribution, order
from portfolio import comparisons, ledger, metrics, positions, references, valuations

END = date(2026, 12, 4)


def _navs():
    days = pd.bdate_range("2026-10-07", "2026-12-04")
    rng = np.random.default_rng(7)
    equity = 10 * np.cumprod(1 + rng.normal(0.0004, 0.009, len(days)))
    bonds = 3 * np.cumprod(1 + rng.normal(0.0001, 0.002, len(days)))
    frame = pd.DataFrame({"equity": equity, "bonds": bonds}, index=days)
    frame["usd_per_eur"] = 1.10 * np.cumprod(1 + rng.normal(0, 0.003, len(days)))
    frame["rate_carried"] = False
    return frame


@pytest.fixture
def record(write_ledger):
    navs = _navs()
    first = pd.Timestamp("2026-10-08")
    # The portfolio pays a little above the net asset value, so its return differs from reference portfolio A's.
    rows = [order("2026-10-08", "16:00:00", EQ, "buy", f"{700 / (navs.loc[first, 'equity'] * 1.002):.10f}",
                  f"{navs.loc[first, 'equity'] * 1.002:.6f}"),
            order("2026-10-08", "16:01:00", BD, "buy", f"{299 / (navs.loc[first, 'bonds'] * 1.001):.10f}",
                  f"{navs.loc[first, 'bonds'] * 1.001:.6f}")]  # fmt: skip
    t, c = write_ledger(rows, [contribution("2026-10-08", "before 15:59:00", 1000, "start"),
                               contribution("2026-11-02", "09:00", 50, "top-up"),
                               contribution("2026-12-01", "09:00", 50, "top-up")])  # fmt: skip
    records = ledger.read(t, c)
    values = valuations.build(positions.build(records, END), navs)
    base = metrics.base_day(records, navs)
    ref_a = references.simulate(records, navs, END, "rules")
    ref_b = references.simulate(records, navs, END, "calendar")
    table = metrics.daily(records, values, ref_a, ref_b, pd.Series(dtype=float), base)
    rate = pd.Series([3.6, 3.6, 3.24], index=pd.to_datetime(["2026-10-01", "2026-10-30", "2026-11-16"]))
    return {"records": records, "navs": navs, "values": values, "table": table, "ref_a": ref_a, "ref_b": ref_b,
            "rate": rate}  # fmt: skip


def _build(r, blend=None):
    blend = pd.Series(dtype=float) if blend is None else blend
    return comparisons.build(r["records"], r["navs"], r["values"], r["table"], r["ref_a"], r["ref_b"], blend, r["rate"], END)


def test_the_bands_of_the_other_splits():
    assert comparisons.split_band(0.6) == (0.55, 0.65) and comparisons.split_band(1.0) == (0.95, 1.0)
    assert comparisons.split_target(0.8) == {"equity": 0.8, "bonds": 0.2}


def test_the_rules_around_70_30_give_reference_portfolio_a(record):
    same = references.simulate(record["records"], record["navs"], END, "rules", comparisons.split_target(0.7),
                               comparisons.split_band(0.7))  # fmt: skip
    pd.testing.assert_frame_equal(same, record["ref_a"])


def test_savings_accrue_on_every_calendar_day_over_360(record):
    days = pd.to_datetime(["2026-10-08", "2026-10-09", "2026-10-12"])
    value = comparisons.savings(record["records"], pd.Series([3.6], index=pd.to_datetime(["2026-10-01"])), days)["value"]
    assert value.iloc[0] == 1000
    assert value.iloc[1] == pytest.approx(1000 * 1.0001)
    assert value.iloc[2] == pytest.approx(1000 * 1.0001**4)  # Friday to Monday is three days


def test_the_band_is_two_tracking_errors_times_the_square_root_of_the_years():
    days = pd.bdate_range("2026-10-07", periods=6)
    base = pd.Series([100, 101, 100.5, 102, 101, 103.0], index=days)
    other = pd.Series([100, 100.8, 100.9, 101.5, 101.4, 102.0], index=days)
    m = comparisons.measures(other, base)
    gap = (other / other.shift(1) - 1 - (base / base.shift(1) - 1)).iloc[1:]
    te = gap.std(ddof=1) * math.sqrt(252)
    assert m["tracking_error"] == pytest.approx(te) and m["band"] == pytest.approx(2 * te * math.sqrt(5 / 252))
    assert m["difference"] == pytest.approx(0.02 - 0.03) and m["inside_band"] == ("yes" if 0.01 <= m["band"] else "no")


def test_the_daily_effects_sum_to_each_daily_difference_exactly(record):
    r = record
    sims, _, growth = comparisons.simulations(r["records"], r["navs"], r["values"], r["table"], r["ref_a"], r["ref_b"],
                                              r["rate"], END)  # fmt: skip
    days = r["table"].index
    returns = pd.DataFrame({k: comparisons._returns(g) for k, g in growth.items()})
    funds = comparisons._fund_returns(r["navs"], days)
    state = {k: comparisons._state(sims[k], r["navs"], days) for k in ["reference_a", *(s[0] for s in comparisons.SPLITS)]}
    for key in ["reference_a", "reference_b", *(s[0] for s in comparisons.SPLITS), "savings"]:
        effects = comparisons.daily_effects(key, returns, funds, state)
        gap = returns[key] - returns["portfolio"]
        assert np.abs(effects.sum(axis=1) - gap).max() < 1e-12, key
    split = comparisons.daily_effects("split_100_0", returns, funds, state)
    assert split["dollar"].abs().sum() > 0 and split["split"].abs().sum() > 0


def test_the_summary_the_growth_and_the_effects(record):
    out = _build(record)
    summary = out["summary"].set_index("comparator")
    assert list(summary.index) == [k for k, _, _ in comparisons.ROWS]
    assert summary.loc["portfolio", "return_time_weighted"] == pytest.approx(record["table"]["growth_portfolio"].iloc[-1] / 100 - 1)
    assert math.isnan(summary.loc["portfolio", "difference"]) and math.isnan(summary.loc["savings", "correlation"])
    assert summary.loc["split_100_0", "volatility"] > summary.loc["split_60_40", "volatility"]
    effects = out["effects"]
    record_rows = effects[effects["period"] == "record"].pivot(index="comparator", columns="effect", values="value")
    for key in record_rows.index:
        total = record_rows.loc[key].drop("timing").sum()
        assert total == pytest.approx(summary.loc[key, "difference"], abs=1e-12), key
        months = effects[(effects["comparator"] == key) & (effects["period"] != "record")]
        by_effect = months.groupby("effect")["value"].sum()
        assert by_effect.drop(["timing", "compounding"]).sum() == pytest.approx(total - record_rows.loc[key, "compounding"])
    assert set(record_rows.loc["reference_a"][record_rows.loc["reference_a"] != 0].index) <= {"implementation", "timing", "compounding"}
    assert out["daily"].columns[0] == "date" and "growth_savings" in out["daily"]
    assert math.isnan(summary.loc["benchmark", "return_time_weighted"])


def test_the_benchmark_waits_for_six_month_ends(record):
    growth = record["table"]["growth_portfolio"]
    ends = pd.to_datetime(["2026-10-30", "2026-11-30"])
    short = pd.Series([growth.loc[ends[0]], growth.loc[ends[0]] * 1.01], index=ends)
    row = comparisons._benchmark_row("Benchmark", "same_rules", short, growth)
    assert row["return_time_weighted"] == pytest.approx(0.01) and math.isnan(row["band"]) and math.isnan(row["difference"])
    six = pd.Series(np.linspace(100, 104, 6), index=pd.bdate_range("2026-10-30", periods=6))
    portfolio = pd.Series(np.linspace(100, 103, 6), index=six.index)
    row = comparisons._benchmark_row("Benchmark", "same_rules", six, portfolio)
    assert not math.isnan(row["band"]) and row["difference"] == pytest.approx(0.01)


def test_the_comparisons_part_on_the_page():
    import json
    import re

    from portfolio import config

    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    view = page.split('id="view-performance"', 1)[1].split('<section class="view"', 1)[0]
    assert view.index('id="c3"') < view.index('id="comparisons"') < view.index('id="contributions"')
    part = view.split('id="comparisons"', 1)[1].split('id="contributions"', 1)[0]
    # E10: the panes are the browser's disclosure element, closed by default, each under the question it answers.
    assert re.findall(r'<details class="ch-pane"><summary>([^<]+)</summary>', part) == [
        "The same rules without costs", "The same rules with other funds or splits", "The money left in the bank",
        "Where each difference came from"]
    assert '<details class="ch-pane" open' not in part
    summary = part.split('<div class="ch-pair">', 1)[0] if '<div class="ch-pair">' in part else part.split('ch-pair', 1)[0]
    names = re.findall(r"<tr><td>([^<]+)</td>", summary)
    assert names[:3] == ["The portfolio", "The benchmark, the index blend", "Reference A, the same rules without costs"]
    assert "inside the band" in summary and "the square root of 252" in summary
    for word in ("ahead", "behind", "beat", "trail", "outperform", "attribution"):
        assert word not in part.lower(), word
    assert '<select id="comparisons-effects-select" data-chart="comparisons-effects">' in part
    data = json.loads(re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', page, re.S).group(1).replace("<\\/", "</"))
    charts = {c["id"]: c for c in data["charts"]}
    assert all(charts[c]["view"] == "performance" for c in charts if c.startswith("comparisons"))
    assert sum(t["visible"] for t in charts["comparisons-effects"]["traces"]) == 1
    assert [t["name"] for t in charts["c21"]["traces"]][2] == "US series"


def test_the_comparator_funds_are_fixed_with_their_dates_and_the_ranked_ones_are_the_first_offered():
    from portfolio import config

    funds = references.comparator_funds()
    assert sorted(set(funds["comparator"])) == ["first_ranked", "lifestrategy_60", "lifestrategy_80", "mag7", "msci_world", "nasdaq100"]
    assert (funds["fixed_on"] == "2026-11-10").all() and funds["isin"].str.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d").all()
    by = funds.set_index(["comparator", "sleeve"])["isin"]
    assert by[("first_ranked", "equity")] == "IE00B44Z5B48" and by[("first_ranked", "bonds")] == "IE00BH04GL39"
    assert by[("lifestrategy_60", "mixed")] == "IE00BMVB5P51" and by[("lifestrategy_80", "mixed")] == "IE00BMVB5R75"
    mag7 = funds[funds["comparator"] == "mag7"].iloc[0]
    assert mag7["isin"] == "IE000NFL4BX4" and mag7["series_from"] == "2026-11-04" and mag7["condition"]
    assert references.first_offered(config.METHOD_DIR / "selection_msci_world.csv")[1] == by[("msci_world", "equity")]
    assert references.first_offered(config.METHOD_DIR / "selection_nasdaq100.csv")[1] == by[("nasdaq100", "equity")]
    # The first equity fund of the rules' own ranking is not offered on the account, so it differs from the fund held.
    ranking = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv").drop_duplicates("isin")
    first = ranking[(ranking["sleeve"] == "equity") & (ranking["rank"] == 1)].iloc[0]
    assert first["isin"] == "IE00B44Z5B48" and first["offered_on_the_account"] == "no"
