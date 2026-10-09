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
    assert "<h3>A title</h3>" in html and "As of 2026-10-08" in html and "outputs/x.csv" in html
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
