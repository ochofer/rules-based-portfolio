"""One rounding for every display, and colours named by role only."""

import json
import re

import pandas as pd
import pytest

from portfolio import config, formatting as fmt, site


def test_rounding_rules():
    assert fmt.pct(0.70149) == "70.1%" and fmt.pct(-0.00049, signed=True) == "0.0%"
    assert fmt.pct(0.0312, signed=True) == "+3.1%" and fmt.pct(-0.0312, signed=True) == "−3.1%"
    assert fmt.bps(-11.6) == "−12 bp" and fmt.bps(0.4) == "0 bp"
    assert fmt.loading(-0.0579) == "−0.06" and fmt.loading(0.996) == "1.00"
    assert fmt.points(0.25) in ("+0.2 points", "+0.3 points")
    assert fmt.day("2026-10-08") == "2026-10-08" and fmt.month("2026-10-31") == "2026-10"
    assert fmt.day_short("2026-10-08") == "8 Oct 2026" and fmt.month_words("2026-10") == "October 2026"
    assert fmt.month_short("2026-10") == "Oct 2026"
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
    assert line.startswith('<p class="colophon">') and line.endswith("Built 9 October 2026</p>")
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
    sections["performance"].append(site._card("c7", "Costs", "", None, note=f"They add up in {site._ref('c8')}."))
    sections["performance"].append(site._card("c8", "Implementation cost", "", None))
    sections["performance"].append(site._card("ownership", "What it costs", "", None, plot=False, kind="table"))
    sections["method"].append(site._card("notes", "Monthly notes", "", None, plot=False))
    numbers = site._number(sections)
    assert numbers == {"c2": ("figure", 1), "c7": ("figure", 2), "c8": ("figure", 3), "ownership": ("table", 1)}
    assert '<h3 id="figure-3">Figure 3 | Implementation cost</h3>' in sections["performance"][1]
    assert '<h3 id="table-1">Table 1 | What it costs</h3>' in sections["performance"][2]
    assert 'They add up in <a href="#figure-3">Figure 3</a>.' in sections["performance"][0]
    assert "<h3>Monthly notes</h3>" in sections["method"][0]


def test_a_reference_to_an_exhibit_not_on_the_page_stops_the_build():
    sections = {v: [] for v, _ in site.VIEWS}
    sections["performance"].append(site._card("c7", "Costs", "", None, note=f"See {site._ref('c99')}."))
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
    # The page never calls itself real-time. The Other projects block quotes other projects' cards word for word,
    # so it is left out of this one check.
    own = re.sub(r'<article class="card wide projects" id="method-projects">.*?</article>', " ", visible, flags=re.S)
    assert own != visible
    assert "real-time" not in html.unescape(re.sub(r"<[^>]+>", " ", own)).lower()


def test_the_log_writes_the_next_cycle_day_in_words():
    # Every date a reader sees is in words (E7 of the house standard). Files keep the ISO form.
    assert site._next_cycle_day({"positions_as_of": "2026-10-08"}) == "5 November 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-11-05"}) == "5 November 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-12-06"}) == "7 December 2026"
    assert site._next_cycle_day({"positions_as_of": "2026-12-08"}) == "5 January 2027"


def test_the_record_has_one_date_and_names_what_came_after_it():
    now = {"weights_as_of": "2026-11-04", "positions_as_of": "2026-11-04", "built": "2026-11-05", "contributions_after": ""}
    assert site._two_dates(now) == "As of 4 November 2026"
    assert site._two_dates({"weights_as_of": "2026-11-04", "positions_as_of": "2026-11-05"}).startswith("Prices as of")
    assert site._colophon(now).endswith("Built 5 November 2026</p>")
    assert site._next_cycle_day(now) == "5 November 2026"
    orders = pd.DataFrame({"date": ["2026-10-08", "2026-10-08", "2026-11-05", "2026-11-05"]})
    assert site._after_record(orders, now) == ("The two orders of 5 November 2026 came after the last net asset values, "
                                               "of 4 November 2026, and enter the record with the next ones.")
    assert site._after_record(orders, now, counted=True) == ("The count includes the two orders of 5 November 2026, "
                                                             "placed after the last net asset values, of 4 November 2026.")
    top_up = dict(now, weights_as_of="2026-12-01", positions_as_of="2026-12-01", contributions_after="2026-12-02")
    assert site._after_record(orders, top_up) == ("The top-up of 2 December 2026 came after the last net asset values, "
                                                  "of 1 December 2026, and enters the record with the next ones.")
    assert site._after_record(orders.iloc[:2], now) == "" and site._after_record(orders, now, counted=True).count("orders") == 1


