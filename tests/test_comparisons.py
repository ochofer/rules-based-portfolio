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


def _build(r, blend=None, extra=None):
    blend = pd.Series(dtype=float) if blend is None else blend
    return comparisons.build(r["records"], r["navs"], r["values"], r["table"], r["ref_a"], r["ref_b"], blend, r["rate"], END,
                             extra)  # fmt: skip


def _walk(days, seed, start=100.0, scale=0.01):
    rng = np.random.default_rng(seed)
    return pd.Series(start * np.cumprod(1 + rng.normal(0.0003, scale, len(days))), index=days)


def _extra(navs, mag7_from="2026-11-03"):
    """Invented inputs of the second stage: three dollar funds, one euro mixed fund, one feed that stopped, the four
    regions' levels, two snapshots of region weights and the ECB spot rate."""
    days = navs.index
    usd = {k: _walk(days, i) for i, k in enumerate(["msci_world", "mag7", "first_ranked"], start=11)}
    eur = {k: v / navs["usd_per_eur"] for k, v in usd.items()}
    mixed = _walk(days, 21, 50.0, 0.005)
    levels = pd.DataFrame({name: _walk(days, 31 + i) for i, name in enumerate(comparisons.REGION_NAMES)})
    rows = []
    for key, first, second in [("held", (0.65, 0.15, 0.08, 0.12), (0.66, 0.14, 0.08, 0.12)),
                               ("msci_world", (0.75, 0.17, 0.08, 0.0), (0.74, 0.18, 0.08, 0.0)),
                               ("first_ranked", (0.64, 0.16, 0.08, 0.12), (0.64, 0.16, 0.08, 0.12)),
                               ("lifestrategy_60", (0.60, 0.20, 0.08, 0.12), (0.60, 0.20, 0.08, 0.12)),
                               ("mag7", (1.0, 0, 0, 0), (1.0, 0, 0, 0))]:  # fmt: skip
        for day, weights in (("2026-10-30", first), ("2026-11-20", second)):
            rows += [{"comparator": key, "snapshot": pd.Timestamp(day), "region": n, "weight": w}
                     for n, w in zip(comparisons.REGION_NAMES, weights)]  # fmt: skip
    spot = pd.Series(np.linspace(0.026, 0.024, len(days)) + 0.001 * np.sin(np.arange(len(days))), index=days)
    return {
        "one_fund": {
            "msci_world": {"eur": eur["msci_world"], "usd": usd["msci_world"], "share": 1.0},
            "lifestrategy_60": {"eur": mixed, "usd": None, "share": 0.6, "bonds_na": True},
            "nasdaq100": {"eur": None, "status": "series not read on 2026-12-04"},
            "mag7": {"eur": eur["mag7"], "usd": usd["mag7"], "share": 1.0, "from": pd.Timestamp(mag7_from)},
        },
        "first_ranked": {"eur": eur["first_ranked"], "usd": usd["first_ranked"]},
        "regions": pd.DataFrame(rows),
        "region_levels": levels,
        "bond": {"spot": spot, "duration": 6.7},
        "unavailable": {"bank_offensief": "no published return"},
    }


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
    sims, _, growth, _, _ = comparisons.simulations(r["records"], r["navs"], r["values"], r["table"], r["ref_a"], r["ref_b"],
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
    first_stage = {"portfolio", "benchmark", "reference_a", "reference_b", "savings", *(s[0] for s in comparisons.SPLITS)}
    assert list(summary.index) == [k for k, _, _ in comparisons.ROWS if k in first_stage]
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
        "The same rules without costs", "The same rules with other funds or splits", "One fund instead of two",
        "Every asset class at its market value", "The money left in the bank",
        "Not like for like: a bank&#x27;s managed profile", "Where each difference came from"]
    assert "4 Nov to" in summary_rows(part, "The Mag7 fund") and "How the one-fund comparators&#x27; funds were chosen" in part
    # The market portfolio's pane: the note opens on what the comparator is, and its weight table follows the chart.
    pane = part.split("<summary>Every asset class at its market value</summary>", 1)[1].split('<details class="ch-pane">', 1)[0]
    assert pane.index("is a comparator the portfolio&#x27;s design names, and the benchmark remains the index blend") \
        < pane.index("The global market portfolio&#x27;s weights and funds, by asset class")
    # Its two sources are the first notes of the dashboard's Notes list, cited in order of mention.
    assert re.findall(r'<sup class="fn"><a href="#note-(\d+)"', pane) == ["1", "2"] and "inside the band" in pane
    assert "doi.org" not in pane.split("</h3>", 1)[1].split('<p class="source">', 1)[0]
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


