"""Step 4 of the pipeline: the public outputs to the dashboard, index.html at the repository root.

The page is built from the committed files only (outputs/, method/, mandate/ and rules/RULES.md), so
every figure on it can be traced to a file. Each figure is formatted once by formatting.py and passed to
the page as a string; the page's script maps colour roles to the palette (site/palette.json) and draws
each chart with Plotly. A chart that names a colour by anything other than a role stops the build.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd

from . import comparisons as comparisons_module
from . import config, references, trading_days
from . import risk as risk_module
from . import formatting as fmt
from . import guide as guide_module
from . import notes as notes_module
from . import quarterly as quarterly_module

SITE_URL = "https://www.carlohofer.com/"
PROJECTS_URL = SITE_URL + "projects/"
PROJECT_PAGE_URL = PROJECTS_URL + "rules-based-portfolio/"
FAVICON_URL = SITE_URL + "images/favicon.svg"
WRAP_FIRST_ABOVE = 28  # characters: a longer label in a table's first column wraps on a phone
PLOTLY = "https://cdn.plot.ly/plotly-cartesian-2.35.2.min.js"  # the smallest bundle with the heatmap
PLOTLY_INTEGRITY = "sha384-gKF7EaMDoWW1zLWkouldmVWF5jqEKrAswAciW73iNzqlomabVVPO60XkJvL5q/Ie"
VIEWS = [
    ("overview", "Overview"),
    ("performance", "Performance"),
    ("portfolio", "Portfolio"),
    ("risk", "Risk"),
    ("method", "Method"),
]
# The parts of the page in page order, each with its view and the title of its heading. A part's anchor is its
# name, so that a link to #costs or #lookthrough opens the view that holds the part, at the part. A part without a
# title opens its view, or carries its own heading.
PARTS = [
    ("overview", "overview", None),
    ("growth", "performance", None),
    ("comparisons", "performance", "Comparisons"),
    ("contributions", "performance", "Contributions"),
    ("costs", "performance", "Costs"),
    ("rebalancing", "portfolio", "Rebalancing"),
    ("lookthrough", "portfolio", "Look-through"),
    ("factors", "portfolio", "Factor exposures"),
    ("risk", "risk", None),
    ("simulations", "risk", "Simulations"),
    ("method", "method", None),
    ("glossary", "method", "Terms"),
    ("log", "method", "Log"),
]
VIEW_OF = {part: view for part, view, _ in PARTS}
FACTOR_ROLE = {f: f"@factor_{i}" for i, f in enumerate(config.FACTORS, start=1)}
SHORT_FUND = {
    "IE00B44Z5B48": "SPDR MSCI ACWI",
    "IE00B6R52259": "iShares MSCI ACWI",
    "IE00BK5BQT80": "Vanguard FTSE All-World",
    "IE00B3YLTY66": "SPDR MSCI ACWI IMI",
    "IE000716YHJ7": "Invesco FTSE All-World",
    "IE00BH04GL39": "Vanguard EUR Eurozone Govt",
    "LU2089238898": "Amundi Prime Euro Govt",
    "IE00BMYHQM42": "SPDR Bloomberg Euro Govt",
    "LU0290355717": "Xtrackers Eurozone Govt",
    "IE00066KZ5B5": "HSBC Euro Govt",
    "IE0008U15456": "iShares Core EUR Govt",
    "LU0969639474": "UBS Core EUR Gov 1-10",
}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
YEAR_SYMBOL = {2023: "circle", 2024: "square", 2025: "diamond"}
NUMBER_WORD = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}


class Page:
    """Collects the charts of each part of the page and their HTML. views() then sets the parts into their views."""

    def __init__(self):
        self.charts = []
        self.sections = {part: [] for part, _, _ in PARTS}

    def add(self, part, html_block, chart=None):
        self.sections[part].append(html_block)
        if chart:
            chart["view"] = part
            self.charts.append(chart)

    def views(self, leads: dict) -> None:
        """Each view's parts in page order, a part with a title under a heading that carries its lead, and every
        chart drawn with the view that holds it."""
        views = {v: [] for v, _ in VIEWS}
        for part, view, title in PARTS:
            if title:
                views[view].append(_group(title, part, leads.get(part, "")))
            elif part in leads:
                views[view].append(f'<p class="wide partlead">{leads[part]}</p>')
            views[view] += self.sections[part]
        for chart in self.charts:
            chart["view"] = VIEW_OF.get(chart["view"], chart["view"])
        self.sections = views


def _read(name: str, folder: Path = None) -> pd.DataFrame:
    path = (folder or config.OUTPUTS_DIR) / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


ROUNDING = "Due to rounding, the parts may not sum to 100 per cent."


def _table(columns, rows, numeric=(), prose=False, wrap_first=None, rounding=False, wrap_head=False) -> str:
    head = "".join(f'<th class="num">{_esc(c)}</th>' if c in numeric else f"<th>{_esc(c)}</th>" for c in columns)
    body = []
    for r in rows:
        cells = "".join(
            f'<td class="num">{_esc(v)}</td>' if c in numeric else f"<td>{_esc(v)}</td>" for c, v in zip(columns, r)
        )
        body.append(f"<tr>{cells}</tr>")
    # The first column stays in place while the table scrolls sideways. Long labels wrap on a phone, so that
    # the column never covers the columns that scroll behind it.
    longest = max((len(str(r[0])) for r in rows), default=0)
    wrap_first = longest > WRAP_FIRST_ABOVE if wrap_first is None else wrap_first
    classes = (["wrapfirst"] if wrap_first else []) + (["prose"] if prose else []) + (["headwrap"] if wrap_head else [])
    wrap = f' class="{" ".join(classes)}"' if classes else ""
    note = f'<p class="rounding">{ROUNDING}</p>' if rounding else ""
    return (f'<div class="tw"><div class="tablewrap"><table{wrap}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div>{note}')


def _files(source) -> str:
    """The files of a source line, in the body's type."""
    return ", ".join(_esc(s) for s in ([source] if isinstance(source, str) else source))


def _card(cid, title, asof, source, plot=True, table=None, note=None, wide=False, height=300, empty=None,
          anchor=None, kind=None, extra=None) -> str:  # fmt: skip
    """A card. A chart card is a figure and a card that is a table on its own is a table (kind), each numbered by
    the build in page order. A card of text takes kind="text" and no number. A note may be one paragraph or a tuple of them,
    and extra is markup placed under them."""
    kind = kind or ("figure" if plot else "text")
    target = f' id="{anchor}"' if anchor else ""
    heading = f'<h3 data-exhibit="{cid}" data-kind="{kind}">' if kind in ("figure", "table") else "<h3>"
    parts = [f'<article class="card{" wide" if wide else ""}"{target}>', f"{heading}{_esc(title)}</h3>"]
    if asof:
        parts.append(f'<p class="asof">{_esc(asof)}</p>')
    if empty:
        parts.append(f'<div class="empty">{_esc(empty)}</div>')
    elif plot:
        parts.append(f'<div class="plot" id="{cid}" style="height:{height}px" role="img" aria-label="{_esc(title)}"></div>')
    for paragraph in [note] if isinstance(note, str) else (note or []):
        parts.append(f'<p class="note">{_esc(paragraph)}</p>')
    if extra:
        parts.append(extra)
    if source:
        parts.append(f'<p class="source">Source: {_files(source)}</p>')
    if table:
        parts.append(f'<details class="twin"><summary>Table</summary>{table}</details>')
    parts.append("</article>")
    return "".join(parts)


def _ref(cid: str) -> str:
    """A reference in the text to an exhibit, written as Figure N or Table N, with a link, once the build has
    numbered the page."""
    return f"\u27e6{cid}\u27e7"


EXHIBIT = re.compile(r'<h3 data-exhibit="([^"]+)" data-kind="(figure|table)">')
REFERENCE = re.compile("\u27e6([^\u27e7]+)\u27e7")
NOTE_MARK = re.compile("\u2e28note:([a-z0-9_]+)\u2e29")
NOTE_LIST = "\u2e28notes\u2e29"


def _note(key: str) -> str:
    """A footnote mark for one of CITATIONS, numbered by the build in order of first mention on the page."""
    return f"\u2e28note:{key}\u2e29"


def _note_text(text: str, url: str, title: str = None) -> str:
    """A note of the Notes list. A paper or a dataset with a DOI is followed by the DOI's address. A web page without
    a DOI carries its link on its title, given as title, and its address is not written out."""
    if title is None:
        return f'{_esc(text)} <a href="{_esc(url)}">{_esc(url)}</a>'
    if text.count(title) != 1:
        raise ValueError(f"the note does not name its title once: {title}")
    before, after = text.split(title)
    return f'{_esc(before)}<a href="{_esc(url)}">{_esc(title)}</a>{_esc(after)}'


def _number_notes(sections: dict) -> list:
    """Number the notes in order of first mention across the views, write each mark as a link to its note and the
    Notes list in its place. A mark without a note, or marks on a page without the Notes list, stop the build."""
    order = []
    for v, _ in VIEWS:
        for html in sections[v]:
            for key in NOTE_MARK.findall(html):
                if key not in CITATIONS:
                    raise ValueError(f"the text cites {key}, which has no note")
                if key not in order:
                    order.append(key)
    if order and sum(html.count(NOTE_LIST) for v, _ in VIEWS for html in sections[v]) != 1:
        raise ValueError("the page cites notes and does not carry the Notes list once")
    number = {key: i for i, key in enumerate(order, start=1)}
    seen = set()

    def mark(m):
        n = number[m.group(1)]
        first = n not in seen
        seen.add(n)
        return _fn(n) if first else f'<sup class="fn"><a href="#note-{n}">{n}</a></sup>'

    items = "".join(f'<li id="note-{number[k]}">{_note_text(*CITATIONS[k])}</li>' for k in order)
    for v, _ in VIEWS:
        sections[v] = [NOTE_MARK.sub(mark, html).replace(NOTE_LIST, items) for html in sections[v]]
    return order


def _number(sections: dict) -> dict:
    """Number the figures and the tables in page order across the views, and write every reference in the
    text from the exhibit it points to. A reference to an exhibit that is not on the page stops the build."""
    numbers, counts = {}, {"figure": 0, "table": 0}

    def heading(m):
        cid, kind = m.group(1), m.group(2)
        if cid in numbers:
            raise ValueError(f"exhibit {cid} appears twice on the page")
        counts[kind] += 1
        numbers[cid] = (kind, counts[kind])
        return f'<h3 id="{kind}-{counts[kind]}">{kind.capitalize()} {counts[kind]} | '

    for v, _ in VIEWS:
        sections[v] = [EXHIBIT.sub(heading, html) for html in sections[v]]

    def reference(m):
        if m.group(1) not in numbers:
            raise ValueError(f"the text refers to {m.group(1)}, which is not on the page")
        kind, n = numbers[m.group(1)]
        return f'<a href="#{kind}-{n}">{kind.capitalize()} {n}</a>'

    for v, _ in VIEWS:
        sections[v] = [REFERENCE.sub(reference, html) for html in sections[v]]
    return numbers


def _hover(texts) -> dict:
    return {"customdata": list(texts), "hovertemplate": "%{customdata}<extra></extra>"}


def _hline(y, role="@axis", dash=None, label=None, xref="paper", width=1):
    shape = {"type": "line", "xref": xref, "x0": 0, "x1": 1, "yref": "y", "y0": y, "y1": y,
             "line": {"color": role, "width": width}}  # fmt: skip
    if dash:
        shape["line"]["dash"] = dash
    return shape


def _vline(x, role="@axis"):
    return {"type": "line", "yref": "paper", "y0": 0, "y1": 1, "xref": "x", "x0": x, "x1": x,
            "line": {"color": role, "width": 1}}  # fmt: skip


def _label(x, y, text, xref="x", yref="y", anchor="left", role="@ink2", xshift=6, yshift=0):
    return {"x": x, "y": y, "xref": xref, "yref": yref, "text": _esc(text), "showarrow": False,
            "xanchor": anchor, "xshift": xshift, "yshift": yshift, "font": {"color": role, "size": 12.5}}  # fmt: skip


# The mandate's two limits on a chart of falls: the full label at width, a short one on a phone. A limit is a
# dashed line with its label at the end.
LIMIT_LABELS = ((35, "Test limit of the mandate, 35%", "Test limit, 35%"), (40, "Outer bound, 40%", "Outer bound, 40%"))
FALL_AXIS_ROOM = 1.08  # the axis runs a little past its deepest tick, so the tick's label clears the dates


def _limit_lines(deepest: float, x: float = 1, anchor: str = "right", levels=(35, 40)) -> tuple:
    """The limit lines within the range, and their labels at width and on a phone."""
    shapes, wide, narrow = [], [], []
    for level, long_text, short_text in LIMIT_LABELS:
        if level <= deepest and level in levels:
            shapes.append(_hline(level, "@ink2", dash="dash", width=1.5))
            wide.append({**_label(x, level, long_text, xref="paper", anchor=anchor, yshift=2, xshift=0), "yanchor": "bottom"})
            narrow.append({**_label(x, level, short_text, xref="paper", anchor=anchor, yshift=2, xshift=0), "yanchor": "bottom"})
    return shapes, wide, narrow


def _group(title: str, anchor: str, lead: str = "") -> str:
    """The heading of a part of a view, across its whole width, with an anchor for links and the part's lead, which
    may hold links."""
    line = f'<p class="sub">{lead}</p>' if lead else ""
    return f'<div class="group wide" id="{anchor}"><h2>{_esc(title)}</h2>{line}</div>'


def _section(title: str, anchor: str, sub: str = "", tone: str = "") -> str:
    """A heading that groups the cards after it within a part, across the whole width of the view, with an anchor
    for links."""
    line = f'<p class="sub">{_esc(sub)}</p>' if sub else ""
    return f'<div class="section wide {tone}" id="{anchor}"><h3>{_esc(title)}</h3>{line}</div>'


def _link(anchor: str, text: str) -> str:
    return f'<a href="#{anchor}">{_esc(text)}</a>'


def _and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _month_tick(month) -> str:
    """A month on a category axis, the month over the year: Oct over 2026."""
    return fmt.month_short(month).replace(" ", "<br>")


def _start_label(day, i) -> str:
    """The first row of a daily series is the starting amount at the close before the first order."""
    return f"{fmt.day_short(day)}, start" if i == 0 else fmt.day_short(day)


