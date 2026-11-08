"""The guide to the dashboard: guide/guide.html, built from guide/source.md with the dashboard, and guide/guide.pdf,
printed from that page.

The source holds one entry for every view, part, tile and exhibit of the dashboard. A heading names what its entry
covers with a mark between brackets: ⟦view:overview⟧ for a view, ⟦c3⟧ for the exhibit whose id is c3, and
⟦#log-notes⟧ for a part of a view with that anchor. A tile is covered by a paragraph that opens with its name in
bold. A mark in the text, such as ⟦c3⟧, becomes the exhibit's number with a link to its entry. The build stops when
the dashboard holds a view, an exhibit, an anchored part or a tile that the guide has no entry for, or when the guide
has an entry for something the dashboard no longer holds, so the guide changes whenever the dashboard does.

The page keeps the date of its edition while its words stay the same and takes the build's date when they change.
The PDF is printed from the page with `python3 -m portfolio guide --print`, and the tests fail while its words differ
from the page's.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path

import pandas as pd

from . import config, quarterly

FOLDER = "guide"
AUTHOR, SITE_URL, PROJECT_URL, FAVICON_URL = quarterly.AUTHOR, quarterly.SITE_URL, quarterly.PROJECT_URL, quarterly.FAVICON_URL
SOURCE = "source.md"
PAGE = "guide.html"
PDF = "guide.pdf"
TITLE = "Guide to the dashboard"
DOCUMENT_TITLE = f"{TITLE} | Rules-based portfolio"
EDITION = "⟦edition⟧"  # replaced by the edition's date once the page's words are known
MARK = re.compile("⟦([^⟧]+)⟧")
HEADING = re.compile("^(#{2,3}) ((?:⟦[^⟧]+⟧ )*)(.+)$", re.M)
EDITION_LINE = re.compile(r"Edition of (\d{1,2} [A-Z][a-z]+ \d{4})")


class GuideError(ValueError):
    pass


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def parts(sections: dict, numbers: dict, views) -> dict:
    """What the dashboard holds, from its numbered sections: the views, the exhibits by id with their kind, number
    and view, the anchored parts that are not exhibits, and the tiles, each with its view."""
    found = {"views": {v: title for v, title in views}, "exhibits": {}, "anchors": {}, "tiles": {}}
    by_number = {(kind, n): cid for cid, (kind, n) in numbers.items()}
    for view, _ in views:
        text = "".join(sections[view])
        for kind, n in re.findall(r'<h3 id="(figure|table)-(\d+)">', text):
            found["exhibits"][by_number[(kind, int(n))]] = (kind, int(n), view)
        for anchor, opening in re.findall(r'<(?:div|article) class="(?:section|card)[^"]*" id="([^"]+)">(<h\d[^>]*>)', text):
            if not re.match(r'<h3 id="(figure|table)-\d+">', opening):
                found["anchors"][anchor] = view
        for name in re.findall(r'<p class="name">(.*?)</p>', text, flags=re.S):
            found["tiles"][html.unescape(re.sub(r"<[^>]+>", "", name)).strip()] = view
    return found


def coverage(source: str, found: dict) -> list:
    """The faults of the guide against the dashboard: a part of the page without an entry, or an entry for a part the
    page no longer holds."""
    marks = [m for _, named, _ in HEADING.findall(source) for m in MARK.findall(named)]
    covered_views = {m.split(":", 1)[1] for m in marks if m.startswith("view:")}
    covered_anchors = {m[1:] for m in marks if m.startswith("#")}
    covered_exhibits = {m for m in marks if not m.startswith(("view:", "#"))}
    covered_tiles = set(re.findall(r"^\*\*([^*]+?)\.\*\*", source, flags=re.M))
    faults = []
    for label, wanted, covered in (("view", set(found["views"]), covered_views),
                                   ("exhibit", set(found["exhibits"]), covered_exhibits),
                                   ("part", set(found["anchors"]), covered_anchors),
                                   ("tile", set(found["tiles"]), covered_tiles)):  # fmt: skip
        faults += [f"the dashboard's {label} {x} has no entry in {FOLDER}/{SOURCE}" for x in sorted(wanted - covered)]
        if label != "tile":
            faults += [f"{FOLDER}/{SOURCE} has an entry for the {label} {x}, which the dashboard no longer holds"
                       for x in sorted(covered - wanted)]  # fmt: skip
    return faults


def _number_text(cid: str, found: dict) -> tuple:
    kind, n, view = found["exhibits"][cid]
    return f"{kind}-{n}", f"{kind.capitalize()} {n}", view


def _where(anchor: str, label: str, view: str, found: dict) -> str:
    view_title = found["views"][view]
    return (f'<p class="gd-where">On the dashboard: <a href="{config.DASHBOARD_URL}#{anchor}">{html.escape(label)}, '
            f"in the {html.escape(view_title)} view</a></p>")  # fmt: skip


def _heading(level: str, named: str, title: str, found: dict, contents: list) -> str:
    """A heading of the source as HTML, with its id and, for a part of the dashboard, the link to it. A heading may
    name more than one part, as when a section of a view holds a single exhibit: the first mark names the entry, and
    each further anchor gets a target of its own in the heading."""
    tag = "h2" if level == "##" else "h3"
    marks = MARK.findall(named)
    mark = marks[0] if marks else ""
    targets = "".join(f'<span id="{m[1:]}"></span>' for m in marks[1:] if m.startswith("#"))
    if not mark:
        anchor, label, where = _slug(title), title, ""
    elif mark.startswith("view:"):
        view = mark.split(":", 1)[1]
        anchor, label = f"view-{view}", title
        where = (f'<p class="gd-where">On the dashboard: <a href="{config.DASHBOARD_URL}#{view}">the '
                 f"{html.escape(found['views'][view])} view</a></p>")  # fmt: skip
    elif mark.startswith("#"):
        anchor, label = mark[1:], title
        where = _where(anchor, title, found["anchors"][anchor], found)
    else:
        anchor, number, view = _number_text(mark, found)
        label = f"{number} | {title}"
        where = _where(anchor, number, view, found)
    contents.append((tag, anchor, label))
    return f'\n<{tag} id="{anchor}">{targets}{html.escape(label)}</{tag}>\n{where}\n'


def body(source: str, found: dict) -> tuple:
    """The guide's text as HTML, and its contents as (level, anchor, label)."""
    import markdown

    contents = []
    text = re.sub(r"\A# [^\n]*\n", "", source)
    text = HEADING.sub(lambda m: _heading(m.group(1), m.group(2), m.group(3), found, contents), text)

    def inline(m):
        mark = m.group(1)
        if mark not in found["exhibits"]:
            raise GuideError(f"{FOLDER}/{SOURCE} refers to {mark}, which the dashboard does not hold")
        anchor, number, _ = _number_text(mark, found)
        return f'<a href="#{anchor}">{number}</a>'

    text = MARK.sub(inline, text)
    return markdown.markdown(text), contents