def summary_rows(part, name):
    import re

    table = part.split("ch-pair", 1)[0]
    return next(r for r in re.findall(r"<tr>(.*?)</tr>", table) if f"<td>{name}</td>" in r)


def test_the_second_pane_is_named_for_the_splits_until_the_first_ranked_funds_are_in_it():
    from portfolio import config, site

    class Page:
        def __init__(self):
            self.charts, self.html = [], []

        def add(self, view, html):
            self.html.append(html)

    out = {n: pd.read_csv(config.OUTPUTS_DIR / n) for n in ("comparisons.csv", "comparisons_daily.csv", "comparison_effects.csv",
                                                           "comparison_fees.csv", "comparison_regions.csv")}  # fmt: skip
    for drop, headline in ((False, "The same rules with other funds or splits"), (True, "The same rules at other splits")):
        page = Page()
        summary = out["comparisons.csv"]
        effects = out["comparison_effects.csv"]
        if drop:
            summary = summary[summary["comparator"] != "first_ranked"]
            effects = effects[effects["comparator"] != "first_ranked"]
        site.comparisons_part(page, summary, out["comparisons_daily.csv"], effects, out["comparison_fees.csv"],
                              out["comparison_regions.csv"])  # fmt: skip
        html = "".join(page.html)
        assert f"<summary>{headline}</summary>" in html
        assert ("70/30 with the first-ranked funds" in html.split("<summary>One fund", 1)[0].split("The same rules", 2)[-1]) is not drop


def test_the_comparator_funds_are_fixed_with_their_dates_and_the_ranked_ones_are_the_first_offered():
    from portfolio import config

    funds = references.comparator_funds()
    assert sorted(set(funds["comparator"])) == ["first_ranked", "lifestrategy_60", "lifestrategy_80", "mag7", "market_portfolio", "msci_world", "nasdaq100"]
    assert (funds["fixed_on"] == "2026-11-10").all() and funds["isin"].str.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d").all()
    by = funds.set_index(["comparator", "sleeve"])["isin"]
    assert by[("first_ranked", "equity")] == "IE00B44Z5B48" and by[("first_ranked", "bonds")] == "IE00BH04GL39"
    assert by[("lifestrategy_60", "mixed")] == "IE00BMVB5P51" and by[("lifestrategy_80", "mixed")] == "IE00BMVB5R75"
    mag7 = funds[funds["comparator"] == "mag7"].iloc[0]
    assert mag7["isin"] == "IE000NFL4BX4" and mag7["series_from"] == "2026-11-04" and mag7["condition"] and mag7["condition_met_on"] == "2026-11-10"
    assert references.first_offered(config.METHOD_DIR / "selection_msci_world.csv")[1] == by[("msci_world", "equity")]
    assert references.first_offered(config.METHOD_DIR / "selection_nasdaq100.csv")[1] == by[("nasdaq100", "equity")]
    # The first equity fund of the rules' own ranking is not offered on the account, so it differs from the fund held.
    ranking = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv").drop_duplicates("isin")
    first = ranking[(ranking["sleeve"] == "equity") & (ranking["rank"] == 1)].iloc[0]
    assert first["isin"] == "IE00B44Z5B48" and first["offered_on_the_account"] == "no"


def test_the_market_portfolio_holds_one_fund_per_class_each_the_first_the_account_offers():
    from portfolio import config

    funds = references.comparator_funds()
    market = funds[funds["comparator"] == "market_portfolio"].set_index("sleeve")
    assert list(market.index) == ["equities", "aggregate", "private_equity", "real_estate", "em_debt", "inflation_linked", "high_yield"]
    assert (market["fixed_on"] == "2026-11-10").all() and (market["hedging"] == "unhedged").all()
    assert market.loc["equities", "isin"] == config.ISIN[config.EQUITY]
    table = config.METHOD_DIR / "selection_market_portfolio.csv"
    ranking = pd.read_csv(table)
    for sleeve in ranking["sleeve"].unique():
        first = references.first_offered(table, sleeve)
        expected = first[1] if first else market.loc[references.MARKET_PARENT[sleeve], "isin"]
        assert market.loc[sleeve, "isin"] == expected, sleeve
    # The account offers no accumulating class of the aggregate funds, so the class held distributes. It offers the
    # first inflation-linked fund only in a hedged class, and the second is a hedged class by its issuer's page, so
    # the inflation-linked class is held in its parent, the aggregate fund.
    funds_ranked = ranking.drop_duplicates("isin").set_index("isin")
    assert market.loc["aggregate", "income"] == "distributing" and "ex-dates" in market.loc["aggregate", "how_chosen"]
    assert funds_ranked.loc[market.loc["aggregate", "isin"], "rank"] == 3
    assert references.first_offered(table, "inflation_linked") is None
    assert market.loc["inflation_linked", "isin"] == market.loc["aggregate", "isin"]
    hedged = funds_ranked.loc["LU0908508814"]
    assert hedged["passes_the_criteria"] == "no" and hedged["hedging"] == "hedged" and "afgedekt" in hedged["note"]
    # Three years of tracking difference give the average, and the values seen before the funds were fixed are
    # named beside them.
    for isin, group in ranking.groupby("isin"):
        if group["average_points"].notna().any():
            assert group["tracking_difference_points"].mean() == pytest.approx(group["average_points"].iloc[0], abs=5e-4)
    assert ranking.drop_duplicates("isin")["value_seen_before_fixing"].notna().sum() == 3


