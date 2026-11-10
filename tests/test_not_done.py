"""What the portfolio does not do: the section's values come from the committed files, its notes link once
each, and the S&P 500 alternative is the same contributions in one ETF at its net asset value."""

import json
import re
from datetime import date

import pandas as pd
import pytest

from conftest import BD, EQ, contribution, order
from portfolio import config, ledger, metrics, positions, prices, references, site, valuations

MANDATE = config.ROOT / "mandate"
RANKING = re.compile(r"\b(ahead|behind|beat\w*|trail\w*|outperform\w*|underperform\w*)\b", re.I)


def _section(added="2026-11-06"):
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv")
    us = pd.read_csv(MANDATE / "allocation_check_us_results.csv")
    daily = pd.read_csv(config.OUTPUTS_DIR / "portfolio_daily.csv")
    page = site.Page()
    site._not_done(page, allocation, us, daily, "An S&P 500 fund", site._test_period(), pd.Timestamp(added))
    return page, " ".join(page.sections["method"])


def test_the_values_in_the_text_are_computed_from_the_committed_files():
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv").set_index("split")
    first, last, months = site._test_period()
    assert (first, last, months) == ("1999-02", "2025-12", 323)
    error = allocation.loc["100/0", "volatility"] / (months / 12) ** 0.5 * 100
    gap = (allocation.loc["100/0", "growth_per_year"] - allocation.loc["40/60", "growth_per_year"]) * 100
    _, html = _section()
    assert f"is about {error:.1f} percentage points" in html and f"a gap in growth per year of {gap:.1f} points" in html
    assert "over the test&#x27;s 27 years" in html
    assert ("the largest split within 35 per cent is 65/35, and the worst fall at 70/30 is 36.0 per cent, from August "
            "2000 to February 2003") in html  # fmt: skip
    assert "would be in An S&amp;P 500 fund, the S&amp;P 500 ETF" in html
    assert "Added on 6 November 2026, after the first cycle day, in answer to the questions readers ask most." in html
    assert "The US series was added in November 2026, after the first cycle day" in html


def test_the_sentence_on_the_us_market_is_written_from_the_committed_periods():
    periods = pd.read_csv(MANDATE / "allocation_check_us_periods.csv")
    assert list(periods["first_month"]) == ["2000-01", "2000-01", "2010-01", "2010-01"]
    assert list(periods["months"]) == [120, 120, 180, 180]
    figures = {(r.series[:2], r.first_month): site._per_cent(r.cumulative_return_usd) for r in periods.itertuples()}
    _, html = _section()
    assert (f"grew popular in the years after 2009, when the US stock market returned {figures[('US', '2010-01')]} in "
            f"dollars, dividends included, against {figures[('De', '2010-01')]} for the developed markets outside the "
            f"United States, and over the ten years from 2000 to 2009 the same two series returned "
            f"{figures[('US', '2000-01')]} and {figures[('De', '2000-01')]}.") in html  # fmt: skip
    assert site._per_cent(-0.0374) == "minus 3.7 per cent" and site._per_cent(0.296) == "29.6 per cent"
    sentence = re.search(r"The advice to hold the index alone.*?United States, and over the ten years.*?\.", html).group(0)
    assert not RANKING.search(sentence) and "the index lost" not in html


def test_every_footnote_links_to_one_note_and_every_note_has_one_link():
    # The dashboard's notes are numbered in order of first mention across the views, so the market portfolio's two
    # sources in the Performance view come before the six this section cites, and the Notes list closes this section.
    html = (config.ROOT / "index.html").read_text(encoding="utf-8")
    marks = re.findall(r'<sup class="fn"><a href="#note-(\d+)"', html)
    assert marks == [str(n) for n in range(1, len(site.CITATIONS) + 1)]
    assert "\u2e28" not in html and "\u2e29" not in html
    notes = re.findall(r'<li id="note-(\d+)">(.*?)</li>', html)
    assert [n for n, _ in notes] == marks
    assert all(body.count("<a href=") == 1 for _, body in notes)
    assert notes[0][1].startswith("Doeswijk, R., Lam, T. and Swinkels, L. (2014). The global multi-asset market portfolio")
    assert notes[1][1].startswith("Doeswijk, R., Lam, T. and Swinkels, L. (2024). Data update:")
    assert notes[2][1].startswith("DeMiguel, V., Garlappi, L. and Uppal, R. (2009).")
    # A page or file of the author's own carries its link on its title, with no address written out.
    assert notes[3][1].startswith('<a href="https://www.carlohofer.com/projects/optimal-vs-naive-diversification/">'
                                  'Optimal versus naive diversification</a>, the replication')
    assert notes[7][1] == ('The agenda of the review, <a href="https://github.com/ochofer/rules-based-portfolio/blob/main/'
                           'mandate/REVIEW_2027.md">mandate/REVIEW_2027.md</a> in the repository.')
    section = html.split('id="method-not-done"', 1)[1].split('<p class="label">Notes</p>', 1)[0]
    assert re.findall(r'<sup class="fn"><a href="#note-(\d+)"', section) == [str(n) for n in range(3, 9)]
    with pytest.raises(ValueError):
        site._number_notes({v: ([site._note("no_such_note")] if v == "method" else []) for v, _ in site.VIEWS})


