"""The benchmark and the comparators that follow the target weights in force: with a made-up change of the target
weights under rule 11, the page and the guide give 70/30 and 70 per cent only where they stay by design. Those are
the rules, which change only by amendment; the simulations and the history exhibit, which run the rules of
7 October 2026 at 70/30 and say so; the allocation test's own figures for its splits; 70/30 fixed, the comparator
that keeps a change of the target visible; and the issued records, the cycle reports and the monthly notes, which
keep their words. The README's opening gives the target of today and is not on the page."""

import html
import json
import re

import pandas as pd

from portfolio import rule_11, site
from test_metrics_references import made_up_change

FOUND = re.compile(r"70/30|70 per cent")
# The parts that keep 70/30 by design, by the heading they stand under.
KEPT_UNDER = re.compile(r"\bThe rules\b|Simulat|Resampled paths|History\b|rolling ten-year windows|The allocation test")
# The sentences that keep it by design wherever they stand: the fixed comparator, the simulations' figure in the
# Risk view, and the allocation test's result in the section on what the portfolio does not do.
KEPT_PHRASES = re.compile(r"70/30 fixed|the split nearest the equity weight|is the largest target weight whose worst "
                          r"fall|the worst fall at 70/30 is")  # fmt: skip
# The charts of the simulations, the history exhibit and the allocation test.
KEPT_CHARTS = {"c21", "c25", "c26", "c27a", "c27b", "c33", "history-windows"}
HEADING = re.compile(r"<h[23][^>]*>(.*?)</h[23]>", re.S)
# The rules card, which renders rules/RULES.md, and the issued records, which keep their words.
KEPT_REGIONS = re.compile(r'<article class="card wide rules" id="method-rules">.*?</article>|<article class="card wide '
                          r'notebody">.*?</article>|<div class="reportbody">.*?</div><p class="label">', re.S)  # fmt: skip


def _plain(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def _strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, str):
        yield value


def stray(document: str) -> list:
    """Each 70/30 or 70 per cent of a page outside the places that keep it, with its heading and its words."""
    data = re.search(r'<script type="application/json" id="dashboard-data">(.*?)</script>', document, flags=re.S)
    body = KEPT_REGIONS.sub(" ", re.sub(r"<style.*?</style>|<script.*?</script>", " ", document, flags=re.S))
    found = []
    for m in FOUND.finditer(body):
        opened = max(body.rfind("<h2", 0, m.start()), body.rfind("<h3", 0, m.start()))
        if opened > max(body.rfind("</h2>", 0, m.start()), body.rfind("</h3>", 0, m.start())):
            heading = _plain(body[opened: body.find("</h", m.start())])  # the words are in the heading itself
        else:
            headings = HEADING.findall(body, 0, m.start())
            heading = _plain(headings[-1]) if headings else ""
        words = _plain(body[max(0, m.start() - 60): m.end() + 60])
        if not (KEPT_UNDER.search(heading) or KEPT_PHRASES.search(words)):
            found.append((heading, words))
    if data:
        for chart in json.loads(data.group(1).replace("<\\/", "</"))["charts"]:
            if chart.get("id") not in KEPT_CHARTS:
                found += [(chart.get("id"), s) for s in _strings(chart) if FOUND.search(s) and not KEPT_PHRASES.search(s)]
    return found


def test_with_a_made_up_change_of_target_the_page_and_the_guide_give_70_30_only_where_it_stays(monkeypatch, tmp_path):
    monkeypatch.setattr(rule_11, "load", lambda *args, **kwargs: made_up_change("2026-11-05", "60/40"))
    assert rule_11.current_target() == {"equity": 0.60, "bonds": 0.40}
    site.build(out_dir=tmp_path)
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    guide = (tmp_path / "guide" / "guide.html").read_text(encoding="utf-8")
    assert stray(page) == [] and stray(guide) == []
    # The texts built by the program give the split in force.
    assert "with a target of 60 per cent in a global equity ETF and 40 per cent" in _plain(page)
    assert '<meta name="description" content="A real-money portfolio run under written rules, 60/40 equity' in page
    assert "Reference B, back to the target weights every cycle day" in _plain(page)


def test_at_70_30_the_texts_built_by_the_program_give_70_30(monkeypatch, tmp_path):
    monkeypatch.setattr(rule_11, "load", lambda *args, **kwargs: pd.DataFrame(columns=rule_11.TARGET_COLUMNS))
    site.build(out_dir=tmp_path)
    page = _plain((tmp_path / "index.html").read_text(encoding="utf-8"))
    assert "with a target of 70 per cent in a global equity ETF and 30 per cent" in page
    assert "lie on one line through reference portfolio A, which is 70/30." in page