def test_the_published_spreadsheets_of_state_street_hanetf_and_dws(tmp_path):
    from portfolio import prices

    (tmp_path / "ssga").mkdir()
    (tmp_path / "hanetf").mkdir()
    ssga = pd.DataFrame([["Fund Name:", "SPDR fund"], ["ISIN:", "IE00BFY0GT14"], ["Base Currency:", "USD"], [None, None],
                         ["Date", "Net asset value"], ["09-Nov-2026", "40.5"], ["06-Nov-2026", "40.1"], ["Marketing communication", None]])  # fmt: skip
    ssga.to_excel(tmp_path / "ssga" / "IE00BFY0GT14_navhist.xlsx", header=False, index=False)
    hanetf = pd.DataFrame([["Fund Name:", "Mag7"], ["Date", "Net asset value"], [pd.Timestamp("2026-11-04"), 7.9], [pd.Timestamp("2026-11-05"), 7.6]])
    hanetf.to_excel(tmp_path / "hanetf" / "IE000NFL4BX4_nav.xlsx", header=False, index=False)
    series, currency = prices.load_comparator("IE00BFY0GT14", cache_dir=tmp_path)
    assert currency == "USD" and list(series.index) == list(pd.to_datetime(["2026-11-06", "2026-11-09"]))
    assert list(series) == [40.1, 40.5]
    series, currency = prices.load_comparator("IE000NFL4BX4", cache_dir=tmp_path)
    assert currency == "USD" and series.iloc[0] == 7.9 and len(series) == 2
    # DWS's sheet: the net asset value is the third column, after the assets under management.
    (tmp_path / "dws").mkdir()
    dws = pd.DataFrame([["* disclaimer", None, None, None], ["Name", "NASDAQ 100 UCITS ETF 1C", None, None],
                        ["ISIN", "IE00BMFKG444", None, None], ["Currency", "USD", None, None], [None, None, None, None],
                        ["Date", "Asset Under Management", "Net asset value", "Index Level"], ["09.11.2026", 2.9e9, 64.7658, 32544.0],
                        ["06.11.2026", 2.8e9, 62.6374, 31473.9]])  # fmt: skip
    dws.to_excel(tmp_path / "dws" / "IE00BMFKG444_history.xlsx", header=False, index=False)
    series, currency = prices.load_comparator("IE00BMFKG444", cache_dir=tmp_path)
    assert currency == "USD" and list(series) == [62.6374, 64.7658] and series.index[0] == pd.Timestamp("2026-11-06")
    with pytest.raises(ValueError):
        prices.load_comparator("IE00B4L5Y983", cache_dir=tmp_path)