def test_the_two_exhibits_sit_inside_the_section_in_the_order_the_text_names_them():
    page, html = _section()
    benchmark = html.index("<b>The benchmark, and why not the S&amp;P 500.</b>")
    assert benchmark < html.index('data-exhibit="c33"') < html.index('data-exhibit="c34"') < html.index("<b>No views.</b>")
    assert html.index("<b>No views.</b>") < html.index("<b>No signal.</b>") < html.index('<ol class="notes">')
    assert [c["id"] for c in page.charts] == ["c33", "c34"] and {c["view"] for c in page.charts} == {"method"}
    assert "Committed in" not in html


def test_the_us_exhibit_pairs_the_two_series_and_holds_the_global_split_in_the_accent():
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv")
    us = pd.read_csv(MANDATE / "allocation_check_us_results.csv")
    assert (us["chosen"] == "no").all() and list(us["split"]) == list(allocation["split"])
    card, chart = site._us_test(allocation, us, site._test_period(), pd.Timestamp("2026-11-06"))
    world, usa = chart["traces"]
    assert [c for c, s in zip(world["marker"]["color"], world["y"]) if c == "@accent"] == ["@accent"]
    assert world["marker"]["color"][world["y"].index("70/30")] == "@accent" and usa["marker"]["color"] == "@us_series"
    assert chart["layout"]["barmode"] == "group" and [s["x0"] for s in chart["layout"]["shapes"]] == [35, 40]
    assert "At 70/30 the global series&#x27; worst fall runs from August 2000 to March 2003, and the US series&#x27; from August 2000 to February 2003." in card


def test_the_alternative_exhibit_ranks_neither_line_and_gives_the_gap_with_its_sign():
    daily = pd.DataFrame({"date": ["2026-10-07", "2026-10-08", "2026-10-09"], "growth_portfolio": [100.0, 100.1, 101.1],
                          "growth_reference_a": [100.0, 100.0, 101.0], "growth_sp500_alternative": [100.0, 100.0, 100.4]})
    card, chart = site._alternative(daily, "An S&P 500 fund")
    assert not RANKING.search(card)
    assert ("Two rule sets on the same contributions from the first purchase, both without costs. The S&amp;P 500 "
            "alternative is An S&amp;P 500 fund, at its net asset value in euro. Over the record&#x27;s months the gap "
            "says nothing about either rule set.") in card  # fmt: skip
    assert '<td class="num">−0.6</td>' in card and "7 Oct 2026, start" in card
    assert [t["line"]["color"] for t in chart["traces"]] == ["@reference_a", "@sp500_alternative"]
    assert "growth_portfolio" not in json.dumps(chart) and "Portfolio" not in json.dumps(chart)


def test_the_growth_of_100_links_to_the_section_and_the_other_projects_close_the_method_part():
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    assert ('Why the portfolio has no optimiser, no single market index as its benchmark, no views and no signal: '
            '<a href="#method-not-done">Method</a>.') in page  # fmt: skip
    assert page.index('id="method-correlation"') < page.index('id="method-not-done"') < page.index('id="method-selection"')
    assert page.index('id="method-rules"') < page.index('id="method-projects"') < page.index('id="glossary"') < page.index('id="log"')


def test_the_readme_lists_the_other_projects_in_the_words_and_links_of_the_page():
    section = (config.ROOT / "README.md").read_text().split("\n## Other projects\n", 1)[1]
    for title, words, links in site.OTHER_PROJECTS:
        assert f"- **{title}** {words} " + ", ".join(f"[{w}]({u})" for w, u in links) in section
    assert "#method-not-done" in (config.ROOT / "README.md").read_text()


