"""One rounding for every display, and colours named by role only."""

import pytest

from portfolio import formatting as fmt, site


def test_rounding_rules():
    assert fmt.pct(0.70149) == "70.1%" and fmt.pct(-0.00049, signed=True) == "0.0%"
    assert fmt.pct(0.0312, signed=True) == "+3.1%" and fmt.pct(-0.0312, signed=True) == "−3.1%"
    assert fmt.bps(-11.6) == "−12 bp" and fmt.bps(0.4) == "0 bp"
    assert fmt.loading(-0.0579) == "−0.06" and fmt.loading(0.996) == "1.00"
    assert fmt.points(0.25) in ("+0.2 points", "+0.3 points")
    assert fmt.day("2026-10-08") == "2026-10-08" and fmt.month("2026-10-31") == "2026-10"
    assert fmt.pct(float("nan")) == "n/a"


def test_a_chart_with_a_colour_value_stops_the_build():
    palette = {"light": {"accent": "x"}, "dark": {"accent": "x"}}
    site._check_roles([{"traces": [{"marker": {"color": "@accent"}}]}], palette)
    with pytest.raises(ValueError, match="by value"):
        site._check_roles([{"traces": [{"marker": {"color": "#2a78d6"}}]}], palette)
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