def test_the_second_stage_effects_sum_to_each_daily_difference_exactly(record):
    """The identity of the first stage, extended: for the one-fund comparators the regions, the dollar's part and the
    rest within each region close the gap to the two funds held at the fund's equity share, and for savings the
    bond rows close the gap to the bond fund."""
    r, extra = record, _extra(record["navs"])
    sims, values, growth, windows, missing = comparisons.simulations(r["records"], r["navs"], r["values"], r["table"],
                                                                     r["ref_a"], r["ref_b"], r["rate"], END, extra)  # fmt: skip
    assert missing == {"nasdaq100": "series not read on 2026-12-04", "bank_offensief": "no published return"} and windows == {"mag7": pd.Timestamp("2026-11-03")}
    days = r["table"].index
    returns = pd.DataFrame({k: comparisons._returns(g) for k, g in growth.items()})
    funds = comparisons._fund_returns(r["navs"], days)
    state = {k: comparisons._state(sims[k], r["navs"], days) for k in ["reference_a", *(s[0] for s in comparisons.SPLITS)]}
    navs_f = comparisons._with_equity(r["navs"], extra["first_ranked"]["eur"])
    state["first_ranked"] = comparisons._state(sims["first_ranked"], navs_f, days)
    returns["_first_ranked_fund"] = comparisons._fund_returns(navs_f, days)["r_e"]
    ctx = comparisons._context(extra, days, sims, r["navs"])
    for key in ["first_ranked", "msci_world", "lifestrategy_60", "mag7", "savings"]:
        window = returns.index if key not in windows else returns.index[returns.index > windows[key]]
        effects = comparisons.daily_effects(key, returns.loc[window], funds.loc[window], state, ctx)
        gap = returns.loc[window, key] - returns.loc[window, "portfolio"]
        assert np.abs(effects.sum(axis=1) - gap).max() < 1e-12, key
        if key != "savings":
            assert effects["regions"].abs().sum() > 0 and effects["within_regions"].abs().sum() > 0, key
    savings = comparisons.daily_effects("savings", returns, funds, state, ctx)
    assert savings["change_in_yield"].abs().sum() > 0 and savings["bonds_rest"].abs().sum() > 0
    mixed = comparisons.daily_effects("lifestrategy_60", returns, funds, state, ctx)
    assert mixed[list(comparisons.BOND_EFFECTS)].isna().all().all()
    # The regions effect is Brinson and Fachler's allocation term: weights that differ only by a constant add nothing.
    same = comparisons.region_shares(pd.Series({"North America": 0.6, "Pacific": 0.2, "Europe and Middle East": 0.2}))
    assert same.sum() == pytest.approx(1.0) and same["Emerging markets"] == 0


def test_the_second_stage_rows(record):
    extra = _extra(record["navs"])
    out = _build(record, extra=extra)
    summary = out["summary"].set_index("comparator")
    keys = [k for k, _, _ in comparisons.ROWS if k not in ("sp500", "lifestrategy_80", "market_portfolio")]
    assert list(summary.index) == keys
    # A fund held alone: its time-weighted return is its net asset value's, in euro.
    unit = extra["one_fund"]["msci_world"]["eur"]
    days = record["table"].index
    assert summary.loc["msci_world", "return_time_weighted"] == pytest.approx(unit.loc[days[-1]] / unit.loc[days[1]] - 1)
    # The Mag7 fund runs from its first day with the portfolio's value at that close.
    day = pd.Timestamp("2026-11-03")
    assert summary.loc["mag7", "first_day"] == day
    mag7 = extra["one_fund"]["mag7"]["eur"]
    assert summary.loc["mag7", "return_time_weighted"] == pytest.approx(mag7.loc[days[-1]] / mag7.loc[day] - 1)
    growth = record["table"]["growth_portfolio"]
    own = growth.loc[days[-1]] / growth.loc[day] - 1
    assert summary.loc["mag7", "difference"] == pytest.approx(summary.loc["mag7", "return_time_weighted"] - own)
    assert summary.loc["nasdaq100", "status"] == "series not read on 2026-12-04"
    assert summary.loc["bank_offensief", "status"] == "no published return"
    assert summary.loc["lifestrategy_60", "equity_share"] == 0.6 and summary.loc["msci_world", "equity_share"] == 1.0
    assert math.isnan(summary.loc["nasdaq100", "return_time_weighted"])
    effects = out["effects"]
    record_rows = effects[effects["period"] == "record"].pivot(index="comparator", columns="effect", values="value")
    for key in ["first_ranked", "msci_world", "lifestrategy_60", "mag7", "savings"]:
        total = record_rows.loc[key].drop("timing").sum()  # the empty bond rows of the mixed fund are skipped
        assert total == pytest.approx(summary.loc[key, "difference"], abs=1e-12), key
    assert record_rows.loc["lifestrategy_60", list(comparisons.BOND_EFFECTS)].isna().all()
    assert "nasdaq100" not in record_rows.index
    # Fewer than 20 daily returns: the return shows, the difference, the band and the effects wait.
    short = _build(record, extra=_extra(record["navs"], mag7_from="2026-11-23"))
    row = short["summary"].set_index("comparator").loc["mag7"]
    assert row["periods"] < comparisons.MIN_DAILY_RETURNS and not math.isnan(row["return_time_weighted"])
    assert math.isnan(row["difference"]) and math.isnan(row["band"]) and math.isnan(row["volatility"])
    assert "mag7" not in set(short["effects"]["comparator"])


