"""One rounding for every display, and colours named by role only."""

import json

import pytest

from portfolio import config, formatting as fmt, site


def test_rounding_rules():
    assert fmt.pct(0.70149) == "70.1%" and fmt.pct(-0.00049, signed=True) == "0.0%"
    assert fmt.pct(0.0312, signed=True) == "+3.1%" and fmt.pct(-0.0312, signed=True) == "−3.1%"
    assert fmt.bps(-11.6) == "−12 bp" and fmt.bps(0.4) == "0 bp"
    assert fmt.loading(-0.0579) == "−0.06" and fmt.loading(0.996) == "1.00"
    assert fmt.points(0.25) in ("+0.2 points", "+0.3 points")
    assert fmt.day("2026-10-08") == "2026-10-08" and fmt.month("2026-10-31") == "2026-10"
    assert fmt.pct(float("nan")) == "n/a"


def test_a_chart_with_a_colour_value_stops_the_build():
    palette = {"light": {"accent": "x"}}
    site._check_roles([{"traces": [{"marker": {"color": "@accent"}}]}], palette)
    with pytest.raises(ValueError, match="by value"):
        site._check_roles([{"traces": [{"marker": {"color": "#24599e"}}]}], palette)
    with pytest.raises(ValueError, match="does not define"):
        site._check_roles([{"traces": [{"marker": {"color": "@nothing"}}]}], palette)


def test_every_card_has_a_title_an_as_of_line_a_source_and_a_table():
    html = site._card("c1", "A title", "As of 2026-10-08", "outputs/x.csv", table="<table></table>")
    assert 'data-kind="figure">A title</h3>' in html and "As of 2026-10-08" in html and "outputs/x.csv" in html
    assert "<summary>Table</summary>" in html


def test_the_page_shows_the_readme_terms_once_each():
    terms = site.terms()
    names = [name.lower() for name, _ in terms]
    assert len(names) == len(set(names))
    assert {"drawdown", "worst fall", "net asset value", "implementation cost", "basis point"} <= set(names)


def test_a_short_date_axis_has_one_tick_per_valuation_day_and_none_twice():
    assert site._date_axis(["2026-10-07", "2026-10-08"])["tickvals"] == ["2026-10-07", "2026-10-08"]
    twelve = [f"2026-10-{d:02d}" for d in range(1, 13)]
    ticks = site._date_axis(twelve, 5)["tickvals"]
    assert ticks[-1] == "2026-10-12" and len(ticks) <= 5 and len(set(ticks)) == len(ticks)
    assert "tickvals" not in site._date_axis(["2026-06-01", "2026-10-08"])


def test_the_page_has_one_theme_light():
    palette = json.loads((config.SITE_DIR / "palette.json").read_text())
    assert list(palette) == ["light"]
    css = site._palette_css(palette)
    assert "color-scheme: light" in css and "prefers-color-scheme" not in css and "data-theme" not in css
    assert "theme" not in (config.SITE_DIR / "app.js").read_text()


def test_the_footer_ends_with_the_author_the_data_the_code_and_the_build_date():
    line = site._colophon({"positions_as_of": "2026-10-09"})
    assert line.startswith('<p class="colophon">') and line.endswith("Built 2026-10-09</p>")
    assert f'<a href="{config.REPOSITORY_URL}">Code on GitHub</a>' in line


def test_every_table_sits_in_a_frame_that_scrolls_with_a_sticky_first_column():
    table = site._table(["Month", "Return"], [["2026-10", "+0.1%"]], numeric=("Return",))
    assert table.startswith('<div class="tw"><div class="tablewrap"><table>')
    assert table.endswith("</table></div></div>")
    rules = site._rules_html()
    assert rules.count("<table>") == rules.count('<div class="tw"><div class="tablewrap"><table>') > 0
    label = "Kenneth French, Developed 5 Factors and Momentum"
    long_labels = site._table(["Source", "Downloaded"], [[label, "2026-10-09"]])
    assert '<table class="wrapfirst">' in long_labels and 'class="wrapfirst"' not in table