def test_the_alternative_fund_is_the_first_in_rank_order_that_the_account_offers(tmp_path):
    frame = pd.DataFrame({"sleeve": "sp500", "rank": [2, 1, 3], "fund": ["B", "A", "C"], "isin": ["X2", "X1", "X3"],
                          "offered_on_the_account": ["yes", "no", "yes"]})
    frame.to_csv(tmp_path / "selection.csv", index=False)
    assert references.alternative_fund(tmp_path / "selection.csv") == ("B", "X2")
    assert references.alternative_fund()[1] in prices.HSBC_FEEDS


def test_the_alternative_grows_with_its_funds_net_asset_value(write_ledger):
    # 1,000 buys 50 units at 20 on the day of the first purchase, and the top-up of 50 buys at 22 on 2 November.
    # With contributions removed the growth of 100 is the net asset value's own growth: 100 x 24 / 20 = 120.
    days = pd.to_datetime(["2026-10-07", "2026-10-08", "2026-10-09", "2026-11-02", "2026-11-03"])
    frame = pd.DataFrame({"equity": [10.0] * 5, "bonds": [3.0] * 5}, index=days)
    frame["usd_per_eur"], frame["rate_carried"] = 1.1, False
    t, c = write_ledger([order("2026-10-08", "16:00:00", EQ, "buy", "70", "10.0"),
                         order("2026-10-08", "16:01:00", BD, "buy", "100", "3.0")],
                        [contribution("2026-10-08", "before 15:59:00", 1000, "start"),
                         contribution("2026-11-02", "09:00", 50, "top-up")])  # fmt: skip
    records = ledger.read(t, c)
    unit_value = pd.Series([19.0, 20.0, 21.0, 22.0, 24.0], index=days)
    alt = references.sp500_alternative(records, unit_value, date(2026, 11, 3))
    assert alt.index[0] == pd.Timestamp("2026-10-08")
    assert alt.loc["2026-10-09", "value"] == pytest.approx(50 * 21.0)
    assert alt.loc["2026-11-03", "units"] == pytest.approx(50 + 50 / 22.0)
    values = valuations.build(positions.build(records, date(2026, 11, 3)), frame)
    ref = references.simulate(records, frame, date(2026, 11, 3), "rules")
    table = metrics.daily(records, values, ref, ref, pd.Series(dtype=float), metrics.base_day(records, frame), alt)
    assert table.loc["2026-10-09", "growth_sp500_alternative"] == pytest.approx(105.0)
    assert table["growth_sp500_alternative"].iloc[-1] == pytest.approx(120.0)


def test_the_issuers_price_history_is_read_in_us_dollars_and_another_currency_stops(tmp_path):
    answer = {"isin": "IE000JZ473P7", "currency": "USD",
              "series": [{"name": "Price", "data": [{"x": "2026-11-03", "y": 74.5}, {"x": "2026-11-02", "y": 74.1},
                                                     {"x": "2026-11-04", "y": None}]}]}  # fmt: skip
    (tmp_path / "a.json").write_text(json.dumps(answer))
    navs = prices.parse_hsbc_navs(tmp_path / "a.json")
    assert list(navs.index.strftime("%Y-%m-%d")) == ["2026-11-02", "2026-11-03"] and navs.iloc[-1] == 74.5
    (tmp_path / "b.json").write_text(json.dumps({**answer, "currency": "EUR"}))
    with pytest.raises(ValueError, match="US dollars"):
        prices.parse_hsbc_navs(tmp_path / "b.json")
    with pytest.raises(ValueError, match="no net asset value feed"):
        prices.load_alternative("IE00B5BMR087", cache_dir=tmp_path)


def test_the_benchmark_is_the_index_blend_in_the_key_facts_the_method_view_and_the_terms():
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    facts = re.search(r'<aside class="ch-facts".*?</aside>', page, flags=re.S).group(0)
    assert ("<dt>Benchmark</dt><dd>The 70/30 blend of the two funds&#x27; own indices, rebalanced at each month end "
            '(<a href="#method-not-done">the index blend</a>)</dd>') in facts  # fmt: skip
    section = page.split('id="method-not-done"', 1)[1]
    assert ("<b>The benchmark, and why not the S&amp;P 500.</b> A benchmark is the portfolio a client would hold "
            "without the manager") in section  # fmt: skip
    assert "This portfolio&#x27;s benchmark is the blend of its two funds&#x27; own indices at 70/30" in section
    assert "No single market index is the benchmark. The question readers ask most" in section
    assert "None by design" not in page and "no index benchmark" not in page
    terms = dict(site.terms())
    assert terms["Index blend"].endswith("rebalanced at each month end, the portfolio's benchmark.")