def test_region_weights_by_day_and_the_snapshots_kept():
    table = pd.DataFrame([{"comparator": "x", "snapshot": pd.Timestamp(d), "region": "Pacific", "weight": w}
                          for d, w in (("2026-10-30", 0.1), ("2026-11-09", 0.2), ("2026-11-27", 0.3), ("2026-12-02", 0.4))])  # fmt: skip
    kept = comparisons.keep_snapshots(None, table, date(2026, 12, 3))
    assert list(kept["snapshot"].dt.strftime("%Y-%m-%d")) == ["2026-10-30", "2026-11-27", "2026-12-02"]
    days = pd.to_datetime(["2026-10-20", "2026-11-02", "2026-11-30"])
    weights = comparisons.by_day(comparisons._snapshots(kept, "x"), days, ["Pacific"])
    assert list(weights["Pacific"]) == [0.1, 0.1, 0.3]  # the first snapshot holds for the days before it
    holdings = pd.DataFrame({"country": ["United States", "Japan", "", "Germany"], "weight": [0.6, 0.1, 0.05, 0.25]})
    regions = pd.DataFrame({"country": ["United States", "Japan", "Germany"],
                            "region": ["North America", "Pacific", "Europe and Middle East"]})  # fmt: skip
    shares = comparisons.by_country(holdings, regions)
    assert shares.sum() == pytest.approx(1.0) and shares["North America"] == pytest.approx(0.6 / 0.95)
    regions = pd.concat([regions, pd.DataFrame({"country": ["Korea (South)"], "region": ["Emerging markets"]})])
    named = comparisons.by_country(pd.DataFrame({"country": ["South Korea", "United States"], "weight": [0.1, 0.9]}), regions)
    assert named["Emerging markets"] == pytest.approx(0.1)
    with pytest.raises(ValueError):
        comparisons.by_country(pd.DataFrame({"country": ["Atlantis"], "weight": [1.0]}), regions)


def test_a_lifestrategy_fund_takes_its_regions_from_its_underlying_funds():
    import pandas as pd
    from portfolio import config

    mapping = pd.read_csv(config.METHOD_DIR / "lifestrategy_underlying.csv")
    allocation = pd.DataFrame({"fund": ["Vanguard FTSE All-World UCITS ETF (USD) Accumulating",
                                        "Vanguard FTSE North America UCITS ETF",
                                        "Vanguard Global Aggregate Bond UCITS ETF EUR Hedged Accumulating",
                                        "Vanguard FTSE Japan UCITS ETF (USD) Accumulating"],
                               "share": [0.3, 0.2, 0.4, 0.1]})  # fmt: skip
    held = pd.Series({"North America": 0.6, "Europe and Middle East": 0.2, "Pacific": 0.1, "Emerging markets": 0.1})
    equity, weights = comparisons.mixed_regions(allocation, mapping, held, held)
    assert equity == pytest.approx(0.6)
    assert weights["North America"] == pytest.approx((0.3 * 0.6 + 0.2) / 0.6)
    assert weights["Pacific"] == pytest.approx((0.3 * 0.1 + 0.1) / 0.6) and weights.sum() == pytest.approx(1.0)
    with pytest.raises(ValueError):
        comparisons.mixed_regions(pd.DataFrame({"fund": ["Vanguard Something New"], "share": [1.0]}), mapping, held, held)


def test_the_costs_beside_the_comparisons():
    ownership = pd.DataFrame({"sleeve": ["equity", "bonds", "portfolio"], "ongoing_costs": [0.0021, 0.0007, 0.00167],
                              "document_date": ["2026-09-03", "2026-09-29", None]})  # fmt: skip
    implementation = pd.Series([-9.6, -5.4], index=pd.to_datetime(["2026-11-05", "2026-11-06"]))
    bank = {"basic_a_quarter": 0.0006, "management_a_quarter": 0.001, "funds_low": 0.001, "funds_high": 0.0015,
            "dated": pd.Timestamp("2025-05-01")}  # fmt: skip
    out = comparisons.fees(ownership, implementation, {"lifestrategy_60": (0.0025, pd.Timestamp("2026-09-30"))}, bank)
    rows = out.set_index(["comparator", "item"])
    assert rows.loc[("portfolio", "Ongoing costs of the two ETFs at the portfolio's weights"), "bps_low"] == pytest.approx(16.7)
    assert rows.loc[("portfolio", "Implementation cost, cumulative"), "bps_low"] == -5.4
    assert rows.loc[("lifestrategy_60", "Ongoing charges figure"), "bps_high"] == pytest.approx(25)
    all_in = rows.loc[("bank_offensief", "All in")]
    assert all_in["bps_low"] == pytest.approx(74) and all_in["bps_high"] == pytest.approx(79)