def _ownership_text(against, now, invested=1.0):
    costs = pd.DataFrame([
        {"sleeve": "equity", "fund": "E", "isin": config.ISIN[config.EQUITY], "weight": 0.7, "management_fees": 0.002,
         "transaction_costs": 0.0001, "ongoing_costs": 0.0021, "document_date": "2026-09-03"},
        {"sleeve": "bonds", "fund": "B", "isin": config.ISIN[config.BONDS], "weight": 0.3, "management_fees": 0.0007,
         "transaction_costs": 0.0, "ongoing_costs": 0.0007, "document_date": "2026-09-29"},
        {"sleeve": "portfolio", "fund": "W", "isin": "", "weight": invested, "management_fees": 0.0016,
         "transaction_costs": 0.00007, "ongoing_costs": 0.00168, "document_date": ""},
    ])  # fmt: skip
    implementation = pd.DataFrame({"date": ["2026-10-07", "2026-10-08"], "implementation_cost_bps": [0.0, -9.6]})
    orders = pd.DataFrame({"date": ["2026-10-08", "2026-10-08", "2026-11-05"], "price_against_nav": against})
    page = site.Page()
    site._cost_of_ownership(page, costs, implementation, pd.DataFrame(), orders, now)
    return " ".join(page.sections["costs"])


def test_the_cost_sentence_reads_each_order_against_its_own_day_and_names_the_later_ones():
    now = {"weights_as_of": "2026-11-04", "positions_as_of": "2026-11-04", "built": "2026-11-05", "contributions_after": ""}
    text = _ownership_text(["below", "below", ""], now)
    assert "each of the two orders valued so far was executed below its day&#x27;s net asset value" in text or \
        "each of the two orders valued so far was executed below its day's net asset value" in text
    assert "The order of 5 November 2026 came after the last net asset values" in text
    assert "the net asset value is set at the close, so the gap can go either way" in text
    text = _ownership_text(["below", "above", ""], now)
    assert ("positive when the portfolio&#x27;s value is below reference portfolio A&#x27;s and negative when it is above."
            in text or "positive when the portfolio's value is below reference portfolio A's and negative when it is above." in text)
    assert "valued so far" not in text and "ahead" not in text and "trails" not in text
    assert ">Cash<" not in text
    # Cash not yet invested has its own row, so the weights add up to the portfolio.
    text = _ownership_text(["below", "below", ""], now, invested=0.952)
    assert ">Cash<" in text and ">4.8%<" in text and ">100.0%<" in text


def _page() -> str:
    return (config.ROOT / "index.html").read_text(encoding="utf-8")


def test_the_page_opens_with_the_site_menu_the_hero_and_five_views():
    # Appendices B and E of the house standard: the menu as renamed on 6 November 2026, the navy hero, five views.
    page = _page()
    menu = re.search(r'<div class="ch-menu"[^>]*>(.*?)</div>', page).group(1)
    assert re.findall(r">([^<]+)</a>", menu) == ["Investment research", "Portfolio", "Publications", "Academic CV"]
    assert "All projects" not in page and ">Projects<" not in page
    hero = re.search(r'<header class="ch-hero">(.*?)</header>', page, flags=re.S).group(1)
    assert f'<a href="{site.PROJECT_PAGE_URL}">&larr; Rules-based portfolio</a>' in hero
    assert '<p class="ch-over">Portfolio in practice</p>' in hero and "<h1>Rules-based portfolio</h1>" in hero
    assert re.search(r"<span>Figures as of \d{1,2} [A-Z][a-z]+ \d{4}</span><span>Built \d{1,2} [A-Z][a-z]+ \d{4}</span>", hero)
    assert re.findall(r">([^<]+)</a>", re.search(r'<div class="ch-docs">(.*?)</div>', hero).group(1)) == [
        "Rules", "Mandate", "Guide to the dashboard (PDF)", "Code on GitHub"]
    assert [v for v, _ in site.VIEWS] == ["overview", "performance", "portfolio", "risk", "method"]
    assert re.findall(r'data-view="([a-z]+)"', page) == [v for v, _ in site.VIEWS]


def test_every_former_view_address_lands_in_the_view_that_holds_its_part():
    # A link to a former view, such as #costs, opens the view that now holds the part, at the part.
    page = _page()
    starts = {v: page.index(f'id="view-{v}"') for v, _ in site.VIEWS}
    expected = {"rebalancing": "portfolio", "costs": "performance", "contributions": "performance", "lookthrough": "portfolio",
                "factors": "portfolio", "simulations": "risk", "log": "method", "lookthrough-risk-section": "risk",
                "method-not-done": "method", "key-facts": "overview", "glossary": "method"}  # fmt: skip
    for anchor, view in expected.items():
        at = page.index(f' id="{anchor}"')
        assert max((s, v) for v, s in starts.items() if s < at)[1] == view, anchor
    assert page.count(' id="costs"') == 1 and site.VIEW_OF["costs"] == "performance"