def _simulations_page(monthly):
    mandate = config.ROOT / "mandate"
    history = site._read("simulation_history.csv", mandate)
    paths = site._read("simulation_paths.csv", mandate)
    page = site.Page()
    site.simulations(page, history, paths, monthly)
    return " ".join(page.sections["simulations"])


def test_the_record_joins_the_resampled_paths_with_the_ruled_sentence():
    import pandas as pd

    waiting = _simulations_page(pd.DataFrame({"month": ["2026-10"], "complete": ["to date"], "value_in_units": [100.4]}))
    assert "From the first month end, 31 October 2026, the record&#x27;s own path is drawn inside the bands." in waiting
    drawn = _simulations_page(pd.DataFrame({"month": ["2026-10"], "complete": ["yes"], "value_in_units": [100.4]}))
    assert "where the market&#x27;s draw has taken it and is not evidence about the rules" in drawn


def test_the_visible_text_of_the_page_has_no_semicolon():
    # W6 of the house standard. The rules card quotes rules/RULES.md as fixed, which keeps its own wording.
    import html
    import re

    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    page = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    page = re.sub(r'<article class="card wide rules" id="method-rules">.*?</article>', " ", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", page))
    assert ";" not in text, re.findall(r".{0,60};.{0,60}", text)


def test_the_build_numbers_figures_and_tables_in_page_order_and_writes_the_references():
    # C5 and L3 of the house standard: one sequence for figures and one for tables, across the views in order.
    sections = {v: [] for v, _ in site.VIEWS}
    sections["overview"].append(site._card("c2", "Allocation", "", None))
    sections["costs"].append(site._card("c7", "Costs", "", None, note=f"They add up in {site._ref('c8')}."))
    sections["costs"].append(site._card("c8", "Implementation cost", "", None))
    sections["costs"].append(site._card("ownership", "What it costs", "", None, plot=False, kind="table"))
    sections["log"].append(site._card("notes", "Monthly notes", "", None, plot=False))
    numbers = site._number(sections)
    assert numbers == {"c2": ("figure", 1), "c7": ("figure", 2), "c8": ("figure", 3), "ownership": ("table", 1)}
    assert '<h3 id="figure-3">Figure 3 | Implementation cost</h3>' in sections["costs"][1]
    assert '<h3 id="table-1">Table 1 | What it costs</h3>' in sections["costs"][2]
    assert 'They add up in <a href="#figure-3">Figure 3</a>.' in sections["costs"][0]
    assert "<h3>Monthly notes</h3>" in sections["log"][0]


def test_a_reference_to_an_exhibit_not_on_the_page_stops_the_build():
    sections = {v: [] for v, _ in site.VIEWS}
    sections["costs"].append(site._card("c7", "Costs", "", None, note=f"See {site._ref('c99')}."))
    with pytest.raises(ValueError, match="c99"):
        site._number(sections)


def test_a_table_of_parts_carries_the_rounding_note():
    assert site.ROUNDING in site._table(["Sleeve", "Weight"], [["Equity", "70.0%"]], rounding=True)
    assert site.ROUNDING not in site._table(["Sleeve", "Weight"], [["Equity", "70.0%"]])


def test_the_page_numbers_its_exhibits_and_every_reference_finds_one():
    import html
    import re

    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    for kind in ("figure", "table"):
        found = [int(n) for n in re.findall(rf'<h3 id="{kind}-(\d+)">', page)]
        assert found == list(range(1, len(found) + 1))
        for n in re.findall(rf'<a href="#{kind}-(\d+)">', page):
            assert int(n) in found
    assert "data-exhibit" not in page and "⟦" not in page
    visible = re.sub(r"<script.*?</script>|<style.*?</style>", " ", page, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", visible))
    assert not re.search(r"\bcharts? \d", text, re.I), re.findall(r".{0,40}\bcharts? \d.{0,20}", text, re.I)
    assert "real-time" not in text.lower()


def test_the_log_writes_the_next_cycle_day_in_words():
    # Dates in prose are written in words. Stamps, tables and axes keep the ISO form.
    assert site._next_cycle_day({"positions_as_of": "2026-10-08"}) == "5 November 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-11-05"}) == "5 November 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-12-06"}) == "7 December 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-12-08"}) == "5 January 2027"