def test_the_rabobank_cost_overview_is_read_from_its_text():
    from portfolio import prices

    text = ("Basisdienstverlening • Inclusief transacties.\nU betaalt tot € 100.000 0,06% per kwartaal over het\n"
            "Portefeuillebeheer online inzicht\nU betaalt tot € 100.000 0,10% over het gemiddeld\n"
            "Per jaar bedragen deze kosten tussen 0,1 en 0,15% van de waarde\nKostenoverzicht Rabo Beheerd Beleggen Basis mei 2025")
    costs = prices.parse_rabobank_costs(text)
    assert costs["basic_a_quarter"] == pytest.approx(0.0006) and costs["management_a_quarter"] == pytest.approx(0.001)
    assert costs["funds_high"] == pytest.approx(0.0015) and costs["dated"] == pd.Timestamp("2025-05-01")
    with pytest.raises(ValueError):
        prices.parse_rabobank_costs("Kostenoverzicht without its rates")


def test_on_the_first_purchase_day_every_effect_but_implementation_is_zero(record):
    """The comparators and reference portfolio A buy at the first day's net asset values, so on that day the
    difference is implementation alone, and over the record the effects with timing sum to the money-weighted
    difference."""
    r, extra = record, _extra(record["navs"])
    sims, values, growth, windows, _ = comparisons.simulations(r["records"], r["navs"], r["values"], r["table"], r["ref_a"],
                                                               r["ref_b"], r["rate"], END, extra)  # fmt: skip
    days = r["table"].index
    returns = pd.DataFrame({k: comparisons._returns(g) for k, g in growth.items()})
    funds = comparisons._fund_returns(r["navs"], days)
    state = {k: comparisons._state(sims[k], r["navs"], days) for k in ["reference_a", *(s[0] for s in comparisons.SPLITS)]}
    navs_f = comparisons._with_equity(r["navs"], extra["first_ranked"]["eur"])
    state["first_ranked"] = comparisons._state(sims["first_ranked"], navs_f, days)
    returns["_first_ranked_fund"] = comparisons._fund_returns(navs_f, days)["r_e"]
    ctx = comparisons._context(extra, days, sims, r["navs"])
    first = days[1]
    for key in ["reference_a", "reference_b", *(s[0] for s in comparisons.SPLITS), "first_ranked", "msci_world",
                "lifestrategy_60", "savings"]:  # fmt: skip
        effects = comparisons.daily_effects(key, returns, funds, state, ctx)
        line = effects.loc[first].drop("implementation").dropna()
        assert (line == 0).all(), key
        assert effects.loc[first, "implementation"] == pytest.approx(-returns.loc[first, "portfolio"])
    out = _build(record, extra=extra)
    summary = out["summary"].set_index("comparator")
    rows = out["effects"][out["effects"]["period"] == "record"].pivot(index="comparator", columns="effect", values="value")
    own = summary.loc["portfolio", "return_money_weighted"]
    for key in rows.index:
        if key == "mag7":
            continue  # its window has its own money-weighted return for the portfolio
        assert rows.loc[key].sum() == pytest.approx(summary.loc[key, "return_money_weighted"] - own, abs=1e-12), key


def _market(navs, as_of="2023-12-29"):
    """Invented inputs of the global market portfolio: the held equity fund's series run back to the end of 2023, five
    dollar funds and one euro fund, and the published weights."""
    history = pd.bdate_range(as_of, navs.index[0] - pd.Timedelta(days=1))
    days = history.append(navs.index)
    rate = pd.concat([pd.Series(1.10, index=history), navs["usd_per_eur"]])
    equity_before = _walk(history, 40, 8.0)
    equity = pd.concat([equity_before * navs["equity"].iloc[0] / equity_before.iloc[-1] / 1.001, navs["equity"]])
    usd = {k: _walk(days, 50 + i, 20.0, 0.006) for i, k in enumerate(["aggregate", "private_equity", "real_estate", "em_debt", "high_yield"])}
    eur = pd.DataFrame({k: v / rate for k, v in usd.items()})
    eur["equities"] = equity
    eur["inflation_linked"] = _walk(days, 60, 30.0, 0.004)
    weights = pd.Series([0.43, 0.386, 0.078, 0.04, 0.039, 0.016, 0.011], index=list(comparisons.MARKET_SLEEVES))
    return {"eur": eur[list(comparisons.MARKET_SLEEVES)], "usd": pd.DataFrame(usd), "weights": weights / weights.sum(),
            "as_of": pd.Timestamp(as_of)}