def _contents(contents: list) -> str:
    """The contents: each section of the guide, with its entries under it, every line a link."""
    groups = []
    for tag, anchor, label in contents + [("h2", "terms", "Terms")]:
        if tag == "h2" or not groups:
            groups.append((anchor, label, []))
        else:
            groups[-1][2].append((anchor, label))
    items = "".join(f'<li><a href="#{a}">{html.escape(l)}</a>'
                    + ("<ul>" + "".join(f'<li><a href="#{sa}">{html.escape(sl)}</a></li>' for sa, sl in sub) + "</ul>"
                       if sub else "") + "</li>" for a, l, sub in groups)  # fmt: skip
    return f'<div class="gd-contents" role="navigation" aria-label="Contents"><h2 id="contents">Contents</h2><ul>{items}</ul></div>'


def page(source: str, found: dict, terms: list) -> str:
    """The guide's page, with its edition's date left as a mark."""
    text, contents = body(source, found)
    css = (config.SITE_DIR / "report.css").read_text(encoding="utf-8").replace("Quarterly report, ISSUE", TITLE)
    css += (config.SITE_DIR / "guide.css").read_text(encoding="utf-8")
    glossary = "".join(f"<dt>{html.escape(a)}</dt><dd>{html.escape(b)}</dd>" for a, b in terms)
    stamp = (f"Edition of {EDITION} &middot; For the dashboard at "
             f'<a href="{config.DASHBOARD_URL}">{config.DASHBOARD_URL}</a>'
             f'<span class="rp-noprint"> &middot; <a href="{PDF}">The guide as a PDF</a></span>')  # fmt: skip
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(DOCUMENT_TITLE)}</title>
<meta name="author" content="{AUTHOR}">
<meta name="description" content="What each view, tile, figure and table of the rules-based portfolio's dashboard shows, how to read it and where its numbers come from.">
<link rel="icon" href="{FAVICON_URL}" type="image/svg+xml">
<style>{css}</style>
</head>
<body>
<header class="ch-band"><div class="ch-band__in">
  <a class="ch-word" href="{SITE_URL}">Carlo Hofer</a>
  <div class="ch-menu" role="navigation" aria-label="Site"><a href="{SITE_URL}projects/">Projects</a></div>
</div></header>
<p class="ch-back"><a href="{config.DASHBOARD_URL}">&larr; Rules-based portfolio, the dashboard</a> &middot; <a href="{PROJECT_URL}">The project</a></p>
<main class="rp gd">
<p class="rp-kicker">Rules-based portfolio &middot; {TITLE}</p>
<h1>{TITLE}</h1>
<p class="rp-stamp">{stamp}</p>
{_contents(contents)}
{text}
<h2 id="terms">Terms</h2>
<dl class="rp-terms">{glossary}</dl>
</main>
<footer class="ch-foot"><div>{AUTHOR} &middot; Data: the issuers' published data &middot; <a href="{config.REPOSITORY_URL}">Code on GitHub</a> &middot; Edition of {EDITION}</div></footer>
</body>
</html>
"""


def edition(new_page: str, previous: Path, built) -> str:
    """The edition's date: the previous page's while the words stay the same, and the build's day when they change."""
    if previous.exists():
        old = previous.read_text(encoding="utf-8")
        dated = EDITION_LINE.search(old)
        if dated and EDITION_LINE.sub(f"Edition of {EDITION}", old) == new_page:
            return dated.group(1)
    day = pd.Timestamp(built)
    return f"{day.day} {day.strftime('%B %Y')}"