def test_no_return_sits_in_the_key_figures_and_one_sentence_gives_it():
    # E5: the strip shows where the portfolio stands against its rules, and the returns follow in the sentence under it.
    page = _page()
    labels = re.findall(r'<p class="ch-kpi__label">(.*?)</p>', page)
    assert labels == ["Equity weight", "Drift from target", "Drawdown now", "Orders this month"]
    assert re.search(r'<p class="ch-returns">Since the first purchase: <b>[^<]+</b> time-weighted and <b>[^<]+</b> '
                     r"money-weighted, in euro, after costs", page)  # fmt: skip
    daily = pd.DataFrame({"date": ["2026-10-07", "2026-10-08", "2027-10-29"], "growth_portfolio": [100.0, 99.0, 110.0]})
    first_year = pd.DataFrame({"money_weighted_since_start": [-0.02], "money_weighted_per_year": [float("nan")]})
    assert "not annualised. The record is shorter than a year, so no annual figures are shown yet." in site._returns(daily, first_year)
    later = pd.DataFrame({"money_weighted_since_start": [0.12], "money_weighted_per_year": [0.11]})
    assert "a year time-weighted and <b>+11.0%</b> a year money-weighted" in site._returns(daily, later)
    facts = re.findall(r"<dt>([^<]+)</dt>", re.search(r'<aside class="ch-facts".*?</aside>', page, flags=re.S).group(0))
    assert facts == ["Equity sleeve", "Bond sleeve", "Band", "Contributions", "Rebalancing", "Risk limit", "Ongoing costs",
                     "Valuation", "First purchase", "Benchmark"]  # fmt: skip
    # One number carries one wording everywhere, and each fund its full name, which identifies the share class held.
    assert "Target 70%, band 65 to 75" in page and " pts<" not in page
    assert "iShares MSCI ACWI UCITS ETF USD (Acc), target 70%" in page
    assert "Vanguard EUR Eurozone Government Bond UCITS ETF (EUR) Accumulating, target 30%" in page
    assert "a year at the sleeve weights, TER plus transaction costs (equity" in page
    assert "Every figure of the record is computed from the ledger" in page and "with a target of 70 per cent" in page
    footer = page.split("<footer>", 1)[1]
    assert "They are time-weighted, except the money-weighted return of the Overview and the monthly table." in footer
    assert "Past performance is no guide to future returns." in footer


def test_every_date_a_reader_sees_is_in_words():
    # E7: a note's line of figures and a cycle report, which the Log quotes word for word, keep their own. The rules'
    # amendments table writes its dates as the page does, and rules/RULES.md keeps its own form.
    import html
    import json

    page = _page()
    data = json.loads(re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', page,
                                flags=re.S).group(1).replace("<\\/", "</"))  # fmt: skip
    visible = re.sub(r"<script.*?</script>|<style.*?</style>|<head>.*?</head>", " ", page, flags=re.S)
    for fixed in (r'<p class="figures">.*?</p>', r'<div class="reportbody">.*?</div>'):
        visible = re.sub(fixed, " ", visible, flags=re.S)
    text = re.sub(r"\b(notes|cycles)/\d{4}-\d{2}\.md", " ", html.unescape(re.sub(r"<[^>]+>", " ", visible)))
    assert not re.search(r"\b\d{4}-\d{2}\b", text), re.findall(r".{0,40}\b\d{4}-\d{2}\b.{0,20}", text)
    shown = json.dumps([[t.get("customdata"), t.get("text"), t.get("name")] for c in data["charts"] for t in c["traces"]])
    assert not re.search(r"\b\d{4}-\d{2}\b", shown)
    formats = re.findall(r'"(?:tick|hover)format":"([^"]+)"', json.dumps(data["charts"], separators=(",", ":")))
    assert formats and not [f for f in formats if "%m" in f or "%Y-" in f]
    assert "<td>7 Oct 2026</td>" in page and "| 2026-10-07 |" in (config.ROOT / "rules" / "RULES.md").read_text()


def test_the_sleeves_take_navy_and_slate_and_the_band_its_shade():
    palette = json.loads((config.SITE_DIR / "palette.json").read_text())["light"]
    assert (palette["equity"], palette["bonds"], palette["band"]) == ("#16213a", "#8d9ab0", "#e9edf3")