def test_the_market_weights_are_the_dataset_s_eight_summed_by_class_fund():
    weights, as_of = comparisons.market_weights()
    assert list(weights.index) == list(comparisons.MARKET_SLEEVES) and weights.sum() == pytest.approx(1.0)
    assert as_of == pd.Timestamp("2023-12-31")
    table = pd.read_csv(comparisons.config.METHOD_DIR / "market_portfolio_weights.csv")
    assert len(table) == 8 and set(table["held_in"]) == set(comparisons.MARKET_SLEEVES)
    assert (table["doi"] == "10.25397/eur.9371741").all() and (table["version"] == 6).all()
    # Government bonds and investment-grade credits share the aggregate fund.
    assert weights["aggregate"] == pytest.approx(table.loc[table["held_in"] == "aggregate", "weight"].sum() / table["weight"].sum())
    assert weights[list(comparisons.EQUITY_LIKE)].sum() == pytest.approx(0.548, abs=0.001)


def test_a_second_version_of_the_weights_stops_the_build_until_its_move_is_written(tmp_path):
    table = pd.read_csv(comparisons.config.METHOD_DIR / "market_portfolio_weights.csv")
    later = table.assign(version=7, as_of="2024-12-31", published="2026-12-01")
    pd.concat([table, later]).to_csv(tmp_path / "weights.csv", index=False)
    with pytest.raises(ValueError, match="more than one version"):
        comparisons.market_weights(tmp_path / "weights.csv")


def test_the_weights_are_carried_by_each_class_fund_s_return():
    days = pd.bdate_range("2023-12-28", "2024-01-05")
    values = pd.DataFrame({"a": [1, 1, 1, 1.1, 1.1, 1.1, 1.1], "b": [2, 2, 2, 2, 2, 2, 1.0]}, index=days)
    carried = comparisons.carried_weights(pd.Series({"a": 0.5, "b": 0.5}), values, "2023-12-31", "2024-01-04")
    assert carried["a"] == pytest.approx(0.55 / 1.05) and carried.sum() == pytest.approx(1.0)
    with pytest.raises(ValueError):
        comparisons.carried_weights(pd.Series({"a": 0.5, "b": 0.5}), values, "2023-12-01", "2024-01-04")


def test_the_market_portfolio_drifts_and_tops_up_in_proportion(record):
    r, market = record, _market(record["navs"])
    days = r["table"].index
    held, turnover = comparisons.market_portfolio(r["records"], market["eur"], market["weights"], days[1:])
    assert turnover == []
    weights = held[list(comparisons.MARKET_SLEEVES)]
    assert weights.iloc[0].to_numpy() == pytest.approx(market["weights"].to_numpy())
    # Prices move the weights, and a top-up leaves them where it found them.
    level = market["eur"].reindex(days[1:])
    grown = market["weights"] * level.iloc[-1] / level.iloc[0]
    assert weights.iloc[-1].to_numpy() == pytest.approx((grown / grown.sum()).to_numpy())
    top_up = pd.Timestamp("2026-11-02")
    assert held.loc[top_up, "value"] == pytest.approx(
        (held.loc[top_up - pd.offsets.BDay(), "value"] * (weights.loc[top_up - pd.offsets.BDay()] * level.loc[top_up]
         / level.loc[top_up - pd.offsets.BDay()]).sum()) + 50)  # fmt: skip
    # A later weight set: the comparator moves to it on its day, and the turnover is half the weight changes.
    new = pd.Series([0.5, 0.3, 0.08, 0.04, 0.05, 0.02, 0.01], index=list(comparisons.MARKET_SLEEVES))
    moved, turnover = comparisons.market_portfolio(r["records"], market["eur"], market["weights"], days[1:],
                                                   ((pd.Timestamp("2026-11-05"), new),))  # fmt: skip
    assert moved.loc["2026-11-05", list(comparisons.MARKET_SLEEVES)].to_numpy() == pytest.approx(new.to_numpy())
    before = weights.loc["2026-11-05"]
    assert turnover[0][1] == pytest.approx(0.5 * (new - before).abs().sum())