def write(sections: dict, numbers: dict, views, terms: list, built, out_dir: Path = None) -> Path:
    """Build the guide's page from its source and the numbered dashboard, and stop when the two do not cover each
    other. The edition is read from the repository's own page, so a build elsewhere reproduces it."""
    source = (config.ROOT / FOLDER / SOURCE).read_text(encoding="utf-8")
    found = parts(sections, numbers, views)
    faults = coverage(source, found)
    if faults:
        raise GuideError("the guide does not match the dashboard: " + "; ".join(faults))
    new = page(source, found, terms)
    dated = edition(new, config.ROOT / FOLDER / PAGE, built)
    target = (out_dir or config.ROOT) / FOLDER / PAGE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(new.replace(EDITION, dated), encoding="utf-8")
    return target


# The PDF ----------------------------------------------------------------------------------------------


def print_pdf(page_path: Path = None, font: Path = None) -> Path:
    """Print the page to guide/guide.pdf with Chromium, with the outline of its headings, and set the author. A print
    that does not carry the page's words is not kept."""
    from playwright.sync_api import sync_playwright  # only where the PDF is printed
    import pikepdf

    page_path = Path(page_path or config.ROOT / FOLDER / PAGE)
    out = page_path.with_name(PDF)
    part = out.with_suffix(".part.pdf")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page()
        if font:
            data = Path(font).read_bytes()
            tab.route("https://www.carlohofer.com/assets/fonts/**", lambda r: r.fulfill(
                status=200, body=data, headers={"Content-Type": "font/woff2", "Access-Control-Allow-Origin": "*"}))
        tab.goto(page_path.resolve().as_uri(), wait_until="networkidle")
        tab.evaluate("document.fonts.ready")
        tab.pdf(path=str(part), format="A4", print_background=True, prefer_css_page_size=True, tagged=True,
                outline=True)  # fmt: skip
        browser.close()
    with pikepdf.open(part, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Author"] = AUTHOR
        pdf.save(part)
    faults = check(page_path, part)
    if faults:
        part.unlink()
        raise GuideError(f"the print was not kept: {faults[0]}")
    part.replace(out)
    return out


def metadata_faults(path: Path) -> list:
    """The faults of the PDF's metadata: the page's title, the author and the printing tool, and no attached file or
    metadata stream. Internal links are kept as named destinations, the one entry the catalog's names may hold. It
    reads the PDF with pdfplumber, as the tests do, so the check runs wherever the tests run."""
    import pdfplumber
    from pdfminer.pdftypes import resolve1

    faults = []
    with pdfplumber.open(path) as pdf:
        info = {k: str(v) for k, v in (pdf.metadata or {}).items()}
        catalog = pdf.doc.catalog
        names = {f"/{k}" for k in (resolve1(catalog["Names"]) or {})} if "Names" in catalog else set()
        attached = sorted(f"/{k}" for k in ("AF", "Metadata") if k in catalog)
    if info.get("Author") != AUTHOR:
        faults.append(f"the author is {info.get('Author')!r}, not {AUTHOR!r}")
    if info.get("Title") != DOCUMENT_TITLE:
        faults.append(f"the title is {info.get('Title')!r}, not the page's")
    extra = sorted(set(info) - quarterly.INFO_FIELDS)
    if extra:
        faults.append(f"the PDF has fields beyond the title, the author and the printing tool: {extra}")
    if names - {"/Dests"}:
        faults.append(f"the PDF's names hold {sorted(names - {'/Dests'})}, beyond the destinations of its links")
    if attached:
        faults.append(f"the PDF carries {attached}, which the printing tool does not write")
    return faults


def check(page_path: Path = None, pdf_path: Path = None) -> list:
    """The faults of the PDF against the page: it prints every word of the page and nothing else, its metadata is the
    page's, and it exists."""
    import logging

    logging.getLogger("pdfminer").setLevel(logging.ERROR)  # Chromium's fonts lack a box that the reader warns about
    page_path = Path(page_path or config.ROOT / FOLDER / PAGE)
    pdf_path = Path(pdf_path or page_path.with_name(PDF))
    if not pdf_path.exists():
        return [f"{FOLDER}/{PDF} does not exist: print it with python3 -m portfolio guide --print"]
    faults = quarterly.compare_words(page_path.read_text(encoding="utf-8"), pdf_path)
    faults = [f"{FOLDER}/{PDF} is not the print of {FOLDER}/{PAGE}: {f}" for f in faults]
    return faults + metadata_faults(pdf_path)