def _date_axis(dates, most: int = 5) -> dict:
    """A date axis, its ticks as 8 Oct and as Oct 2026 once the dates span most of a year. Over two weeks or less
    Plotly ticks by the hour and repeats each date, so the ticks are then valuation days, at most `most` of them, the
    last day always among them."""
    days = sorted({str(d)[:10] for d in dates})
    long = bool(days) and (pd.Timestamp(days[-1]) - pd.Timestamp(days[0])).days > 300
    axis = {"type": "date", "tickformat": "%b %Y" if long else "%-d %b", "hoverformat": "%-d %B %Y"}
    if days and (pd.Timestamp(days[-1]) - pd.Timestamp(days[0])).days <= 14:
        step = -(-len(days) // most)
        axis.update(tickmode="array", tickvals=days[::-1][::step][::-1])
    return axis


def _date_axes(dates) -> tuple:
    """The date axis for the page at full width and for a narrow screen."""
    return {"xaxis": _date_axis(dates)}, {"xaxis": _date_axis(dates, 3)}


def _colophon(now_row) -> str:
    """The footer's last line. The record is built on the date of its holdings, so the build date comes
    from the committed outputs and a rebuild reproduces the page."""
    built = fmt.day_words(_built(now_row))
    return (f'<p class="colophon">Carlo Hofer &middot; Data: the issuers\' published data &middot; '
            f'<a href="{config.REPOSITORY_URL}">Code on GitHub</a> &middot; Last build: {_esc(built)}</p>')


def _asof(day, extra="") -> str:
    return f"As of {fmt.day_words(day)}" + (f". {extra}" if extra else "")


def _built(now_row) -> pd.Timestamp:
    """The day of the build: the column built, or the date of the holdings where the table has no such column."""
    value = now_row.get("built") if hasattr(now_row, "get") else None
    return pd.Timestamp(now_row["positions_as_of"] if value is None or pd.isna(value) else value)


def _two_dates(now_row) -> str:
    """The date of the record. The prices and the holdings share it, and when they differ both are written."""
    prices, held = pd.Timestamp(now_row["weights_as_of"]), pd.Timestamp(now_row["positions_as_of"])
    if prices == held:
        return f"As of {fmt.day_words(prices)}"
    return f"Prices as of {fmt.day_words(prices)}, holdings as of {fmt.day_words(held)}"


def _stamp(now_row) -> str:
    """The hero's stamp: the date of the figures, both dates when the prices and the holdings differ."""
    dates = _two_dates(now_row)
    return "Figures as of" + dates[len("As of"):] if dates.startswith("As of") else dates


def _later_orders(orders, now_row) -> pd.DataFrame:
    """The orders placed after the last net asset values, which enter the record with the next ones."""
    if now_row is None or not len(orders):
        return orders.iloc[0:0]
    return orders[pd.to_datetime(orders["date"]) > pd.Timestamp(now_row["weights_as_of"])]


def _after_record(orders, now_row, counted=False) -> str:
    """One sentence on the top-ups received and the orders placed after the last net asset values, by day. With
    counted, the sentence says that a count of orders includes them."""
    if now_row is None:
        return ""
    day = pd.Timestamp(now_row["weights_as_of"])
    parts = []
    if not counted:
        raw = now_row.get("contributions_after", "") if hasattr(now_row, "get") else ""
        dates = [d for d in raw.split("|") if d] if isinstance(raw, str) else []
        parts += [f"the top-up of {fmt.day_words(d)}" for d in dates]
    later = _later_orders(orders, now_row)
    sizes = later.groupby("date").size() if len(later) else pd.Series(dtype=int)
    for d, n in sizes.items():
        parts.append(f"the order of {fmt.day_words(d)}" if n == 1
                     else f"the {NUMBER_WORD.get(n, str(n)).lower()} orders of {fmt.day_words(d)}")  # fmt: skip
    if not parts:
        return ""
    what = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    if counted:
        return f"The count includes {what}, placed after the last net asset values, of {fmt.day_words(day)}."
    events = len(parts) - len(sizes) + int(sizes.sum()) if len(sizes) else len(parts)
    verb = "enters" if events == 1 else "enter"
    return (f"{what[0].upper()}{what[1:]} came after the last net asset values, of {fmt.day_words(day)}, and {verb} "
            "the record with the next ones.")


# Overview ------------------------------------------------------------------------------------------


def _whole(share: float) -> str:
    """A share as a whole number of per cent, 0.7 -> 70."""
    return fmt.count(round(share * 100))


def _span(first, last) -> str:
    """A period in words: 7 October to 6 November 2026, with both years when they differ."""
    a, b = pd.Timestamp(first), pd.Timestamp(last)
    start = f"{a.day} {a.strftime('%B')}" + ("" if a.year == b.year else f" {a.year}")
    return f"{start} to {fmt.day_words(b)}"


def _key_figures(w_now, last, month_orders: int) -> str:
    """The strip of key figures: where the portfolio stands against its rules, each figure over the line that names
    its reference."""
    low, high = config.BAND
    target = config.TARGET[config.EQUITY]
    figures = [
        ("Equity weight", fmt.pct(w_now["weight_equity"]), f"Target {_whole(target)}%, band {_whole(low)} to {_whole(high)}"),
        ("Drift from target", fmt.points((w_now["weight_equity"] - target) * 100),
         f"Equity weight minus {_whole(target)}%"),
        ("Drawdown now", fmt.pct(-last["drawdown_portfolio"]) if last is not None else "n/a",
         "Below the previous peak" if last is not None else "From the first valuation day"),
        ("Orders this month", f"{month_orders} of {config.ORDERS_PER_MONTH}", "Allowance of rule 6"),
    ]  # fmt: skip
    def value(text: str) -> str:
        # A unit in words, such as points, is set smaller beside its number, so the figure keeps to one line.
        if not text.endswith(" points"):
            return _esc(text)
        return _esc(text[: -len(" points")]) + ' <span class="ch-kpi__unit">points</span>'

    cells = "".join(f'<div class="ch-kpi"><p class="ch-kpi__label">{_esc(n)}</p><div class="ch-kpi__value">{value(v)}</div>'
                    f'<div class="ch-kpi__ref">{_esc(r)}</div></div>' for n, v, r in figures)  # fmt: skip
    return f'<div class="ch-kpis">{cells}</div>'


def _returns(daily: pd.DataFrame, monthly: pd.DataFrame) -> str:
    """The sentence under the key figures: the return since the first purchase, time-weighted and money-weighted.
    Within the first year both are cumulative and no annual figure is shown, and from the first year on both are given
    per year."""
    history = daily.iloc[1:] if len(daily) else daily
    latest = monthly.iloc[-1] if len(monthly) else None
    if not len(history) or latest is None:
        return "The returns start with the first valuation day."
    growth = history["growth_portfolio"].iloc[-1] / 100
    if pd.notna(latest.get("money_weighted_per_year")):
        years = (pd.Timestamp(history["date"].iloc[-1]) - pd.Timestamp(daily["date"].iloc[0])).days / 365.25
        return (f"Since the first purchase: <b>{_esc(fmt.pct(growth ** (1 / years) - 1, True))}</b> a year time-weighted "
                f"and <b>{_esc(fmt.pct(latest['money_weighted_per_year'], True))}</b> a year money-weighted, in euro, after "
                "costs.")  # fmt: skip
    return (f"Since the first purchase: <b>{_esc(fmt.pct(growth - 1, True))}</b> time-weighted and "
            f"<b>{_esc(fmt.pct(latest['money_weighted_since_start'], True))}</b> money-weighted, in euro, after costs, "
            "not annualised. The record is shorter than a year, so no annual figures are shown yet.")  # fmt: skip


TOP_UP_SHARE = 5  # the monthly top-up, per cent of the starting amount (rule 3)


def _key_facts(first_day, costs: pd.DataFrame) -> str:
    """Key facts: the sleeves with the funds' full names, the band, the contributions, the rebalancing, the risk limit,
    the costs, the valuation, the first purchase and the benchmark, the index blend."""
    low, high = config.BAND
    held = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv")
    held = held[held["held"] == "yes"].drop_duplicates("sleeve").set_index("sleeve")["fund"]
    rows = [
        ("Equity sleeve", f"{held['equity']}, target {_whole(config.TARGET[config.EQUITY])}%"),
        ("Bond sleeve", f"{held['bonds']}, target {_whole(config.TARGET[config.BONDS])}%"),
        ("Band", f"Equity between {_whole(low)}% and {_whole(high)}%"),
        ("Contributions", f"A starting amount, then a fixed monthly top-up of {TOP_UP_SHARE}% of it"),
        ("Rebalancing", "Through the top-ups, and back to target when equity leaves the band on a cycle day"),
        ("Risk limit", f"Worst fall within about one third, tested at {_whole(config.RISK_LIMIT_TEST)}%"),
    ]  # fmt: skip
    if len(costs):
        by = costs.set_index("sleeve")["ongoing_costs"]
        two = lambda v: f"{v * 100:.2f}%"  # noqa: E731
        rows.append(("Ongoing costs", f"{two(by['portfolio'])} a year at the sleeve weights, TER plus transaction costs "
                                      f"(equity {two(by['equity'])}, bonds {two(by['bonds'])})"))  # fmt: skip
    rows += [("Valuation", "Euro, at the issuers' net asset values"),
             ("First purchase", fmt.day_words(first_day) if first_day is not None else "n/a")]  # fmt: skip
    facts = "".join(f'<div class="ch-fact"><dt>{_esc(a)}</dt><dd>{_esc(b)}</dd></div>' for a, b in rows)
    benchmark = _esc("The 70/30 blend of the two funds' own indices, rebalanced at each month end")
    facts += (f'<div class="ch-fact"><dt>Benchmark</dt><dd>{benchmark} '
              f'({_link("method-not-done", "the index blend")})</dd></div>')  # fmt: skip
    return f'<aside class="ch-facts" id="key-facts"><h3>Key facts</h3><dl>{facts}</dl></aside>'


def _allocation(w_now, pending: str) -> tuple:
    """Chart 2: the allocation against the target and the band, a bullet chart: the weight as a bar, the target as a
    tick, the band shaded."""
    low, high = config.BAND
    band_text = f"Band {_whole(low)} to {_whole(high)}"
    rows = [("Equity", w_now["weight_equity"], config.TARGET[config.EQUITY], "@equity", band_text),
            ("Bonds", w_now["weight_bonds"], config.TARGET[config.BONDS], "@bonds", "No band of its own")]  # fmt: skip
    traces, annotations = [], []
    for name, w, target, role, band in rows:
        hover = f"{name} {fmt.pct(w)}<br>Target {fmt.pct(target)}<br>{band}"
        traces.append({"type": "bar", "orientation": "h", "y": [name], "x": [fmt.rounded(w * 100, 2)], "name": name,
                       "width": 0.45, "marker": {"color": role}, "showlegend": False, **_hover([hover])})  # fmt: skip
        annotations.append({**_label(max(w, target) * 100, name, "", anchor="left", role="@accent", xshift=10),
                            "text": f"<b>{_esc(fmt.pct(w))}</b>"})  # fmt: skip
    traces.append({"type": "scatter", "mode": "markers", "name": "Target weight", "y": [r[0] for r in rows],
                   "x": [r[2] * 100 for r in rows], "showlegend": False,
                   "marker": {"symbol": "line-ns", "size": 34, "color": "@ink", "line": {"color": "@ink", "width": 2}},
                   **_hover([f"{r[0]} target {fmt.pct(r[2])}" for r in rows])})  # fmt: skip
    label = _label((low + high) * 50, -0.42, band_text, anchor="center", xshift=0, yshift=2)
    label["yanchor"] = "bottom"
    layout = {
        "barmode": "overlay", "showlegend": False, "height": 200,
        "xaxis": {"range": [0, 100], "dtick": 25, "showline": False},
        "yaxis": {"type": "category", "range": [1.55, -0.78], "showline": False, "showgrid": False, "ticks": ""},
        "shapes": [{"type": "rect", "xref": "x", "yref": "y", "x0": low * 100, "x1": high * 100, "y0": -0.42, "y1": 0.42,
                    "fillcolor": "@band", "line": {"width": 0}, "layer": "below"}],
        "annotations": annotations + [label], "margin": {"t": 8, "r": 56},
    }  # fmt: skip
    cash = w_now["weight_cash"]
    table = _table(["Sleeve", "Weight", "Target weight", "Band"],
                   [["Equity", fmt.pct(w_now["weight_equity"]), fmt.pct(config.TARGET[config.EQUITY]), band_text],
                    ["Bonds", fmt.pct(w_now["weight_bonds"]), fmt.pct(config.TARGET[config.BONDS]), ""],
                    ["Cash", fmt.pct(cash), "", ""]], numeric=("Weight", "Target weight"), rounding=True)  # fmt: skip
    dates = _two_dates(w_now)
    unit = "Per cent of the portfolio, " + (dates[len("As of "):] if dates.startswith("As of ") else dates[0].lower() + dates[1:])
    note = (f"The vertical marks are the target weights. Cash {fmt.pct(cash)}. The band applies to the equity weight only."
            + (f" {pending}" if pending else ""))  # fmt: skip
    card = _card("c2", "Allocation against the target and the band", unit, "outputs/allocation_now.csv", table=table,
                 note=note, height=200)
    return card, {"id": "c2", "view": "overview", "traces": traces, "layout": layout}


def _drawdown(daily: pd.DataFrame, empty) -> tuple:
    """Chart 4: the drawdown against the mandate's limit, as a positive fall below the previous peak on a reversed
    axis that runs to the outer bound or deeper."""
    history = daily.iloc[1:] if len(daily) else daily
    traces, annotations = [], []
    worst = -daily["drawdown_portfolio"].min() if len(daily) else 0.0
    if len(history):
        falls = [fmt.rounded(-v * 100, 1) for v in daily["drawdown_portfolio"]]
        traces.append({"type": "scatter", "mode": "lines", "name": "Portfolio", "x": list(daily["date"]), "y": falls,
                       "fill": "tozeroy", "line": {"color": "@accent", "width": 2}, "fillcolor": "@drawdown_fill",
                       **_hover([f"{fmt.day_words(d)}<br>Portfolio: {fmt.pct(-v)} below the previous peak" for d, v in
                                 zip(daily["date"], daily["drawdown_portfolio"])])})  # fmt: skip
        traces.append({"type": "scatter", "mode": "markers", "x": [daily["date"].iloc[-1]], "y": [falls[-1]],
                       "marker": {"size": 7, "color": "@accent"}, "showlegend": False, "hoverinfo": "skip",
                       "cliponaxis": False})  # fmt: skip
        annotations.append({**_label(daily["date"].iloc[-1], falls[-1], "", anchor="right", role="@accent", xshift=-4,
                                     yshift=-14), "text": f"<b>{_esc(fmt.pct(-daily['drawdown_portfolio'].iloc[-1]))}</b>"})  # fmt: skip
        blend = daily[["date", "drawdown_index_blend"]].dropna()
        if len(blend) >= 2:
            traces.append({"type": "scatter", "mode": "lines+markers", "name": "Index blend", "x": list(blend["date"]),
                           "y": [fmt.rounded(-v * 100, 1) for v in blend["drawdown_index_blend"]],
                           "line": {"color": "@index_blend", "width": 2}, "marker": {"size": 8},
                           **_hover([f"{fmt.day_words(d)}<br>Index blend: {fmt.pct(-v)} below the previous peak" for d, v in
                                     zip(blend["date"], blend["drawdown_index_blend"])])})  # fmt: skip
    deepest = max(config.RISK_LIMIT_OUTER * 100, 10 * -(-worst * 100 // 10))
    shapes, labels, short_labels = _limit_lines(deepest, levels=(35,))
    ticks = list(range(0, int(deepest) + 1, 10))
    wide, narrow = _date_axes(daily["date"])
    if len(daily) > 1:
        ends = [daily["date"].iloc[0], daily["date"].iloc[-1]]
        wide["xaxis"]["range"], narrow["xaxis"]["range"] = ends, ends
    layout = {"showlegend": len(traces) > 2, "height": 210,
              "yaxis": {"range": [deepest + 0.5, -0.5], "tickmode": "array", "tickvals": ticks,
                        "ticktext": [f"{t}%" if t == 0 else str(t) for t in ticks], "showline": False},
              **wide, "shapes": shapes, "annotations": annotations + labels, "margin": {"t": 8}}  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.pct(-r["drawdown_portfolio"]), fmt.pct(-r["drawdown_index_blend"])]
            for i, (_, r) in enumerate(daily.iterrows())]  # fmt: skip
    table = _table(["Date", "Portfolio", "Index blend"], rows, numeric=("Portfolio", "Index blend"))
    unit = (f"Per cent below the previous peak, daily, {_span(daily['date'].iloc[0], daily['date'].iloc[-1])}"
            if len(daily) else "Per cent below the previous peak, daily")  # fmt: skip
    note = (f"The worst fall to date is {fmt.pct(worst)}. The mandate's test limit is 35 per cent and its outer bound 40 "
            "per cent. Its test used month-end values, which miss falls that reverse within a month, so the worst daily "
            "fall is at least as deep.")  # fmt: skip
    card = _card("c4", "Drawdown against the mandate's limit", unit, "outputs/portfolio_daily.csv",
                 table=None if empty else table, height=210, empty=empty, note=note)
    chart = None if empty else {"id": "c4", "view": "overview", "traces": traces, "layout": layout,
                                "layout_narrow": {**narrow, "annotations": annotations + short_labels}}  # fmt: skip
    return card, chart


def overview(page: Page, daily: pd.DataFrame, monthly: pd.DataFrame, now: pd.DataFrame, orders: pd.DataFrame,
             costs: pd.DataFrame = pd.DataFrame()):  # fmt: skip
    """The Overview: the key figures, the returns, the allocation and the drawdown in a pair, and the key facts. The
    growth of 100 opens the Performance view."""
    history = daily.iloc[1:] if len(daily) else daily
    last = history.iloc[-1] if len(history) else None
    w_now = now.iloc[0]
    month_orders = 0
    if len(orders):
        current = _built(w_now).to_period("M")
        month_orders = int((pd.to_datetime(orders["date"]).dt.to_period("M") == current).sum())
    first_order = orders["date"].min() if len(orders) else None
    empty = None if len(history) >= 1 else (f"The series starts with the net asset values of {fmt.day_words(first_order)}, "
                                            "the day of the first purchase, which the issuers publish the next working day.")  # fmt: skip
    pending = _after_record(orders, w_now)
    allocation_card, allocation_chart = _allocation(w_now, pending)
    drawdown_card, drawdown_chart = _drawdown(daily, empty)
    page.charts += [c for c in (allocation_chart, drawdown_chart) if c]
    source = '<p class="source">Source: outputs/allocation_now.csv, outputs/portfolio_daily.csv, outputs/metrics_monthly.csv</p>'
    page.add("overview", f'<div class="wide ch-top"><div class="ch-main">{_key_figures(w_now, last, month_orders)}'
             f'<p class="ch-returns">{_returns(daily, monthly)}</p>{source}'
             f'<div class="ch-pair">{allocation_card}{drawdown_card}</div></div>{_key_facts(first_order, costs)}</div>')  # fmt: skip

    # Chart 3: growth of 100.
    series = [("Portfolio", "growth_portfolio", "@accent", 2),
              (COMPARATOR_NAME["reference_a"][0], "growth_reference_a", "@reference_a", 2),
              (COMPARATOR_NAME["reference_b"][0], "growth_reference_b", "@reference_b", 2),
              ("Index blend", "growth_index_blend", "@index_blend", 2)]  # fmt: skip
    traces, annotations, rows = [], [], []
    for name, column, role, width in series:
        data = daily[["date", column]].dropna()
        if len(data) < 2:
            continue
        traces.append({"type": "scatter", "mode": "lines+markers" if len(data) < 3 else "lines", "name": name,
                       "x": list(data["date"]), "y": [fmt.rounded(v, 1) for v in data[column]],
                       "line": {"color": role, "width": width, "dash": "dot" if column == "growth_reference_b" else "solid"},
                       "marker": {"size": 8, "color": role},
                       **_hover([f"{fmt.day_words(d)}<br>{name}: {fmt.index(v)}" for d, v in zip(data["date"], data[column])])})  # fmt: skip
        if column == "growth_portfolio":
            end = data.iloc[-1]
            annotations.append(_label(end["date"], fmt.rounded(end[column], 1), fmt.index(end[column])))
    for i, (_, r) in enumerate(daily.iterrows()):
        rows.append([_start_label(r["date"], i)] + [fmt.index(r[c]) for _, c, _, _ in series])
    wide, narrow = _date_axes(daily["date"])
    layout = {"showlegend": True, "legend": {"y": 1.02}, "yaxis": {"title": {"text": "Growth of 100"}},
              **wide, "annotations": annotations, "hovermode": "closest", "margin": {"r": 48}}  # fmt: skip
    table = _table(["Date", "Portfolio", "Reference A", "Reference B", "Index blend"], rows,
                   numeric=("Portfolio", "Reference A", "Reference B", "Index blend"))  # fmt: skip
    blend_points = daily[["date", "growth_index_blend"]].dropna() if "growth_index_blend" in daily else daily.iloc[0:0]
    blend_text = ("The index blend starts at the first month end" if len(blend_points) != 1 else
                  "The index blend starts at the portfolio's level on the first month end, "
                  f"{fmt.day_words(blend_points['date'].iloc[0])}, and is drawn once a second month's returns are published")
    asof3 = _asof(daily["date"].iloc[-1] if len(daily) else w_now["weights_as_of"],
                  f"100 is the starting amount before the first order. {blend_text}")  # fmt: skip
    same = (len(daily) > 1 and {"growth_reference_a", "growth_reference_b"} <= set(daily.columns)
            and float((daily["growth_reference_a"] - daily["growth_reference_b"]).abs().max()) < 1e-4)  # fmt: skip
    overlap = ("<p class=\"note\">Reference B&#x27;s dotted line lies on reference A&#x27;s so far: on each cycle day "
               "the top-up alone has brought reference portfolio A back to 70/30, which is where reference portfolio B "
               "goes on every cycle day.</p>") if same else ""  # fmt: skip
    why = overlap + ("<p class=\"note\">Why the portfolio has no optimiser, no single market index as its benchmark, no views "
           "and no signal: "
           f"{_link('method-not-done', 'Method')}.</p>")
    page.add("growth", _card("c3", "Growth of 100: the portfolio, the two reference portfolios and the index blend",
             asof3, "outputs/portfolio_daily.csv", table=None if empty else table, height=340, wide=True, empty=empty,
             extra=why),
             None if empty else {"id": "c3", "traces": traces, "layout": layout,
                                 "layout_narrow": {"annotations": [], "margin": {"r": 12}, **narrow}})  # fmt: skip


# Rebalancing ---------------------------------------------------------------------------------------


def rebalancing(page, daily, orders, band, compliance, monthly, now=None):
    history = daily.iloc[1:]
    empty = None if len(history) else "The equity weight starts on the first valuation day."
    low, high = config.BAND
    traces = []
    if len(history):
        traces.append({"type": "scatter", "mode": "lines", "name": "Equity weight", "x": list(history["date"]),
                       "y": [fmt.rounded(v * 100, 1) for v in history["weight_equity"]],
                       "line": {"color": "@equity", "width": 2},
                       **_hover([f"{fmt.day_words(d)}<br>Equity weight {fmt.pct(v)}" for d, v in
                                 zip(history["date"], history["weight_equity"])])})  # fmt: skip
        weight_on = dict(zip(history["date"], history["weight_equity"]))
        # The equity marker is the larger, so that a day with both purchases shows both.
        for sleeve, role, label, size in (("equity", "@equity", "Purchase of the equity ETF", 14),
                                          ("bonds", "@bonds", "Purchase of the bond ETF", 8)):  # fmt: skip
            sel = orders[(orders["sleeve"] == sleeve) & (orders["side"] == "buy")] if len(orders) else orders
            pts = [(d, weight_on[d]) for d in sel["date"] if d in weight_on] if len(sel) else []
            if pts:
                traces.append({"type": "scatter", "mode": "markers", "name": label, "x": [p[0] for p in pts],
                               "y": [fmt.rounded(p[1] * 100, 1) for p in pts],
                               "marker": {"size": size, "color": role, "line": {"color": "@surface", "width": 2}},
                               **_hover([f"{fmt.day_words(d)}<br>{label}" for d, _ in pts])})  # fmt: skip
        annotations = []
        if len(band):
            pts = [(d, weight_on.get(d)) for d in band["date"] if d in weight_on]
            traces.append({"type": "scatter", "mode": "markers", "name": "Band order",
                           "x": [p[0] for p in pts], "y": [fmt.rounded(p[1] * 100, 1) for p in pts],
                           "marker": {"size": 11, "symbol": "diamond", "color": "@status_breach"},
                           **_hover([f"{fmt.day_words(d)}<br>Band order, rule 5" for d, _ in pts])})  # fmt: skip
            annotations += [_label(p[0], fmt.rounded(p[1] * 100, 1), "◆ Band order") for p in pts]
        missed = compliance[compliance["issue"] == "called for by the rules and not placed"] if len(compliance) else compliance
        if len(missed):
            pts = [(d, weight_on.get(d)) for d in missed["date"] if d in weight_on]
            traces.append({"type": "scatter", "mode": "markers", "name": "Order not placed",
                           "x": [p[0] for p in pts], "y": [fmt.rounded(p[1] * 100, 1) for p in pts],
                           "marker": {"size": 11, "symbol": "circle-open", "color": "@status_missed",
                                      "line": {"width": 2}},
                           **_hover([f"{fmt.day_words(d)}<br>Order called for by the rules and not placed" for d, _ in pts])})  # fmt: skip
            annotations += [_label(p[0], fmt.rounded(p[1] * 100, 1), "○ Not placed") for p in pts]
    wide, narrow = _date_axes(history["date"])
    layout = {"showlegend": True, "yaxis": {"title": {"text": "Equity weight, per cent"}, "range": [60, 80], "dtick": 5},
              **wide,
              "shapes": [{"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": low * 100,
                          "y1": high * 100, "fillcolor": "@band", "line": {"width": 0}, "layer": "below"},
                         _hline(70, "@ink")]}  # fmt: skip
    if len(history):
        layout["annotations"] = annotations
    rows = [[fmt.day_short(r["date"]), fmt.pct(r["weight_equity"]), fmt.pct(r["weight_bonds"]), fmt.pct(r["weight_cash"])]
            for _, r in history.iterrows()]  # fmt: skip
    table = _table(["Date", "Equity", "Bonds", "Cash"], rows, numeric=("Equity", "Bonds", "Cash"), rounding=True)
    first_cycle = "No cycle day yet: the line covers the days since the first purchase" if not len(band) and (
        not len(orders) or (orders["rule"].isin(["4", "5", "4+5"])).sum() == 0) else ""  # fmt: skip
    page.add("rebalancing", _card("c5", "Equity weight in its band, with every order",
             _asof(daily["date"].iloc[-1], first_cycle), ["outputs/portfolio_daily.csv", "outputs/orders.csv",
             "outputs/band_events.csv", "outputs/compliance.csv"], table=table, note=_after_record(orders, now) or None,
             height=320, wide=True, empty=empty),
             None if empty else {"id": "c5", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip

    # Chart 6: orders against the allowance.
    if len(orders):
        months = pd.to_datetime(orders["date"]).dt.strftime("%Y-%m")
        counts = months.value_counts().sort_index()
        counts.index = [_month_tick(m) for m in counts.index]
    else:
        counts = pd.Series(dtype=int)
    traces = [{"type": "bar", "x": list(counts.index), "y": [int(v) for v in counts.values], "name": "Orders",
               "width": 0.45, "marker": {"color": "@accent"},
               **_hover([f"{fmt.month_words(m.replace('<br>', ' '))}: {v} of {config.ORDERS_PER_MONTH}" for m, v in counts.items()])}]
    shown = max(len(counts), 6)
    layout = {"yaxis": {"title": {"text": "Orders in the month"}, "range": [0, 6], "dtick": 1},
              "xaxis": {"type": "category", "title": {"text": "Month"}, "range": [-0.5, shown - 0.5]},
              "shapes": [_hline(config.ORDERS_PER_MONTH, "@ink")],
              "annotations": [_label(1, config.ORDERS_PER_MONTH, "Allowance, 5", xref="paper", anchor="right",
                                     xshift=0, yshift=8)]}  # fmt: skip
    rows = [[fmt.day_short(r["date"]), r["sleeve"], r["side"], r["rule"], r["inside_rule_7_window"], r["bid_and_ask_recorded"]]
            for _, r in orders.iterrows()] if len(orders) else []  # fmt: skip
    table = _table(["Date", "Sleeve", "Side", "Rule", "Inside 15:45 to 17:00", "Bid and ask recorded"], rows)
    note = _departures(compliance, orders)
    page.add("rebalancing", _card("c6", "Orders per month against the allowance of five",
             _asof(daily["date"].iloc[-1], _after_record(orders, now, counted=True).rstrip(".")), "outputs/orders.csv",
             table=table, note=note, height=260),
             {"id": "c6", "traces": traces, "layout": layout})  # fmt: skip


def _orders_named(group: pd.DataFrame, orders: pd.DataFrame) -> str:
    """'The equity and bond orders of 8 October 2026, the first purchases,' for the departures of one day."""
    day = group["date"].iloc[0]
    sleeves = sorted(set(group["sleeve"]), key=lambda x: config.SLEEVES.index(x))
    words = {"equity": "equity", "bonds": "bond"}
    what = " and ".join(words[x] for x in sleeves) + (" orders" if len(sleeves) > 1 else " order")
    first = len(orders) and (orders[orders["date"] == day]["rule"] == "start").all()
    return f"The {what} of {fmt.day_words(day)}" + (", the first purchases," if first else "")


def _departures(compliance: pd.DataFrame, orders: pd.DataFrame) -> str:
    """One plain sentence per kind of departure from the rules, with the orders it concerns."""
    if not len(compliance):
        return "The departures register has no entry so far."
    start, end = (t.strftime("%H:%M") for t in config.ORDER_WINDOW)
    rule = {"outside the rule 7 window": (f"Rule 7 allows orders between {start} and {end} Amsterdam time.",
                                          "{} placed outside that window."),
            "on a day Xetra is closed": ("Rule 7 allows orders only on trading days.", "{} placed on a day Xetra was closed."),
            "called for by the rules and not placed": ("", "{} called for by the rules and not placed.")}  # fmt: skip
    sentences = []
    for issue, group in compliance.groupby("issue", sort=False):
        lead, body = rule.get(issue, ("", "{} " + issue + "."))
        named = [_orders_named(g, orders) for _, g in group.groupby("date")]
        verb = "were" if len(group) > 1 else "was"
        sentences += [lead] if lead else []
        sentences.append(body.format(" ".join(named) + f" {verb}").replace("  ", " "))
    sentences.append("The record keeps every order as it was placed.")
    return " ".join(sentences)


# Costs ---------------------------------------------------------------------------------------------


def costs(page, monthly, implementation, daily):
    traces = []
    # The navy ramp runs from the lightest step to the darkest, so that the part that usually carries the cost,
    # the price paid against net asset value, is the darkest.
    parts = [("Commissions", "commissions_bps", "@cost_4"), ("Half-spread at execution", "half_spread_bps", "@cost_3"),
             ("Currency conversion", "currency_conversion_bps", "@cost_2"),
             ("Price paid against net asset value", "execution_against_nav_bps", "@cost_1")]  # fmt: skip
    if len(monthly):
        for name, column, role in parts:
            traces.append({"type": "bar", "name": name, "x": [_month_tick(m) for m in monthly["month"]], "width": 0.45,
                           "y": [fmt.rounded(v, 0) for v in monthly[column]],
                           "marker": {"color": role, "line": {"color": "@surface", "width": 2}},
                           **_hover([f"{fmt.month_words(m)}<br>{name}: {fmt.bps(v, signed=False)}<br>Implementation cost of the month: "
                                     f"{fmt.bps(t, signed=False)}" for m, v, t in
                                     zip(monthly["month"], monthly[column], monthly["implementation_cost_month_bps"])])})  # fmt: skip
    layout = {"barmode": "relative", "showlegend": True, "bargap": 0.45, "legend": {"traceorder": "normal"},
              "yaxis": {"title": {"text": "Basis points of the portfolio's value"}},
              "xaxis": {"type": "category", "title": {"text": "Month"},
                        "range": [-0.5, max(len(monthly), 6) - 0.5]}, "shapes": [_hline(0, "@ink")]}  # fmt: skip
    rows = [[fmt.month_short(r["month"]), fmt.bps(r["commissions_bps"], False), fmt.bps(r["half_spread_bps"], False),
             fmt.count(r["orders_without_bid_and_ask"]), fmt.bps(r["currency_conversion_bps"], False),
             fmt.bps(r["execution_against_nav_bps"], False), fmt.bps(r["implementation_cost_month_bps"], False)]
            for _, r in monthly.iterrows()] if len(monthly) else []  # fmt: skip
    numeric = ("Commissions", "Half-spread", "Orders without bid and ask", "Conversion", "Price against net asset value",
               "Month's implementation cost")
    table = _table(["Month"] + list(numeric), rows, numeric=numeric)
    missing = int(monthly["orders_without_bid_and_ask"].sum()) if len(monthly) else 0
    note = ("Basis points of the portfolio's value on the day of each order. Price paid against net asset value is "
            "the gap between each order's price and the ETF's net asset value of that day, beyond the half-spread. It "
            "is computed as the month's implementation cost minus commissions, half-spread and currency conversion, "
            f"so the four sources of a month add up to that month's implementation cost in {_ref('c8')}.")  # fmt: skip
    if missing:
        which = f"the {NUMBER_WORD[missing].lower()} orders" if missing > 1 else "the one order"
        note += (f" For {which} without a recorded bid and ask, the half-spread is not measured and is part of the "
                 "price paid against net asset value.")  # fmt: skip
    empty = None if len(monthly) else "Costs start with the first valuation day."
    page.add("costs", _card("c7", "Cost per month by source", _asof(daily["date"].iloc[-1]),
             "outputs/costs_monthly.csv", table=table, note=note, height=280, empty=empty),
             None if empty else {"id": "c7", "traces": traces, "layout": layout,
                                 "layout_narrow": {"yaxis": {"title": {"text": "Basis points"}}}})  # fmt: skip

    data = implementation.dropna(subset=["implementation_cost_bps"]) if len(implementation) else implementation
    empty = None if len(data) > 1 else "The comparison starts on the first valuation day."
    traces, layout, narrow = [], {}, {}
    if not empty:
        traces = [{"type": "scatter", "mode": "lines+markers" if len(data) < 3 else "lines",
                   "name": "Reference portfolio A against the portfolio", "x": list(data["date"]),
                   "y": [fmt.rounded(v, 0) for v in data["implementation_cost_bps"]],
                   "line": {"color": "@accent", "width": 2}, "marker": {"size": 8, "color": "@accent"},
                   **_hover([f"{fmt.day_words(d)}<br>{fmt.bps(v)}" for d, v in zip(data["date"], data["implementation_cost_bps"])])}]
        end = data.iloc[-1]
        wide, narrow = _date_axes(data["date"])
        layout = {"yaxis": {"title": {"text": "Basis points, cumulative"}}, **wide, "shapes": [_hline(0, "@ink")],
                  "annotations": [_label(end["date"], fmt.rounded(end["implementation_cost_bps"], 0),
                                         fmt.bps(end["implementation_cost_bps"]))], "margin": {"r": 56}}  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.bps(r["implementation_cost_bps"])]
            for i, (_, r) in enumerate(data.iterrows())]  # fmt: skip
    table = _table(["Date", "Implementation cost"], rows, numeric=("Implementation cost",))
    page.add("costs", _card("c8", "Implementation cost, cumulative: reference portfolio A against the portfolio",
             _asof(daily["date"].iloc[-1], "Positive when the portfolio's value is below reference portfolio A's and negative "
                                          "when it is above"),
             "outputs/implementation_cost.csv", table=None if empty else table, height=280, empty=empty,
             note="Reference portfolio A applies the same rules at net asset value and without costs, so the gap "
                  "between reference portfolio A and the portfolio is the cumulative cost of running the portfolio. "
                  f"A cost of 10 basis points in one month of {_ref('c7')} moves this line up by 10 basis points in that "
                  "month."),
             None if empty else {"id": "c8", "traces": traces, "layout": layout,
                                 "layout_narrow": {**narrow, "yaxis": {"title": {"text": "Basis points"}}}})  # fmt: skip


# Comparisons ---------------------------------------------------------------------------------------

# The name of each row of the comparisons in a table, and in a chart where room is short.
COMPARATOR_NAME = {
    "portfolio": ("The portfolio", "The portfolio"),
    "benchmark": ("The benchmark, the index blend", "Benchmark"),
    "reference_a": ("Reference A, the same rules without costs", "Reference A"),
    "reference_b": ("Reference B, 70/30 every cycle day", "Reference B"),
    "split_100_0": ("100/0, the same rules", "100/0"),
    "split_90_10": ("90/10, the same rules", "90/10"),
    "split_80_20": ("80/20, the same rules", "80/20"),
    "split_60_40": ("60/40, the same rules", "60/40"),
    "first_ranked": ("70/30 with the first-ranked funds, the same rules", "First-ranked funds"),
    "sp500": ("The S&P 500 fund", "S&P 500"),
    "msci_world": ("The MSCI World fund", "MSCI World"),
    "lifestrategy_60": ("LifeStrategy 60% Equity", "LifeStrategy 60"),
    "lifestrategy_80": ("LifeStrategy 80% Equity", "LifeStrategy 80"),
    "nasdaq100": ("The Nasdaq-100 fund", "Nasdaq-100"),
    "mag7": ("The Mag7 fund", "Mag7"),
    "market_portfolio": ("The global market portfolio", "The global market portfolio"),
    "savings": ("Savings at the euro short-term rate", "Savings"),
    "bank_offensief": ("Rabobank's managed profile Offensief", "Rabobank Offensief"),
}
COMPARATOR_ROLE = {"benchmark": "@index_blend", "reference_a": "@reference_a", "reference_b": "@reference_b",
                   "split_100_0": "@comparator_1", "split_90_10": "@comparator_2", "split_80_20": "@comparator_3",
                   "split_60_40": "@comparator_4", "first_ranked": "@comparator_7", "sp500": "@sp500_alternative",
                   "msci_world": "@comparator_5", "lifestrategy_60": "@comparator_3", "lifestrategy_80": "@comparator_4",
                   "nasdaq100": "@comparator_2", "mag7": "@comparator_6", "market_portfolio": "@comparator_7",
                   "savings": "@savings"}  # fmt: skip
EFFECT_NAME = {"implementation": "Implementation", "drift": "Drift", "split": "Split", "dollar": "The dollar",
               "cash": "Cash", "regions": "Regions", "within_regions": "Within each region",
               "equity_classes": "Equity classes", "bond_classes": "Bond classes",
               "rate_against_yield": "The rate against the bonds' yield", "change_in_yield": "The change in yield",
               "bonds_rest": "The rest of the bond return", "timing": "Timing of contributions",
               "compounding": "Compounding"}  # fmt: skip
OTHER_SPLITS = "The same rules at other splits"  # the second pane's headline while it holds the splits alone
PANES = (
    ("same_rules", "The same rules without costs", ("reference_a", "reference_b"), "comparisons-same-rules"),
    ("other_funds_or_splits", "The same rules with other funds or splits",
     ("split_100_0", "split_90_10", "split_80_20", "split_60_40", "first_ranked"), "comparisons-splits"),
    ("one_fund", "One fund instead of two", ("sp500", "msci_world", "lifestrategy_60", "lifestrategy_80", "nasdaq100", "mag7"),
     "comparisons-one-fund"),
    ("market_portfolio", "Every asset class at its market value", ("market_portfolio",), "comparisons-market"),
    ("bank", "The money left in the bank", ("savings",), "comparisons-savings"),
    ("managed", "Not like for like: a bank's managed profile", ("bank_offensief",), "comparisons-managed"),
)  # fmt: skip
MARKET_NOTE = (
    "The global market portfolio is a comparator the portfolio's design names, and the benchmark remains the index blend. "
    "It holds every asset class at its share of the world's invested market value, as Doeswijk, Lam and Swinkels "
    "measure the global multi-asset market portfolio," + _note("doeswijk_2014") + " at the weights of 31 December "
    "2023 in their data update, version 6." + _note("doeswijk_2024"),
    "It takes the same contributions on the same days. It bought the published weights carried to the day before the "
    "first purchase by each class fund's return in euro, holds them as they move with prices, as the market holds them, "
    "and invests each top-up in proportion to what it holds. The carried weights are not the market's weights of that "
    "day. When the authors publish a new set, the comparator moves to it on the first cycle day after, carried from its "
    "own date.",
    "Each class is held through one ETF, the first in the rules' ranking for its class that the account offers, at its "
    "net asset value in euro, US dollar values at the ECB's reference rate of the day, without costs. Government bonds "
    "and investment-grade credits share one global aggregate bond fund. The account offers that fund only in its "
    "distributing class, so the distributing class stands in for the accumulating one and its distributions are added "
    "back on their ex-dates. No fund the account offers holds inflation-linked bonds without hedging their currencies, "
    "so that class is held in the aggregate fund. Private equity is held through listed private equity companies on "
    "developed-market exchanges, the widest index a fund of the class tracks, and they are not the private funds the "
    "dataset counts. Real estate is held through listed property companies, which are not the invested real estate the "
    "dataset counts. Emerging-market debt is held through local-currency government bonds, 55 per cent of the class in "
    "the dataset beside dollar government bonds (18), corporate bonds (16) and inflation-linked bonds (11).",
)  # fmt: skip
MARKET_SHARE = ("Its equity-like share, equities, private equity and real estate together, is {published} per cent in the "
                "published weights, {start} per cent at the start and {current} per cent on {day}, against the "
                "portfolio's {target}, and nothing scales the comparator to the portfolio's risk.")  # fmt: skip
SELECTIONS = (("S&P 500", "selection_sp500.csv"), ("MSCI World", "selection_msci_world.csv"),
              ("Nasdaq-100", "selection_nasdaq100.csv"))  # fmt: skip
CHANCE = ("Volatility, worst falls and correlations become informative within months, and differences of return over "
          "years. Over the record's {days} trading days a difference says nothing about either rule set.")  # fmt: skip
BAND_NOTE = ("The band is the one chance alone produces over the same span: plus or minus two tracking errors times the "
             "square root of the years, where the tracking error is the standard deviation of the daily differences "
             "between the two series times the square root of 252.")  # fmt: skip
MINIMUM_NOTE = (f"A daily comparator's volatility, correlation, difference and band are shown from its "
                f"{comparisons_module.MIN_DAILY_RETURNS}th daily return, about a month, and its effects with them.")  # fmt: skip


def _points(x, decimals: int = 1) -> str:
    """A difference of two returns in percentage points, signed: minus 1.9 points."""
    if pd.isna(x):
        return "n/a"
    if decimals == 1:
        return fmt.points(float(x) * 100)
    value = round(float(x) * 100, decimals) + 0.0
    return (f"{value:+.{decimals}f}" if value else f"{0:.{decimals}f}").replace("-", fmt.MINUS)


def _diff(x) -> str:
    """A difference in a table whose heading gives the unit, points: minus 1.9."""
    return _points(x).replace(" points", "")


def _band(row, unit: bool = False) -> str:
    """The band chance alone produces, and whether the difference lies inside it, in those words."""
    if pd.isna(row["band"]):
        return "n/a"
    inside = "inside the band" if row["inside_band"] == "yes" else "outside the band"
    return f"±{round(float(row['band']) * 100, 1):.1f}{' points' if unit else ''}, {inside}"


def _status(text) -> str:
    """Why a comparator has no figures, in words: a series not read, net asset values that stop early, or none
    published."""
    found = re.search(r"(\d{4}-\d{2}-\d{2})", str(text))
    words = str(text)
    if found:
        words = words.replace(found.group(1), fmt.day_short(found.group(1)))
    return words[:1].upper() + words[1:]


def _window(row) -> str:
    status = row.get("status")
    if isinstance(status, str) and status and pd.isna(row.get("first_day")):
        return _status(status)
    if row["comparator"] == "benchmark":
        first = row["first_day"]
        return f"Month ends from {fmt.day_short(first)}" if isinstance(first, str) else "From the first month end"
    first, last = pd.Timestamp(row["first_day"]), pd.Timestamp(row["last_day"])
    start = f"{first.day} {first.strftime('%b')}" if first.year == last.year else fmt.day_short(first)
    return f"{start} to {fmt.day_short(last)}, {int(row['periods'])} days"


def _fall(row, dates: bool = False) -> str:
    if pd.isna(row["worst_fall"]):
        return "n/a"
    text = fmt.pct(row["worst_fall"])
    if dates and isinstance(row["worst_fall_peak"], str):
        peak, low = pd.Timestamp(row["worst_fall_peak"]), pd.Timestamp(row["worst_fall_low"])
        start = f"{peak.day} {peak.strftime('%b')}" if peak.year == low.year else fmt.day_short(peak)
        text += f", {start} to {fmt.day_short(low)}"
    return text


def _ratio(x) -> str:
    return "n/a" if pd.isna(x) else fmt.loading(x)


def _comparison_rows(summary: pd.DataFrame, keys) -> str:
    """Every measure of the comparators of a pane, the portfolio first."""
    columns = ["Comparator", "Time-weighted return", "Money-weighted return", "Volatility", "Worst fall",
               "Correlation", "Difference, points", "Band, points"]  # fmt: skip
    rows = []
    for key in ("portfolio", *keys):
        r = summary.loc[key]
        rows.append([COMPARATOR_NAME[key][0], fmt.pct(r["return_time_weighted"], True),
                     fmt.pct(r["return_money_weighted"], True), fmt.pct(r["volatility"]), _fall(r, dates=True),
                     _ratio(r["correlation"]), _diff(r["difference"]), _band(r)])  # fmt: skip
    return _table(columns, rows, numeric=tuple(columns[1:]), wrap_first=True, wrap_head=True)


def _differences(summary: pd.DataFrame, shown: list) -> tuple:
    """One bar per comparator from zero to its difference, over the band chance alone produces, a light bar centred
    on zero."""
    names = [COMPARATOR_NAME[k][1] for k in shown]
    band = [fmt.rounded(summary.loc[k, "band"] * 100, 2) for k in shown]
    diff = [fmt.rounded(summary.loc[k, "difference"] * 100, 2) for k in shown]
    hover = [f"{COMPARATOR_NAME[k][1]}: {_points(summary.loc[k, 'difference'])}<br>Band: {_band(summary.loc[k], True)}<br>"
             f"Volatility {fmt.pct(summary.loc[k, 'volatility'])}, worst fall {_fall(summary.loc[k])}" for k in shown]  # fmt: skip
    traces = [{"type": "bar", "orientation": "h", "name": "Band chance alone produces", "y": names,
               "x": [2 * b for b in band], "base": [-b for b in band], "width": 0.62, "marker": {"color": "@band"},
               **_hover(hover)},
              {"type": "bar", "orientation": "h", "name": "Difference to the portfolio", "y": names, "x": diff,
               "width": 0.26, "marker": {"color": "@accent"}, **_hover(hover)}]  # fmt: skip
    layout = {"barmode": "overlay", "showlegend": True, "legend": {"traceorder": "normal"},
              "xaxis": {"title": {"text": "Points, comparator minus the portfolio"}, "zeroline": False},
              "yaxis": {"type": "category", "autorange": "reversed"}, "shapes": [_vline(0, "@ink")],
              "margin": {"t": 8}}  # fmt: skip
    rows = [[COMPARATOR_NAME[k][0], _diff(summary.loc[k, "difference"]), _band(summary.loc[k]),
             fmt.pct(summary.loc[k, "volatility"]), _fall(summary.loc[k])] for k in shown]  # fmt: skip
    headers = ["Comparator", "Difference, points", "Band chance alone produces, points", "Volatility", "Worst fall"]
    table = _table(headers, rows, numeric=tuple(headers[1:]))
    return traces, layout, table


def _ladder(summary: pd.DataFrame, shown: list) -> tuple:
    """Realised volatility against the return since the first purchase: the splits on one line through reference
    portfolio A, which is 70/30 under the same rules, the portfolio marked."""
    def point(k):
        return fmt.rounded(summary.loc[k, "volatility"] * 100, 2), fmt.rounded(summary.loc[k, "return_time_weighted"] * 100, 2)

    def hover(k):
        r = summary.loc[k]
        return (f"{COMPARATOR_NAME[k][1]}: volatility {fmt.pct(r['volatility'])}, return {fmt.pct(r['return_time_weighted'], True)}"
                f"<br>Worst fall {_fall(r)}, band {_band(r, True)}")  # fmt: skip

    ladder = [k for k in ("split_60_40", "reference_a", "split_80_20", "split_90_10", "split_100_0") if k in shown]
    traces = [{"type": "scatter", "mode": "lines+markers", "name": "Splits under the same rules",
               "x": [point(k)[0] for k in ladder], "y": [point(k)[1] for k in ladder],
               "line": {"color": "@other", "width": 2}, "marker": {"size": 8, "color": "@ink2"},
               **_hover([hover(k) for k in ladder])}]  # fmt: skip
    for k in [k for k in shown if k not in ladder] + ["portfolio"]:
        role = "@accent" if k == "portfolio" else COMPARATOR_ROLE[k]
        x, y = point(k)
        traces.append({"type": "scatter", "mode": "markers", "name": COMPARATOR_NAME[k][1], "x": [x], "y": [y],
                       "marker": {"size": 13 if k == "portfolio" else 9, "color": role}, **_hover([hover(k)])})  # fmt: skip
    annotations = []
    for k, anchor, shift in (("split_60_40", "right", -10), ("split_100_0", "right", -10), ("portfolio", "left", 10),
                             ("savings", "left", 10)):  # fmt: skip
        if k in shown or k == "portfolio":
            x, y = point(k)
            label = "The portfolio, 70/30" if k == "portfolio" else COMPARATOR_NAME[k][1]
            annotations.append(_label(x, y, label, anchor=anchor, role="@accent" if k == "portfolio" else "@ink2",
                                      xshift=shift, yshift=8 if k != "portfolio" else 14))  # fmt: skip
    layout = {"showlegend": True, "legend": {"traceorder": "normal"},
              "xaxis": {"title": {"text": "Volatility, per cent a year"}, "rangemode": "tozero"},
              "yaxis": {"title": {"text": "Return since the first purchase, per cent"}},
              "annotations": annotations, "shapes": [_hline(0, "@axis")], "margin": {"t": 16}}  # fmt: skip
    rows = [[COMPARATOR_NAME[k][0], fmt.pct(summary.loc[k, "volatility"]), fmt.pct(summary.loc[k, "return_time_weighted"], True),
             _fall(summary.loc[k]), _band(summary.loc[k])] for k in ["portfolio", *shown]]  # fmt: skip
    headers = ["Comparator", "Volatility", "Return, time-weighted", "Worst fall", "Band chance alone produces, points"]
    table = _table(headers, rows, numeric=tuple(headers[1:]))
    return traces, layout, table


def _gap(daily: pd.DataFrame, key: str) -> pd.Series:
    """A comparator's growth of 100 minus the portfolio's, in points. A comparator whose series starts after the first
    purchase starts at 100 on its first day, against the portfolio's growth rebased to 100 on that day."""
    own = daily[f"growth_{key}"]
    first = own.first_valid_index()
    base = daily.loc[first, "growth_portfolio"] / 100 if first is not None else 1.0
    return own - daily["growth_portfolio"] / base


def _spread(ends: dict, gap: float) -> dict:
    """Label heights for line ends, each at least gap from the next and as near its line's end as that allows."""
    order = sorted(ends, key=lambda k: ends[k])
    at = [ends[k] for k in order]
    for _ in range(100):
        moved = False
        for i in range(1, len(at)):
            short = gap - (at[i] - at[i - 1])
            if short > 1e-9:
                at[i - 1] -= short / 2
                at[i] += short / 2
                moved = True
        if not moved:
            break
    return dict(zip(order, at))


def _pane_chart(cid: str, daily: pd.DataFrame, keys) -> tuple:
    """The cumulative difference of each comparator to the portfolio over time, in points; zero is the portfolio."""
    traces, annotations, rows = [], [], []
    dates = list(daily["date"])
    keys = [k for k in keys if f"growth_{k}" in daily]
    gaps = {k: _gap(daily, k) for k in keys}
    span = max([float(g.max()) for g in gaps.values()] + [0.0]) - min([float(g.min()) for g in gaps.values()] + [0.0])
    placed = _spread({k: float(g.iloc[-1]) for k, g in gaps.items()}, 0.065 * span)
    for k in keys:
        gap = gaps[k]
        role = COMPARATOR_ROLE[k]
        traces.append({"type": "scatter", "mode": "lines", "name": COMPARATOR_NAME[k][1], "x": dates,
                       "y": [fmt.rounded(v, 2) for v in gap], "line": {"color": role, "width": 2,
                       "dash": "dot" if k == "reference_b" else "solid"},
                       **_hover([f"{fmt.day_words(d)}<br>{COMPARATOR_NAME[k][1]}: {_points(v / 100)}" for d, v in zip(dates, gap)])})  # fmt: skip
        ends = {round(float(gaps[j].iloc[-1]), 2) for j in keys}
        if len(keys) > 1:
            label = COMPARATOR_NAME[k][1]
            if len(ends) == 1:  # every line ends at the same point, so one label names them all
                if k != keys[0]:
                    continue
                label = _and([COMPARATOR_NAME[j][1] for j in keys])
            annotations.append({**_label(dates[-1], fmt.rounded(placed[k], 2), label, role=role), "xshift": 6})
    for i, (_, r) in enumerate(daily.iterrows()):
        rows.append([_start_label(r["date"], i)] + [_points(gaps[k].iloc[i] / 100) for k in keys])
    wide, narrow = _date_axes(daily["date"])
    layout = {"showlegend": len(keys) == 1, "yaxis": {"title": {"text": "Points, comparator minus the portfolio"}}, **wide,
              "shapes": [_hline(0, "@ink")], "annotations": annotations, "margin": {"r": 64 if len(keys) > 1 else 24}}  # fmt: skip
    headers = ["Date"] + [COMPARATOR_NAME[k][1] for k in keys]
    table = _table(headers, rows, numeric=tuple(headers[1:]))
    chart = {"id": cid, "view": "comparisons", "traces": traces, "layout": layout,
             "layout_narrow": {**narrow, "yaxis": {"title": {"text": "Points"}}}}  # fmt: skip
    return chart, table


def _effects(summary: pd.DataFrame, effects: pd.DataFrame, keys: list) -> tuple:
    """The waterfall from the portfolio's money-weighted return through each effect to the comparator's, one per
    comparator, and the table of every comparator's effects."""
    order = list(comparisons_module.EFFECTS)
    record = effects[effects["period"] == "record"].pivot(index="comparator", columns="effect", values="value")
    record = record.reindex(columns=order)
    start = summary.loc["portfolio", "return_money_weighted"] * 100
    traces = []
    for i, k in enumerate(keys):
        values = [record.loc[k, e] * 100 for e in order]
        bases, level = [], start
        for v in values:  # an effect that is n/a for the comparator takes no room
            v = 0.0 if pd.isna(v) else v
            bases.append(level if v >= 0 else level + v)
            level += v
        end = summary.loc[k, "return_money_weighted"] * 100
        labels = ["The portfolio, money-weighted"] + [EFFECT_NAME[e] for e in order] + [f"{COMPARATOR_NAME[k][1]}, money-weighted"]
        x = [abs(start)] + [0.0 if pd.isna(v) else abs(v) for v in values] + [abs(end)]
        base = [min(0.0, start)] + bases + [min(0.0, end)]
        colours = ["@accent"] + ["@cost_3" if v < 0 else "@cost_2" for v in values] + ["@accent"]
        text = [fmt.pct(start / 100, True)] + [_points(v / 100, 2) for v in values] + [fmt.pct(end / 100, True)]
        traces.append({"type": "bar", "orientation": "h", "name": COMPARATOR_NAME[k][1], "y": labels,
                       "x": [fmt.rounded(v, 4) for v in x], "base": [fmt.rounded(v, 4) for v in base],
                       "marker": {"color": colours}, "visible": i == 0, "width": 0.6,
                       **_hover([f"{label}: {t}" for label, t in zip(labels, text)])})  # fmt: skip
    layout = {"barmode": "overlay", "yaxis": {"type": "category", "autorange": "reversed"},
              "xaxis": {"title": {"text": "Per cent, and points for each effect"}}, "shapes": [_vline(0, "@ink")],
              "margin": {"t": 8}}  # fmt: skip
    columns = [""] + [COMPARATOR_NAME[k][1] for k in keys]
    rows = [["The portfolio, money-weighted"] + [fmt.pct(start / 100, True)] * len(keys),
            ["The portfolio, time-weighted"] + [fmt.pct(summary.loc["portfolio", "return_time_weighted"], True)] * len(keys)]
    rows += [[EFFECT_NAME[e]] + [_points(record.loc[k, e], 2) for k in keys] for e in order]
    rows += [["The comparator, time-weighted"] + [fmt.pct(summary.loc[k, "return_time_weighted"], True) for k in keys],
             ["The comparator, money-weighted"] + [fmt.pct(summary.loc[k, "return_money_weighted"], True) for k in keys],
             ["Difference, time-weighted, points"] + [_diff(summary.loc[k, "difference"]) for k in keys],
             ["Band chance alone produces, points"] + [_band(summary.loc[k]) for k in keys],
             ["The comparator's volatility"] + [fmt.pct(summary.loc[k, "volatility"]) for k in keys],
             ["The comparator's worst fall"] + [_fall(summary.loc[k]) for k in keys]]
    table = _table(columns, rows, numeric=tuple(columns[1:]), wrap_first=True, wrap_head=True)
    # Many comparators side by side: a band and its words wrap within the cell.
    table = table.replace('<table class="wrapfirst headwrap">', '<table class="wrapfirst headwrap cellwrap">', 1)
    return traces, layout, table


def _selection_card(as_of) -> str:
    """How each one-fund comparator's fund was chosen: the rules' ranking with its index in place of the global
    index, one row per fund, as the ETF selection of the Method view shows it for the two funds held."""
    rows = []
    for index, name in SELECTIONS:
        path = config.METHOD_DIR / name
        if not path.exists():
            continue
        data = pd.read_csv(path)
        for isin, fund in data.groupby("isin", sort=False):
            first = fund.iloc[0]
            years = {int(y): v for y, v in zip(fund["year"], fund["tracking_difference_points"])}
            rows.append([index, int(first["rank"]), SHORT_FUND.get(isin, first["fund"]), isin,
                         f"{first['ter_per_cent']:.2f}"]
                        + ["n/a" if pd.isna(years.get(y)) else f"{years[y]:+.2f}".replace("-", fmt.MINUS) for y in (2023, 2024, 2025)]
                        + ["n/a" if pd.isna(first["average_points"]) else f"{first['average_points']:+.3f}".replace("-", fmt.MINUS),
                           first["offered_on_the_account"], fmt.day_short(first["factsheet_date"])])  # fmt: skip
    columns = ["Index", "Rank", "Fund", "ISIN", "TER", "2023", "2024", "2025", "Average", "Offered", "Factsheet"]
    table = _table(columns, rows, numeric=("TER", "2023", "2024", "2025", "Average"), wrap_first=False, prose=True)
    note = ("Each fund is the first in rank order that the account offers under the rules' equity criteria, with the "
            "index in place of the global index: Irish domicile, then the highest average tracking difference over three "
            "full calendar years, fund return minus index return in percentage points from the issuers' factsheets, then "
            "the lowest TER, in per cent a year. A fund without three years of factsheet returns ranks after those with them. The LifeStrategy "
            "funds are the euro accumulating classes, and the Mag7 fund was named when the comparators were fixed on "
            "10 November 2026, before any of their values was read.")  # fmt: skip
    return _card("comparisons-selection", "How the one-fund comparators' funds were chosen",
                 "Tracking difference in percentage points, calendar years 2023 to 2025",
                 tuple(f"method/{n}" for _, n in SELECTIONS) + ("method/comparator_funds.csv",), plot=False, kind="table",
                 wide=True, extra=table + f'<p class="note">{_esc(note)}</p>')  # fmt: skip


# The asset classes of the global market portfolio, in the order of its weight table.
MARKET_CLASS = {"equities": "Equities", "aggregate": "Government bonds and investment-grade credits",
                "private_equity": "Private equity", "real_estate": "Real estate", "em_debt": "Emerging-market debt",
                "inflation_linked": "Inflation-linked bonds", "high_yield": "High-yield bonds"}  # fmt: skip


def _share(x) -> str:
    """A weight in per cent to two decimals, as the dataset gives its weights: 42.96%."""
    return "n/a" if pd.isna(x) else f"{round(float(x) * 100, 2):.2f}%"


def _market_card(market: pd.DataFrame, fees: pd.DataFrame, as_of) -> str:
    """The global market portfolio's weights by asset class: as published, carried to the comparator's start and at
    the last close, each class's fund with its ISIN and TER, and the TERs weighted by the published weights."""
    if not len(market):
        return ""
    first = market.iloc[0]
    rows = []
    for _, r in market.iterrows():
        fund = "In the aggregate fund" if r["sleeve"] == "inflation_linked" else r["fund"]
        rows.append([MARKET_CLASS[r["sleeve"]], fund, r["isin"], f"{float(r['ter_per_cent']):.2f}", _share(r["published"]),
                     _share(r["start"]), _share(r["current"])])  # fmt: skip
    weighted = fees[(fees["comparator"] == "market_portfolio") & fees["item"].str.startswith("TERs weighted")] if len(fees) else fees
    if len(weighted):
        rows.append(["All classes", "TERs weighted by the published weights", "", f"{float(weighted['bps_low'].iloc[0]) / 100:.2f}",
                     _share(market["published"].sum()), _share(market["start"].sum()), _share(market["current"].sum())])  # fmt: skip
    columns = ["Asset class", "Fund", "ISIN", "TER", f"Published, {fmt.day_short(first['published_as_of'])}",
               f"At the start, {fmt.day_short(first['start_as_of'])}", f"On {fmt.day_short(first['current_as_of'])}"]  # fmt: skip
    table = _table(columns, rows, numeric=tuple(columns[3:]), wrap_first=True, wrap_head=True, prose=True)
    note = ("Weights in per cent of the comparator, TER in per cent a year. The published weights are the dataset's at the "
            "end of 2023, with government bonds and investment-grade credits summed into the class the aggregate fund holds. "
            "The weights at the start are the published ones carried to the day before the first purchase by each class "
            "fund's return in euro, and the comparator bought them on the first purchase day. The current weights have "
            "moved with the funds' prices since. Each fund is the first in its class's ranking that the account offers "
            "(method/selection_market_portfolio.csv). The account offers no inflation-linked fund that passes the "
            "criteria, so that class is held in the aggregate fund.")  # fmt: skip
    return _card("comparisons-market-weights", "The global market portfolio's weights and funds, by asset class",
                 _asof(as_of), ("outputs/comparison_market.csv", "method/market_portfolio_weights.csv",
                 "method/selection_market_portfolio.csv"), plot=False, kind="table", wide=True,
                 extra=table + f'<p class="note">{_esc(note)}</p>')  # fmt: skip


def _bps(low: float, high: float) -> str:
    """Basis points as a whole number, or a range when the source gives one."""
    return f"{low:.0f}" if round(low) == round(high) else f"{low:.0f} to {high:.0f}"


# What a single cost a year is made up of, in words, by the item the fee table gives it.
COST_WORDS = {"Ongoing costs of the two ETFs at the portfolio's weights": "The two ETFs' TER and transaction costs, at the "
              "portfolio's weights", "Ongoing charges figure": "The fund's ongoing charges figure"}  # fmt: skip


def _managed_card(summary: pd.DataFrame, fees: pd.DataFrame, as_of) -> str:
    """The bank's managed profile beside the portfolio: one row for each, with its costs a year and what they are made
    up of, since a bank publishes no return for its managed profiles. The portfolio's implementation cost, which is
    cumulative, is a sentence under the table."""
    fees = fees[fees["comparator"] != "market_portfolio"] if len(fees) else fees
    rows, implementation = [], None
    for key in dict.fromkeys(fees["comparator"]) if len(fees) else []:
        own = fees[fees["comparator"] == key]
        yearly = own[own["per"].str.startswith("a year")]
        for _, r in own[~own.index.isin(yearly.index)].iterrows():
            if key == "portfolio" and "Implementation" in r["item"]:
                implementation = float(r["bps_low"])
        if not len(yearly):
            continue
        total = yearly[yearly["item"] == "All in"]
        parts = yearly[yearly["item"] != "All in"]
        if len(total):
            # The profile's charges, each named as the cost overview names it, without how often it is charged.
            named = [f"{str(r['item']).split(',')[0]} {_bps(float(r['bps_low']), float(r['bps_high']))}"
                     for _, r in parts.iterrows()]  # fmt: skip
            named = named[:1] + [n[:1].lower() + n[1:] for n in named[1:]]
            made_up = ", ".join(named[:-1]) + " and " + named[-1] if len(named) > 1 else named[0]
            head = total.iloc[0]
        else:
            head = parts.iloc[0]
            made_up = COST_WORDS.get(str(head["item"]), str(head["item"]))
        who = COMPARATOR_NAME.get(key, (key,))[0] + (", 70/30" if key == "bank_offensief" else "")
        dated = fmt.month_short(str(head["dated"])[:7]) if key == "bank_offensief" else fmt.day_short(head["dated"])
        rows.append([who, _bps(float(head["bps_low"]), float(head["bps_high"])), made_up, f"{head['source']}, {dated}"])
    columns = ["", "Costs a year, basis points", "Made up of", "Source"]
    table = _table(columns, rows, numeric=("Costs a year, basis points",), wrap_first=True, prose=True) if rows else ""
    status = summary.loc["bank_offensief", "status"] if "bank_offensief" in summary.index else ""
    note = (f"{_status(status)}, so this table sets the costs a year side by side and nothing else: there is no return, "
            "volatility or worst fall to set beside the portfolio's, and the profile is not like for like. Rabobank "
            "manages index funds for its clients in Rabo Beheerd Beleggen Basis, in four profiles from Defensief to Zeer "
            "Offensief, and its brochure and Risicometer give Offensief 70 per cent equity and 30 per cent bonds, the "
            "portfolio's split. Its costs are read from Rabobank's published cost overview at each build: the basic "
            "service and the portfolio management are each charged a quarter at a time on the first 100,000 euro "
            "invested, as the overview's examples show, and the funds' own costs are the range the overview states.")  # fmt: skip
    after = ""
    if implementation is not None:
        after = (f" The portfolio's implementation cost since the first purchase, {_esc(f'{implementation:.1f}'.replace('-', fmt.MINUS))} "
                 'basis points, is cumulative and not a cost a year, and is in <a href="#costs">Costs</a>.')  # fmt: skip
    return _card("comparisons-managed", "Not like for like: a bank's managed profile and its costs, in basis points",
                 _asof(as_of), ("outputs/comparison_fees.csv", "outputs/comparisons.csv"), plot=False, kind="table",
                 wide=True, extra=table + f'<p class="note">{_esc(note)}{after}</p>')  # fmt: skip


def comparisons_part(page, summary: pd.DataFrame, daily: pd.DataFrame, effects: pd.DataFrame,
                     fees: pd.DataFrame = pd.DataFrame(), regions: pd.DataFrame = pd.DataFrame(),
                     market: pd.DataFrame = pd.DataFrame()) -> None:  # fmt: skip
    """The record beside its comparators: the summary table, the differences and the risk ladder, then the panes."""
    if not len(summary):
        return
    summary = summary.set_index("comparator")
    if "status" not in summary:
        summary["status"] = ""
    portfolio = summary.loc["portfolio"]
    days = int(portfolio["periods"])
    as_of = portfolio["last_day"]
    shown = [k for k in summary.index if k != "portfolio" and not pd.isna(summary.loc[k, "band"])]
    rows = []
    for key in summary.index:
        r = summary.loc[key]
        rows.append([COMPARATOR_NAME[key][0], fmt.pct(r["return_time_weighted"], True), fmt.pct(r["volatility"]),
                     _fall(r), _diff(r["difference"]), _band(r), _window(r.to_dict() | {"comparator": key})])  # fmt: skip
    columns = ["Comparator", "Return, time-weighted", "Volatility", "Worst fall", "Difference, points",
               "Band chance alone produces, points", "Window"]  # fmt: skip
    table = _table(columns, rows, numeric=tuple(columns[1:6]), wrap_first=True, wrap_head=True)
    bench_note = ("The benchmark has values at month ends only, because the bond index has no public daily series. Its "
                  "return runs from the first month end and is shown from the second, and its volatility, worst fall, "
                  "correlation, difference and band come from monthly values times the square root of 12 and are shown "
                  f"from the sixth month end, since a tracking error from fewer monthly differences is not an estimate.")  # fmt: skip
    late = [k for k in summary.index if k != "benchmark" and isinstance(summary.loc[k, "first_day"], str)
            and summary.loc[k, "first_day"] > portfolio["first_day"]]  # fmt: skip
    window_note = "".join(f" {COMPARATOR_NAME[k][0]}'s series starts on {fmt.day_words(summary.loc[k, 'first_day'])}, so its "
                          "figures run from that day's close, against the portfolio's over the same days."
                          for k in late)  # fmt: skip
    notes = ("In euro, on the same contributions on the same days, at the issuers' net asset values or the published "
             "rate. The comparators carry no costs, and the portfolio's costs are in the Costs part. Returns since the first "
             "purchase are cumulative and not annualised. Differences are the comparator's return minus the portfolio's, "
             "in percentage points." + window_note, BAND_NOTE, MINIMUM_NOTE + " " + bench_note, CHANCE.format(days=days))  # fmt: skip
    page.add("comparisons", _card("comparisons", "The portfolio and its comparators since the first purchase",
             _asof(as_of), "outputs/comparisons.csv", plot=False, kind="table", wide=True,
             extra=table + "".join(f'<p class="note">{_esc(n)}</p>' for n in notes)))  # fmt: skip

    traces, layout, diff_table = _differences(summary, shown)
    diff_card = _card("comparisons-differences", "The difference of each comparator to the portfolio, and its band",
                      _asof(as_of, "Points, comparator minus the portfolio"), "outputs/comparisons.csv", table=diff_table,
                      height=40 * len(shown) + 90,
                      note="The navy bar is the difference and the light bar the band chance alone produces over the same "
                           "span, centred on zero. The benchmark joins at the sixth month end, and a daily comparator at "
                           f"its {comparisons_module.MIN_DAILY_RETURNS}th daily return.")  # fmt: skip
    traces_l, layout_l, ladder_table = _ladder(summary, shown)
    ladder_card = _card("comparisons-ladder", "Volatility against return since the first purchase",
                        _asof(as_of), "outputs/comparisons.csv", table=ladder_table, height=380,
                        note=("The splits under the same rules lie on one line through reference portfolio A, which is 70/30. "
                              "The benchmark joins at the sixth month end. " + CHANCE.format(days=days)))  # fmt: skip
    page.add("comparisons", f'<div class="wide ch-pair">{diff_card}{ladder_card}</div>')
    page.charts += [{"id": "comparisons-differences", "view": "comparisons", "traces": traces, "layout": layout,
                     "layout_narrow": {"xaxis": {"title": {"text": "Points"}}}},
                    {"id": "comparisons-ladder", "view": "comparisons", "traces": traces_l, "layout": layout_l,
                     "layout_narrow": {"xaxis": {"title": {"text": "Volatility, per cent"}},
                                       "yaxis": {"title": {"text": "Return, per cent"}}}}]  # fmt: skip

    shares = {k: summary.loc[k, "equity_share"] for k in ("lifestrategy_60", "lifestrategy_80")
              if k in summary.index and "equity_share" in summary and pd.notna(summary.loc[k, "equity_share"])}  # fmt: skip
    mixed = ""
    if shares:
        dated = regions[regions["comparator"].isin(list(shares))]["snapshot"].max() if len(regions) else None
        held = _and([f"{COMPARATOR_NAME[k][0]} {fmt.pct(v)}" for k, v in shares.items()])
        mixed = (f" The equity share of the underlying funds is {held}" + (f", on Vanguard's factsheet of {fmt.day_words(dated)}"
                 if isinstance(dated, str) else "") + ".")  # fmt: skip
    first_ranked = "first_ranked" in summary.index and pd.notna(summary.loc["first_ranked", "return_time_weighted"])
    panes = []
    market_share = ""
    if len(market):
        like = market[market["sleeve"].isin(comparisons_module.EQUITY_LIKE)]
        share = {k: f"{float(like[k].sum()) * 100:.1f}" for k in ("published", "start", "current")}
        market_share = MARKET_SHARE.format(**share, day=fmt.day_words(market["current_as_of"].iloc[0]),
                                           target=f"{config.TARGET[config.EQUITY] * 100:.0f}")  # fmt: skip
    pane_notes = {
        "same_rules": ("Reference portfolio A follows the rules at net asset value without costs, so its difference to the "
                       "portfolio is the implementation cost with the opposite sign. Reference portfolio B goes back to "
                       "70/30 on every cycle day, so its difference to reference portfolio A is the drift effect. "
                       "The benchmark joins this pane at the sixth month end."),
        "other_funds_or_splits": ("The same two ETFs at other target weights, under rules 3 to 6 with the band of rule 5 "
                                  "five points either side of each target, which never binds for 100/0."
                                  + (" 70/30 with the first-ranked funds runs reference portfolio A's rules with the "
                                     "first equity fund of the rules' own ranking, SPDR MSCI ACWI, which the account does "
                                     "not offer, in place of the held one, and the bond fund held, which ranks first."
                                     if first_ranked else "")),
        "one_fund": ("Each fund takes the same contributions on the same days at its net asset value in euro, US dollar "
                     "values at the ECB's reference rate of the day, and is held throughout without costs, as the S&P 500 "
                     "alternative of the Method view is. The Mag7 fund publishes net asset values from 4 November 2026, "
                     "so it holds the portfolio's value at that day's close, bought at that net asset value, and takes the "
                     "contributions after it. Each of its figures runs over that window." + mixed),
        "market_portfolio": (*MARKET_NOTE, market_share) if market_share else MARKET_NOTE,
        "bank": ("The contributions held at the euro short-term rate, compounded daily on calendar days at the rate over "
                 "360. Its volatility comes from interest landing in three-day steps over weekends, and its correlation "
                 "with the portfolio is not shown, since the rate barely moves from day to day."),
    }  # fmt: skip
    for pane, headline, keys, cid in PANES:
        keys = tuple(k for k in keys if k in summary.index)
        if not keys:
            continue
        if pane == "other_funds_or_splits" and not first_ranked:
            headline, keys = OTHER_SPLITS, tuple(k for k in keys if k != "first_ranked")
        if pane == "managed":
            body = _managed_card(summary, fees, as_of)
        else:
            chart, chart_table = _pane_chart(cid, daily, keys)
            note = pane_notes[pane] if isinstance(pane_notes[pane], tuple) else (pane_notes[pane],)
            body = _card(cid, f"{headline}: the difference to the portfolio over time", _asof(as_of, "Points, comparator minus the portfolio"),
                         ("outputs/comparisons_daily.csv", "outputs/comparisons.csv"), table=chart_table, wide=True,
                         height=300, note=(*note, BAND_NOTE), extra=_comparison_rows(summary, keys))  # fmt: skip
            page.charts.append(chart)
            if pane == "one_fund":
                body += _selection_card(as_of)
            if pane == "market_portfolio":
                body += _market_card(market, fees, as_of)
        panes.append(f'<details class="ch-pane"><summary>{_esc(headline)}</summary><div class="ch-pane__body">{body}</div></details>')

    with_effects = set(effects.loc[effects["period"] == "record", "comparator"]) if len(effects) else set()
    keys = [k for k in summary.index if k not in ("portfolio", "benchmark") and k in with_effects]
    traces_w, layout_w, effects_table = _effects(summary, effects, keys)
    default = keys.index("split_100_0") if "split_100_0" in keys else 0
    for i, t in enumerate(traces_w):
        t["visible"] = i == default
    options = "".join(f'<option value="{i}"{" selected" if i == default else ""}>{_esc(COMPARATOR_NAME[k][1])}</option>'
                      for i, k in enumerate(keys))  # fmt: skip
    select = (f'<p class="ch-select"><label for="comparisons-effects-select">Comparator</label> '
              f'<select id="comparisons-effects-select" data-chart="comparisons-effects">{options}</select></p>')  # fmt: skip
    effect_notes = (
        "Each difference is split into effects computed day by day, summed by month and then over the months. Implementation "
        "is reference portfolio A's return minus the portfolio's. Drift is reference portfolio B's return minus reference "
        "portfolio A's. Split is the difference in the equity share of the invested part times the equity fund's return in "
        "US dollars minus the bond fund's return, and the dollar is the same difference times the gap between the equity "
        "fund's return in euro and in US dollars, at the ECB's reference rates, so the two sum to the split in euro. The "
        "fund's other currencies stay inside its dollar return. Cash is the difference in cash weight times the return of "
        "the invested part.",
        "For a comparator that holds other funds, the difference runs through the two funds held at the comparator's equity "
        "share without cash, which gives cash, split and the dollar by the same definitions. Regions is the comparator's equity share "
        "times the sum over the four regions of its weight in the region minus the held equity fund's, times the "
        "region's MSCI index return in euro, Brinson and Fachler's allocation term, with each fund's weights scaled to "
        "the four regions. A US dollar fund's own currency gap against the held fund's goes to the dollar, and within "
        "each region is the rest: the funds' choice of companies inside each region, their costs and their timing "
        "against the indices. The funds and the indices are valued at different times of the day, so a fund's gap "
        "against the indices can reach some tenths of a point on a day and reverse the next. The gap cancels between a "
        "comparator and the held fund when both are converted at the ECB's rate, and a gap under a tenth of a point "
        "between two rows is within what the valuation times alone produce. 70/30 with the first-ranked funds splits its "
        "equity fund's return the same way. Region "
        "weights are each fund's latest, held for the record so far and kept at each month end. The S&P 500, Nasdaq-100 "
        "and Mag7 funds count as North America, a LifeStrategy fund's equity part takes its underlying funds' regions, "
        "a FTSE All-World fund taking the held fund's and a FTSE Developed World fund the MSCI World fund's "
        "(method/lifestrategy_underlying.csv), and the SPDR funds' come from their holdings by country through "
        "method/msci_regions.csv.",
        "For the global market portfolio, the difference runs through the two funds held at its equity-like share, "
        "equities, private equity and real estate together, which gives cash, split and the dollar by the same "
        "definitions. Equity classes is the weight of private equity and of real estate times each fund's return in euro "
        "minus the equity fund's, and bond classes is the weight of each bond class times its fund's return in euro minus "
        "the bond fund's. Each dollar fund's conversion to euro goes to the dollar, less the equity fund's for an "
        "equity-like class, so the currencies inside a bond fund's dollar return stay in bond classes. Regions and within "
        "each region are zero for it.",
        "For savings, the bond fund's return against the rate is split three ways at the ECB curve's spot rate at the "
        "bond fund's duration in whole years: the rate against the bonds' yield earned over the days, the duration times "
        "the change in that yield, and the rest of the bond return. The LifeStrategy funds hold global bonds hedged to the "
        "euro, which the ECB curve does not price, so their bond rows are n/a and their bonds' difference to the bond "
        "fund stays within each region.",
        "Timing of contributions is the comparator's money-weighted return minus its time-weighted return, less the "
        "portfolio's. Compounding is the difference of the cumulative returns minus the sum of the daily effects. An "
        "effect that does not apply to a comparator is zero. Effects are in percentage points to two decimals. The table "
        "carries each comparator's difference, band, volatility and worst fall beside its effects.")  # fmt: skip
    card = _card("comparisons-effects", "Where each difference came from: from the portfolio's money-weighted return to "
                 "the comparator's", _asof(as_of), ("outputs/comparison_effects.csv", "outputs/comparisons.csv",
                 "outputs/comparison_regions.csv"), table=None, wide=True, height=480, note=effect_notes,
                 extra=effects_table + f'<p class="rounding">{ROUNDING.replace("100 per cent", "the difference")}</p>')  # fmt: skip
    card = card.replace('<div class="plot"', select + '<div class="plot"', 1)
    page.charts.append({"id": "comparisons-effects", "view": "comparisons", "traces": traces_w, "layout": layout_w,
                        "select": "comparisons-effects-select", "layout_narrow": {"xaxis": {"title": {"text": "Per cent and points"}}}})  # fmt: skip
    panes.append('<details class="ch-pane"><summary>Where each difference came from</summary>'
                 f'<div class="ch-pane__body">{card}</div></details>')
    page.add("comparisons", f'<div class="wide ch-panes">{"".join(panes)}</div>')


# Contributions -------------------------------------------------------------------------------------


def contributions(page, daily, monthly):
    history = daily
    empty = None if len(daily) > 1 else "The value in units starts on the first valuation day."
    traces = []
    if not empty:
        x = list(daily["date"])
        value = [fmt.rounded(v, 1) for v in daily["value_in_units"]]
        paid = [fmt.rounded(v, 1) for v in daily["contributions_in_units"]]
        # One fill between the two lines: which line is on top shows whether the gap is a gain or a loss.
        traces = [
            {"type": "scatter", "mode": "lines", "x": x, "y": paid, "line": {"width": 0},
             "hoverinfo": "skip", "showlegend": False},
            {"type": "scatter", "mode": "lines", "x": x, "y": value, "fill": "tonexty", "fillcolor": "@gap_fill",
             "line": {"width": 0}, "hoverinfo": "skip", "name": "Gap between value and money paid in", "showlegend": True},
            {"type": "scatter", "mode": "lines", "name": "Contributions paid in", "x": x, "y": paid,
             "line": {"color": "@ink2", "width": 2},
             **_hover([f"{fmt.day_words(d)}<br>Paid in: {fmt.index(p)}" for d, p in zip(x, daily["contributions_in_units"])])},
            {"type": "scatter", "mode": "lines+markers" if len(x) < 4 else "lines", "name": "Value of the portfolio",
             "x": x, "y": value, "line": {"color": "@accent", "width": 2}, "marker": {"size": 8, "color": "@accent"},
             **_hover([f"{fmt.day_words(d)}<br>Value: {fmt.index(v)}" for d, v in zip(x, daily["value_in_units"])])},
        ]  # fmt: skip
    wide, narrow = _date_axes(daily["date"])
    # From zero, so that the gap between the value and the money paid in is drawn to scale.
    layout = {"showlegend": True, "legend": {"traceorder": "reversed"},
              "yaxis": {"title": {"text": "Units of the starting amount"}, "rangemode": "tozero"}, **wide}  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.index(r["contributions_in_units"]), fmt.index(r["value_in_units"])]
            for i, (_, r) in enumerate(daily.iterrows())]  # fmt: skip
    table = _table(["Date", "Paid in", "Value"], rows, numeric=("Paid in", "Value"))
    page.add("contributions", _card("c9", "Money paid in and the value of the portfolio, in units of the starting amount",
             _asof(daily["date"].iloc[-1], "The starting amount is 100 units and each top-up is 5"),
             "outputs/portfolio_daily.csv", table=None if empty else table, height=320, empty=empty),
             None if empty else {"id": "c9", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip

    empty = None if len(monthly) else "The first month starts with the first valuation day."
    rows = [[fmt.month_short(r["month"]) + ("" if r["complete"] == "yes" else " (to date)"), fmt.pct(r["market_effect"], True),
             fmt.pct(r["contribution_effect"], True)] for _, r in monthly.iterrows()] if len(monthly) else []  # fmt: skip
    table = _table(["Month", "Market effect", "Contribution"], rows, numeric=("Market effect", "Contribution"))
    chart_a = chart_b = None
    if not empty:
        m = [_month_tick(x) for x in monthly["month"]]
        months_shown = [-0.5, max(len(m), 6) - 0.5]
        chart_a = {"id": "c10a", "traces": [{"type": "bar", "name": "Market effect", "x": m, "width": 0.45,
                   "y": [fmt.rounded(v * 100, 1) for v in monthly["market_effect"]],
                   "marker": {"color": "@accent"},
                   **_hover([f"{fmt.month_words(a)}<br>Market effect {fmt.pct(v, True)}" for a, v in zip(monthly["month"], monthly["market_effect"])])}],
                   "layout": {"yaxis": {"title": {"text": "Market effect, per cent"}, "zeroline": True},
                              "xaxis": {"type": "category", "range": months_shown}, "shapes": [_hline(0, "@ink")]}}  # fmt: skip
        chart_b = {"id": "c10b", "traces": [{"type": "bar", "name": "Contribution", "x": m, "width": 0.45,
                   "y": [fmt.rounded(v * 100, 1) for v in monthly["contribution_effect"]], "marker": {"color": "@ink2"},
                   **_hover([f"{fmt.month_words(a)}<br>Contribution {fmt.pct(v, True)}" for a, v in zip(monthly["month"], monthly["contribution_effect"])])}],
                   "layout": {"yaxis": {"title": {"text": "Contribution, per cent"}}, "xaxis": {"type": "category",
                              "title": {"text": "Month"}, "range": months_shown}}}  # fmt: skip
    body = "" if empty else ('<div class="plot" id="c10a" style="height:200px" role="img" aria-label="Market effect by month"></div>'
                             '<div class="plot" id="c10b" style="height:200px" role="img" aria-label="Contribution by month"></div>')  # fmt: skip
    block = _card("c10", "Market effect and contribution by month, in per cent of the value at the start of the month",
                  _asof(daily["date"].iloc[-1]), "outputs/metrics_monthly.csv", plot=False, table=table, empty=empty,
                  kind="figure")
    block = block.replace('<p class="source">', body + '<p class="source">', 1)
    page.add("contributions", block, chart_a)
    if chart_b:
        chart_b["view"] = "contributions"
        page.charts.append(chart_b)


# Look-through --------------------------------------------------------------------------------------


def _bars(cid, frame, label, role, title, asof, source, page, view, note=None, share_col="share_of_portfolio",
          sleeve=True, sort=True, rounding=False):
    frame = frame.copy()
    names = list(frame[label])
    values = list(frame[share_col])
    hover = []
    for _, r in frame.iterrows():
        text = f"{r[label]}: {fmt.pct(r[share_col])} of the portfolio"
        if sleeve and "share_of_sleeve" in frame:
            text += f"<br>{fmt.pct(r['share_of_sleeve'])} of the sleeve"
        hover.append(text)
    traces = [{"type": "bar", "orientation": "h", "y": names, "x": [fmt.rounded(v * 100, 1) for v in values],
               "marker": {"color": role}, "text": [fmt.pct(v) for v in values], "textposition": "outside",
               "cliponaxis": False, "textfont": {"color": "@ink2", "size": 11}, **_hover(hover)}]  # fmt: skip
    height = 60 + 26 * len(names)
    layout = {"yaxis": {"autorange": "reversed", "showline": False, "ticks": ""},
              "xaxis": {"title": {"text": "Per cent of the portfolio"}, "rangemode": "tozero"},
              "margin": {"r": 48}, "bargap": 0.45}  # fmt: skip
    cols = [label.capitalize(), "Share of the portfolio"] + (["Share of the sleeve"] if sleeve and "share_of_sleeve" in frame else [])
    rows = [[r[label], fmt.pct(r[share_col])] + ([fmt.pct(r["share_of_sleeve"])] if len(cols) == 3 else [])
            for _, r in frame.iterrows()]  # fmt: skip
    table = _table(cols, rows, numeric=tuple(cols[1:]), rounding=rounding)
    page.add(view, _card(cid, title, asof, source, table=table, note=note, height=height),
             {"id": cid, "traces": traces, "layout": layout})


def lookthrough(page, out):
    def asof(frame):
        r = frame.iloc[0]
        return f"Holdings as of {fmt.day_words(r['holdings_as_of'])}, sleeve weights as of {fmt.day_words(r['weights_as_of'])}"

    held = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv")
    held = held[held["held"] == "yes"].drop_duplicates("sleeve").set_index("sleeve")["fund"]
    markets = list(pd.read_csv(config.METHOD_DIR / "funds_held.csv")["country"])
    weights = out["allocation_now.csv"].iloc[0]
    page.add("lookthrough", _section("Equity sleeve", "lookthrough-equity", tone="equity",
             sub=f"{held['equity']}, {fmt.pct(weights['weight_equity'])} of the portfolio"))  # fmt: skip
    region, country, sector = out["lookthrough_equity_region.csv"], out["lookthrough_equity_country.csv"], out["lookthrough_equity_sector.csv"]
    _bars("c11a", region, "region", "@equity", "Equity by region", asof(region),
          "outputs/lookthrough_equity_region.csv", page, "lookthrough",
          note="Regions follow MSCI's market classification (method/msci_regions.csv).", rounding=True)
    _bars("c11b", country, "country", "@equity", "Equity by country: the ten largest", asof(country),
          "outputs/lookthrough_equity_country.csv", page, "lookthrough",
          note=f"Country is the issuer's location as iShares reports it. {NUMBER_WORD[len(markets)]} of the fund's holdings are iShares "
               f"ETFs that each hold one market ({_and(markets)}), and each is counted under that market.")
    _bars("c12", sector, "sector", "@equity", "Equity by sector", asof(sector), "outputs/lookthrough_equity_sector.csv",
          page, "lookthrough", note="GICS sectors as iShares reports them. The single-market ETFs held by the fund have no single sector.",
          rounding=True)
    top = out["lookthrough_top10.csv"]
    total = top["share_of_portfolio"].sum()
    _bars("c14", top, "company", "@equity", f"The ten largest companies: {fmt.pct(total)} of the portfolio", asof(top),
          "outputs/lookthrough_top10.csv", page, "lookthrough",
          note="Share classes of one company are summed (method/companies.csv).")
    page.add("lookthrough", _section("Bond sleeve", "lookthrough-bonds", tone="bonds",
             sub=f"{held['bonds']}, {fmt.pct(weights['weight_bonds'])} of the portfolio"))  # fmt: skip
    bonds = out["lookthrough_bonds_country.csv"]
    _bars("c15", bonds, "country", "@bonds", "Bonds by issuing country", asof(bonds),
          "outputs/lookthrough_bonds_country.csv", page, "lookthrough", rounding=True)
    # Chart 16: maturity ladder with the duration tiles.
    mat = out["lookthrough_bonds_maturity.csv"]
    dur = out["lookthrough_bonds_duration.csv"].iloc[0]
    labels = list(mat["maturity"])
    ranges = [m for m in labels if m != "Cash and derivatives"]
    short = [m.replace(" years", "").replace(" year", "").replace("Cash and derivatives", "Cash") for m in labels]
    colors = ["@bonds"] * len(ranges) + (["@muted"] if len(labels) > len(ranges) else [])
    traces = [{"type": "bar", "x": short, "y": [fmt.rounded(v * 100, 1) for v in mat["share_of_sleeve"]],
               "marker": {"color": colors}, "text": [fmt.pct(v) for v in mat["share_of_sleeve"]], "textposition": "outside",
               "cliponaxis": False, "textfont": {"color": "@ink2", "size": 11},
               **_hover([f"{m}: {fmt.pct(s)} of the sleeve<br>{fmt.pct(p)} of the portfolio" for m, s, p in
                         zip(labels, mat["share_of_sleeve"], mat["share_of_portfolio"])])}]  # fmt: skip
    layout = {"xaxis": {"type": "category", "title": {"text": "Years to maturity"}, "tickangle": 0},
              "yaxis": {"title": {"text": "Per cent of the bond sleeve"}, "rangemode": "tozero"}, "margin": {"t": 16},
              "bargap": 0.3}
    rows = [[m, fmt.pct(s), fmt.pct(p)] for m, s, p in zip(labels, mat["share_of_sleeve"], mat["share_of_portfolio"])]
    table = _table(["Maturity", "Share of the sleeve", "Share of the portfolio"], rows,
                   numeric=("Share of the sleeve", "Share of the portfolio"), rounding=True)
    tiles = (f'<div class="duo"><div class="tile"><p class="name">Duration of the bond sleeve</p>'
             f'<div class="value">{_esc(fmt.years(dur["duration_years"]))}</div><div class="change">Vanguard factsheet of '
             f'{_esc(fmt.day_words(dur["holdings_as_of"]))}</div></div><div class="tile"><p class="name">Duration contribution to the portfolio</p>'
             f'<div class="value">{_esc(fmt.years(dur["portfolio_duration_years"]))}</div><div class="change">Sleeve weight times duration'
             f'</div></div></div>')  # fmt: skip
    block = _card("c16", "Bonds by maturity, and duration", asof(mat), ["outputs/lookthrough_bonds_maturity.csv",
                  "outputs/lookthrough_bonds_duration.csv"], table=table, height=280,
                  note="Maturities are measured from the holdings' as-of date. Duration is the factsheet's average duration.")
    block = block.replace("</h3>", "</h3>" + tiles, 1)
    page.add("lookthrough", block, {"id": "c16", "traces": traces, "layout": layout})
    rating = out["lookthrough_bonds_rating.csv"]
    labels = list(rating["rating"])
    traces = [{"type": "bar", "x": labels, "y": [fmt.rounded(v * 100, 1) for v in rating["share_of_sleeve"]],
               "marker": {"color": "@bonds"},
               "text": [fmt.pct(v) for v in rating["share_of_sleeve"]], "textposition": "outside", "cliponaxis": False,
               "textfont": {"color": "@ink2", "size": 11},
               **_hover([f"{m}: {fmt.pct(s)} of the sleeve<br>{fmt.pct(p)} of the portfolio" for m, s, p in
                         zip(labels, rating["share_of_sleeve"], rating["share_of_portfolio"])])}]  # fmt: skip
    layout = {"xaxis": {"type": "category", "title": {"text": "Rating"}},
              "yaxis": {"title": {"text": "Per cent of the bond sleeve"}, "rangemode": "tozero"}, "margin": {"t": 16}}
    rows = [[m, fmt.pct(s), fmt.pct(p)] for m, s, p in zip(labels, rating["share_of_sleeve"], rating["share_of_portfolio"])]
    table = _table(["Rating", "Share of the sleeve", "Share of the portfolio"], rows,
                   numeric=("Share of the sleeve", "Share of the portfolio"), rounding=True)
    page.add("lookthrough", _card("c17", "Credit quality of the bond sleeve, as the issuer reports it",
             f"Vanguard factsheet as of {fmt.day_words(rating['holdings_as_of'].iloc[0])}", "outputs/lookthrough_bonds_rating.csv",
             table=table, height=260, note="The factsheet takes the median of the Moody's, Fitch and S&P ratings of each issue."),
             {"id": "c17", "traces": traces, "layout": layout})  # fmt: skip

    # Chart 13: currency exposure of the whole portfolio, each bar split by the sleeve it comes from.
    page.add("lookthrough", _section("Whole portfolio", "lookthrough-portfolio",
             sub="Both sleeves and cash together"))  # fmt: skip
    currency = out["lookthrough_currency.csv"]
    names = list(currency["currency"])
    parts = [("Equity sleeve", "from_equity_sleeve", "@equity"), ("Bond sleeve", "from_bond_sleeve", "@bonds"),
             ("Cash", "from_cash", "@cash")]  # fmt: skip
    traces = []
    for label, column, role in parts:
        if not (currency[column] > 0).any():
            continue
        traces.append({"type": "bar", "orientation": "h", "name": label, "y": names,
                       "x": [fmt.rounded(v * 100, 2) for v in currency[column]],
                       "marker": {"color": role, "line": {"color": "@surface", "width": 2}},
                       **_hover([f"{c}: {fmt.pct(v)} of the portfolio from the {label.lower()}<br>{fmt.pct(t)} in all"
                                 for c, v, t in zip(names, currency[column], currency["share_of_portfolio"])])})  # fmt: skip
    labels = [_label(fmt.rounded(t * 100, 2), c, fmt.pct(t), xshift=6) for c, t in zip(names, currency["share_of_portfolio"])]
    layout = {"barmode": "stack", "showlegend": True, "legend": {"traceorder": "normal"}, "bargap": 0.45,
              "yaxis": {"autorange": "reversed", "showline": False, "ticks": "", "type": "category"},
              "xaxis": {"title": {"text": "Per cent of the portfolio"}, "rangemode": "tozero"},
              "annotations": labels, "margin": {"r": 48}}  # fmt: skip
    rows = [[r["currency"], fmt.pct(r["share_of_portfolio"]), fmt.pct(r["from_equity_sleeve"]),
             fmt.pct(r["from_bond_sleeve"]), fmt.pct(r["from_cash"])] for _, r in currency.iterrows()]  # fmt: skip
    table = _table(["Currency", "Share of the portfolio", "From the equity sleeve", "From the bond sleeve", "From cash"],
                   rows, numeric=("Share of the portfolio", "From the equity sleeve", "From the bond sleeve", "From cash"),
                   rounding=True)
    note = ("Each holding counts in the currency of its market, as the issuers report it, so buying the equity ETF's "
            "US dollar share class in euro on Xetra does not change the exposure. Currencies are named until the rest "
            "is below 10 per cent of the portfolio.")  # fmt: skip
    page.add("lookthrough", _card("c13", "Currency exposure, by sleeve", asof(currency),
             "outputs/lookthrough_currency.csv", table=table, note=note, height=80 + 30 * len(names), wide=True),
             {"id": "c13", "traces": traces, "layout": layout})  # fmt: skip


# Risk of the whole portfolio ------------------------------------------------------------------------

# Chart 30's column labels: two lines on a desktop, short codes on a phone, both level (G6).
COLUMN_LABEL = {"North America": "North<br>America", "Europe and Middle East": "Europe and<br>Middle East", "Pacific": "Pacific",
                "Emerging markets": "Emerging<br>markets", "Bonds, short": "Bonds,<br>short", "Bonds, medium": "Bonds,<br>medium",
                "Bonds, long": "Bonds,<br>long"}  # fmt: skip
COLUMN_CODE = {"North America": "NAm", "Europe and Middle East": "Eur", "Pacific": "Pac", "Emerging markets": "EM",
               "Bonds, short": "Sh", "Bonds, medium": "Med", "Bonds, long": "Lg"}  # fmt: skip
SHORT_COMPONENT = {"North America": "N. America", "Europe and Middle East": "Europe, ME", "Pacific": "Pacific",
                   "Emerging markets": "Emerging", "Bonds, short": "Short", "Bonds, medium": "Medium",
                   "Bonds, long": "Long", "Cash": "Cash"}  # fmt: skip
STUDY_URL = SITE_URL + "projects/optimal-vs-naive-diversification/"
STUDY_NAME = "Optimal versus naive diversification"


def _window_text(summary) -> str:
    return f"the 120 months from {_month_name(summary['window_start'])} to {_month_name(summary['window_end'])}"


def _risk_tiles(page, summary, boot, weight_equity, monthly):
    """Item 3: the estimated volatility, the estimated worst fall at the nearest split, and from month 12 the
    forecast's calibration."""
    split_weight = round(weight_equity * 20) / 20
    split = f"{round(split_weight * 100)}/{round((1 - split_weight) * 100)}"
    row = boot[(boot["horizon_years"] == 10) & (boot["block_months"] == 12) & (boot["split"] == split)]
    fall = (fmt.pct(row["median_worst_fall"].iloc[0]), fmt.pct(row["p95_worst_fall"].iloc[0])) if len(row) else ("n/a", "n/a")
    months = int(summary["calibration_months"]) if pd.notna(summary["calibration_months"]) else 0
    if pd.notna(summary["calibration"]):
        calibration = (f"{summary['calibration']:.2f}",
                       f"Over {months} months. Realised volatility {fmt.pct(summary['realised_volatility_12m'])} over the last 12")
    else:
        calibration = ("n/a", "From the October 2027 month end, when twelve months of returns exist, with the realised volatility")
    tiles = [("Estimated volatility", fmt.pct(summary["estimated_volatility"]),
              f"A year, at the look-through weights of {fmt.day_words(summary['weights_as_of'])}, on {_window_text(summary)}"),
             ("Estimated worst fall over ten years", fall[0],
              f"Median of the bootstrap at {split}, the split nearest the equity weight of {fmt.day_words(summary['weights_as_of'])}, "
              f"on the returns from February 1999 to December 2025. 95th percentile {fall[1]}"),
             ("The forecast's calibration", *calibration)]  # fmt: skip
    tile_html = "".join(f'<div class="tile"><p class="name">{_esc(n)}</p><div class="value">{_esc(v)}</div>'
                        f'<div class="change">{_esc(c)}</div></div>' for n, v, c in tiles)  # fmt: skip
    line = ("The forecast's calibration is the standard deviation, over the months, of each month's return divided by the "
            "monthly volatility estimated at the end of the month before. 1 means the estimates matched the returns, and "
            "above 1 that they were too low. Every estimate is kept as first written, in outputs/ex_ante_risk.csv.")  # fmt: skip
    page.add("risk", f'<div class="wide"><div class="tiles three">{tile_html}</div><p class="tilenote">{_esc(line)}</p>'
             '<p class="source">Estimated on index returns, at today\'s weights, and not the record. Source: '
             'outputs/risk_summary.csv, mandate/simulation_bootstrap.csv</p></div>')  # fmt: skip


def _tail_tiles(page, summary):
    """One-month value at risk and expected shortfall at 95 per cent, historical beside normal, and from month 12
    the months beyond the value at risk set at the month end before."""
    months = int(summary["months_with_value_at_risk"]) if pd.notna(summary.get("months_with_value_at_risk")) else 0
    if months >= risk_module.CALIBRATION_FROM:
        beyond = int(summary["months_beyond_value_at_risk"])
        count = f"{beyond} of {months} months beyond it, against {months * risk_module.TAIL:.1f} expected"
    else:
        count = "Months beyond it counted from October 2027"
    monthly = fmt.pct(summary["estimated_volatility"] / 12**0.5)
    tiles = [("Value at risk, historical", fmt.pct(summary["value_at_risk_historical"]), f"The sixth worst of 120 months. {count}"),
             ("Expected shortfall, historical", fmt.pct(summary["expected_shortfall_historical"]), "The mean loss of those six months"),
             ("Value at risk, normal", fmt.pct(summary["value_at_risk_normal"]), f"1.645 times the monthly volatility of {monthly}"),
             ("Expected shortfall, normal", fmt.pct(summary["expected_shortfall_normal"]), "The normal mean loss beyond that point")]  # fmt: skip
    tile_html = "".join(f'<div class="tile"><p class="name">{_esc(n)}</p><div class="value">{_esc(v)}</div>'
                        f'<div class="change">{_esc(c)}</div></div>' for n, v, c in tiles)  # fmt: skip
    line = (f"Losses over one month at 95 per cent, at the look-through weights of {fmt.day_words(summary['weights_as_of'])}, "
            f"on {_window_text(summary)}. The historical value at risk is the sixth worst of the 120 months and the expected "
            "shortfall the mean of those six. The normal figures, with zero mean, are 1.645 times the monthly volatility and "
            f"the normal tail mean. The window holds 2020 and 2022 and neither 2008 nor 2000 to 2003, which {_ref('stress')} "
            "holds. Not a limit, and never a reason to sell, under rule 8, since the mandate binds on the worst fall over "
            "years. Each month end's value at risk is kept as first written, in outputs/ex_ante_risk.csv, and twelve months "
            "give the count of months beyond it almost no power. It starts to say something at about sixty.")  # fmt: skip
    page.add("risk", f'<div class="wide"><div class="tiles four">{tile_html}</div><p class="tilenote">{_esc(line)}</p>'
             '<p class="source">Estimated on index returns, at today\'s weights, and not the record. Source: '
             'outputs/risk_summary.csv, outputs/ex_ante_risk.csv</p></div>')  # fmt: skip


def _correlation_heatmap(page, components, pairs, summary):
    names = [c for c in components["component"] if c != "Cash"]
    matrix = pairs.pivot(index="component_a", columns="component_b", values="correlation").loc[names, names]
    z = [[fmt.rounded(matrix.loc[a, b], 4) for b in names] for a in names]
    text = [[fmt.loading(matrix.loc[a, b]) for b in names] for a in names]
    trace = {"type": "heatmap", "x": names, "y": names, "z": z, "text": text, "texttemplate": "%{text}", "zmin": -1, "zmax": 1,
             "colorscale": [[0, "@diverging_negative"], [0.5, "@diverging_mid"], [1, "@diverging_positive"]],
             "colorbar": {"title": {"text": "Correlation", "side": "right"}, "thickness": 12, "len": 0.9, "tickvals": [-1, -0.5, 0, 0.5, 1]},
             "xgap": 2, "ygap": 2, "customdata": [[f"{a} and {b}: {t}" for b, t in zip(names, r)] for a, r in zip(names, text)],
             "hovertemplate": "%{customdata}<extra></extra>"}  # fmt: skip
    layout = {"xaxis": {"type": "category", "showline": False, "ticks": "", "tickangle": 0, "showgrid": False,
                        "tickmode": "array", "tickvals": names, "ticktext": [COLUMN_LABEL.get(n, n) for n in names]},
              "yaxis": {"type": "category", "autorange": "reversed", "showline": False, "ticks": "", "showgrid": False},
              "margin": {"t": 8}}  # fmt: skip
    short = [SHORT_COMPONENT.get(n, n) for n in names]
    narrow = {"xaxis": {"tickmode": "array", "tickvals": names, "ticktext": [COLUMN_CODE.get(n, n) for n in names], "tickangle": 0},
              "yaxis": {"tickmode": "array", "tickvals": names, "ticktext": short}}  # fmt: skip
    rows = [[r["component"], fmt.pct(r["weight"]), fmt.pct(r["estimated_volatility"]), r["series"]]
            for _, r in components.iterrows()]  # fmt: skip
    table = _table(["Component", "Weight", "Volatility, a year", "Series"], rows, numeric=("Weight", "Volatility, a year"),
                   rounding=True)
    israel = fmt.pct(summary["israel_share_of_portfolio"])
    note = (f"Monthly returns in euro over {_window_text(summary)}. The equity regions are MSCI's regional indices, net total "
            "return. MSCI publishes no series for Europe and the Middle East together, so that region is priced by MSCI Europe, "
            f"and Israel, {israel} of the portfolio, goes with it. Each maturity group is a zero-coupon euro area government "
            "bond at the group's midpoint, priced from the ECB's curve as the allocation test prices its seven-year bond: "
            "short 1 to 5 years at 3, medium 5 to 10 years at 7.5, and long over 10 years at 20. Cash has no return and no "
            "correlation.")  # fmt: skip
    block = _card("c30", "Correlation of the components' monthly returns", f"Window {_month_name(summary['window_start'])} to {_month_name(summary['window_end'])}",
                  ["outputs/risk_correlation.csv", "outputs/risk_components.csv"], note=note, wide=True, height=420,
                  anchor="lookthrough-risk")  # fmt: skip
    block = block.replace('<p class="note">', table + '<p class="note">', 1)
    page.add("risk", block, {"id": "c30", "traces": [trace], "layout": layout, "layout_narrow": narrow})


def _risk_contributions(page, components, summary):
    order = components.sort_values("risk_contribution", ascending=False, kind="stable")
    order = pd.concat([order[order["component"] != "Cash"], order[order["component"] == "Cash"]])
    names = list(order["component"])
    traces = [{"type": "bar", "orientation": "h", "name": "Weight", "y": names, "x": [fmt.rounded(v * 100, 2) for v in order["weight"]],
               "marker": {"color": "@weight_bar"}, **_hover([f"{n}: weight {fmt.pct(v)}" for n, v in zip(names, order["weight"])])},
              {"type": "bar", "orientation": "h", "name": "Share of the estimated variance", "y": names,
               "x": [fmt.rounded(v * 100, 2) for v in order["risk_contribution"]], "marker": {"color": "@accent"},
               **_hover([f"{n}: {fmt.pct(v)} of the estimated variance" for n, v in zip(names, order["risk_contribution"])])}]  # fmt: skip
    layout = {"barmode": "group", "showlegend": True, "legend": {"traceorder": "normal"}, "bargap": 0.3,
              "yaxis": {"autorange": "reversed", "type": "category", "showline": False, "ticks": ""},
              "xaxis": {"title": {"text": "Per cent, each set summing to 100"}, "zeroline": True},
              "shapes": [_vline(0, "@ink")]}  # fmt: skip
    narrow = {"yaxis": {"tickmode": "array", "tickvals": names, "ticktext": [SHORT_COMPONENT.get(n, n) for n in names]}}
    rows = [[r["component"], fmt.pct(r["weight"]), fmt.pct(r["risk_contribution"])] for _, r in order.iterrows()]
    rows.append(["Sum", fmt.pct(order["weight"].sum()), fmt.pct(order["risk_contribution"].sum())])
    table = _table(["Component", "Weight", "Share of the estimated variance"], rows, numeric=("Weight", "Share of the estimated variance"),
                   rounding=True)
    equity = order[order["sleeve"] == "equity"]
    bonds = order[order["sleeve"] == "bonds"]
    note = (f"Each component's share is its weight times its covariance with the portfolio, over the portfolio's estimated "
            f"variance, on {_window_text(summary)}. The equity regions carry {fmt.pct(equity['risk_contribution'].sum())} of "
            f"the estimated variance against {fmt.pct(equity['weight'].sum())} of the weight, and the maturity groups "
            f"{fmt.pct(bonds['risk_contribution'].sum())} against {fmt.pct(bonds['weight'].sum())}.")  # fmt: skip
    page.add("risk", _card("c31", "Each component's share of the estimated variance, beside its weight",
             f"Look-through weights of {fmt.day_words(summary['weights_as_of'])}", "outputs/risk_components.csv", table=table, note=note,
             wide=True, height=360), {"id": "c31", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip


def _frontier(page, frontiers, summary, components):
    traces = []
    for window, name, role, width in (("earlier", "Frontier of the 120 months before", "@other", 2),
                                      ("current", "Frontier of the window", "@ink2", 2)):  # fmt: skip
        f = frontiers[frontiers["window"] == window]
        traces.append({"type": "scatter", "mode": "lines", "name": name, "x": [fmt.rounded(v * 100, 3) for v in f["estimated_volatility"]],
                       "y": [fmt.rounded(v * 100, 3) for v in f["estimated_return"]], "line": {"color": role, "width": width},
                       **_hover([f"{name}<br>volatility {fmt.pct(v)}, return {fmt.pct(r)}" for v, r in
                                 zip(f["estimated_volatility"], f["estimated_return"])])})  # fmt: skip
    traces.append({"type": "scatter", "mode": "markers", "name": "Minimum-variance portfolio",
                   "x": [fmt.rounded(summary["minimum_variance_volatility"] * 100, 3)],
                   "y": [fmt.rounded(summary["minimum_variance_return"] * 100, 3)],
                   "marker": {"size": 10, "symbol": "circle-open", "color": "@ink2", "line": {"width": 2, "color": "@ink2"}},
                   **_hover([f"Minimum-variance portfolio<br>volatility {fmt.pct(summary['minimum_variance_volatility'])}, "
                             f"return {fmt.pct(summary['minimum_variance_return'])}"])})  # fmt: skip
    traces.append({"type": "scatter", "mode": "markers", "name": "The portfolio, at its look-through weights",
                   "x": [fmt.rounded(summary["estimated_volatility"] * 100, 3)], "y": [fmt.rounded(summary["estimated_return"] * 100, 3)],
                   "marker": {"size": 12, "color": "@accent"},
                   **_hover([f"The portfolio<br>volatility {fmt.pct(summary['estimated_volatility'])}, "
                             f"return {fmt.pct(summary['estimated_return'])}"])})  # fmt: skip
    layout = {"showlegend": True, "legend": {"traceorder": "normal"},
              "xaxis": {"title": {"text": "Estimated volatility, per cent a year"}, "rangemode": "tozero"},
              "yaxis": {"title": {"text": "Estimated return, per cent a year"}}}  # fmt: skip
    current = frontiers[frontiers["window"] == "current"]
    weight_columns = [c for c in current.columns if c.startswith("weight_")]
    labels = [c for c in components["component"] if c != "Cash"]
    rows = [[int(r["point"]) + 1, fmt.pct(r["estimated_return"]), fmt.pct(r["estimated_volatility"])] +
            [fmt.pct(r[c]) for c in weight_columns] for _, r in current.iterrows()]  # fmt: skip
    columns = ["Point", "Return", "Volatility"] + labels
    table = _table(columns, rows, numeric=tuple(columns[1:]), rounding=True)
    note = (f"Estimated on the past returns of {_window_text(summary)}, of which the means are the least reliable input: "
            "long-only portfolios of the components, fully invested, at 25 target returns from the minimum-variance portfolio's "
            "to the highest component mean. The portfolio does not optimise, by its rules, and its point is where its two "
            "cap-weighted ETFs put it. The distance from the curve is how far the cap weights sat from the frontier estimated on this window, "
            f"and the grey curve, the 120 months before it, shows how far the frontier moves between windows. The study "
            f"{STUDY_NAME} finds that sample-based optimisation of this kind does not keep its in-sample advantage out of "
            "sample. The table gives the weights of each point of the window's frontier.")  # fmt: skip
    block = _card("c32", "The efficient frontier of the components, and the portfolio's point",
                  f"The 120 months to {_month_name(summary['earlier_window_end'])}, and to {_month_name(summary['window_end'])}", "outputs/risk_frontier.csv",
                  table=table, note=note, wide=True, height=380)  # fmt: skip
    block = block.replace(f"The study {STUDY_NAME} finds", f'The study <a href="{STUDY_URL}">{STUDY_NAME}</a> finds', 1)
    page.add("risk", block, {"id": "c32", "traces": traces, "layout": layout})


def _stress(page, episodes):
    series = {"the components": "Components", "the allocation test's two series": "Allocation test"}
    rows = [[r["episode"], fmt.pct(r["equity_contribution"], True), fmt.pct(r["bond_contribution"], True),
             fmt.pct(r["total"], True), f"{fmt.month_short(r['from_month_end'])} to {fmt.month_short(r['to_month_end'])}", series.get(r["series"], r["series"])]
            for _, r in episodes.iterrows()]  # fmt: skip
    columns = ["Episode", "Equity", "Bonds", "Total", "Month ends", "Series"]
    table = _table(columns, rows, numeric=("Equity", "Bonds", "Total"), wrap_first=True)
    note = ("Estimated, on index returns, at today's weights, and not the record. Each episode holds today's look-through "
            "weights from the end of its first month to the end of its last, without rebalancing, so the two sleeves' "
            "contributions add up to the total. Month-end values miss falls that reverse within a month. The components' "
            "series start in January 2001 (MSCI) and October 2004 (the ECB curve), so the fall of 2000 to 2003 takes the "
            "allocation test's two series at the sleeve weights.")  # fmt: skip
    page.add("risk", _card("stress", "Today's portfolio in five historical episodes, estimated", "Per cent of the portfolio, by sleeve",
             "outputs/stress.csv", plot=False, kind="table", wide=True, note=note).replace('<p class="note">', table + '<p class="note">', 1))  # fmt: skip


def risk_view(page, out, boot, monthly):
    summary = out.get("risk_summary.csv", pd.DataFrame())
    if not len(summary):
        return
    summary = summary.iloc[0]
    page.add("risk", _group("Risk of the whole portfolio", "lookthrough-risk-section",
             "Estimated on index returns at the look-through weights."))  # fmt: skip
    _risk_tiles(page, summary, boot, out["allocation_now.csv"].iloc[0]["weight_equity"], monthly)
    _tail_tiles(page, summary)
    components = out["risk_components.csv"]
    _correlation_heatmap(page, components, out["risk_correlation.csv"], summary)
    _risk_contributions(page, components, summary)
    _frontier(page, out["risk_frontier.csv"], summary, components)
    _stress(page, out["stress.csv"])


def _cost_of_ownership(page, costs, implementation, monthly, orders, now=None):
    if not len(costs):
        return
    funds = costs[costs["sleeve"] != "portfolio"]
    weighted = costs[costs["sleeve"] == "portfolio"].iloc[0]
    data = implementation.dropna(subset=["implementation_cost_bps"]) if len(implementation) else implementation
    if len(data):
        latest = float(data["implementation_cost_bps"].iloc[-1])
        impl = (f"Beside them, the implementation cost of {_ref('c8')} is {fmt.bps(latest)}, cumulative since "
                f"{fmt.day_words(data['date'].iloc[0])}, positive when the portfolio's value is below reference portfolio A's "
                "and negative when it is above. ")
        against = (orders["price_against_nav"].fillna("").astype(str) if len(orders) and "price_against_nav" in orders
                   else pd.Series(dtype=str))  # fmt: skip
        valued = against[against.isin(["below", "above", "at"])]
        count, below = len(valued), int((valued == "below").sum())
        if round(latest) < 0 and count and below == count:
            which = (f"each of the {NUMBER_WORD.get(count, str(count)).lower()} orders valued so far was" if count > 1
                     else "the one order valued so far was")  # fmt: skip
            impl += (f"It is negative because {which} executed below its day's net asset value ({_ref('c7')}). An order "
                     "fills at a price during the day and the net asset value is set at the close, so the gap can go either way. ")
        pending = _after_record(orders, now)
        if pending:
            impl += f"{pending} "
    else:
        impl = f"Beside them, {_ref('c8')} gives the implementation cost from the first order. "
    line = (f"The two ETFs' ongoing costs, from their key information documents, come to "
            f"{fmt.bps(weighted['ongoing_costs'] * 1e4, False)} a year at the portfolio's weights. Each ETF's ongoing costs "
            f"are its TER plus its transaction costs. {impl}The ongoing costs are taken inside the ETFs' net asset values, "
            f"so {_ref('c8')} does not hold them.")  # fmt: skip
    bp = lambda v: fmt.bps(v * 1e4, False)  # noqa: E731
    rows = [[SHORT_FUND.get(r["isin"], r["fund"]), bp(r["ongoing_costs"]), bp(r["management_fees"]), bp(r["transaction_costs"]),
             fmt.pct(r["weight"]), fmt.day_short(r["document_date"])] for _, r in funds.iterrows()]  # fmt: skip
    # Cash not yet invested carries no ongoing costs. Its row makes the weights add up to the portfolio.
    cash = 1.0 - float(weighted["weight"])
    if cash >= 0.0005:
        rows.append(["Cash", bp(0.0), bp(0.0), bp(0.0), fmt.pct(cash), ""])
    rows.append(["The portfolio", bp(weighted["ongoing_costs"]), bp(weighted["management_fees"]), bp(weighted["transaction_costs"]),
                 fmt.pct(float(weighted["weight"]) + max(cash, 0.0) if cash >= 0.0005 else weighted["weight"]), ""])  # fmt: skip
    columns = ["Fund", "Ongoing costs", "TER", "Transaction", "Weight", "Document of"]
    table = _table(columns, rows, numeric=("Ongoing costs", "TER", "Transaction", "Weight"), wrap_first=True, rounding=True)
    page.add("costs", _card("ownership", "What the portfolio costs a year, in basis points",
             "Ongoing costs of the two ETFs, TER and transaction costs", ["outputs/cost_of_ownership.csv",
             "outputs/implementation_cost.csv"], plot=False, wide=True, note=line, kind="table").replace('<p class="note">', table +
             '<p class="note">', 1))  # fmt: skip


def _attribution(page, attribution, as_of):
    if not len(attribution):
        page.add("factors", _card("attribution", "The difference to the index blend in three parts", _asof(as_of), None,
                 plot=False, wide=True, kind="table", empty="From the October 2027 month end, when twelve months exist, this table splits the "
                 f"difference to the index blend into three parts that sum to it, over the period of {_ref('c20')}: the portfolio "
                 "against reference portfolio A, the drift effect, and the tracking difference of the two ETFs."))  # fmt: skip
        return
    r = attribution.iloc[0]
    rows = [["The portfolio against reference portfolio A", "The portfolio's return minus reference portfolio A's",
             fmt.pct(r["portfolio_against_reference_a"], True)],
            ["Drift effect", "Reference portfolio A's return minus reference portfolio B's", fmt.pct(r["drift_effect"], True)],
            ["Tracking difference, with the day mismatch", "Reference portfolio B's return minus the index blend's",
             fmt.pct(r["tracking_difference"], True)],
            ["The difference to the index blend", "The portfolio's return minus the index blend's", fmt.pct(r["total"], True)]]  # fmt: skip
    table = _table(["Part", "Measured as", "Return, percentage of the start"], rows, numeric=("Return, percentage of the start",))
    page.add("factors", _card("attribution", "The difference to the index blend in three parts",
             f"{_span(r['period_start'], r['period_end'])}, {int(r['months'])} months", "outputs/attribution.csv",
             plot=False, wide=True, kind="table", note="Differences of the returns over the period, so the three parts sum to the total. The "
             f"first part is negative when the portfolio's value is below reference portfolio A's and positive when it is above, "
             f"the opposite sign to the implementation cost of {_ref('c8')}.").replace('<p class="note">', table + '<p class="note">', 1))  # fmt: skip


# Factor exposures ----------------------------------------------------------------------------------


def factor_view(page, loadings, rolling, as_of):
    weekly = loadings[loadings["method"] == "weekly"].set_index("factor").loc[list(config.FACTORS)]
    daily = loadings[loadings["method"] != "weekly"].set_index("factor").loc[list(config.FACTORS)]
    names = [config.FACTOR_NAME[f] for f in config.FACTORS]
    traces = []
    for f, name in zip(config.FACTORS, names):
        r = weekly.loc[f]
        traces.append({"type": "scatter", "mode": "markers", "name": name, "y": [name], "x": [fmt.rounded(r["loading"], 2)],
                       "marker": {"size": 10, "color": FACTOR_ROLE[f]},
                       "error_x": {"type": "data", "symmetric": False,
                                   "array": [fmt.rounded(r["upper"], 2) - fmt.rounded(r["loading"], 2)],
                                   "arrayminus": [fmt.rounded(r["loading"], 2) - fmt.rounded(r["lower"], 2)],
                                   "color": FACTOR_ROLE[f], "thickness": 2, "width": 0},
                       **_hover([f"{name}: {fmt.loading(r['loading'])}<br>two standard errors: {fmt.loading(r['lower'])} "
                                 f"to {fmt.loading(r['upper'])}"])})  # fmt: skip
    first = weekly.iloc[0]
    layout = {"yaxis": {"autorange": "reversed", "type": "category", "showline": False},
              "xaxis": {"title": {"text": "Loading, with two standard errors"}, "zeroline": False},
              "shapes": [_vline(0, "@ink")]}  # fmt: skip
    rows = []
    for f, name in zip(config.FACTORS, names):
        w, d = weekly.loc[f], daily.loc[f]
        rows.append([name, fmt.loading(w["loading"]), fmt.loading(w["standard_error"]), fmt.loading(d["loading"]),
                     fmt.loading(d["standard_error"])])
    rows.append(["Intercept, per period", fmt.loading(first["intercept"] * 100) + "%",
                 "", fmt.loading(daily.iloc[0]["intercept"] * 100) + "%", ""])  # fmt: skip
    rows.append(["R squared", fmt.loading(first["r_squared"]), "", fmt.loading(daily.iloc[0]["r_squared"]), ""])
    rows.append(["Observations", fmt.count(first["observations"]), "", fmt.count(daily.iloc[0]["observations"]), ""])
    rows.append(["Newey-West lag", fmt.count(first["newey_west_lag"]), "", fmt.count(daily.iloc[0]["newey_west_lag"]), ""])
    table = _table(["Factor", "Weekly loading", "Weekly s.e.", "Daily, with the previous day", "Daily s.e."], rows,
                   numeric=("Weekly loading", "Weekly s.e.", "Daily, with the previous day", "Daily s.e."))  # fmt: skip
    asof = (f"Weekly returns, Wednesday to Wednesday to avoid week-start and week-end effects, "
            f"{_span(first['window_start'], first['window_end'])}, {int(first['observations'])} weeks")  # fmt: skip
    note = ("The regression uses the ETF's net asset value in US dollars and Kenneth French's developed-market factors, "
            "also in US dollars, so no exchange rate enters it. Standard errors are Newey-West. The table adds a daily "
            "estimate as a check, with each factor's return of the same day and of the previous day (Dimson's "
            "correction): the fund's valuation point and the timing of French's daily returns may not coincide day by "
            "day, which would bias loadings estimated on same-day returns. The bond sleeve is not regressed on equity "
            "factors.")  # fmt: skip
    page.add("factors", _card("c18", "Factor loadings of the equity ETF", asof, "outputs/factor_loadings.csv",
             table=table, note=note, height=300, wide=True), {"id": "c18", "traces": traces, "layout": layout})  # fmt: skip

    blocks = []
    rows = []
    others = rolling[rolling["factor"] != "Mkt-RF"]["loading"]
    pad = 0.05 * (others.max() - others.min()) if len(others) else 0.0
    shared = [fmt.rounded(min(others.min(), 0) - pad, 2), fmt.rounded(max(others.max(), 0) + pad, 2)] if len(others) else None
    for f, name in zip(config.FACTORS, names):
        data = rolling[rolling["factor"] == f]
        cid = f"c19_{f.replace('-', '')}"
        blocks.append(f'<div><p class="label">{_esc(name)}</p><div class="plot" id="{cid}" style="height:170px" '
                      f'role="img" aria-label="Rolling {_esc(name)} loading"></div></div>')  # fmt: skip
        traces = [{"type": "scatter", "mode": "lines", "name": name, "x": list(data["window_end"]),
                   "y": [fmt.rounded(v, 2) for v in data["loading"]], "line": {"color": FACTOR_ROLE[f], "width": 2},
                   **_hover([f"{fmt.month_words(d)}<br>{name}: {fmt.loading(v)}" for d, v in
                             zip(data["window_end"], data["loading"])])}]  # fmt: skip
        yaxis = {"zeroline": False} if f == "Mkt-RF" else {"zeroline": False, "range": shared}
        layout = {"xaxis": {"type": "date", "tickformat": "%Y", "hoverformat": "%B %Y"}, "yaxis": yaxis,
                  "shapes": [_hline(0, "@ink")] if f != "Mkt-RF" else [], "margin": {"t": 4, "b": 4}}  # fmt: skip
        page.charts.append({"id": cid, "view": "factors", "traces": traces, "layout": layout})
    wide = rolling.pivot(index="window_end", columns="factor", values="loading")[list(config.FACTORS)]
    rows = [[fmt.month_short(d)] + [fmt.loading(v) for v in r] for d, r in wide.iterrows()]
    table = _table(["Window end"] + names, rows, numeric=tuple(names))
    block = _card("c19", "Rolling loadings: 36-month windows of weekly returns, stepped at each month end",
                  f"Windows ending {fmt.month_words(rolling['window_end'].min())} to {fmt.month_words(rolling['window_end'].max())}. "
                  "The five panels after the market share one scale",
                  "outputs/factor_rolling.csv", plot=False, table=table, wide=True, kind="figure")
    block = block.replace('<p class="source">', f'<div class="multiples">{"".join(blocks)}</div><p class="source">', 1)
    page.add("factors", block)
    page.add("factors", _card("c20", "Where the difference to the index blend came from",
             _asof(as_of),
             None, plot=False, wide=True, kind="figure", empty="From the October 2027 month end, when twelve months exist, this chart splits the "
             "portfolio's monthly return against the index blend into exposures times factor returns and a residual."))  # fmt: skip


# Method --------------------------------------------------------------------------------------------


def _allocation_curve(page, allocation: pd.DataFrame, us: pd.DataFrame = None):
    """The allocation test as the curve of the splits: growth per year against the worst fall, one point per split."""
    splits = list(allocation["split"])
    x = [fmt.rounded(v * 100, 2) for v in allocation["worst_fall"]]
    y = [fmt.rounded(v * 100, 2) for v in allocation["growth_per_year"]]
    held = [c == "yes" for c in allocation["chosen"]]
    hover = [f"{s}: worst fall {fmt.pct(f)}, growth per year {fmt.pct(g)}"
             for s, f, g in zip(splits, allocation["worst_fall"], allocation["growth_per_year"])]  # fmt: skip
    traces = [{"type": "scatter", "mode": "lines+markers", "name": "Splits", "x": x, "y": y, "showlegend": False,
               "line": {"color": "@other", "width": 2}, "marker": {"size": 8, "color": "@ink2"}, **_hover(hover)},
              {"type": "scatter", "mode": "markers", "name": "70/30, held", "showlegend": False,
               "x": [v for v, h in zip(x, held) if h], "y": [v for v, h in zip(y, held) if h],
               "marker": {"size": 13, "color": "@accent"}, **_hover([t for t, h in zip(hover, held) if h])}]  # fmt: skip
    us = us if us is not None and len(us) else None
    if us is not None:
        # The same test on the US stock market in euro: the second curve of the ladder, 70/30 marked on it as well.
        ux = [fmt.rounded(v * 100, 2) for v in us["worst_fall"]]
        uy = [fmt.rounded(v * 100, 2) for v in us["growth_per_year"]]
        uhover = [f"US series, {s}: worst fall {fmt.pct(f)}, growth per year {fmt.pct(g)}"
                  for s, f, g in zip(us["split"], us["worst_fall"], us["growth_per_year"])]  # fmt: skip
        at = list(us["split"]).index("70/30") if "70/30" in list(us["split"]) else None
        traces.append({"type": "scatter", "mode": "lines+markers", "name": "US series", "x": ux, "y": uy,
                       "showlegend": False, "line": {"color": "@us_series", "width": 2},
                       "marker": {"size": 7, "color": "@us_series"}, **_hover(uhover)})  # fmt: skip
        if at is not None:
            traces.append({"type": "scatter", "mode": "markers", "name": "70/30 on the US series", "showlegend": False,
                           "x": [ux[at]], "y": [uy[at]], "marker": {"size": 12, "color": "@us_series",
                           "line": {"color": "@surface", "width": 2}}, **_hover([uhover[at]])})  # fmt: skip
    annotations = [_label(35, 1, "35%", yref="paper", anchor="right", role="@status_breach", xshift=-4, yshift=8),
                   _label(40, 1, "40%", yref="paper", anchor="left", role="@status_breach", xshift=4, yshift=8)]  # fmt: skip
    if us is not None:
        last = len(ux) - 1
        annotations += [_label(x[-1], y[-1], "Global", anchor="left", role="@ink2", xshift=8, yshift=-10),
                        _label(ux[last], uy[last], "US", anchor="left", role="@us_series", xshift=8, yshift=-10)]  # fmt: skip
    for split, anchor, shift in (("40/60", "left", 10), ("70/30", "right", -10), ("100/0", "right", -10)):
        if split in splits:
            i = splits.index(split)
            role = "@accent" if held[i] else "@ink2"
            annotations.append(_label(x[i], y[i], split, anchor=anchor, role=role, xshift=shift, yshift=8 if split == "70/30" else 0))
    layout = {"xaxis": {"title": {"text": "Worst fall, per cent"}},
              "yaxis": {"title": {"text": "Growth per year, per cent"}},
              "shapes": [_vline(35, "@status_breach"), _vline(40, "@status_breach")], "annotations": annotations,
              "margin": {"t": 24}}  # fmt: skip
    rows = [[r["split"], fmt.pct(r["worst_fall"]), fmt.pct(r["growth_per_year"]), r["within_limit"], r["chosen"]]
            for _, r in allocation.iterrows()]  # fmt: skip
    headers = ["Split", "Worst fall", "Growth per year", "Within 35%", "Held"]
    numeric = ("Worst fall", "Growth per year")
    title = "The allocation test: growth per year against the worst fall of each split"
    source = "mandate/allocation_check_results.csv"
    note = ("The split held is the largest equity target weight whose worst fall stayed within 35 per cent. With "
            "two assets every split lies on this curve, and the limit picks the point.")  # fmt: skip
    if us is not None:
        by_split = us.set_index("split")
        rows = [r + [fmt.pct(by_split.loc[r[0], "worst_fall"]), fmt.pct(by_split.loc[r[0], "growth_per_year"])] for r in rows]
        headers += ["Worst fall, US series", "Growth per year, US series"]
        numeric += ("Worst fall, US series", "Growth per year, US series")
        title += ", on the global and the US equity series"
        source = (source, "mandate/allocation_check_us_results.csv")
        note += (" The second curve, in teal, repeats the test with the US stock market in euro in place of the global "
                 "equity series, with the same bonds, band rule, splits and months.")  # fmt: skip
    table = _table(headers, rows, numeric=numeric)
    page.add("method", _card("c21", title,
             "Monthly euro returns, February 1999 to December 2025, rebalanced by the band, splits from 40/60 to 100/0",
             source, table=table, wide=True, height=360, anchor="method-allocation", note=note),
             {"id": "c21", "traces": traces, "layout": layout})  # fmt: skip


def _correlation(page, test: pd.DataFrame, etfs: pd.DataFrame):
    """The rolling correlation of the two sleeves' monthly returns: the allocation test's index series, and the
    two ETFs' net asset values."""
    traces, rows = [], {}
    for frame, name, role in ((test, "The allocation test's index returns", "@test_series"),
                              (etfs, "The two ETFs' net asset values", "@accent")):  # fmt: skip
        if not len(frame):
            continue
        traces.append({"type": "scatter", "mode": "lines", "name": name, "x": [_month_end(m) for m in frame["window_end"]],
                       "y": [fmt.rounded(v, 4) for v in frame["correlation"]], "line": {"color": role, "width": 2},
                       **_hover([f"Window to {_month_name(m)}<br>{name}: {fmt.loading(v)}" for m, v in zip(frame["window_end"], frame["correlation"])])})  # fmt: skip
        for m, v in zip(frame["window_end"], frame["correlation"]):
            rows.setdefault(m, ["", ""])[0 if frame is test else 1] = fmt.loading(v)
    layout = {"showlegend": True, "yaxis": {"title": {"text": "Correlation"}, "range": [-1, 1], "dtick": 0.5},
              "xaxis": {"type": "date", "tickformat": "%Y", "hoverformat": "%B %Y"}, "shapes": [_hline(0, "@ink")]}  # fmt: skip
    year_ends = [m for m in sorted(rows) if m.endswith("-12")] + ([max(rows)] if rows and not max(rows).endswith("-12") else [])
    table = _table(["Window to", "Allocation test", "The two ETFs"], [[fmt.month_short(m)] + rows[m] for m in year_ends],
                   numeric=("Allocation test", "The two ETFs"))  # fmt: skip
    spans = [f"{_month_name(f['window_end'].iloc[0])} to {_month_name(f['window_end'].iloc[-1])} on {what}"
             for f, what in ((test, "the test's series"), (etfs, "the ETFs")) if len(f)]  # fmt: skip
    note = ("Monthly returns in euro over rolling windows of 36 months: the allocation test's index series from February "
            "1999, and the two ETFs from March 2019, the first full month of the bond share class, which started on 19 "
            "February 2019. The test's worst fall and the bootstrap's bands rest on this correlation, which the block "
            "resampling keeps within each block. The years in which it turned positive are the ones in which bonds did "
            "not offset the falls of equity. The table gives the windows to each December and to the last month.")  # fmt: skip
    page.add("method", _card("c29", "Rolling 36-month correlation of the two sleeves' monthly returns",
             "Monthly. Windows ending " + ", and ".join(spans), ["mandate/sleeve_correlation.csv", "outputs/etf_correlation.csv"],
             table=table, note=note, wide=True, height=300, anchor="method-correlation"),
             {"id": "c29", "traces": traces, "layout": layout})  # fmt: skip


def _month_name(month: str) -> str:
    return pd.Period(month, "M").strftime("%B %Y")


def _short_date(value) -> str:
    """A date of a table cell as 6 Nov 2026, and a month as Oct 2026."""
    text = str(value)
    return fmt.month_short(text) if re.fullmatch(r"\d{4}-\d{2}", text) else fmt.day_short(text)


def _controls(page, controls: pd.DataFrame):
    rows = [[r["control"], r["frequency"], r["evidence"]] for _, r in controls.iterrows()]
    page.add("method", _card("controls", "Controls", "Each control with its frequency and its evidence", "method/controls.csv",
             plot=False, wide=True, anchor="method-controls", table=None, kind="table",
             note=None).replace('<p class="source">', _table(["Control", "Frequency", "Evidence"], rows, prose=True) + '<p class="source">', 1))  # fmt: skip


def method(page, allocation: pd.DataFrame, selection: pd.DataFrame, rules_html: str, sources: pd.DataFrame,
           bootstrap: pd.DataFrame, correlation: tuple = (pd.DataFrame(), pd.DataFrame()),
           controls: pd.DataFrame = pd.DataFrame(), not_done: dict = None):  # fmt: skip
    _allocation_curve(page, allocation, (not_done or {}).get("us_test"))
    if len(bootstrap):
        _bootstrap(page, bootstrap)
    if any(len(c) for c in correlation):
        _correlation(page, *correlation)
    if not_done:
        history = {k: not_done.pop(k) for k in ("history", "history_windows") if k in not_done}
        _not_done(page, allocation, **not_done)
        if history:
            history_pane(page, history["history"], history["history_windows"])

    blocks = []
    for sleeve, title in (("equity", "Equity ETFs"), ("bonds", "Bond ETFs")):
        data = selection[selection["sleeve"] == sleeve].sort_values(["rank", "year"])
        funds = data.drop_duplicates("isin")
        labels = [f"{int(r)}. {SHORT_FUND.get(i, n)}" for r, i, n in zip(funds["rank"], funds["isin"], funds["fund"])]
        traces = []
        for (_, f), label in zip(funds.iterrows(), labels):
            rows_f = data[data["isin"] == f["isin"]].dropna(subset=["tracking_difference_points"])
            role = "@accent" if f["held"] == "yes" else "@other"
            hollow = "" if f["offered_on_the_account"] == "yes" else "-open"
            traces.append({"type": "scatter", "mode": "markers", "name": label, "y": [label] * len(rows_f),
                           "x": [fmt.rounded(v, 2) for v in rows_f["tracking_difference_points"]], "showlegend": False,
                           "marker": {"size": 9, "color": role, "line": {"width": 2, "color": role},
                                      "symbol": [YEAR_SYMBOL[int(y)] + hollow for y in rows_f["year"]]},
                           **_hover([f"{label}, {y}: {v:+.2f} points".replace("-", fmt.MINUS) for y, v in
                                     zip(rows_f["year"], rows_f["tracking_difference_points"])])})  # fmt: skip
            if pd.notna(f["average_points"]):
                traces.append({"type": "scatter", "mode": "markers", "name": f"{label}, average", "y": [label],
                               "x": [fmt.rounded(f["average_points"], 3)], "showlegend": False,
                               "marker": {"size": 16, "symbol": "line-ns", "color": role, "line": {"width": 3, "color": role}},
                               **_hover([f"{label}: average {f['average_points']:+.3f} points".replace("-", fmt.MINUS)])})  # fmt: skip
        for year, symbol in YEAR_SYMBOL.items():
            traces.append({"type": "scatter", "mode": "markers", "name": str(year), "x": [None], "y": [None],
                           "marker": {"size": 9, "symbol": symbol, "color": "@ink2"}, "hoverinfo": "skip"})  # fmt: skip
        traces.append({"type": "scatter", "mode": "markers", "name": "Three-year average", "x": [None], "y": [None],
                       "marker": {"size": 16, "symbol": "line-ns", "color": "@ink2", "line": {"width": 3, "color": "@ink2"}},
                       "hoverinfo": "skip"})  # fmt: skip
        cid = f"c22_{sleeve}"
        shown = int(data.groupby("isin")["tracking_difference_points"].count().gt(0).sum())
        page.charts.append({"id": cid, "view": "method", "traces": traces,
                            "layout": {"yaxis": {"autorange": "reversed", "type": "category", "showline": False},
                                       "xaxis": {"title": {"text": "Tracking difference, percentage points"}},
                                       "showlegend": True, "shapes": [_vline(0, "@ink")], "margin": {"l": 8}},
                            "layout_narrow": {"xaxis": {"title": {"text": "Percentage points"}}}})  # fmt: skip
        blocks.append(f'<p class="label">{title}</p><div class="plot" id="{cid}" style="height:{88 + 42 * shown}px" '
                      f'role="img" aria-label="Tracking difference of the {title.lower()}"></div>')  # fmt: skip
    rows = [[int(r["rank"]), SHORT_FUND.get(r["isin"], r["fund"]), r["isin"], r["year"],
             "n/a" if pd.isna(r["tracking_difference_points"]) else f"{r['tracking_difference_points']:+.2f}".replace("-", fmt.MINUS),
             "n/a" if pd.isna(r["average_points"]) else f"{r['average_points']:+.3f}".replace("-", fmt.MINUS),
             r["offered_on_the_account"], r["held"], fmt.day_short(r["factsheet_date"])] for _, r in selection.iterrows()]  # fmt: skip
    table = _table(["Rank", "Fund", "ISIN", "Year", "Tracking difference", "Average", "Offered", "Held", "Factsheet"], rows,
                   numeric=("Tracking difference", "Average"))  # fmt: skip
    block = _card("c22", "The ETF selection: tracking difference by fund and year", "Calendar years 2023 to 2025, "
                  "fund return minus index return, from the issuers' factsheets", "method/selection_tracking_difference.csv",
                  plot=False, table=table, wide=True, anchor="method-selection", kind="figure",
                  note="Tracking difference is the fund's calendar-year return minus "
                  "the return of its index, so a higher figure means a smaller shortfall. Each mark is one year, with the "
                  "shape given in the legend, and the bar is the three-year average. The funds are numbered in the rank order fixed before they were "
                  "compared: equity ETFs by Irish domicile, then the highest average tracking difference, then the lowest "
                  "TER, and bond ETFs by the highest average tracking difference, then the lowest TER. The held funds, "
                  "in the primary ink, are the first in rank order that the account offers. Hollow marks are funds the "
                  "account does not offer.")  # fmt: skip
    block = block.replace('<p class="note">', "".join(blocks) + '<p class="note">', 1)
    page.add("method", block)

    rows = [[r["source"], _short_date(r["last_date_covered"]), _short_date(r["downloaded"]) if isinstance(r["downloaded"], str) else ""]
            for _, r in sources.iterrows()]  # fmt: skip
    page.add("method", _card("sources", "Data sources", "", "outputs/sources.csv", plot=False, wide=True, anchor="method-sources", kind="table",
             table=_table(["Source", "Last date covered", "Downloaded"], rows),
             note="Every source is downloaded at build time, cached locally and not redistributed. Only the figures "
             "computed from them are published."))  # fmt: skip
    if len(controls):
        _controls(page, controls)
    page.add("method", f'<article class="card wide rules" id="method-rules"><h3>The rules</h3><p class="asof">Rendered from '
             f'rules/RULES.md at build time, with the amendments table</p>{rules_html}</article>')
    page.add("method", _other_projects())


# What the portfolio does not do ------------------------------------------------------------------------

ADDED_WITH = "method/selection_sp500.csv"  # the section came with this file, so the file's first commit dates it
TEST_PERIOD = re.compile(r"from (\d{4}-\d{2}) to (\d{4}-\d{2}), (\d+) months")
# Every note of the dashboard's Notes list, keyed. The build numbers them in order of first mention on the page.
CITATIONS = {
    "doeswijk_2014": ("Doeswijk, R., Lam, T. and Swinkels, L. (2014). The global multi-asset market portfolio, "
                      "1959\u20132012. Financial Analysts Journal 70(2), 26 to 41.", "https://doi.org/10.2469/faj.v70.n2.1"),
    "doeswijk_2024": ("Doeswijk, R., Lam, T. and Swinkels, L. (2024). Data update: the global multi-asset market "
                      "portfolio, 1959\u20132012, version 6. Licence CC BY 4.0.", "https://doi.org/10.25397/eur.9371741"),
}  # fmt: skip
NOTES = (
    ("DeMiguel, V., Garlappi, L. and Uppal, R. (2009). Optimal versus naive diversification: how inefficient is the "
     "1/N portfolio strategy? Review of Financial Studies 22(5), 1915 to 1953.", "https://doi.org/10.1093/rfs/hhm075"),
    ("Optimal versus naive diversification, the replication and the index-tracking study, with its dashboard, note "
     "and code.", STUDY_URL, "Optimal versus naive diversification"),
    ("Kenneth French's data library, the US market return and the developed markets outside the United States.",
     "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html", "Kenneth French's data library"),
    ("Black, F. and Litterman, R. (1992). Global portfolio optimization. Financial Analysts Journal 48(5), 28 to 43.",
     "https://doi.org/10.2469/faj.v48.n5.28"),
    ("Grinold, R. C. (1989). The fundamental law of active management. Journal of Portfolio Management 15(3), 30 to "
     "37.", "https://doi.org/10.3905/jpm.1989.409211"),
    ("The agenda of the review, mandate/REVIEW_2027.md in the repository.",
     config.REPOSITORY_URL + "/blob/main/mandate/REVIEW_2027.md", "mandate/REVIEW_2027.md"),
)
# The section on what the portfolio does not do cites these, as {n1} to {n6} in its text.
ESSAY_NOTES = ("demiguel_2009", "naive_diversification_study", "french_library", "black_litterman_1992",
               "grinold_1989", "review_2027")
CITATIONS.update(zip(ESSAY_NOTES, NOTES))
# The wording of the cards on the site's projects page. The README's section Other projects carries the same.
OTHER_PROJECTS = (
    ("Optimal versus naive diversification.",
     "Under an index-tracking mandate on French's 49 industries, five covariance estimators understate their own "
     "tracking error, by 22 to 61 per cent. The replication of DeMiguel, Garlappi and Uppal (2009) reproduces 29 of "
     "the 30 Sharpe ratios that carry a band.",
     (("Page", STUDY_URL), ("dashboard", SITE_URL + "optimal-vs-naive-diversification/dashboard/B-P_dashboard.html"),
      ("code", "https://github.com/ochofer/optimal-vs-naive-diversification"))),
    ("Climate risk as an equity signal.",
     "An ownership graph linking 328 listed companies to the 5,115 tracked assets they own. Of 19 apparent "
     "ownership changes checked by hand, 12 had no transaction behind them.",
     (("Page", PROJECTS_URL + "climate-risk-equity-signal/"),
      ("note", "https://github.com/ochofer/paper1-hazard-exposure-data/releases/download/note-v1.2/"
               "what-a-vintage-difference-measures.pdf"),
      ("code", "https://github.com/ochofer/paper1-hazard-exposure-data"))),
    ("Volatility-managed portfolios: a replication.",
     "A replication of Moreira and Muir's volatility-managed portfolios and of the real-time critique on Ken French's "
     "factors, then the months after the paper's sample. In build: the data and the signal are in place, and nothing "
     "in it is a result yet.",
     (("Page", PROJECTS_URL + "volatility-managed-portfolios/"),
      ("code", "https://github.com/ochofer/volatility-managed-portfolios"))),
)


def _first_commit_day(path: str, fallback) -> pd.Timestamp:
    """The day of a file's first commit, read from git, or the fallback while the file is not yet committed or
    the tree is not a clone."""
    import subprocess

    try:
        found = subprocess.run(["git", "--no-optional-locks", "log", "--diff-filter=A", "--format=%cs", "--", path],
                               cwd=config.ROOT, capture_output=True, text=True, timeout=30).stdout.split()
    except (OSError, subprocess.SubprocessError):
        found = []
    return pd.Timestamp(found[-1] if found else fallback)


def _test_period(path: Path = None) -> tuple:
    """The allocation test's first and last month and its number of months, from the results file it writes."""
    text = (path or config.ROOT / "mandate" / "allocation_check_results.md").read_text(encoding="utf-8")
    first, last, months = TEST_PERIOD.search(text).groups()
    return first, last, int(months)


def _fn(n: int) -> str:
    """A footnote mark that links to its entry in the notes."""
    return f'<sup class="fn"><a href="#note-{n}" id="note-ref-{n}">{n}</a></sup>'


def _signed(x) -> str:
    """A difference of two indices, one decimal, with its sign."""
    value = round(float(x), 1) + 0.0
    return (f"{value:+.1f}" if value else "0.0").replace("-", fmt.MINUS)


def _us_test(allocation: pd.DataFrame, us: pd.DataFrame, period: tuple, added) -> tuple:
    """The worst fall of each split under the band rule, on the global equity series of the allocation test and
    on the US stock market, as paired bars."""
    splits = list(allocation["split"])
    us = us.set_index("split").reindex(splits).reset_index()
    held = [c == "yes" for c in allocation["chosen"]]
    traces = []
    for frame, name, colour, label in (
            (allocation, "Global equity series", ["@accent" if h else "@other" for h in held], "global series"),
            (us, "US stock market", "@us_series", "US stock market")):  # fmt: skip
        traces.append({"type": "bar", "orientation": "h", "name": name, "y": splits,
                       "x": [fmt.rounded(v * 100, 2) for v in frame["worst_fall"]], "marker": {"color": colour},
                       **_hover([f"{s}, {label}: worst fall {fmt.pct(v)}" for s, v in zip(splits, frame["worst_fall"])])})  # fmt: skip
    annotations = [_label(35, 1, "35%", yref="paper", anchor="right", role="@status_breach", xshift=-4, yshift=8),
                   _label(40, 1, "40%", yref="paper", anchor="left", role="@status_breach", xshift=4, yshift=8)]  # fmt: skip
    layout = {"barmode": "group", "bargap": 0.28, "bargroupgap": 0.06, "showlegend": True,
              "legend": {"orientation": "h", "x": 0, "y": -0.1, "yanchor": "top", "traceorder": "normal"},
              "yaxis": {"type": "category", "categoryorder": "array", "categoryarray": splits, "autorange": "reversed",
                        "title": {"text": "Split, equity/bonds"}, "showgrid": False},
              "xaxis": {"title": {"text": "Worst fall, per cent"}, "rangemode": "tozero"},
              "shapes": [_vline(35, "@status_breach"), _vline(40, "@status_breach")], "annotations": annotations,
              "margin": {"t": 24}}  # fmt: skip
    rows = [[s, fmt.pct(g["worst_fall"]), fmt.pct(u["worst_fall"]), fmt.pct(g["growth_per_year"]),
             fmt.pct(u["growth_per_year"]), g["within_limit"], u["within_limit"]]
            for s, (_, g), (_, u) in zip(splits, allocation.iterrows(), us.iterrows())]  # fmt: skip
    columns = ["Split", "Worst fall, global", "Worst fall, US", "Growth per year, global", "Growth per year, US",
               "Within 35%, global", "Within 35%, US"]  # fmt: skip
    table = _table(columns, rows, numeric=tuple(columns[1:5]))
    g70, u70 = allocation.set_index("split").loc["70/30"], us.set_index("split").loc["70/30"]
    first, last, _ = period
    note = ("The allocation test run again with the US stock market in euro in place of the global equity series, "
            "with the same bonds, the same band rule, the same splits and the same months. At 70/30 the global "
            f"series' worst fall runs from {_month_name(g70['peak'])} to {_month_name(g70['low'])}, and the US "
            f"series' from {_month_name(u70['peak'])} to {_month_name(u70['low'])}. The US series was added in "
            f"{pd.Timestamp(added).strftime('%B %Y')}, after the first cycle day, in answer to a question readers ask, "
            "and the split was set on the global series alone. The global series' 70/30 bar, in the primary ink, is "
            "the split held.")  # fmt: skip
    asof = (f"Monthly euro returns, {_month_name(first)} to {_month_name(last)}, rebalanced by the band, splits from "
            "40/60 to 100/0")  # fmt: skip
    card = _card("c33", "The allocation test on the US stock market: the worst fall of each split beside the global series",
                 asof, ["mandate/allocation_check_results.csv", "mandate/allocation_check_us_results.csv"],
                 table=table, note=note, height=520,
                 anchor="method-united-states")  # fmt: skip
    return card, {"id": "c33", "view": "method", "traces": traces, "layout": layout}


def _alternative(daily: pd.DataFrame, fund: str) -> tuple:
    """The growth of 100 of reference portfolio A and of the S&P 500 alternative from the first purchase."""
    series = ((COMPARATOR_NAME["reference_a"][0], "growth_reference_a", "@reference_a"),
              ("S&P 500 alternative", "growth_sp500_alternative", "@sp500_alternative"))  # fmt: skip
    columns = ["date"] + [c for _, c, _ in series]
    data = daily[columns].dropna() if set(columns) <= set(daily.columns) else pd.DataFrame(columns=columns)
    traces = [{"type": "scatter", "mode": "lines+markers" if len(data) < 3 else "lines", "name": name,
               "x": list(data["date"]), "y": [fmt.rounded(v, 1) for v in data[column]],
               "line": {"color": role, "width": 2}, "marker": {"size": 8, "color": role},
               **_hover([f"{fmt.day_words(d)}<br>{name}: {fmt.index(v)}" for d, v in zip(data["date"], data[column])])}
              for name, column, role in series]  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.index(r["growth_reference_a"]), fmt.index(r["growth_sp500_alternative"]),
             _signed(r["growth_sp500_alternative"] - r["growth_reference_a"])] for i, (_, r) in enumerate(data.iterrows())]  # fmt: skip
    headers = ["Date", "Reference A", "S&P 500 alternative", "Alternative minus reference A, index points"]
    table = _table(headers, rows, numeric=tuple(headers[1:]))
    caption = ("Two rule sets on the same contributions from the first purchase, both without costs. The S&P 500 "
               f"alternative is {fund}, at its net asset value in euro. Over the record's months the gap says nothing "
               "about either rule set.")  # fmt: skip
    note = ("The portfolio's own line is not on the chart. Reference A stands for it, and the difference between the "
            "portfolio and reference A is the implementation cost, shown under Costs in the Performance view.")  # fmt: skip
    empty = None if len(data) >= 2 else "The S&P 500 alternative is drawn from the second valuation day."
    asof = _asof(data["date"].iloc[-1], "100 is the starting amount before the first order") if len(data) else ""
    wide, narrow = _date_axes(data["date"])
    layout = {"showlegend": True, "legend": {"y": 1.02}, "yaxis": {"title": {"text": "Growth of 100"}}, **wide,
              "hovermode": "closest"}  # fmt: skip
    card = _card("c34", "Growth of 100: reference portfolio A and the S&P 500 alternative", asof,
                 "outputs/portfolio_daily.csv", table=None if empty else table,
                 note=(caption, note), height=320, empty=empty, anchor="method-alternative")  # fmt: skip
    chart = None if empty else {"id": "c34", "view": "method", "traces": traces, "layout": layout,
                                "layout_narrow": narrow}  # fmt: skip
    return card, chart


def _per_cent(x: float) -> str:
    """A return in words in a sentence, one decimal: minus 3.7 per cent, 29.6 per cent."""
    value = round(float(x) * 100, 1) + 0.0
    return f"minus {abs(value):.1f} per cent" if value < 0 else f"{value:.1f} per cent"


def _not_done(page, allocation: pd.DataFrame, us_test: pd.DataFrame, daily: pd.DataFrame, fund: str, period: tuple,
              added, periods: pd.DataFrame = None) -> None:  # fmt: skip
    """What the portfolio does not do, and why: a card of text across the Method view, with the US run of the
    allocation test and the S&P 500 alternative inside it. Every value in the text is read from a committed file."""
    first, last, months = period
    if periods is None:
        periods = _read("allocation_check_us_periods.csv", config.ROOT / "mandate")
    cumulative = periods.set_index(["series", "first_month"])["cumulative_return_usd"]
    test = allocation.set_index("split")
    error = test.loc["100/0", "volatility"] / (months / 12) ** 0.5 * 100
    gap = (test.loc["100/0", "growth_per_year"] - test.loc["40/60", "growth_per_year"]) * 100
    within = us_test[us_test["within_limit"] == "yes"]
    u70 = us_test.set_index("split").loc["70/30"]
    costs = '<a href="#costs">Costs</a> in the Performance view'
    fields = {
        "test": _ref("c21"), "frontier": _ref("c32"), "growth": _ref("c3"), "us_test": _ref("c33"),
        "alternative": _ref("c34"), "costs": costs, "years": f"{months / 12:.0f}", "error": f"{error:.1f}",
        "gap": f"{gap:.1f}", "us_split": _esc(within.loc[within["equity_weight"].idxmax(), "split"]),
        "us_fall": f"{u70['worst_fall'] * 100:.1f}", "us_peak": _month_name(u70["peak"]),
        "us_low": _month_name(u70["low"]), "fund": _esc(fund), **{f"n{i}": _note(key) for i, key in enumerate(ESSAY_NOTES, start=1)},
        "us_after": _per_cent(cumulative[("US stock market", "2010-01")]),
        "rest_after": _per_cent(cumulative[("Developed markets outside the United States", "2010-01")]),
        "us_decade": _per_cent(cumulative[("US stock market", "2000-01")]),
        "rest_decade": _per_cent(cumulative[("Developed markets outside the United States", "2000-01")]),
    }  # fmt: skip
    parts = (
        ("No optimiser.",
         "The split is set by the risk limit: 70 per cent equity is the largest target weight whose worst fall on the "
         "test's history stayed within 35 per cent ({test}). An optimiser would need the expected return of each "
         "sleeve, and that is the input the data cannot supply. The standard error of the equity series' mean yearly "
         "return over the test's {years} years is about {error} percentage points, computed as the series' yearly "
         "volatility over the square root of its years, against a gap in growth per year of {gap} points between the "
         "40/60 and the 100/0 split on the same history (the table under {test}). DeMiguel, Garlappi and Uppal "
         "measured how much history a sample-based optimiser needs before it beats an equal split out of sample: about "
         "3,000 months for 25 assets and about 6,000 for 50.{n1} A replication of their study by the same author finds "
         "that none of the seven optimising rules it tests earns a higher Sharpe ratio than the equal split at the 5 "
         "per cent level, on any of four sets of assets, over the 261 months since the paper.{n2} The frontier of the two sleeves is in the Risk view ({frontier}). With two assets it is a "
         "line, and the limit picks the point on it."),
        ("The benchmark, and why not the S&P 500.",
         "A benchmark is the portfolio a client would hold without the manager, so that the manager's contribution can "
         "be measured as the difference and bounded. This portfolio's benchmark is the blend of its two funds' own "
         "indices at 70/30, rebalanced at each month end, the policy the rules implement. The difference to it is the "
         "cost of implementing that policy: the funds' costs and tracking differences, the band's drift from 70/30, "
         "cash waiting for the cycle day, and trading. The rules take no position against the benchmark, so there is "
         "no active return to claim, and the difference is expected to be small and negative. The two reference "
         "portfolios split it into its parts: reference A, the same contributions under the same rules at net asset "
         "value, and reference B, the same contributions returned to 70/30 on every cycle day ({growth}). No single "
         "market index is the benchmark. The question readers ask most is why the portfolio does not simply hold the "
         "S&P 500. The global equity fund already holds the "
         "index's companies at about two thirds of its weight, so holding the index alone sells the other third of the "
         "world's listed companies and puts the whole portfolio into one country and one currency. A weight on one "
         "country above its share of the world is a view, and the rules take none. The advice to hold the index alone "
         "grew popular in the years after 2009, when the US stock market returned {us_after} in dollars, dividends "
         "included, against {rest_after} for the developed markets outside the United States, and over the ten years "
         "from 2000 to 2009 the same two series returned {us_decade} and {rest_decade}.{n3} On the limit, {us_test} repeats the allocation test "
         "with the US stock market in euro in place of the global series, with the same splits, the same band rule and "
         "the same months: the largest split within 35 per cent is {us_split}, and the worst fall at 70/30 is "
         "{us_fall} per cent, from {us_peak} to {us_low}. {alternative} shows what the same contributions on the same "
         "days would be in {fund}, the S&P 500 ETF that the selection criteria of the rules pick, at its net asset "
         "value in euro and without costs, beside reference A. The two lines are two rule sets over the record's "
         "months, a span on which the gap says nothing about either."),
        ("No views.",
         "A view is a statement that an asset's expected return differs from what its price implies, held with a "
         "stated confidence. The standard method for turning views into weights starts from the market portfolio and "
         "tilts it by each view in proportion to the confidence in it.{n4} With no views the method returns the market "
         "portfolio, and that is what the equity sleeve holds, at the weights of the world's listed companies. The one "
         "judgement in the rules is the one behind holding equity at all, that its return exceeds the return on bonds "
         "over five to ten years, and the limit sets how much of the portfolio rides on it."),
        ("No signal.",
         "A signal is a view produced by a rule applied to data and tested on history. None enters the portfolio. The "
         "value of a forecasting skill grows with the square root of the number of independent bets it is applied "
         "to,{n5} and a portfolio of two funds with one decision a year makes about one bet a year, so no skill would "
         "be detectable in its record and none would be worth its cost. At this portfolio's size the orders a signal "
         "calls for cost more than the signal could earn, and the cost of each order is shown under {costs}. A portfolio "
         "that carries a signal also becomes a test of that signal, and a few years of one portfolio cannot run that "
         "test. Signals belong in a separate study on decades of data, and a signal that passes its test there can "
         "enter the portfolio only through the yearly review of the rules, as a dated amendment with its test fixed "
         "in advance.{n6} The first review is in October 2027 and its agenda is public."),
    )
    us_card, us_chart = _us_test(allocation, us_test, period, added)
    alt_card, alt_chart = _alternative(daily, fund)
    paragraphs = [f'<p class="part"><b>{_esc(label)}</b> {_esc(body).format(**fields)}</p>' for label, body in parts]
    dated = (f"Added on {fmt.day_words(added)}, after the first cycle day, in answer to the questions readers ask "
             "most. The rules are unchanged.")  # fmt: skip
    page.add("method", f'<article class="card wide essay" id="method-not-done"><h3>What the portfolio does not do, '
             f'and why</h3><p class="asof">{_esc(dated)}</p>{"".join(paragraphs[:2])}<div class="ch-pair">{us_card}{alt_card}</div>'
             f'{"".join(paragraphs[2:])}<p class="label">Notes</p><ol class="notes">{NOTE_LIST}</ol></article>', us_chart)  # fmt: skip
    if alt_chart:
        page.charts.append(alt_chart)


# History of the comparisons ------------------------------------------------------------------------

HISTORY_ROLE = {"100/0": "@comparator_5", "60/40": "@comparator_4", "the US stock market at 70/30": "@us_series"}
HISTORY_NAME = {"100/0": "100/0", "60/40": "60/40", "the US stock market at 70/30": "The US stock market at 70/30"}


def _pp(x) -> str:
    """A difference or an effect in points, two decimals, signed: +2.83, and n/a where it does not apply."""
    if pd.isna(x):
        return "n/a"
    value = round(float(x) * 100, 2) + 0.0
    return (f"{value:+.2f}" if value else "0.00").replace("-", fmt.MINUS)


def _history_band(row) -> str:
    inside = "inside the band" if row["inside_band"] == "yes" else "outside the band"
    return f"±{float(row['band']) * 100:.2f}, {inside}"


def _span_name(row) -> str:
    if row["kind"] == "year":
        return f"{row['span']}, from February" if int(row["months"]) < 12 else str(row["span"])
    first, last = str(row["first_month"]), str(row["last_month"])
    return f"{_month_name(first)} to {_month_name(last)}"


def _history_table(history: pd.DataFrame) -> str:
    """One table of every span of every comparator, in blocks by comparator: the whole test and the two periods per
    year, then each calendar year, each block headed by its unit."""
    columns = ["Span", "Difference", "Split", "The dollar", "The US stock market in dollars", "Compounding", "Volatility",
               "Worst fall", "Band chance alone produces"]  # fmt: skip
    numeric = set(columns[1:])
    head = "".join(f'<th class="num">{_esc(c)}</th>' if c in numeric else f"<th>{_esc(c)}</th>" for c in columns)
    body = []
    for name in HISTORY_NAME:
        own = history[history["comparator"] == name]
        for kinds, unit in ((("whole", "period"), "points a year"), (("year",), "points")):
            rows = own[own["kind"].isin(kinds)]
            label = (f"{HISTORY_NAME[name]} against 70/30, " + ("the whole test and two periods" if unit == "points a year"
                     else "calendar years") + f", in {unit}, with volatility and worst fall in per cent")  # fmt: skip
            body.append(f'<tr class="group"><td colspan="{len(columns)}"><b>{_esc(label)}</b></td></tr>')
            for _, r in rows.iterrows():
                cells = [_span_name(r), _pp(r["difference"]), _pp(r["split"]), _pp(r["dollar"]), _pp(r["us_stock_market"]),
                         _pp(r["compounding"]), fmt.pct(r["volatility"]), fmt.pct(r["worst_fall"]), _history_band(r)]  # fmt: skip
                body.append("<tr>" + "".join(f'<td class="num">{_esc(v)}</td>' if c in numeric else f"<td>{_esc(v)}</td>"
                                             for c, v in zip(columns, cells)) + "</tr>")  # fmt: skip
    return (f'<div class="tw"><div class="tablewrap"><table class="history"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div>')


def _history_windows(windows: pd.DataFrame) -> tuple:
    """The difference per year of each comparator over rolling windows of ten calendar years, at each window's
    last year, with the windows' effects, volatility, worst fall and band in its table."""
    traces, annotations, ends = [], [], {}
    for name, label in HISTORY_NAME.items():
        own = windows[windows["comparator"] == name]
        x, y = list(own["last_year"]), [fmt.rounded(v * 100, 2) for v in own["difference"]]
        hover = [f"{int(r['first_year'])} to {int(r['last_year'])}<br>{label}: {_pp(r['difference'])} points a year<br>"
                 f"Band: {_history_band(r)}<br>Volatility {fmt.pct(r['volatility'])}, worst fall {fmt.pct(r['worst_fall'])}"
                 for _, r in own.iterrows()]  # fmt: skip
        traces.append({"type": "scatter", "mode": "lines+markers", "name": label, "x": x, "y": y,
                       "line": {"color": HISTORY_ROLE[name], "width": 2}, "marker": {"size": 6, "color": HISTORY_ROLE[name]},
                       **_hover(hover)})  # fmt: skip
        ends[name] = float(own["difference"].iloc[-1]) * 100 if len(own) else 0.0
    values = [v * 100 for v in windows["difference"]] + [0.0]
    placed = _spread(ends, 0.065 * (max(values) - min(values)))
    for name, label in HISTORY_NAME.items():
        if len(windows[windows["comparator"] == name]):
            annotations.append({**_label(int(windows["last_year"].max()), fmt.rounded(placed[name], 2), label,
                                         role=HISTORY_ROLE[name]), "xshift": 6})  # fmt: skip
    layout = {"showlegend": False, "annotations": annotations, "shapes": [_hline(0, "@ink")], "margin": {"r": 200},
              "xaxis": {"title": {"text": "Last year of the ten-year window"}, "dtick": 2,
                        "range": [float(windows["last_year"].min()) - 0.5, float(windows["last_year"].max()) + 0.5]},
              "yaxis": {"title": {"text": "Points a year, comparator minus 70/30"}}}  # fmt: skip
    rows = [[f"{int(r['first_year'])} to {int(r['last_year'])}", HISTORY_NAME[r["comparator"]], _pp(r["difference"]),
             _pp(r["split"]), _pp(r["dollar"]), _pp(r["us_stock_market"]), _pp(r["compounding"]), fmt.pct(r["volatility"]),
             fmt.pct(r["worst_fall"]), _history_band(r)] for _, r in windows.iterrows()]  # fmt: skip
    columns = ["Window", "Comparator", "Difference, points a year", "Split", "The dollar", "The US stock market in dollars",
               "Compounding", "Volatility", "Worst fall", "Band chance alone produces"]  # fmt: skip
    table = _table(columns, rows, numeric=tuple(columns[2:]), wrap_head=True)
    # On a phone the longest label takes two lines, so that it fits beside the plot.
    narrow = [{**a, "text": a["text"].replace("stock market at", "stock market<br>at"), "align": "left"} for a in annotations]
    chart = {"id": "history-windows", "view": "method", "traces": traces, "layout": layout,
             "layout_narrow": {"margin": {"r": 130}, "annotations": narrow, "yaxis": {"title": {"text": "Points a year"}},
                               "xaxis": {"title": {"text": "Last year of the window"}, "dtick": 4}}}  # fmt: skip
    return chart, table


def history_pane(page, history: pd.DataFrame, windows: pd.DataFrame) -> None:
    """The pane "The same effects on 1999 to 2025": the split and the dollar effects of 70/30 against 100/0, 60/40
    and the US stock market at 70/30 on the allocation test's own series, history and in-sample."""
    if not len(history):
        return
    whole = history[history["kind"] == "whole"].iloc[0]
    first, last = _month_name(str(whole["first_month"])), _month_name(str(whole["last_month"]))
    tracking = {r["comparator"]: r["tracking_error"] for _, r in history[history["kind"] == "whole"].iterrows()}
    errors = _and([f"{v * 100:.2f} points a year for {k}" for k, v in tracking.items()])
    notes = (
        f"History, in-sample: the allocation test's own monthly euro series from {first} to {last}, with no contributions "
        "and no costs, each split rebalanced by the band of rule 5 at month ends. The comparators are 100/0 and 60/40 on "
        "the global series and the US stock market at 70/30, the test's US run, with the same bonds and the same band and "
        "French's US stock market in place of the global equity series. Each row is the comparator's return minus 70/30's.",
        "Split is the difference in equity weight at the previous month end times the global equity series' return in US "
        "dollars minus the bonds' return, and the dollar is the same difference times the gap between that series' return "
        "in euro and in US dollars. For the US stock market at 70/30, the US stock market in dollars is its equity weight "
        "at the previous month end times the US market's return in dollars less the global series'. Both equity series "
        "are converted at the same rate, so that comparator's dollar row holds the drift term and the conversion's cross "
        "term only, and the currencies inside the global series' dollar return stay in that return, as on the record. "
        "The split of the US stock market at 70/30 is nonzero because the two paths' equity weights drift apart between "
        "rebalancings, and the band triggers on different month ends when the two equity series differ.",
        "Calendar years are cumulative, in points, and 1999 runs from February. The whole test and the two periods are "
        "per year, in points a year: the difference of the two growth rates per year, with each effect as its monthly sum "
        "divided by the span's years. Compounding is the difference less the sum of the effects. It includes the "
        "volatility drag of the more volatile path, which is why it can carry either sign.",
        "The band chance alone produces is two tracking errors times the square root of the years for a calendar year, and "
        "divided by it for a longer span. Each comparator has one tracking error, the standard deviation of its monthly "
        f"differences over the whole test times the square root of 12: {errors}. Volatility and the worst fall are the "
        "comparator's own within each span.",
    )  # fmt: skip
    table_card = _card("history", "History, in-sample: the split and the dollar effects of 70/30 against three comparators",
                       f"Monthly euro returns, {first} to {last}", "mandate/allocation_check_history.csv", plot=False,
                       kind="table", wide=True,
                       extra=_history_table(history) + "".join(f'<p class="note">{_esc(n)}</p>' for n in notes))  # fmt: skip
    chart, chart_table = _history_windows(windows)
    chart_card = _card("history-windows", "History, in-sample: the difference per year over rolling ten-year windows",
                       f"Monthly euro returns, {first} to {last}. Points a year, comparator minus 70/30",
                       "mandate/allocation_check_history_windows.csv", table=chart_table, wide=True, height=320,
                       note=("Each point is a window of ten calendar years, from 2000 to 2009 to 2016 to 2025, at its last "
                             "year: the comparator's growth per year minus 70/30's, in points a year. The test's 27 calendar "
                             "years, 1999 from February, give 17 overlapping windows of ten full years, so the chart smooths "
                             "and adds no evidence. The table gives each window's effects per year, the comparator's "
                             "volatility and worst fall, and the band chance alone produces."))  # fmt: skip
    page.charts.append(chart)
    page.add("method", '<div class="wide ch-panes"><details class="ch-pane" id="method-history"><summary>The same effects on '
             f'1999 to 2025</summary><div class="ch-pane__body">{table_card}{chart_card}</div></details></div>')


def _other_projects() -> str:
    """The links to the other projects, in the wording of their cards on the site."""
    entries = "".join(f'<p><b>{_esc(title)}</b> {_esc(text)} '
                      + ", ".join(f'<a href="{_esc(url)}">{_esc(word)}</a>' for word, url in links) + "</p>"
                      for title, text, links in OTHER_PROJECTS)  # fmt: skip
    return f'<article class="card wide projects" id="method-projects"><h3>Other projects</h3>{entries}</article>'


# Simulations -----------------------------------------------------------------------------------------

SIMULATION_BASIS = "This is not the portfolio's record, which starts in October 2026."
SAMPLE = "the allocation test's monthly euro returns from February 1999 to December 2025"


def _one_in(share: float) -> str:
    """A share of paths as "one in N", N in words up to nine."""
    n = int(round(1 / share)) if share > 0 else 0
    return NUMBER_WORD.get(n, str(n)).lower() if n else "none"


def _month_end(month: str) -> str:
    return pd.Period(month, freq="M").end_time.strftime("%Y-%m-%d")


def _longer_blocks(checks: pd.DataFrame) -> str:
    """The sentence on block lengths of more than a year, from the check rows of 70/30 over ten years."""
    longer = checks[(checks["split"] == "70/30") & (checks["block_months"] > 12)].sort_values("block_months")
    if not len(longer):
        return ""
    months = _and([str(int(m)) for m in longer["block_months"]])
    shares = _and([f"{v * 100:.1f}" for v in longer["share_above_35"]])
    return (f"Blocks of {months} months, which keep the long falls whole, give {shares} per cent, so among blocks of a "
            "year or more the twelve-month figure is the low side. ")  # fmt: skip


def _bootstrap(page, boot):
    """The bootstrap of the allocation test: the worst fall of every split over resampled ten-year paths."""
    main = boot[(boot["horizon_years"] == 10) & (boot["block_months"] == 12)]
    five = boot[(boot["horizon_years"] == 5) & (boot["block_months"] == 12)].set_index("split")
    checks = boot[(boot["horizon_years"] == 10) & (boot["block_months"] != 12)]
    splits = list(main["split"])
    held = [s == "70/30" for s in splits]
    traces = []
    for chosen, role in ((False, "@other"), (True, "@accent")):
        xs, ys = [], []
        for (_, r), h in zip(main.iterrows(), held):
            if h == chosen:
                xs += [fmt.rounded(r["median_worst_fall"] * 100, 1), fmt.rounded(r["p95_worst_fall"] * 100, 1), None]
                ys += [r["split"], r["split"], None]
        traces.append({"type": "scatter", "mode": "lines", "x": xs, "y": ys, "line": {"color": role, "width": 3},
                       "hoverinfo": "skip", "showlegend": False})  # fmt: skip
    marks = ["@accent" if h else "@ink2" for h in held]
    traces.append({"type": "scatter", "mode": "markers", "name": "Median", "y": splits,
                   "x": [fmt.rounded(v * 100, 1) for v in main["median_worst_fall"]],
                   "marker": {"size": 10, "color": marks},
                   **_hover([f"{s}: median worst fall {fmt.pct(v)}" for s, v in zip(splits, main["median_worst_fall"])])})  # fmt: skip
    traces.append({"type": "scatter", "mode": "markers", "name": "95th percentile", "y": splits,
                   "x": [fmt.rounded(v * 100, 1) for v in main["p95_worst_fall"]],
                   "marker": {"size": 10, "symbol": "circle-open", "color": marks, "line": {"width": 2, "color": marks}},
                   **_hover([f"{s}: 95th percentile {fmt.pct(v)}" for s, v in zip(splits, main["p95_worst_fall"])])})  # fmt: skip
    traces.append({"type": "scatter", "mode": "markers", "name": "Allocation test, one path", "y": splits,
                   "x": [fmt.rounded(v * 100, 1) for v in main["worst_fall_one_path"]],
                   "marker": {"size": 11, "symbol": "diamond", "color": "@ink"},
                   **_hover([f"{s}: allocation test {fmt.pct(v)}" for s, v in zip(splits, main["worst_fall_one_path"])])})  # fmt: skip
    shapes = [_vline(35, "@status_breach"), _vline(40, "@status_breach")]
    annotations = [_label(35, 1, "35%", yref="paper", anchor="right", role="@status_breach", xshift=-4, yshift=8),
                   _label(40, 1, "40%", yref="paper", anchor="left", role="@status_breach", xshift=4, yshift=8)]  # fmt: skip
    layout = {"showlegend": True, "legend": {"orientation": "h", "x": 0, "y": -0.12, "yanchor": "top"},
              "yaxis": {"type": "category", "categoryorder": "array", "categoryarray": splits, "autorange": "reversed",
                        "title": {"text": "Split, equity/bonds"}},
              "xaxis": {"title": {"text": "Worst fall over 10 years, per cent"}, "rangemode": "tozero"},
              "shapes": shapes, "annotations": annotations, "margin": {"t": 24}}  # fmt: skip
    rows = [[r["split"], fmt.pct(r["worst_fall_one_path"]), fmt.pct(r["median_worst_fall"]), fmt.pct(r["p95_worst_fall"]),
             fmt.pct(r["share_above_35"]), fmt.pct(r["share_above_40"]), fmt.pct(five.loc[r["split"], "median_worst_fall"]),
             fmt.pct(five.loc[r["split"], "share_above_35"]), fmt.pct(five.loc[r["split"], "share_above_40"])]
            for _, r in main.iterrows()]  # fmt: skip
    columns = ["Split", "Allocation test", "Median, 10 years", "95th percentile, 10 years", "Above 35%, 10 years",
               "Above 40%, 10 years", "Median, 5 years", "Above 35%, 5 years", "Above 40%, 5 years"]  # fmt: skip
    table = _table(columns, rows, numeric=tuple(columns[1:]))
    check_rows = [[f"{int(r['block_months'])} months", fmt.pct(r["median_worst_fall"]), fmt.pct(r["p95_worst_fall"]),
                   fmt.pct(r["share_above_35"]), fmt.pct(r["share_above_40"])]
                  for _, r in pd.concat([main[main["split"] == "70/30"], checks]).sort_values("block_months").iterrows()]  # fmt: skip
    check_columns = ["Block length", "Median", "95th percentile", "Above 35%", "Above 40%"]
    table += '<p class="label">70/30 over 10 years, by block length</p>' + _table(check_columns, check_rows,
                                                                                  numeric=tuple(check_columns[1:]))  # fmt: skip
    share = main.set_index("split")["share_above_35"]
    paths = int(main["paths"].iloc[0])
    note = (f"Simulation on index returns, monthly, in euro, gross of costs and without contributions: {paths:,} paths of ten "
            f"years, each joining twelve-month blocks of {SAMPLE} that start at random months, with the band of rule 5 "
            "at each month end. The paths are resampled from the same returns, so they say nothing about years unlike "
            "those, and the split was chosen on this sample. Over ten years, 70/30 falls more than 35 per cent in about "
            f"one path in {_one_in(share['70/30'])}, and 60/40 in about one in {_one_in(share['60/40'])}. The table adds "
            f"five years and block lengths of 6, 24 and 36 months. {_longer_blocks(checks)}The results are an input to the review of the rules "
            f"in October 2027 and change no rule. {SIMULATION_BASIS}")  # fmt: skip
    page.add("method", _card("c25", "Simulated worst fall of each split over resampled ten-year paths",
             "Bootstrap of the allocation test, 10,000 paths", "mandate/simulation_bootstrap.csv", table=table, note=note,
             height=480, wide=True, anchor="method-bootstrap"),
             {"id": "c25", "traces": traces, "layout": layout,
              "layout_narrow": {"xaxis": {"title": {"text": "Worst fall, per cent"}}}})  # fmt: skip


def simulations(page, history, paths, monthly):
    """The Simulations view: the rules on the allocation test's returns, and the resampled paths."""
    if not len(history) or not len(paths):
        page.add("simulations", _card("c26", "Simulations", "", None, plot=False, wide=True,
                 empty="The simulation tables are not in mandate/."))
        return
    data = history.iloc[1:]
    x = [_month_end(m) for m in data["month"]]
    low, high = config.BAND
    band = data[data["band_order"] == "yes"]
    traces = [{"type": "scatter", "mode": "lines", "name": "Equity weight at the month end", "x": x,
               "y": [fmt.rounded(v * 100, 1) for v in data["equity_weight_before_top_up"]],
               "line": {"color": "@equity", "width": 1.5},
               **_hover([f"{fmt.month_words(m)}: {fmt.pct(v)}" for m, v in zip(data["month"], data["equity_weight_before_top_up"])])},
              {"type": "scatter", "mode": "markers", "name": "Band order", "x": [_month_end(m) for m in band["month"]],
               "y": [fmt.rounded(v * 100, 1) for v in band["equity_weight_before_top_up"]],
               "marker": {"size": 11, "symbol": "diamond", "color": "@status_breach"},
               **_hover([f"{fmt.month_words(m)}: band order, rule 5" for m in band["month"]])}]  # fmt: skip
    layout = {"showlegend": True, "yaxis": {"title": {"text": "Equity weight, per cent"}, "range": [60, 80], "dtick": 5},
              "xaxis": {"type": "date", "tickformat": "%Y", "hoverformat": "%B %Y"},
              "shapes": [{"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": low * 100,
                          "y1": high * 100, "fillcolor": "@band", "line": {"width": 0}, "layer": "below"},
                         _hline(70, "@ink")]}  # fmt: skip
    orders = data["orders"].astype(int)
    outside = ((data["equity_weight_before_top_up"] < low) | (data["equity_weight_before_top_up"] > high)).sum()
    rows = [["Cycle days", fmt.count(len(data))],
            ["Cycle days with one order", fmt.count((orders == 1).sum())],
            ["Cycle days with two orders", fmt.count((orders == 2).sum())],
            ["Cycle days with a band order", fmt.count(len(band))],
            ["Months of the band orders", ", ".join(fmt.month_short(m) for m in band["month"])],
            ["Months with the equity weight outside the band before the top-up", fmt.count(outside)],
            ["Most orders on a cycle day, against the budget of five", fmt.count(orders.max())]]  # fmt: skip
    table = _table(["Count", "Value"], rows)
    note = (f"Simulation on index returns, monthly, in euro, gross of costs, with a starting amount of 100 and a top-up of "
            f"5 a month: {SAMPLE}, with the cycle at each month end in place of the 5th. The line is the equity weight at "
            "each month end, before the top-up. Each top-up buys the sleeve "
            "furthest below its target weight up to that weight, and the remainder buys the other sleeve (rule 4). The band "
            "of rule 5 then applies. Every purchase counts as an order, whatever its size. The split was chosen on this "
            f"sample. {SIMULATION_BASIS}")  # fmt: skip
    page.add("simulations", _section("Mechanics simulation", "simulations-mechanics",
             sub="The rules applied to the allocation test's returns, for the counts of their orders"))  # fmt: skip
    page.add("simulations", _card("c26", "Simulation: the equity weight in its band under the rules, 1999 to 2025",
             "Monthly, February 1999 to December 2025", "mandate/simulation_history.csv", table=table, note=note,
             height=320, wide=True), {"id": "c26", "traces": traces, "layout": layout})  # fmt: skip

    # The historical line: growth of 100 and the fall from the previous peak, beside the target weights restored each month.
    series = (("The rules", "growth_rules", "drawdown_rules", "@accent"),
              ("Back to 70/30 on every cycle day", "growth_every_cycle_day", "drawdown_every_cycle_day", "@reference_b"))
    xs = [_month_end(m) for m in history["month"]]
    growth_traces, fall_traces = [], []
    for name, g, d, role in series:
        growth_traces.append({"type": "scatter", "mode": "lines", "name": name, "x": xs,
                              "y": [fmt.rounded(v, 1) for v in history[g]], "line": {"color": role, "width": 2},
                              **_hover([f"{fmt.month_words(m)}<br>{name}: {fmt.index(v)}" for m, v in zip(history["month"], history[g])])})
        fall_traces.append({"type": "scatter", "mode": "lines", "name": name, "x": xs,
                            "y": [fmt.rounded(-v * 100, 1) for v in history[d]], "line": {"color": role, "width": 2},
                            **_hover([f"{fmt.month_words(m)}<br>{name}: {fmt.pct(-v)} below the previous peak" for m, v in
                                      zip(history["month"], history[d])])})  # fmt: skip
    year_axis = {"type": "date", "tickformat": "%Y", "hoverformat": "%B %Y"}
    growth_layout = {"showlegend": True, "yaxis": {"title": {"text": "Growth of 100"}}, "xaxis": year_axis}
    deepest = max(10.0, 1.3 * float(-history[["drawdown_rules", "drawdown_every_cycle_day"]].min().min()) * 100)
    shapes, annotations, short_labels = _limit_lines(deepest, x=1, anchor="right")
    fall_layout = {"showlegend": True, "xaxis": year_axis, "shapes": shapes, "annotations": annotations,
                   "yaxis": {"title": {"text": "Per cent below the previous peak"}, "range": [deepest * FALL_AXIS_ROOM, -1]}}  # fmt: skip
    year_ends = history[(history["month"].str.endswith("-12")) | (history.index == 0) | (history.index == len(history) - 1)]
    rows = [[fmt.month_short(r["month"]) + (", start" if i == 0 else ""), fmt.index(r["growth_rules"]), fmt.index(r["growth_every_cycle_day"]),
             fmt.pct(-r["drawdown_rules"]), fmt.pct(-r["drawdown_every_cycle_day"])]
            for i, (_, r) in enumerate(year_ends.iterrows())]  # fmt: skip
    columns = ["Month", "The rules", "Every cycle day", "Fall, the rules", "Fall, every cycle day"]
    table = _table(columns, rows, numeric=tuple(columns[1:]))
    note = ("A simulation on index returns, and not the portfolio's record, which starts in October 2026. Gross of costs, "
            "with the starting amount of 100 and the top-up of 5 a month, and the rules applied at each month end. The split "
            "was chosen on this sample, so the simulation is in-sample. The index series run back before the two ETFs "
            "existed: the equity share class since 21 October 2011 and the bond share class since 19 February 2019. "
            "Time-weighted, with contributions removed. The table gives the year ends, and the months are in the source file.")  # fmt: skip
    page.add("simulations", _section("Historical simulation", "simulations-history",
             sub="Growth of 100 and the fall from the previous peak on the allocation test's returns"))  # fmt: skip
    page.add("simulations", _card("c27a", "Simulation: growth of 100 under the rules and with the target weights restored on "
             "every cycle day, 1999 to 2025", "Monthly, February 1999 to December 2025", "mandate/simulation_history.csv",
             table=table, note=note, height=320), {"id": "c27a", "traces": growth_traces, "layout": growth_layout})  # fmt: skip
    page.add("simulations", _card("c27b", "Simulation: fall from the previous peak under the rules and with the target "
             "weights restored on every cycle day, 1999 to 2025", "Monthly, February 1999 to December 2025",
             "mandate/simulation_history.csv", note="The same simulation as the growth of 100, month by month. " + SIMULATION_BASIS,
             height=320), {"id": "c27b", "traces": fall_traces, "layout": fall_layout,
                                      "layout_narrow": {"annotations": short_labels}})  # fmt: skip

    # The resampled paths, with the record drawn inside them from the first month end.
    years = [fmt.rounded(v, 4) for v in paths["years"]]
    band_trace = {"type": "scatter", "mode": "lines", "x": years, "line": {"width": 0}, "hoverinfo": "skip"}
    traces = [{**band_trace, "y": [fmt.rounded(v, 1) for v in paths["p05"]], "showlegend": False},
              {**band_trace, "y": [fmt.rounded(v, 1) for v in paths["p95"]], "fill": "tonexty", "fillcolor": "@fan_outer",
               "name": "5th to 95th percentile"},
              {**band_trace, "y": [fmt.rounded(v, 1) for v in paths["p25"]], "showlegend": False},
              {**band_trace, "y": [fmt.rounded(v, 1) for v in paths["p75"]], "fill": "tonexty", "fillcolor": "@fan_inner",
               "name": "25th to 75th percentile"},
              {"type": "scatter", "mode": "lines", "name": "Median", "x": years,
               "y": [fmt.rounded(v, 1) for v in paths["p50"]], "line": {"color": "@reference_a", "width": 2},
               **_hover([f"Month {int(m)}: median {fmt.index(v)}" for m, v in zip(paths["month"], paths["p50"])])},
              {"type": "scatter", "mode": "lines", "name": "Money paid in", "x": years,
               "y": [fmt.rounded(v, 1) for v in paths["paid_in"]], "line": {"color": "@ink2", "width": 1.5, "dash": "dash"},
               "hoverinfo": "skip"}]  # fmt: skip
    record = monthly[monthly["complete"] == "yes"] if len(monthly) else monthly
    if len(record):
        months = list(range(1, len(record) + 1))
        traces.append({"type": "scatter", "mode": "lines+markers", "name": "The record", "x": [m / 12 for m in [0] + months],
                       "y": [100.0] + [fmt.rounded(v, 1) for v in record["value_in_units"]],
                       "line": {"color": "@accent", "width": 2}, "marker": {"size": 7, "color": "@accent"},
                       "hoverinfo": "skip"})  # fmt: skip
        record_text = ("The record's path is drawn against the range the sample implies. Its position inside the range says "
                       "where the market's draw has taken it and is not evidence about the rules, which a record of this "
                       "length cannot give.")  # fmt: skip
    else:
        record_text = "From the first month end, 31 October 2026, the record's own path is drawn inside the bands."
    layout = {"showlegend": True, "legend": {"traceorder": "normal"},
              "xaxis": {"title": {"text": "Years from the first purchase"}, "range": [0, 10], "dtick": 1},
              "yaxis": {"title": {"text": "Units of the starting amount"}, "rangemode": "tozero"}}  # fmt: skip
    yearly = paths[paths["month"] % 12 == 0]
    rows = [[f"{int(r['month']) // 12}", fmt.index(r["paid_in"]), fmt.index(r["p05"]), fmt.index(r["p25"]),
             fmt.index(r["p50"]), fmt.index(r["p75"]), fmt.index(r["p95"])] for _, r in yearly.iterrows()]  # fmt: skip
    columns = ["Year", "Paid in", "5th", "25th", "Median", "75th", "95th"]
    table = _table(columns, rows, numeric=tuple(columns[1:]))
    note = ("These are resampled paths and not the portfolio's record: 10,000 paths of the portfolio's value over ten years "
            f"from the first purchase that reuse {SAMPLE} in random twelve-month blocks and assume nothing beyond them, so "
            "the bands say what that sample implies and not what will happen. Gross of costs, with the top-up of 5 a month and "
            "the rules applied at each month end, in units of the starting amount, 100. The split was chosen on this sample, so "
            f"the paths are in-sample. {record_text} A record below the lower band is a question for the review of the rules "
            "in October 2027.")  # fmt: skip
    page.add("simulations", _section("Resampled paths", "simulations-paths",
             sub="The portfolio's value over paths resampled from the allocation test's returns"))  # fmt: skip
    page.add("simulations", _card("c28", "Resampled paths of the portfolio's value over ten years from the first purchase",
             "The same 10,000 paths as the bootstrap of the allocation test", "mandate/simulation_paths.csv", table=table,
             note=note, height=360, wide=True), {"id": "c28", "traces": traces, "layout": layout})  # fmt: skip


def _history(path: str) -> str:
    return f'<a href="{config.REPOSITORY_URL}/commits/main/{path}">the commit of {_esc(path)}</a>'


def _report_html(text: str) -> tuple:
    """A cycle report as HTML: its title, and its body with each table in a frame that scrolls."""
    import markdown

    title, _, body = text.strip().partition("\n")
    html_body = markdown.markdown(body, extensions=["tables"])
    html_body = html_body.replace("<table>", '<div class="tw"><div class="tablewrap"><table>').replace("</table>", "</table></div></div>")
    return title.lstrip("# ").strip(), html_body


def _quarterly_issues(root: Path = None) -> list:
    """The issues of the quarterly report under quarterly/, newest first, each as (issue number, period in
    words, figures as of, commit, page path, [(print date, pdf path)])."""
    root = Path(root or config.ROOT)
    found = []
    for name, path, pdfs in quarterly_module.issues(root):
        text = path.read_text(encoding="utf-8")
        number = re.search(r"Issue (\d+) &middot; Figures as of (\d{4}-\d\d-\d\d)", text)
        period = re.search(r"<h1>(.*?)</h1>", text)
        commit = re.search(r'<meta name="commit" content="([0-9a-f]+)">', text)
        prints = [(pdf.stem.split("_", 1)[1], pdf.relative_to(root).as_posix()) for pdf in pdfs]
        found.append((int(number.group(1)), html.unescape(period.group(1)), number.group(2), commit.group(1),
                      path.relative_to(root).as_posix(), prints))  # fmt: skip
    return found


def _log_quarterly(page, issues, orders):
    page.add("log", _section("Quarterly reports", "log-quarterly",
             sub="One report a quarter, kept as issued, with the PDF printed from it"))  # fmt: skip
    if not issues:
        empty = "The first report follows the first quarter end after the first purchase."
        if len(orders):
            first = pd.Timestamp(orders["date"].min())
            end = pd.Period(first, "Q").end_time.normalize()
            after = end + pd.Timedelta(days=1)
            day = trading_days.cycle_day(after.year, after.month)
            empty = (f"The first report covers {quarterly_module._period_words(first, end)} and is published after the "
                     f"cycle day of {fmt.day_words(day)}.")  # fmt: skip
        page.add("log", _card("quarterly", "Quarterly reports", "", None, plot=False, wide=True, empty=empty))
        return
    items = []
    for number, period, as_of, commit, path, prints in issues:
        pdfs = "".join(f' &middot; <a href="{_esc(pdf)}">PDF, printed {_esc(fmt.day_words(day))}</a>' for day, pdf in prints)
        items.append(f'<li><a href="{_esc(path)}">Issue {number}, {_esc(period)}</a>{pdfs}'
                     f'<span class="asof">Figures as of {_esc(fmt.day_words(as_of))}, from commit {_esc(commit)}</span></li>')  # fmt: skip
    page.add("log", '<article class="card wide quarterly"><h3>Quarterly reports</h3><p class="note">Each issue is built '
             "once from the tables at the commit it names and is never rebuilt. A correction goes in the next issue as "
             f'an erratum.</p><ul class="issues">{"".join(items)}</ul><p class="source">Source: quarterly/</p></article>')  # fmt: skip


def _log_notes(page, notes_list, next_cycle):
    page.add("log", _section("Monthly notes", "log-notes", sub="Written after each cycle day, newest first"))
    if not notes_list:
        page.add("log", _card("notes", "Monthly notes", "", None, plot=False, wide=True,
                 empty=f"The first note follows the first cycle day, {next_cycle}."))  # fmt: skip
        return
    for n in notes_list:
        path = f"notes/{n.month}.md"
        body = "".join(f"<p>{_esc(para)}</p>" for para in n.body.split("\n\n"))
        page.add("log", f'<article class="card wide notebody"><h3>{_esc(pd.Period(n.month, "M").strftime("%B %Y"))}</h3>'
                 f'<p class="asof">Cycle day {_esc(fmt.day_words(n.cycle_day))}. Committed in {_history(path)}</p>'
                 f'<p class="figures">{_esc(n.figures)}</p>{body}<p class="source">Source: {_esc(path)}</p></article>')  # fmt: skip


def _log_reports(page, reports, orders, next_cycle):
    page.add("log", _section("Cycle reports", "log-cycles",
             sub="Each rule that bears on the proposed orders, written before the orders, and the line after them"))  # fmt: skip
    if not reports:
        page.add("log", _card("cycles", "Cycle reports", "", None, plot=False, wide=True,
                 empty=f"The first cycle report is written on the first cycle day, {next_cycle}, before its orders."))  # fmt: skip
        return
    for month, text in sorted(reports.items(), reverse=True):
        path = f"cycles/{month}.md"
        title, body = _report_html(text)
        day = trading_days.cycle_day(int(month[:4]), int(month[5:]))
        on_day = orders[pd.to_datetime(orders["date"]).dt.date == day] if len(orders) else orders
        rows = [[r["sleeve"].capitalize(), r["side"], r["rule"], r["inside_rule_7_window"], r["bid_and_ask_recorded"]]
                for _, r in on_day.iterrows()]  # fmt: skip
        placed = (_table(["Sleeve", "Side", "Rule", "Inside 15:45 to 17:00", "Bid and ask recorded"], rows)
                  if rows else '<p class="note">No order is in the record for this day.</p>')  # fmt: skip
        page.add("log", f'<article class="card wide report"><h3>{_esc(title)}</h3><p class="asof">Committed in {_history(path)}</p>'
                 f'<div class="reportbody">{body}</div><p class="label">The orders of {_esc(fmt.day_words(day))} in the record</p>{placed}'
                 f'<p class="source">Source: {_esc(path)}, outputs/orders.csv</p></article>')  # fmt: skip


def _log_register(page, register):
    page.add("log", _section("Departures register", "log-departures", sub="Each departure from the rules, kept as it happened"))
    rows = [[fmt.day_short(r["date"]), r["rule"], r["what_happened"], r["consequence"]] for _, r in register.iterrows()] if len(register) else []
    table = _table(["Date", "Rule", "What happened", "Consequence"], rows, prose=True)
    page.add("log", _card("departures", "Departures register", "Every departure since the first purchase",
             "outputs/departures.csv", plot=False, wide=True, kind="table",
             empty=None if rows else "The register has no entry so far.").replace('<p class="source">', (table if rows else "") + '<p class="source">', 1))  # fmt: skip


def log(page, monthly, notes_list=(), reports=None, orders=pd.DataFrame(), register=pd.DataFrame(), next_cycle="",
        issues=(), now=None):  # fmt: skip
    _log_quarterly(page, list(issues), orders)
    _log_notes(page, list(notes_list), next_cycle)
    _log_reports(page, reports or {}, orders, next_cycle)
    _log_register(page, register)
    page.add("log", _section("Monthly table", "log-table", sub="Every figure behind the tiles and charts, by month"))
    if not len(monthly):
        page.add("log", _card("c24", "The monthly table", "", None, plot=False, wide=True, kind="table",
                 empty="The first row appears with the first valuation day."))
        return
    month = ("Month", lambda r: fmt.month_short(r["month"]) + ("" if r["complete"] == "yes" else " to date"))
    groups = [
        ("Returns and risk", [month, ("Last day", lambda r: fmt.day_short(r["last_day"])),
         ("Return", lambda r: fmt.pct(r["return_month"], True)),
         ("Since the first purchase", lambda r: fmt.pct(r["return_since_start"], True)),
         ("Money-weighted, cumulative", lambda r: fmt.pct(r["money_weighted_since_start"], True)),
         ("Money-weighted, per year", lambda r: fmt.pct(r.get("money_weighted_per_year"), True)),
         ("Drawdown", lambda r: fmt.pct(-r["drawdown"])),
         ("Worst fall to date", lambda r: fmt.pct(r["worst_fall_to_date"])),
         ("Volatility, 12 months", lambda r: fmt.pct(r["volatility_12m"]))]),
        ("Weights, orders and contributions", [month, ("Equity", lambda r: fmt.pct(r["weight_equity"])),
         ("Bonds", lambda r: fmt.pct(r["weight_bonds"])), ("Cash", lambda r: fmt.pct(r["weight_cash"])),
         ("Drift", lambda r: fmt.points(r["drift_points"])), ("Orders", lambda r: fmt.count(r["orders"])),
         ("Paid in, units", lambda r: fmt.index(r["contributions_in_units"])),
         ("Value, units", lambda r: fmt.index(r["value_in_units"])),
         ("Market effect", lambda r: fmt.pct(r["market_effect"], True)),
         ("Contribution", lambda r: fmt.pct(r["contribution_effect"], True))]),
        ("Costs, in basis points", [month, ("Commissions", lambda r: fmt.bps(r["commissions_bps"], False)),
         ("Half-spread", lambda r: fmt.bps(r["half_spread_bps"], False)),
         ("Price paid against net asset value", lambda r: fmt.bps(r["execution_against_nav_bps"], False)),
         ("Implementation cost of the month", lambda r: fmt.bps(r["implementation_cost_month_bps"], False)),
         ("Implementation cost, cumulative", lambda r: fmt.bps(r["implementation_cost_bps"]))]),
    ]  # fmt: skip
    tables = []
    for heading, columns in groups:
        names = [c for c, _ in columns]
        rows = [[f(r) for _, f in columns] for _, r in monthly.iterrows()]
        numeric = tuple(n for n in names[1:] if n != "Last day")
        tables.append(f'<p class="label">{_esc(heading)}</p>' + _table(names, rows, numeric=numeric,
                      rounding=heading.startswith("Weights")).replace("<table>", '<table class="headwrap">', 1))  # fmt: skip
    note = "Each chart's own table is under it, and every key figure is a cell of these tables or of outputs/portfolio_daily.csv."
    if len(_later_orders(orders, now)):
        note = ("Each chart's own table is under it, and every key figure is a cell of these tables or of outputs/portfolio_daily.csv, "
                "except that the orders figure also counts the orders placed after the last net asset values.")
    pending = _after_record(orders, now)
    if pending:
        note += f" {pending}"
    page.add("log", _card("c24", "The monthly table", "Months since the first purchase. Drawdown and worst fall are "
             "per cent below the previous peak. Volatility from month 12", "outputs/metrics_monthly.csv", plot=False, kind="table",
             wide=True, table=None, note=note).replace('<p class="note">', "".join(tables) + '<p class="note">', 1))  # fmt: skip


# The page ------------------------------------------------------------------------------------------


def _next_cycle_day(now_row) -> str:
    """The first cycle day after the date of the holdings, or on it."""
    day = _built(now_row).date()
    cycle = trading_days.cycle_day(day.year, day.month)
    if cycle < day:
        following = pd.Period(day, "M") + 1
        cycle = trading_days.cycle_day(following.year, following.month)
    return fmt.day_words(cycle)

TERM_LINE = re.compile(r"^- \*\*(.+?)\*\*: (.+)$")


def terms() -> list:
    """The terms of the README's Terms section, the one list the page's footer shows."""
    text = (config.ROOT / "README.md").read_text()
    section = text.split("\n## Terms\n", 1)[1].split("\n## ", 1)[0]
    found = [TERM_LINE.match(line.strip()) for line in section.splitlines() if line.strip()]
    if not found or not all(found):
        raise ValueError("README.md: every line of the Terms section must read '- **term**: definition'")
    return [(m.group(1)[0].upper() + m.group(1)[1:], m.group(2).replace("`", "")) for m in found]


# Each view opens with the question it answers.
VIEW_LEADS = {
    "overview": "Where the portfolio stands against its rules.",
    "performance": "What the portfolio has returned since the first purchase, how that sets against its comparators, "
                   "what was paid in and what running it costs.",
    "portfolio": "What the portfolio holds, and how the rules keep the equity weight in its band.",
    "risk": "How far the portfolio could fall, estimated on index returns and simulated under the rules.",
    "method": "How the split and the two ETFs were chosen, the terms the dashboard uses, and the record of each month.",
}


def _part_leads() -> dict:
    """The line under each part's heading, as HTML, some with links to the part's sections."""
    leads = {
        "comparisons": _esc("The record beside comparators that receive the same contributions on the same days, each "
                            "with its volatility, its worst fall and the band chance alone produces over the same span."),
        "contributions": _esc("Money paid in against gains and losses, in units of the starting amount."),
        "costs": _esc("What running the portfolio costs, measured against reference portfolio A, which follows the same "
                      "rules at net asset value without costs."),
        "rebalancing": _esc("The equity weight against its band, and every order against the rules."),
        "lookthrough": "The holdings of the two ETFs, weighted by each sleeve's weight in the portfolio, in three parts: "
                       + _link("lookthrough-equity", "the equity sleeve") + ", " + _link("lookthrough-bonds", "the bond sleeve")
                       + " and " + _link("lookthrough-portfolio", "the whole portfolio") + ", where currency exposure "
                       "combines both. " + _link("lookthrough-risk-section", "The risk of the whole portfolio")
                       + ", estimated on index returns, opens the Risk view.",
        "factors": _esc("The equity ETF's loadings on Kenneth French's developed-market factors."),
        "method": "How the split and the two ETFs were chosen, what the portfolio does not do, the data behind the charts, "
                  "the controls and the rules, in eight parts: " + _link("method-allocation", "the allocation test") + ", "
                  + _link("method-bootstrap", "its bootstrap") + ", "
                  + _link("method-correlation", "the correlation of the two sleeves") + ", "
                  + _link("method-not-done", "what the portfolio does not do and why") + ", "
                  + _link("method-selection", "the ETF selection") + ", " + _link("method-sources", "the data sources")
                  + ", " + _link("method-controls", "the controls") + " and " + _link("method-rules", "the rules") + ".",
        "glossary": _esc("The terms the dashboard uses, each with its definition."),
        "simulations": "The rules applied to the allocation test's returns and to paths resampled from them, in three parts: "
                       + _link("simulations-mechanics", "the mechanics simulation") + ", "
                       + _link("simulations-history", "the historical simulation") + " and "
                       + _link("simulations-paths", "the resampled paths")
                       + ". Every chart here is a simulation on index returns, gross of costs. None is the portfolio's "
                       "record, which starts in October 2026.",
        "log": "The record of each quarter and month, in five parts: " + _link("log-quarterly", "the quarterly reports")
               + ", " + _link("log-notes", "the monthly notes") + ", "
               + _link("log-cycles", "the cycle reports") + ", " + _link("log-departures", "the departures register")
               + " and " + _link("log-table", "the monthly table") + ", which holds every figure behind the key figures "
               "and charts.",
    }  # fmt: skip
    return leads


DESCRIPTION = ("A real-money portfolio run under written rules, 70/30 equity and euro government bonds: allocation, "
               "rebalancing, costs, look-through and factor exposures.")  # fmt: skip
PREVIEW_IMAGE = config.PREVIEW_IMAGE


def _link_preview() -> str:
    """The tags that give a link to the page a title, a description and a picture, once the picture is in the root."""
    if not (config.ROOT / PREVIEW_IMAGE).exists():
        return ""
    width, height = quarterly_module.image_size(config.ROOT / PREVIEW_IMAGE)
    tags = [("property", "og:type", "website"), ("property", "og:title", "Rules-based portfolio"),
            ("property", "og:description", DESCRIPTION), ("property", "og:url", config.DASHBOARD_URL),
            ("property", "og:image", config.DASHBOARD_URL + PREVIEW_IMAGE), ("property", "og:image:width", str(width)),
            ("property", "og:image:height", str(height)), ("name", "twitter:card", "summary_large_image")]  # fmt: skip
    return "".join(f'<meta {kind}="{key}" content="{_esc(value)}">\n' for kind, key, value in tags)


def _palette_css(palette: dict) -> str:
    """The palette's page colours as CSS variables. The page has one theme, light."""
    keys = ["plane", "surface", "ink", "ink2", "muted", "grid", "axis", "ring", "accent", "equity", "bonds"]
    return ":root { color-scheme: light; " + " ".join(f"--{k}: {palette['light'][k]};" for k in keys) + " }\n"


def _check_roles(charts: list, palette: dict) -> None:
    text = json.dumps(charts)
    if HEX.search(text):
        raise ValueError(f"a chart names a colour by value: {HEX.search(text).group(0)}")
    for role in set(re.findall(r'"@([a-z_0-9]+)"', text)):
        if role not in palette["light"]:
            raise ValueError(f"a chart asks for the colour role {role}, which site/palette.json does not define")


def _rules_html() -> str:
    """The rules as rules/RULES.md holds them. A date in a table cell, such as an amendment's day of commit, is
    written as 7 Oct 2026, as every date on the page is, and the file keeps its own form."""
    import markdown

    text = (config.ROOT / "rules" / "RULES.md").read_text()
    body = markdown.markdown(text, extensions=["tables"])
    body = re.sub(r"<h1>.*?</h1>", "", body, count=1)
    body = re.sub(r"<td>(\d{4}-\d{2}-\d{2})</td>", lambda m: f"<td>{fmt.day_short(m.group(1))}</td>", body)
    return body.replace("<table>", '<div class="tw"><div class="tablewrap"><table>').replace("</table>", "</table></div></div>")


def build(out_dir: Path = None) -> Path:
    out = {p.name: pd.read_csv(p) for p in sorted(config.OUTPUTS_DIR.glob("*.csv"))}
    palette = json.loads((config.SITE_DIR / "palette.json").read_text())
    daily, monthly = out["portfolio_daily.csv"], out.get("metrics_monthly.csv", pd.DataFrame())
    if "month" in monthly and monthly["month"].isna().all():
        monthly = pd.DataFrame()
    orders = out["orders.csv"]
    page = Page()
    overview(page, daily, monthly, out["allocation_now.csv"], orders, out.get("cost_of_ownership.csv", pd.DataFrame()))
    now_row = out["allocation_now.csv"].iloc[0]
    rebalancing(page, daily, orders, out["band_events.csv"], out["compliance.csv"], monthly, now_row)
    costs(page, monthly, out["implementation_cost.csv"], daily)
    _cost_of_ownership(page, out.get("cost_of_ownership.csv", pd.DataFrame()), out["implementation_cost.csv"], monthly, orders,
                       now_row)  # fmt: skip
    contributions(page, daily, monthly)
    comparisons_part(page, out.get("comparisons.csv", pd.DataFrame()), out.get("comparisons_daily.csv", pd.DataFrame()),
                     out.get("comparison_effects.csv", pd.DataFrame()), out.get("comparison_fees.csv", pd.DataFrame()),
                     out.get("comparison_regions.csv", pd.DataFrame()), out.get("comparison_market.csv", pd.DataFrame()))
    lookthrough(page, out)
    risk_view(page, out, _read("simulation_bootstrap.csv", config.ROOT / "mandate"), monthly)
    factor_view(page, out["factor_loadings.csv"], out["factor_rolling.csv"], daily["date"].iloc[-1])
    _attribution(page, out.get("attribution.csv", pd.DataFrame()), daily["date"].iloc[-1])
    allocation = pd.read_csv(config.ROOT / "mandate" / "allocation_check_results.csv")
    selection = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv")
    simulated = {name: _read(f"simulation_{name}.csv", config.ROOT / "mandate") for name in ("bootstrap", "history", "paths")}
    correlation = (_read("sleeve_correlation.csv", config.ROOT / "mandate"), out.get("etf_correlation.csv", pd.DataFrame()))
    us_test = _read("allocation_check_us_results.csv", config.ROOT / "mandate")
    not_done = None if not len(us_test) else {
        "us_test": us_test, "daily": daily, "fund": references.alternative_fund()[0], "period": _test_period(),
        "added": _first_commit_day(ADDED_WITH, _built(now_row)),
        "periods": _read("allocation_check_us_periods.csv", config.ROOT / "mandate"),
        "history": _read("allocation_check_history.csv", config.ROOT / "mandate"),
        "history_windows": _read("allocation_check_history_windows.csv", config.ROOT / "mandate")}  # fmt: skip
    method(page, allocation, selection, _rules_html(), out["sources.csv"], simulated["bootstrap"], correlation,
           _read("controls.csv", config.METHOD_DIR), not_done)  # fmt: skip
    simulations(page, simulated["history"], simulated["paths"], monthly)
    reports = {p.stem: p.read_text(encoding="utf-8") for p in sorted(config.CYCLES_DIR.glob("*.md"))} if config.CYCLES_DIR.exists() else {}
    log(page, monthly, notes_module.read(), reports, orders, out.get("departures.csv", pd.DataFrame()),
        _next_cycle_day(now_row), _quarterly_issues(), now_row)  # fmt: skip
    _check_roles(page.charts, palette)
    glossary = "".join(f"<dt>{_esc(a)}</dt><dd>{_esc(b)}</dd>" for a, b in terms())
    page.add("glossary", f'<div class="wide"><dl class="terms">{glossary}</dl></div>')
    page.views(_part_leads())
    numbers = _number(page.sections)
    _number_notes(page.sections)
    # The guide to the dashboard is built with it, and the build stops when a part of the page has no entry in it.
    guide_module.write(page.sections, numbers, VIEWS, terms(), _built(now_row), out_dir)

    first = orders["date"].min() if len(orders) else None
    tabs = "".join(f'<button type="button" data-view="{v}" aria-selected="false">{_esc(t)}</button>' for v, t in VIEWS)
    sections = []
    for v, t in VIEWS:
        sections.append(f'<section class="view" id="view-{v}" aria-label="{_esc(t)}"><p class="ch-view-lead">{_esc(VIEW_LEADS[v])}</p>'
                        f'<div class="grid">{"".join(page.sections[v])}</div></section>')  # fmt: skip
    data = {"palette": palette, "charts": page.charts, "views": [{"id": v, "title": t} for v, t in VIEWS]}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    css = _palette_css(palette) + (config.SITE_DIR / "style.css").read_text()
    script = (config.SITE_DIR / "app.js").read_text()
    since = f" since {fmt.day_words(first)}" if first else ""
    lead = (f"A real-money portfolio run under written rules{since}, with a target of 70 per cent in a global equity ETF "
            "and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. Every "
            "figure of the record is computed from the ledger and the issuers' published data.")  # fmt: skip
    menu = quarterly_module.site_menu()
    documents = (f'<a href="{config.REPOSITORY_URL}/blob/main/rules/RULES.md">Rules</a>'
                 f'<a href="{config.REPOSITORY_URL}/blob/main/mandate/MANDATE.md">Mandate</a>'
                 '<a href="guide/guide.pdf">Guide to the dashboard (PDF)</a>'
                 f'<a href="{config.REPOSITORY_URL}">Code on GitHub</a>')  # fmt: skip
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rules-based portfolio</title>
<link rel="icon" href="{FAVICON_URL}" type="image/svg+xml">
<meta name="description" content="{_esc(DESCRIPTION)}">
{_link_preview()}<style>
{css}</style>
<script src="{PLOTLY}" integrity="{PLOTLY_INTEGRITY}" crossorigin="anonymous" defer></script>
{config.COUNTER}
</head>
<body>
<header class="ch-band"><div class="ch-band__in">
<a class="ch-word" href="{SITE_URL}">Carlo Hofer</a>
<div class="ch-menu" role="navigation" aria-label="Site">{menu}</div>
</div></header>
<header class="ch-hero"><div>
<p class="ch-back"><a href="{PROJECT_PAGE_URL}">&larr; Rules-based portfolio</a></p>
<p class="ch-over">Portfolio in practice</p>
<h1>Rules-based portfolio</h1>
<p class="ch-lead">{_esc(lead)}</p>
<div class="ch-meta"><span>{_esc(_stamp(now_row))}</span><span>Last build: {_esc(fmt.day_words(_built(now_row)))}</span></div>
<div class="ch-docs">{documents}</div>
</div></header>
<div class="ch-tabs" role="navigation" aria-label="Views"><div>{tabs}</div></div>
<main class="wrap">
{"".join(sections)}
</main>
<footer><div class="wrap">
<p>Returns are in euro and valued at the issuers' net asset values, after costs. They are time-weighted, except the money-weighted return of the Overview and the monthly table. A record of five to ten years cannot show that one set of rules is better than another, so the returns are not offered as evidence for the rules. Past performance is no guide to future returns.</p>
{_colophon(now_row)}
</div></footer>
<script type="application/json" id="dashboard-data">{payload}</script>
<script>
{script}</script>
</body>
</html>
"""
    target = (out_dir or config.ROOT) / "index.html"
    target.write_text(document, encoding="utf-8")
    (target.parent / ".nojekyll").write_text("")
    return target