def test_the_market_portfolio_s_effects_sum_to_each_daily_difference_exactly(record):
    """Through the two funds held at the comparator's equity-like share: cash, split and the dollar by the first
    stage's definitions, then each equity-like class against the equity fund and each bond class against the bond
    fund, with every dollar fund's conversion in the dollar row."""
    r, extra = record, _extra(record["navs"])
    extra["market_portfolio"] = _market(r["navs"])
    sims, values, growth, windows, missing = comparisons.simulations(r["records"], r["navs"], r["values"], r["table"],
                                                                     r["ref_a"], r["ref_b"], r["rate"], END, extra)  # fmt: skip
    market = extra["market_portfolio"]
    # The published weights at the end of 2023, carried to the base day by the funds' returns in euro.
    days = r["table"].index
    expected = comparisons.carried_weights(market["weights"], market["eur"], market["as_of"], days[0])
    assert market["carried"].to_numpy() == pytest.approx(expected.to_numpy()) and market["start_as_of"] == days[0]
    returns = pd.DataFrame({k: comparisons._returns(g) for k, g in growth.items()})
    funds = comparisons._fund_returns(r["navs"], days)
    state = {"reference_a": comparisons._state(sims["reference_a"], r["navs"], days)}
    ctx = comparisons._context(extra, days, sims, r["navs"])
    effects = comparisons.daily_effects("market_portfolio", returns, funds, state, ctx)
    gap = returns["market_portfolio"] - returns["portfolio"]
    assert np.abs(effects.sum(axis=1) - gap).max() < 1e-12
    assert effects["equity_classes"].abs().sum() > 0 and effects["bond_classes"].abs().sum() > 0
    assert (effects[["regions", "within_regions"]] == 0).all().all()
    assert (effects.loc[days[1]].drop("implementation") == 0).all()
    out = _build(r, extra=extra)
    summary = out["summary"].set_index("comparator")
    rows = out["effects"][out["effects"]["period"] == "record"].pivot(index="comparator", columns="effect", values="value")
    assert rows.loc["market_portfolio"].drop("timing").sum() == pytest.approx(summary.loc["market_portfolio", "difference"], abs=1e-12)
    table = out["market"].set_index("sleeve")
    assert table["published"].sum() == pytest.approx(1.0) and table["start"].sum() == pytest.approx(1.0)
    assert table["current"].sum() == pytest.approx(1.0) and table.loc["equities", "current_as_of"] == days[-1]


def test_a_distributing_fund_s_total_return_adds_each_distribution_on_its_ex_date():
    from portfolio import prices

    days = pd.bdate_range("2026-01-12", "2026-01-16")
    navs = pd.Series([10.0, 10.1, 9.9, 10.0, 10.2], index=days)
    paid = pd.Series([0.2], index=[pd.Timestamp("2026-01-14")])
    index = prices.with_distributions(navs, paid)
    returns = index / index.shift(1) - 1
    assert returns.loc["2026-01-14"] == pytest.approx((9.9 + 0.2) / 10.1 - 1)
    assert returns.loc["2026-01-15"] == pytest.approx(10.0 / 9.9 - 1)
    assert index.iloc[0] == navs.iloc[0]
    with pytest.raises(ValueError):
        prices.with_distributions(navs, pd.Series([0.2], index=[pd.Timestamp("2026-01-17")]))


def test_the_ishares_fund_file_s_history_and_distributions(tmp_path):
    from portfolio import prices

    def cells(*texts):
        return "<ss:Row>" + "".join(f'<ss:Cell><ss:Data ss:Type="String">{t}</ss:Data></ss:Cell>' for t in texts) + "</ss:Row>"

    body = ('<?xml version="1.0"?><ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
            '<ss:Worksheet ss:Name="Overview"><ss:Table>' + cells("Index", "S&P LISTED PRIVATE EQUITY") + "</ss:Table></ss:Worksheet>"
            '<ss:Worksheet ss:Name="Historical"><ss:Table>' + cells("As Of", "Currency", "Value", "Securities In Issue")
            + cells("09/Nov/2026", "USD", "4.28", "1") + cells("06/Nov/2026", "USD", "4.27", "1") + cells("05/Jun/2018", "USD", "--", "1")
            + "</ss:Table></ss:Worksheet>"
            '<ss:Worksheet ss:Name="Distributions"><ss:Table>' + cells("Record Date", "Ex-Date", "Payable Date", "Total Distribution")
            + cells("17/Jul/2026", "16/Jul/2026", "29/Jul/2026", "0.065") + "</ss:Table></ss:Worksheet></ss:Workbook>")  # fmt: skip
    path = tmp_path / "fund.xml"
    path.write_text(body)
    history = prices.parse_ishares_history(path, "USD")
    assert list(history.index) == [pd.Timestamp("2026-11-06"), pd.Timestamp("2026-11-09")] and history.iloc[-1] == 4.28
    assert prices.parse_ishares_distributions(path).to_dict() == {pd.Timestamp("2026-07-16"): 0.065}
    with pytest.raises(ValueError):
        prices.parse_ishares_history(path, "EUR")
    assert prices.COMPARATOR_FEEDS["IE00B3F81409"] == ("ishares", "291773", "USD")
    assert prices.comparator_cache_name("IE00B3F81409") == "ishares/IE00B3F81409_fund.xml"
