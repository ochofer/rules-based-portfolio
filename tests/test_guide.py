"""The guide to the dashboard: an entry for every part of the page, references that become the page's numbers, an
edition that keeps its date while the words stay, and a PDF that carries the page's words."""

import html
import re

import pandas as pd
import pytest

from portfolio import config, guide, site

GUIDE = config.ROOT / guide.FOLDER


def _ids(text):
    return set(re.findall(r'\bid="([^"]+)"', text))


def test_the_guide_has_an_entry_for_every_part_of_the_dashboard():
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    text = (GUIDE / guide.PAGE).read_text(encoding="utf-8")
    for kind, n, title in re.findall(r'<h3 id="(figure|table)-(\d+)">(Figure|Table) \d+ \|', page):
        assert f'id="{kind}-{n}">{title} {n} | ' in text or f'id="{kind}-{n}"><span' in text, f"{kind} {n}"
        assert f'href="{config.DASHBOARD_URL}#{kind}-{n}"' in text
    anchors = re.findall(r'<div class="(?:section|group)[^"]*" id="([^"]+)">', page) + ["key-facts"]
    anchors += [a for a, h in re.findall(r'<article class="card[^"]*" id="([^"]+)">(<h3[^>]*>)', page) if 'id="' not in h]
    assert anchors and set(anchors) <= _ids(text)
    for view, _ in site.VIEWS:
        assert f'id="view-{view}"' in text and f'href="{config.DASHBOARD_URL}#{view}"' in text
    tiles = [html.unescape(t) for t in re.findall(r'<p class="(?:name|ch-kpi__label)">(.*?)</p>', page)]
    assert len(tiles) >= 13 and "Drift from target" in tiles
    for tile in tiles:
        assert f"<strong>{tile}.</strong>" in html.unescape(text), tile


def _found():
    return {"views": {"overview": "Overview", "costs": "Costs"}, "tiles": {"Equity weight": "overview"},
            "exhibits": {"c2": ("figure", 1, "overview"), "ownership": ("table", 1, "costs")},
            "anchors": {"costs-part": "costs"}}


SOURCE = """# Guide

## ⟦view:overview⟧ Overview

**Equity weight.** The equity sleeve's weight.

### ⟦c2⟧ Allocation now

⟦c2⟧ shows the weights, and ⟦ownership⟧ the costs.

## ⟦view:costs⟧ Costs

### ⟦#costs-part⟧ A part of the view

### ⟦ownership⟧ What it costs
"""


def test_a_part_of_the_dashboard_without_an_entry_stops_the_build():
    assert guide.coverage(SOURCE, _found()) == []
    more = _found()
    more["exhibits"]["c9"] = ("figure", 2, "costs")
    more["tiles"]["Drift from 70%"] = "overview"
    faults = guide.coverage(SOURCE, more)
    assert any("exhibit c9 has no entry" in f for f in faults) and any("tile Drift from 70% has no entry" in f for f in faults)
    fewer = _found()
    del fewer["anchors"]["costs-part"]
    assert any("entry for the part costs-part, which the dashboard no longer holds" in f for f in guide.coverage(SOURCE, fewer))


def test_a_reference_becomes_the_exhibit_number_with_links_to_the_entry_and_the_dashboard():
    text, contents = guide.body(SOURCE, _found())
    assert '<a href="#figure-1">Figure 1</a> shows the weights, and <a href="#table-1">Table 1</a> the costs.' in text
    assert '<h3 id="figure-1">Figure 1 | Allocation now</h3>' in text
    assert f'<a href="{config.DASHBOARD_URL}#figure-1">Figure 1, in the Overview view</a>' in text
    assert f'<a href="{config.DASHBOARD_URL}#costs-part">A part of the view, in the Costs view</a>' in text
    assert [c[1] for c in contents] == ["view-overview", "figure-1", "view-costs", "costs-part", "table-1"]
    with pytest.raises(guide.GuideError, match="c99"):
        guide.body(SOURCE + "\nSee ⟦c99⟧.\n", _found())


def test_a_heading_may_cover_a_part_and_its_one_exhibit():
    found = _found()
    found["anchors"]["log-table"] = "costs"
    source = SOURCE.replace("### ⟦ownership⟧ What it costs", "### ⟦ownership⟧ ⟦#log-table⟧ What it costs")
    assert guide.coverage(source, found) == []
    text, _ = guide.body(source, found)
    assert '<h3 id="table-1"><span id="log-table"></span>Table 1 | What it costs</h3>' in text


def test_the_edition_keeps_its_date_while_the_words_stay_the_same(tmp_path):
    page = f"<head></head><body><p>Edition of {guide.EDITION}</p><p>Words</p><footer>Edition of {guide.EDITION}</footer>"
    previous = tmp_path / "guide.html"
    assert guide.edition(page, previous, "2026-11-08") == "8 November 2026"
    previous.write_text(page.replace(guide.EDITION, "8 November 2026"))
    assert guide.edition(page, previous, "2026-12-07") == "8 November 2026"
    assert guide.edition(page.replace("<head>", f"<head>{config.COUNTER}"), previous, "2026-12-07") == "8 November 2026"
    assert guide.edition(page.replace("Words", "New words"), previous, "2026-12-07") == "7 December 2026"


def test_the_pdf_is_the_print_of_the_page_with_its_title_and_author():
    assert guide.check() == []


def test_every_page_the_repository_publishes_carries_the_pinned_visit_counter_in_its_head():
    assert 'integrity="sha384-' in config.COUNTER and "count.v5.js" in config.COUNTER
    assert "/\\.pdf$/i.test(u.pathname)" in config.COUNTER and "event: true" in config.COUNTER
    for page in (config.ROOT / "index.html", GUIDE / guide.PAGE):
        head = page.read_text(encoding="utf-8").split("</head>")[0]
        assert head.count(config.COUNTER) == 1, page.name


def test_the_dashboard_and_the_readme_link_to_the_guide():
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    assert '<a href="guide/guide.pdf">Guide to the dashboard (PDF)</a>' in page
    assert "](guide/guide.pdf)" in (config.ROOT / "README.md").read_text(encoding="utf-8")
    menu = re.search(r'<div class="ch-menu"[^>]*>(.*?)</div>', (GUIDE / guide.PAGE).read_text(encoding="utf-8")).group(1)
    assert re.findall(r">([^<]+)</a>", menu) == ["Investment research", "Portfolio", "Publications", "Academic CV"]
    edition = re.search(r"Edition of (\d{1,2} [A-Z][a-z]+ \d{4})", (GUIDE / guide.PAGE).read_text(encoding="utf-8"))
    assert edition and pd.Timestamp(edition.group(1)) <= pd.Timestamp.today()
