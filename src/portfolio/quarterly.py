"""The quarterly report: one page for each calendar quarter, quarterly/YYYY-QN.html, and its archival PDF.

An issue is built once, from the committed tables at a named commit, and never rebuilt: the dashboard moves
on and the issue stays as it was published. A correction is a dated erratum in the next issue. The page is
printed once to an A4 PDF, quarterly/YYYY-QN_<print date>.pdf, with the print rules of the page's stylesheet,
so the PDF carries the page's text. The look follows section 11 of the house standard: the period, the stamp
and the basis first, then the exhibits, the commentary, the monthly notes as issued, the closing sentence and
the terms. Charts are static SVG drawn at build, twice: at the A4 text width and at a phone's.

The commentary, quarterly/YYYY-QN-commentary.txt, is written by hand after the quarter: 150 to 300 words under
the monthly note's rules, with no figure that the issue does not show. An issue is not built without it, nor
without the monthly note of each cycle day in the quarter.

check() runs in the release check: each issue must come out byte for byte from its commit, and each PDF must
carry the page's words, the author's name and no other author or producer than the printing tool.
"""

from __future__ import annotations

import html
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

from . import config
from . import formatting as fmt
from . import notes as notes_module
from . import trading_days

FOLDER = "quarterly"
ORDINAL = {1: "first", 2: "second", 3: "third", 4: "fourth"}
WORDS = (150, 300)
AUTHOR = "Carlo Hofer"
PROJECT_URL = "https://www.carlohofer.com/projects/rules-based-portfolio/"
SITE_URL = "https://www.carlohofer.com/"
CLOSING = ("A record of five to ten years cannot show that one set of rules is better than another, so the returns "
           "are not offered as evidence for the rules.")  # fmt: skip
SANS = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif"
INK, INK2, META, FRAME, GRID, NAVY = "#262b33", "#5d6470", "#6b7280", "#cfcfcf", "#e5e5e5", "#16213a"
REF_A, REF_B, BLEND, EQUITY_HUE = "#6e6e6e", "#a3a3a3", "#bdbdbd", "#24599e"
BAND_FILL = "rgba(36,89,158,0.10)"
# The two drawings of each chart: the A4 text width (174 mm) and about 90 mm, for a phone.
WIDE, NARROW = 658, 340
# The fields of the PDF's document information: the title and dates, the author, and the printing tool.
INFO_FIELDS = {"Title", "Author", "Creator", "Producer", "CreationDate", "ModDate"}
DATED = re.compile(r"^Dated: (\d{4}-\d{2}-\d{2})$")


class ReportError(ValueError):
    """An issue that cannot be built or does not pass its checks. The message names the issue and the fault."""


# Quarters ------------------------------------------------------------------------------------------


def parse_quarter(text: str) -> pd.Period:
    m = re.fullmatch(r"(\d{4})-Q([1-4])", text)
    if not m:
        raise ReportError(f"{text}: a quarter is written YYYY-QN, for example 2026-Q4")
    return pd.Period(f"{m.group(1)}Q{m.group(2)}", "Q")


def quarter_name(quarter: pd.Period) -> str:
    """'fourth quarter 2026'."""
    return f"{ORDINAL[quarter.quarter]} quarter {quarter.year}"


def label(quarter: pd.Period) -> str:
    """'2026-Q4', the name of the files."""
    return f"{quarter.year}-Q{quarter.quarter}"


def _words_day(day) -> str:
    return fmt.day_words(day)


def _period_words(first: pd.Timestamp, last: pd.Timestamp) -> str:
    """'8 October to 31 December 2026', the year once when both ends share it."""
    if first.year == last.year:
        return f"{first.day} {first.strftime('%B')} to {last.day} {last.strftime('%B %Y')}"
    return f"{_words_day(first)} to {_words_day(last)}"


# The commentary --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Commentary:
    dated: date
    paragraphs: tuple


def parse_commentary(path: Path, quarter: pd.Period) -> Commentary:
    name = f"{FOLDER}/{Path(path).name}"
    if not Path(path).exists():
        raise ReportError(f"{name} is missing: an issue is not built without the commentary")
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    dated = DATED.match(lines[0].strip()) if lines else None
    if not dated:
        raise ReportError(f"{name}: the first line must read 'Dated: YYYY-MM-DD'")
    day = pd.Timestamp(dated.group(1)).date()
    if day <= quarter.end_time.date():
        raise ReportError(f"{name}: the commentary is dated {day}, inside the quarter it looks back on")
    blocks, current = [], []
    for line in lines[1:] + [""]:
        if line.strip():
            current.append(line.strip())
        elif current:
            blocks.append(" ".join(current))
            current = []
    body = "\n\n".join(blocks)
    count = notes_module.words(body)
    if not WORDS[0] <= count <= WORDS[1]:
        raise ReportError(f"{name}: the commentary has {count} words, and a commentary has {WORDS[0]} to {WORDS[1]} words")
    forward = notes_module.FORWARD.search(body)
    if forward:
        raise ReportError(f"{name}: '{forward.group(0)}' looks forward, and the commentary looks back")
    if notes_module.DRAFT_MARK in body:
        raise ReportError(f"{name}: the draft's placeholder is still in the commentary")
    return Commentary(day, tuple(blocks))


def _figures_in(text: str) -> list:
    """The figures of a text: numbers with their sign and per cent sign, as written."""
    return re.findall(r"[+−-]?\d+(?:[.,]\d+)?%?", text)


# Charts ----------------------------------------------------------------------------------------------


def _n(x: float) -> str:
    """A coordinate, to one decimal, the same on every machine."""
    text = f"{x:.1f}"
    return "0.0" if text == "-0.0" else text


def _nice_step(span: float, target: int = 5) -> float:
    raw = span / max(target, 1)
    for step in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50):
        if step >= raw:
            return step
    return 100.0


def _tick_text(value: float, step: float) -> str:
    decimals = 0 if step >= 1 else (1 if step >= 0.1 else 2)
    text = f"{value:.{decimals}f}"
    if text.startswith("-") and float(text) == 0:
        text = text[1:]
    return text.replace("-", fmt.MINUS)


def _legend(items, width: float, top: float, font: float) -> tuple:
    """Legend items in rows below the plot: a short line in the series' colour and its name."""
    parts, x, y = [], 0.0, top
    for name, colour, dash in items:
        item = 22 + 0.56 * font * len(name) + 14
        if x > 0 and x + item > width:
            x, y = 0.0, y + font * 1.5
        dashing = ' stroke-dasharray="4 3"' if dash else ""
        parts.append(f'<line x1="{_n(x)}" y1="{_n(y - font * 0.35)}" x2="{_n(x + 16)}" y2="{_n(y - font * 0.35)}" '
                     f'stroke="{colour}" stroke-width="2"{dashing}/>'
                     f'<text x="{_n(x + 22)}" y="{_n(y)}" fill="{INK2}" font-size="{_n(font)}">{html.escape(name)}</text>')  # fmt: skip
        x += item
    return "".join(parts), y


def line_chart(series, ticks, width: int, y_title: str, y_range=None, band=None, lines=(), title: str = "") -> str:
    """A static line chart: series is a list of (name, dates, values, colour, line width, dashed); ticks are
    (date, label) pairs on the date axis; band is (low, high) shaded; lines are (value, colour, label)."""
    font, tick_font = 12.0, (10.7 if width >= WIDE else 11.0)
    left, right, top = 46.0, 12.0, 10.0
    plot_h = 190.0 if width >= WIDE else 220.0  # tall enough on a phone for a turned axis title
    first = min(d for _, ds, _, _, _, _ in series for d in ds)
    last = max(d for _, ds, _, _, _, _ in series for d in ds)
    span_days = max((last - first).days, 1)
    values = [v for _, _, vs, _, _, _ in series for v in vs]
    low, high = (min(values), max(values)) if y_range is None else y_range
    if y_range is None:
        pad = (high - low) * 0.08 or 1.0
        low, high = low - pad, high + pad
    step = _nice_step(high - low)
    first_tick = step * int(low // step + (0 if low % step == 0 else 1))
    plot_w = width - left - right

    def x_of(day):
        return left + plot_w * (day - first).days / span_days

    def y_of(value):
        return top + plot_h * (high - value) / (high - low)

    parts = [f'<rect x="{_n(left)}" y="{_n(top)}" width="{_n(plot_w)}" height="{_n(plot_h)}" fill="none"/>']
    if band:
        parts.append(f'<rect x="{_n(left)}" y="{_n(y_of(band[1]))}" width="{_n(plot_w)}" '
                     f'height="{_n(y_of(band[0]) - y_of(band[1]))}" fill="{BAND_FILL}"/>')  # fmt: skip
    tick = first_tick
    while tick <= high + 1e-9:
        y = y_of(tick)
        parts.append(f'<line x1="{_n(left)}" y1="{_n(y)}" x2="{_n(width - right)}" y2="{_n(y)}" stroke="{GRID}" stroke-width="1"/>'
                     f'<text x="{_n(left - 6)}" y="{_n(y + tick_font * 0.35)}" text-anchor="end" fill="{META}" '
                     f'font-size="{_n(tick_font)}">{_tick_text(tick, step)}</text>')  # fmt: skip
        tick = round(tick + step, 10)
    for value, colour, text in lines:
        y = y_of(value)
        parts.append(f'<line x1="{_n(left)}" y1="{_n(y)}" x2="{_n(width - right)}" y2="{_n(y)}" stroke="{colour}" stroke-width="1"/>')
        if text:
            parts.append(f'<text x="{_n(width - right)}" y="{_n(y - 4)}" text-anchor="end" fill="{INK2}" '
                         f'font-size="{_n(tick_font)}">{html.escape(text)}</text>')  # fmt: skip
    parts.append(f'<line x1="{_n(left)}" y1="{_n(top + plot_h)}" x2="{_n(width - right)}" y2="{_n(top + plot_h)}" '
                 f'stroke="{FRAME}" stroke-width="1"/>')  # fmt: skip
    for day, text in ticks:
        x = x_of(day)
        anchor = "start" if x - left < 20 else ("end" if width - right - x < 20 else "middle")
        parts.append(f'<text x="{_n(x)}" y="{_n(top + plot_h + tick_font + 6)}" text-anchor="{anchor}" fill="{META}" '
                     f'font-size="{_n(tick_font)}">{html.escape(text)}</text>')  # fmt: skip
    for _, dates, vals, colour, stroke, dash in reversed(series):
        points = " ".join(f"{_n(x_of(d))},{_n(y_of(v))}" for d, v in zip(dates, vals))
        dashing = ' stroke-dasharray="4 3"' if dash else ""
        if len(dates) == 1:
            parts.append(f'<circle cx="{_n(x_of(dates[0]))}" cy="{_n(y_of(vals[0]))}" r="3" fill="{colour}"/>')
        else:
            parts.append(f'<polyline points="{points}" fill="none" stroke="{colour}" stroke-width="{_n(stroke)}" '
                         f'stroke-linejoin="round"{dashing}/>')  # fmt: skip
    parts.append(f'<text x="12" y="{_n(top + plot_h / 2)}" transform="rotate(-90 12 {_n(top + plot_h / 2)})" '
                 f'text-anchor="middle" fill="{INK2}" font-size="{_n(font)}">{html.escape(y_title)}</text>')  # fmt: skip
    legend, bottom = _legend([(n, c, d) for n, _, _, c, _, d in series if n], width - left, top + plot_h + tick_font + 30, font)
    if legend:
        parts.append(f'<g transform="translate({_n(left)} 0)">{legend}</g>')
    height = bottom + 8 if legend else top + plot_h + tick_font + 14
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {_n(height)}" role="img" '
            f'aria-label="{html.escape(title)}" font-family="{SANS}">{"".join(parts)}</svg>')  # fmt: skip


def _drawings(make) -> str:
    return f'<div class="rp-wide">{make(WIDE)}</div><div class="rp-narrow">{make(NARROW)}</div>'


# Tables ----------------------------------------------------------------------------------------------


def _table(head, rows, numeric_from=1, rounding=False) -> str:
    cells = "".join(f'<th class="num">{html.escape(c)}</th>' if i >= numeric_from else f"<th>{html.escape(c)}</th>"
                    for i, c in enumerate(head))  # fmt: skip
    body = "".join("<tr>" + "".join(f'<td class="num">{html.escape(str(v))}</td>' if i >= numeric_from
                                    else f'<th scope="row">{html.escape(str(v))}</th>' for i, v in enumerate(r)) + "</tr>"
                   for r in rows)  # fmt: skip
    note = '<p class="basis">Due to rounding, the parts may not sum to 100 per cent.</p>' if rounding else ""
    return f'<div class="rp-tw"><div class="rp-scroll"><table><thead><tr>{cells}</tr></thead><tbody>{body}</tbody></table></div></div>{note}'


@dataclass
class Exhibit:
    kind: str  # "figure" or "table"
    title: str
    caption: str
    body: str
    sources: tuple
    basis: str = ""
    source_text: str = "the issuers' published net asset values and author's calculations"
    frequency: str = "Daily"


# The issue -------------------------------------------------------------------------------------------


class Issue:
    """Everything an issue shows, read from the tables of one tree of the repository."""

    def __init__(self, root: Path, quarter: pd.Period, commit: str):
        self.root, self.quarter, self.commit = Path(root), quarter, commit
        out = self.root / "outputs"
        read = lambda name, folder=out: pd.read_csv(folder / name) if (folder / name).exists() else pd.DataFrame()  # noqa: E731
        self.quarters = read("quarters.csv")
        rows = self.quarters[self.quarters["quarter"] == str(quarter)] if len(self.quarters) else self.quarters
        if not len(rows):
            raise ReportError(f"{label(quarter)}: outputs/quarters.csv has no row for the quarter")
        self.row = rows.iloc[0]
        if self.row["complete"] != "yes":
            raise ReportError(f"{label(quarter)}: the quarter is not complete in the record at commit {commit}")
        self.number = int(self.quarters.index[self.quarters["quarter"] == self.row["quarter"]][0]) + 1
        self.daily = read("portfolio_daily.csv")
        self.daily["date"] = pd.to_datetime(self.daily["date"])
        if self.daily["date"].max() <= quarter.end_time:
            raise ReportError(f"{label(quarter)}: the record at commit {commit} does not run past the quarter's end, so "
                              "a value of its last days may not be published yet")  # fmt: skip
        self.first, self.last = pd.Timestamp(self.row["first_day"]), pd.Timestamp(self.row["last_day"])
        before = self.daily[self.daily["date"] < self.first]
        self.start = before.iloc[-1] if len(before) else self.daily.iloc[0]
        self.days = self.daily[(self.daily["date"] >= self.first) & (self.daily["date"] <= self.last)]
        self.monthly = read("metrics_monthly.csv")
        self.orders = read("orders.csv")
        self.departures = read("departures.csv")
        self.costs = read("costs_monthly.csv")
        self.ownership = read("cost_of_ownership.csv")
        self.components = read("risk_components.csv")
        self.summary = read("risk_summary.csv")
        self.currency = read("lookthrough_currency.csv")
        self.attribution = read("attribution.csv")
        self.now = read("allocation_now.csv")
        self.bootstrap = read("simulation_bootstrap.csv", self.root / "mandate")
        self.built = pd.Timestamp(self.now.iloc[0]["positions_as_of"])
        self.notes = [n for n in notes_module.read(self.root / "notes") if pd.Period(n.month, "M").asfreq("Q") == quarter]
        self._require_notes()
        self.commentary = parse_commentary(self.root / FOLDER / f"{label(quarter)}-commentary.txt", quarter)
        # The first issue opens on the day of the first purchase, every later one on the quarter's first day.
        self.issue_start = pd.Timestamp(self.days["date"].iloc[0]) if self.number == 1 else pd.Timestamp(quarter.start_time.date())

    def _require_notes(self):
        first_purchase = pd.Timestamp(self.daily["date"].iloc[1]).date() if len(self.daily) > 1 else None
        due = []
        for month in pd.period_range(self.quarter.asfreq("M", "s"), self.quarter.asfreq("M", "e"), freq="M"):
            day = trading_days.cycle_day(month.year, month.month)
            if first_purchase and first_purchase < day <= self.last.date():
                due.append(str(month))
        have = {n.month for n in self.notes}
        missing = [m for m in due if m not in have]
        if missing:
            raise ReportError(f"{label(self.quarter)}: the monthly note of {', '.join(missing)} is missing from notes/")

    # The month ends of the quarter, with the start, for the tables under the charts.
    def _month_ends(self) -> pd.DataFrame:
        frame = self.days.copy()
        frame["month"] = frame["date"].dt.to_period("M")
        ends = frame.groupby("month").tail(1)
        return ends

    def _ticks(self, from_start: bool = False):
        """The date axis: the first day drawn and each month end."""
        first = pd.Timestamp(self.start["date"]) if from_start else pd.Timestamp(self.days["date"].iloc[0])
        ends = [d for d in self._month_ends()["date"] if d > first]
        return [(d, f"{d.day} {d.strftime('%b')}") for d in [first] + ends]

    def _source(self, files, frequency="Daily") -> str:
        names = ", ".join(f"<code>{html.escape(f)}</code>" for f in files)
        return (f"{frequency}, {html.escape(self.period_words())}, EUR. {names} at commit <code>{html.escape(self.commit)}</code>.")

    def period_words(self) -> str:
        return _period_words(self.issue_start, pd.Timestamp(self.quarter.end_time.date()))

    # Exhibits ------------------------------------------------------------------------------------

    def key_figures(self) -> Exhibit:
        r = self.row
        blend_from = (f", from {_words_day(r['index_blend_from'])}" if pd.notna(r["index_blend_from"])
                      and pd.Timestamp(r["index_blend_from"]) > pd.Timestamp(self.start["date"]) else "")  # fmt: skip
        mw_since = "Return, money-weighted" + (", per year" if pd.notna(r["money_weighted_per_year_since_start"]) else "")
        since_mw = r["money_weighted_per_year_since_start"] if pd.notna(r["money_weighted_per_year_since_start"]) else r["return_money_weighted_since_start"]
        rows = [["Return, time-weighted", fmt.pct(r["return_time_weighted"], True), fmt.pct(r["return_time_weighted_since_start"], True)],
                [mw_since if pd.notna(r["money_weighted_per_year_since_start"]) else "Return, money-weighted",
                 fmt.pct(r["return_money_weighted"], True), fmt.pct(since_mw, True)],
                ["Reference portfolio A", fmt.pct(r["return_reference_a"], True), fmt.pct(r["return_reference_a_since_start"], True)],
                ["Reference portfolio B", fmt.pct(r["return_reference_b"], True), fmt.pct(r["return_reference_b_since_start"], True)],
                [f"Index blend{blend_from}", fmt.pct(r["return_index_blend"], True), fmt.pct(r["return_index_blend_since_start"], True)],
                ["Worst fall", fmt.pct(r["worst_fall"]), fmt.pct(r["worst_fall_to_date"])],
                ["Implementation cost", fmt.bps(r["implementation_cost_bps"]), fmt.bps(r["implementation_cost_since_start_bps"])],
                ["Orders against the allowance", f"{int(r['orders'])} of {int(r['allowance'])}",
                 f"{int(r['orders_since_start'])} of {int(r['allowance_since_start'])}"]]  # fmt: skip
        caption = ("The quarter and the record since the first purchase, to the last valuation day of the quarter, in per "
                   "cent unless stated. The worst fall is in per cent below the previous peak, and the implementation cost "
                   "is positive when the portfolio trails reference portfolio A.")  # fmt: skip
        return Exhibit("table", f"Key figures, {self.period_words()}", caption,
                       _table(["", "The quarter", "Since the first purchase"], rows),
                       ("outputs/quarters.csv",), "Real money. Time-weighted unless stated, net of trading costs, not "
                       "annualised for periods under a year.", frequency="To the last valuation day of the quarter")  # fmt: skip

    def growth(self) -> Exhibit:
        start_day = pd.Timestamp(self.start["date"])
        frame = self.daily[(self.daily["date"] >= start_day) & (self.daily["date"] <= self.last)].copy()
        frame["date"] = pd.to_datetime(frame["date"])
        base = float(self.start["growth_portfolio"])
        lines, table_columns = [], []
        for name, column, colour, stroke in (("Portfolio", "growth_portfolio", NAVY, 2.0),
                                             ("Reference A, same rules", "growth_reference_a", REF_A, 1.5),
                                             ("Reference B, 70/30 each cycle day", "growth_reference_b", REF_B, 1.5),
                                             ("Index blend", "growth_index_blend", BLEND, 1.5)):  # fmt: skip
            data = frame[["date", column]].dropna()
            if not len(data):
                continue
            first = data.iloc[0]
            if first["date"] == start_day:
                scale = 100 / float(first[column])
            else:  # the index blend starts later, at the portfolio's level on its first day
                level = float(frame.loc[frame["date"] == first["date"], "growth_portfolio"].iloc[0]) / base * 100
                scale = level / float(first[column])
            values = [float(v) * scale for v in data[column]]
            lines.append((name, list(data["date"]), values, colour, stroke, False))
            table_columns.append((name, dict(zip(data["date"], values))))
        ends = [start_day] + list(self._month_ends()["date"])
        rows = [[("Start, " + d.strftime("%Y-%m-%d")) if d == start_day else d.strftime("%Y-%m-%d")] +
                [fmt.index(c.get(d)) if d in c else "n/a" for _, c in table_columns] for d in ends]  # fmt: skip
        body = _drawings(lambda w: line_chart(lines, self._ticks(True), w, "Growth of 100", title="Growth of 100"))
        body += _table(["Date"] + [n.split(",")[0] for n, _ in table_columns], rows)
        caption = ("Each series is 100 at the start of the quarter, with contributions removed. The index blend joins at "
                   "its first month end, at the portfolio's level on that day.")  # fmt: skip
        return Exhibit("figure", f"Growth of 100, {self.period_words()}", caption, body, ("outputs/portfolio_daily.csv",),
                       "Real money for the portfolio. The reference portfolios are computed from the same contributions "
                       "and prices without costs.")  # fmt: skip

    def allocation(self) -> Exhibit:
        end = self.days.iloc[-1]
        low, high = config.BAND
        rows = [["Equity", fmt.pct(end["weight_equity"]), fmt.pct(config.TARGET[config.EQUITY]), f"{low * 100:.0f} to {high * 100:.0f}"],
                ["Bonds", fmt.pct(end["weight_bonds"]), fmt.pct(config.TARGET[config.BONDS]), "n/a"],
                ["Cash", fmt.pct(end["weight_cash"]), fmt.pct(0.0), "n/a"]]  # fmt: skip
        caption = f"Per cent of the portfolio at the close of {_words_day(end['date'])}, the last valuation day of the quarter."
        return Exhibit("table", "Allocation at the quarter end against the target and the band", caption,
                       _table(["Sleeve", "Weight", "Target", "Band"], rows, rounding=True), ("outputs/portfolio_daily.csv",))

    def weight(self) -> Exhibit:
        data = self.days[["date", "weight_equity"]].dropna()
        low, high = config.BAND
        series = [("Equity weight", list(data["date"]), [float(v) * 100 for v in data["weight_equity"]], EQUITY_HUE, 2.0, False)]
        lo = min(low * 100 - 3, min(v for v in series[0][2]) - 1)
        hi = max(high * 100 + 3, max(v for v in series[0][2]) + 1)
        body = _drawings(lambda w: line_chart(series, self._ticks(), w, "Per cent of the portfolio", y_range=(lo, hi),
                                              band=(low * 100, high * 100), lines=[(config.TARGET[config.EQUITY] * 100, INK, "")],
                                              title="Equity weight in its band"))  # fmt: skip
        ends = self._month_ends()
        body += _table(["Month end", "Equity", "Bonds", "Cash"], [[d.strftime("%Y-%m-%d"), fmt.pct(e), fmt.pct(b), fmt.pct(c)]
                       for d, e, b, c in zip(ends["date"], ends["weight_equity"], ends["weight_bonds"], ends["weight_cash"])],
                       rounding=True)  # fmt: skip
        caption = (f"The equity weight at each valuation day, against its target weight of 70 per cent, the dark line, and "
                   f"the band of rule 5 from {low * 100:.0f} to {high * 100:.0f} per cent, shaded. Outside the band on a "
                   "cycle day, the portfolio is brought back to 70/30.")  # fmt: skip
        return Exhibit("figure", f"Equity weight in its band, {self.period_words()}", caption, body, ("outputs/portfolio_daily.csv",))

    def orders_table(self) -> Exhibit:
        frame = self.orders.copy()
        if len(frame):
            frame["date"] = pd.to_datetime(frame["date"])
            in_quarter = frame[(frame["date"] >= self.quarter.start_time) & (frame["date"] <= self.quarter.end_time)]
        else:
            in_quarter = pd.DataFrame(columns=["date", "sleeve", "side", "rule", "inside_rule_7_window", "bid_and_ask_recorded"])
        rule = {"start": "first purchase", "4": "4, top-up", "5": "5, band", "4+5": "4 and 5"}
        rows = [[d.strftime("%Y-%m-%d"), s.capitalize(), side, rule.get(str(r), str(r)), w, q]
                for d, s, side, r, w, q in zip(in_quarter["date"], in_quarter["sleeve"], in_quarter["side"], in_quarter["rule"],
                                               in_quarter["inside_rule_7_window"], in_quarter["bid_and_ask_recorded"])]  # fmt: skip
        departures = self.departures.copy()
        if len(departures):
            departures["date"] = pd.to_datetime(departures["date"])
            departures = departures[(departures["date"] >= self.quarter.start_time) & (departures["date"] <= self.quarter.end_time)]
        if len(departures):
            gone = "The departures from the rules in the quarter are in the table after this one."
        else:
            gone = "No order departed from the rules in the quarter."
        caption = (f"Every order of the quarter, {len(rows)} against the allowance of {int(self.row['allowance'])}, "
                   f"with the rule that produced it and the checks of rule 7. {gone}")  # fmt: skip
        body = _table(["Date", "Sleeve", "Side", "Rule", "Inside 15:45 to 17:00", "Bid and ask recorded"], rows, numeric_from=9)
        return Exhibit("table", "The quarter's orders against the rules", caption, body, ("outputs/orders.csv",),
                       source_text="the ledger, from the broker's confirmations", frequency="Each order")

    def departures_table(self):
        departures = self.departures.copy()
        if not len(departures):
            return None
        departures["date"] = pd.to_datetime(departures["date"])
        departures = departures[(departures["date"] >= self.quarter.start_time) & (departures["date"] <= self.quarter.end_time)]
        if not len(departures):
            return None
        rows = [[d.strftime("%Y-%m-%d"), r, w, c] for d, r, w, c in
                zip(departures["date"], departures["rule"], departures["what_happened"], departures["consequence"])]  # fmt: skip
        return Exhibit("table", "Departures from the rules in the quarter", "Each departure with its rule and its consequence. "
                       "The record keeps every order as it was placed.", _table(["Date", "Rule", "What happened", "Consequence"],
                       rows, numeric_from=9), ("outputs/departures.csv",), source_text="the ledger", frequency="Each departure")  # fmt: skip

    def costs_table(self) -> Exhibit:
        frame = self.costs.copy()
        months = [str(m) for m in pd.period_range(self.quarter.asfreq("M", "s"), self.quarter.asfreq("M", "e"), freq="M")]
        frame = frame[frame["month"].isin(months)] if len(frame) else frame
        rows = [[m, fmt.bps(c, False), fmt.bps(h, False), fmt.bps(x, False), fmt.bps(p, False), fmt.bps(t, False)]
                for m, c, h, x, p, t in zip(frame["month"], frame["commissions_bps"], frame["half_spread_bps"],
                                            frame["currency_conversion_bps"], frame["execution_against_nav_bps"],
                                            frame["implementation_cost_month_bps"])]  # fmt: skip
        weighted = self.ownership[self.ownership["sleeve"] == "portfolio"]
        ongoing = (f" The two ETFs' ongoing costs, their TER plus their transaction costs, come to "
                   f"{fmt.bps(weighted.iloc[0]['ongoing_costs'] * 1e4, False)} a year at the portfolio's weights, inside "
                   "their net asset values, so the table does not hold them.") if len(weighted) else ""  # fmt: skip
        caption = ("Basis points of the portfolio's value on the day of each order. The price paid against net asset value "
                   "is what the month's implementation cost leaves after the other three, so the four add up to it." + ongoing)  # fmt: skip
        body = _table(["Month", "Commissions", "Half-spread", "Conversion", "Price against net asset value",
                       "Implementation cost"], rows)  # fmt: skip
        return Exhibit("table", f"Costs by month and source, {self.period_words()}", caption, body,
                       ("outputs/costs_monthly.csv", "outputs/cost_of_ownership.csv"), "Real money. Negative when a source "
                       "added to the return.", source_text="the ledger, the issuers' net asset values and key information "
                       "documents, and author's calculations", frequency="Monthly")  # fmt: skip

    def drawdown(self) -> Exhibit:
        data = self.days[["date", "drawdown_portfolio"]].dropna()
        series = [("", list(data["date"]), [float(v) * 100 for v in data["drawdown_portfolio"]], NAVY, 1.8, False)]
        limits = [(-config.RISK_LIMIT_TEST * 100, FRAME, "Test limit, 35%"), (-40.0, FRAME, "Outer bound, 40%")]
        body = _drawings(lambda w: line_chart(series, self._ticks(), w, "Per cent below the peak", y_range=(-43.0, 1.0),
                                              lines=limits, title="Fall from the previous peak"))  # fmt: skip
        caption = (f"The fall below the previous peak at each valuation day, with contributions removed, against the "
                   f"mandate's test limit of 35 per cent and its outer bound of 40 per cent. The worst in the quarter is "
                   f"{fmt.pct(self.row['worst_fall'])}.")  # fmt: skip
        return Exhibit("figure", f"Fall from the previous peak, {self.period_words()}", caption, body,
                       ("outputs/portfolio_daily.csv",), "Real money. Daily values, which miss falls that reverse within a day.")

    def lookthrough_table(self) -> Exhibit:
        frame = self.components
        rows = [[c, fmt.pct(w), fmt.pct(r), fmt.pct(v)] for c, w, r, v in
                zip(frame["component"], frame["weight"], frame["risk_contribution"], frame["estimated_volatility"])]  # fmt: skip
        s = self.summary.iloc[0]
        caption = (f"The look-through of the two ETFs at the weights of {_words_day(s['weights_as_of'])}: the four equity "
                   "regions, the bond sleeve's three maturity groups and cash, with each component's share of the "
                   f"estimated variance on the 120 months from {pd.Period(s['window_start'], 'M').strftime('%B %Y')} to "
                   f"{pd.Period(s['window_end'], 'M').strftime('%B %Y')}.")  # fmt: skip
        return Exhibit("table", "The look-through by component, with its share of the estimated variance", caption,
                       _table(["Component", "Weight", "Share of the estimated variance", "Volatility, a year"], rows, rounding=True),
                       ("outputs/risk_components.csv",), "Weights from the issuers' holdings files. The shares of the variance "
                       "are estimated on index returns, at today's weights, and not the record.",
                       source_text="the issuers' holdings files, MSCI's regional indices, the ECB's yield curve and author's calculations",
                       frequency="At the quarter end, on monthly returns")  # fmt: skip

    def currency_table(self) -> Exhibit:
        frame = self.currency
        rows = [[c, fmt.pct(p), fmt.pct(e), fmt.pct(b), fmt.pct(x)] for c, p, e, b, x in
                zip(frame["currency"], frame["share_of_portfolio"], frame["from_equity_sleeve"], frame["from_bond_sleeve"], frame["from_cash"])]  # fmt: skip
        as_of = frame["weights_as_of"].iloc[0] if "weights_as_of" in frame and len(frame) else self.last
        caption = (f"Each holding in the currency of its market, at the weights of {_words_day(as_of)}. Neither ETF hedges "
                   "its currencies.")  # fmt: skip
        return Exhibit("table", "Currency exposure, by sleeve", caption,
                       _table(["Currency", "Share of the portfolio", "From the equity sleeve", "From the bond sleeve", "From cash"],
                              rows, rounding=True), ("outputs/lookthrough_currency.csv",), source_text="the issuers' holdings files",
                              frequency="At the quarter end")  # fmt: skip

    def risk_table(self) -> Exhibit:
        s = self.summary.iloc[0]
        split_weight = round(float(self.now.iloc[0]["weight_equity"]) * 20) / 20
        split = f"{round(split_weight * 100)}/{round((1 - split_weight) * 100)}"
        boot = self.bootstrap
        row = boot[(boot["horizon_years"] == 10) & (boot["block_months"] == 12) & (boot["split"] == split)] if len(boot) else boot
        rows = [["Estimated volatility, a year", fmt.pct(s["estimated_volatility"])],
                ["Value at risk, one month, historical", fmt.pct(s["value_at_risk_historical"])],
                ["Expected shortfall, one month, historical", fmt.pct(s["expected_shortfall_historical"])],
                ["Value at risk, one month, normal", fmt.pct(s["value_at_risk_normal"])],
                ["Expected shortfall, one month, normal", fmt.pct(s["expected_shortfall_normal"])]]  # fmt: skip
        if len(row):
            rows += [[f"Worst fall over ten years, the bootstrap's median at {split}", fmt.pct(row["median_worst_fall"].iloc[0])],
                     [f"Worst fall over ten years, the bootstrap's 95th percentile at {split}", fmt.pct(row["p95_worst_fall"].iloc[0])]]  # fmt: skip
        months = int(s["calibration_months"]) if pd.notna(s["calibration_months"]) else 0
        if pd.notna(s.get("calibration")):
            rows.append(["The forecast's calibration", f"{float(s['calibration']):.2f}"])
        caption = (f"Estimated on index returns, at the look-through weights of {_words_day(s['weights_as_of'])}, and not the "
                   f"record. Value at risk and expected shortfall are losses over one month at 95 per cent: the historical "
                   f"value at risk is the sixth worst of the 120 months and the expected shortfall the mean of those six, "
                   f"and the normal figures are 1.645 times the monthly volatility and the normal tail mean. The worst falls "
                   f"are the bootstrap's figures at the split nearest the equity weight, on the allocation test's returns "
                   f"from February 1999 to December 2025. None is a limit, and none is a reason to sell, under rule 8."
                   + ("" if months >= 12 else " The forecast's calibration is given from the October 2027 month end."))  # fmt: skip
        return Exhibit("table", "Estimated risk at the quarter end", caption, _table(["Estimate", "Value"], rows),
                       ("outputs/risk_summary.csv", "mandate/simulation_bootstrap.csv"),
                       source_text="MSCI's regional indices, the ECB's yield curve, the allocation test's series and author's calculations",
                       frequency="At the quarter end, on monthly returns")  # fmt: skip

    def attribution_table(self):
        frame = self.attribution
        if not len(frame):
            return None
        r = frame.iloc[0]
        if pd.Timestamp(r["period_end"]) > self.last:
            return None
        rows = [["The portfolio against reference portfolio A", fmt.pct(r["portfolio_against_reference_a"], True)],
                ["Drift effect", fmt.pct(r["drift_effect"], True)],
                ["Tracking difference, with the day mismatch", fmt.pct(r["tracking_difference"], True)],
                ["The difference to the index blend", fmt.pct(r["total"], True)]]  # fmt: skip
        caption = (f"From {_words_day(r['period_start'])} to {_words_day(r['period_end'])}, {int(r['months'])} months: "
                   "differences of the returns over the period, so the three parts sum to the total.")  # fmt: skip
        return Exhibit("table", "The difference to the index blend in three parts", caption,
                       _table(["Part", "Return, percentage of the start"], rows), ("outputs/attribution.csv",), frequency="Month ends")

    def exhibits(self) -> list:
        items = [self.key_figures(), self.growth(), self.allocation(), self.weight(), self.orders_table(),
                 self.departures_table(), self.costs_table(), self.drawdown(), self.lookthrough_table(),
                 self.currency_table(), self.risk_table(), self.attribution_table()]  # fmt: skip
        return [e for e in items if e is not None]


# The page --------------------------------------------------------------------------------------------


def _terms(root: Path, text: str) -> list:
    """The README's terms that the issue uses, in the singular or the plural, in the README's order."""
    readme = (root / "README.md").read_text(encoding="utf-8")
    section = readme.split("\n## Terms\n", 1)[1].split("\n## ", 1)[0]
    found = []
    for line in section.splitlines():
        m = re.match(r"^- \*\*(.+?)\*\*: (.+)$", line.strip())
        if m and re.search(r"(?<![\w-])" + re.escape(m.group(1)) + r"(?:s|es)?(?![\w-])", text, re.I):
            found.append((m.group(1)[0].upper() + m.group(1)[1:], m.group(2).replace("`", "")))
    return found


def _errata(root: Path, quarter: pd.Period) -> str:
    path = root / FOLDER / f"{label(quarter)}-errata.csv"
    if not path.exists():
        return ""
    frame = pd.read_csv(path)
    items = " ".join(f"{html.escape(str(r['exhibit']))} of issue {int(r['issue'])}, {html.escape(str(r['figure']))}, read "
                     f"{html.escape(str(r['old']))}, should read {html.escape(str(r['new']))}. Corrected "
                     f"{_words_day(r['corrected'])}." for _, r in frame.iterrows())  # fmt: skip
    return f'<div class="rp-errata"><strong>Errata</strong> {items}</div>'


def build(root: Path, quarter: pd.Period, commit: str) -> str:
    """The page of one issue, from the tables, notes and commentary under root."""
    root = Path(root)
    issue = Issue(root, quarter, commit)
    css = (root / "site" / "report.css").read_text(encoding="utf-8").replace("ISSUE", quarter_name(quarter))
    numbers = {"figure": 0, "table": 0}
    blocks = []
    for e in issue.exhibits():
        numbers[e.kind] += 1
        n = numbers[e.kind]
        basis = f'<p class="basis">{html.escape(e.basis)}</p>' if e.basis else ""
        blocks.append(f'<section class="rp-ex" id="{e.kind}-{n}"><h3>{e.kind.capitalize()} {n} | {html.escape(e.title)}</h3>'
                      f'<p class="cap">{html.escape(e.caption)}</p>{e.body}{basis}'
                      f'<p class="src">Source: {html.escape(e.source_text)}. {issue._source(e.sources, e.frequency)}</p></section>')  # fmt: skip
    q_label, words = label(quarter), quarter_name(quarter)
    title = f"Quarterly report, {words} | Rules-based portfolio"
    stamp = (f"Issue {issue.number} &middot; Figures as of {issue.last.strftime('%Y-%m-%d')} &middot; Built "
             f"{issue.built.strftime('%Y-%m-%d')} from commit {html.escape(commit)} &middot; {config.DASHBOARD_URL}")  # fmt: skip
    first_issue = "the first issue and a part quarter" if issue.number == 1 and issue.issue_start > issue.quarter.start_time else f"issue {issue.number}"
    basis = (f"<dt>Period</dt><dd>{html.escape(issue.period_words())}, {first_issue}</dd>"
             "<dt>Valuation</dt><dd>At the issuers' published net asset values</dd>"
             "<dt>Returns</dt><dd>Time-weighted, with contributions removed, and money-weighted where named</dd>"
             "<dt>Costs</dt><dd>Net of the costs of trading. The ongoing costs of the ETFs are inside their values</dd>"
             "<dt>Currency</dt><dd>Euro</dd>"
             "<dt>Status</dt><dd>A personal portfolio, run under written rules. Not an offer and not advice</dd>")  # fmt: skip
    commentary = "".join(f'<p class="prose">{html.escape(p)}</p>' for p in issue.commentary.paragraphs)
    notes_html = []
    for n in sorted(issue.notes, key=lambda x: x.month):
        text = Path(n.path).read_text(encoding="utf-8").strip().splitlines()
        heading = text[0].lstrip("#").strip()
        paragraphs, current = [], []
        for line in text[1:] + [""]:
            if line.strip():
                current.append(line.strip())
            elif current:
                paragraphs.append(" ".join(current))
                current = []
        notes_html.append(f'<div class="rp-note"><h3>{html.escape(heading)}</h3>'
                          + "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs) + "</div>")  # fmt: skip
    main = (f'<p class="rp-kicker">Rules-based portfolio &middot; Quarterly report</p><h1>{html.escape(issue.period_words())}</h1>'
            f'<p class="rp-stamp">{stamp}</p><dl class="rp-basis">{basis}</dl>{_errata(root, quarter)}'
            + "".join(blocks)
            + f'<h2>Commentary</h2>{commentary}<p class="rp-sign">{AUTHOR}, {_words_day(issue.commentary.dated)}</p>'
            + "<h2>Monthly notes, as issued</h2>" + ("".join(notes_html) if notes_html else '<p class="prose">No cycle day fell in the quarter after the first purchase, so no monthly note was due.</p>')
            + f'<p class="rp-close">{html.escape(CLOSING)}</p>')  # fmt: skip
    plain = re.sub(r"<[^>]+>", " ", main)
    terms = "".join(f"<dt>{html.escape(a)}</dt><dd>{html.escape(b)}</dd>" for a, b in _terms(root, html.unescape(plain)))
    _figures_check(issue, html.unescape(re.sub(r"<[^>]+>", " ", "".join(blocks))))
    built = issue.built.strftime("%Y-%m-%d")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="author" content="{AUTHOR}">
<meta name="issue" content="{q_label}">
<meta name="commit" content="{html.escape(commit)}">
<style>{css}</style>
</head>
<body>
<header class="ch-band"><div class="ch-band__in">
  <a class="ch-word" href="{SITE_URL}">Carlo Hofer</a>
  <div class="ch-menu" role="navigation" aria-label="Site"><a href="{SITE_URL}projects/">Projects</a><a href="{SITE_URL}publications/">Publications</a><a href="{SITE_URL}cv/">CV</a></div>
</div></header>
<p class="ch-back"><a href="{config.DASHBOARD_URL}#log">&larr; Rules-based portfolio, Log</a> &middot; <a href="{PROJECT_URL}">The project</a></p>
<main class="rp">
{main}
<h2>Terms</h2>
<dl class="rp-terms">{terms}</dl>
</main>
<footer class="ch-foot"><div>{AUTHOR} &middot; Data: the issuers' published data &middot; <a href="{config.REPOSITORY_URL}">Code on GitHub</a> &middot; Built {built} from commit {html.escape(commit)}</div></footer>
<script>
document.querySelectorAll(".rp-tw").forEach(function (t) {{
  function upd() {{ var s = t.firstElementChild; t.classList.toggle("more", s.scrollWidth - s.clientWidth - s.scrollLeft > 1); }}
  t.addEventListener("scroll", upd, true);
  if ("ResizeObserver" in window) {{ new ResizeObserver(upd).observe(t); }}
  upd();
}});
</script>
</body>
</html>
"""


def _figures_check(issue: Issue, exhibits_text: str) -> None:
    """The commentary shows no figure that the issue does not."""
    shown = set(_figures_in(exhibits_text))
    shown |= {f.replace("−", "-") for f in shown} | {f.lstrip("+") for f in shown}
    missing = [f for f in _figures_in(" ".join(issue.commentary.paragraphs)) if f not in shown and f.lstrip("+") not in shown]
    years_and_days = [f for f in missing if re.fullmatch(r"\d{1,4}", f)]
    missing = [f for f in missing if f not in years_and_days]
    if missing:
        raise ReportError(f"{label(issue.quarter)}: the commentary shows {', '.join(missing)}, which the issue does not")


def write(root: Path, quarter: pd.Period, commit: str, page: str = None) -> Path:
    """Write the issue's page once. The page is the one build_at gives, unless one is passed."""
    path = Path(root) / FOLDER / f"{label(quarter)}.html"
    if path.exists():
        raise ReportError(f"{FOLDER}/{path.name} exists: an issue is never rebuilt")
    page = build(root, quarter, commit) if page is None else page
    path.parent.mkdir(exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path


# The archival PDF ------------------------------------------------------------------------------------


def print_pdf(page: Path, printed: date, font: Path = None) -> Path:
    """Print the page once to quarterly/YYYY-QN_<printed>.pdf with Chromium, and set the author. The site's
    font can be served from a local copy of the same file."""
    from playwright.sync_api import sync_playwright  # only where the PDF is printed
    import pikepdf

    page = Path(page)
    out = page.with_name(f"{page.stem}_{printed:%Y-%m-%d}.pdf")
    if out.exists():
        raise ReportError(f"{FOLDER}/{out.name} exists: a print is never repeated under the same date")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        tab = browser.new_page()
        if font:
            data = Path(font).read_bytes()
            tab.route("https://www.carlohofer.com/assets/fonts/**", lambda r: r.fulfill(
                status=200, body=data, headers={"Content-Type": "font/woff2", "Access-Control-Allow-Origin": "*"}))
        tab.goto(page.resolve().as_uri(), wait_until="networkidle")
        tab.evaluate("document.fonts.ready")
        tab.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True, tagged=True)
        browser.close()
    # Chromium writes the title and not the author. Only the author is added: the title, the creator and the
    # producer stay as the printing tool wrote them, and no other field is written.
    with pikepdf.open(out, allow_overwriting_input=True) as pdf:
        pdf.docinfo["/Author"] = AUTHOR
        pdf.save(out)
    # A print that does not carry the page's words, as when a font's figures extract as private marks, is
    # not kept.
    faults = compare_words(page.read_text(encoding="utf-8"), out)
    if faults:
        out.unlink()
        raise ReportError(f"the print was not kept: {faults[0]}")
    return out


# Checks ----------------------------------------------------------------------------------------------


def _print_hidden(page_html: str) -> set:
    """The classes that the page's own print rules hide, read from its stylesheet, so that an issue is always
    read with the rules it was printed with."""
    css = " ".join(re.findall(r"<style>(.*?)</style>", page_html, flags=re.S))
    hidden = set()
    start = css.find("@media print")
    while start >= 0:
        depth, i = 0, css.index("{", start)
        for j in range(i, len(css)):
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            if depth == 0:
                break
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css[i + 1:j]):
            if re.search(r"display\s*:\s*none", body):
                hidden |= {m.group(1) for sel in selectors.split(",") if (m := re.fullmatch(r"\s*\.([\w-]+)\s*", sel))}
        start = css.find("@media print", j)
    return hidden


class _Text(HTMLParser):
    """The words of the page as it prints: without the head and the scripts, and without the elements its
    print rules hide, such as the phone drawings, the site's menu and the back line. SVG text is kept apart,
    since a chart's labels may print in another order."""

    def __init__(self, hidden=frozenset()):
        super().__init__(convert_charrefs=True)
        self.hidden = set(hidden)
        self.words, self.chart_words, self.stack = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "meta", "link", "img", "input", "line", "rect", "circle", "polyline", "path"):
            return
        classes = set((dict(attrs).get("class") or "").split())
        hidden = tag in ("head", "script", "style", "title") or bool(classes & self.hidden)
        self.stack.append((tag, hidden))

    def handle_startendtag(self, tag, attrs):
        pass  # a self-closing element, such as an SVG line, holds no text

    def handle_endtag(self, tag):
        while self.stack:
            t, _ = self.stack.pop()
            if t == tag:
                break

    def handle_data(self, data):
        if any(h for _, h in self.stack):
            return
        target = self.chart_words if any(t == "svg" for t, _ in self.stack) else self.words
        target.extend(_normal(data))


def _normal(text: str) -> list:
    """Runs of letters and digits, and each other mark on its own, so that a word the PDF splits at a change
    of font, as at the end of a code span, still matches the page's."""
    return re.findall(r"\w+|[^\w\s]", unicodedata.normalize("NFKC", text).lower())


def page_words(page_html: str) -> tuple:
    parser = _Text(_print_hidden(page_html))
    parser.feed(page_html)
    return parser.words, parser.chart_words


def pdf_words(path: Path) -> list:
    """The PDF's words in reading order, line by line down each page, without the running footer in the
    bottom margin."""
    import pdfplumber

    words = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            margin = page.height - 20 * 72 / 25.4
            found = sorted((w for w in page.extract_words() if w["top"] < margin), key=lambda w: (w["top"], w["x0"]))
            lines = []
            for w in found:
                if lines and abs(w["top"] - lines[-1][0]["top"]) <= 2:
                    lines[-1].append(w)
                else:
                    lines.append([w])
            for line in lines:
                for w in sorted(line, key=lambda w: w["x0"]):
                    words.extend(_normal(w["text"]))
    return words


def _exhibits(words: list) -> list:
    """The exhibit labels in the order they come, such as ["figure 1", "table 1", "figure 2"]."""
    return [f"{words[k]} {words[k + 1]}" for k in range(len(words) - 2)
            if words[k] in ("figure", "table") and words[k + 1].isdigit() and words[k + 2] == "|"]  # fmt: skip


def compare_words(page_html: str, pdf_path: Path) -> list:
    """The faults, empty when the PDF prints every word of the page as often as the page has it and nothing
    else, with its exhibits in the page's order. A chart's labels may print in any order and split at any
    point, and a turned axis title may read backwards, so the charts are compared letter for letter."""
    text, chart = page_words(page_html)
    printed = pdf_words(pdf_path)
    faults = []
    lacking = Counter(text) - Counter(printed)
    if lacking:
        faults.append(f"the PDF lacks words of the page: {sorted(lacking.elements())[:12]}")
    rest = Counter(printed) - Counter(text)
    printed_chart = Counter("".join(rest.elements()))
    page_chart = Counter("".join(chart))
    if printed_chart != page_chart:
        extra = "".join(sorted((printed_chart - page_chart).elements()))[:40]
        lost = "".join(sorted((page_chart - printed_chart).elements()))[:40]
        faults.append(f"the PDF's other words are not the charts' labels: in the PDF only {extra!r}, on the page only {lost!r}")
    if _exhibits(printed) != _exhibits(text):
        faults.append(f"the exhibits print in another order: {_exhibits(printed)} against {_exhibits(text)}")
    return faults


def pdf_metadata_faults(path: Path, title: str) -> list:
    """The faults of the PDF's metadata: its fields hold the page's title, the author and the printing tool and
    nothing else, and it carries no attached file and no metadata stream, where a content-credentials manifest
    would sit."""
    import pdfplumber

    faults = []
    with pdfplumber.open(path) as pdf:
        meta = {k: str(v) for k, v in (pdf.metadata or {}).items()}
        catalog = set(pdf.doc.catalog)
    if meta.get("Author") != AUTHOR:
        faults.append(f"the author is {meta.get('Author')!r}, not {AUTHOR!r}")
    if meta.get("Title") != title:
        faults.append(f"the title is {meta.get('Title')!r}, not the page's")
    creator, producer = meta.get("Creator", ""), meta.get("Producer", "")
    if creator and not re.fullmatch(r"Chromium|(Mozilla/5\.0 .*)?HeadlessChrome/[\d.]+.*", creator):
        faults.append(f"the creator {creator!r} is not the printing tool")
    if producer and not re.fullmatch(r"Skia/PDF m\d+", producer):
        faults.append(f"the producer {producer!r} is not the printing tool")
    extra = sorted(set(meta) - INFO_FIELDS)
    if extra:
        faults.append(f"the PDF has fields beyond the title, the author and the printing tool: {extra}")
    attached = sorted(catalog & {"AF", "Names", "Metadata"})
    if attached:
        faults.append(f"the PDF carries {attached}, which the printing tool does not write")
    return faults


def _git_archive(root: Path, commit: str, target: Path) -> None:
    data = subprocess.run(["git", "--no-optional-locks", "archive", "--format=tar", commit], cwd=root, check=True,
                          capture_output=True).stdout  # fmt: skip
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        try:
            tar.extractall(target, filter="data")
        except TypeError:  # a Python without extraction filters
            tar.extractall(target)


def build_at(root: Path, quarter: pd.Period, commit: str) -> str:
    """The issue's page as the code and the tables of the commit build it, from a copy of that commit's tree,
    so that the page is the one any later rebuild from the commit gives."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _git_archive(Path(root), commit, Path(tmp))
        except subprocess.CalledProcessError as e:
            raise ReportError(f"{label(quarter)}: commit {commit} is not in the repository: {e.stderr.decode(errors='replace').strip()}")
        run = subprocess.run([sys.executable, "-m", "portfolio", "quarterly", label(quarter), "--commit", commit, "--root", tmp,
                              "--stdout"], cwd=tmp, capture_output=True,
                             env=dict(os.environ, PYTHONPATH=str(Path(tmp) / "src"), PYTHONDONTWRITEBYTECODE="1",
                                      PYTHONIOENCODING="utf-8"))  # fmt: skip
    if run.returncode != 0:
        raise ReportError(f"{label(quarter)}: the build at commit {commit} stopped: {run.stderr.decode('utf-8', 'replace').strip()[-300:]}")
    return run.stdout.decode("utf-8")


def check(root: Path = None) -> list:
    """Every issue under quarterly/: rebuilt from its commit, it comes out byte for byte, and each of its PDFs
    carries its words, its title and its author. Returns the faults, empty when all pass."""
    root = Path(root or config.ROOT)
    faults = []
    if list((root / FOLDER).glob("*.pdf")):
        try:
            import pdfplumber  # noqa: F401
        except ImportError:
            return ["pdfplumber reads the PDFs. Install it once with:  python3 -m pip install --user -r requirements.txt"]
    for page in sorted((root / FOLDER).glob("[0-9][0-9][0-9][0-9]-Q[1-4].html")):
        text = page.read_text(encoding="utf-8")
        commit = re.search(r'<meta name="commit" content="([0-9a-f]{7,40})">', text)
        title = re.search(r"<title>(.*?)</title>", text)
        if not commit:
            faults.append(f"{FOLDER}/{page.name}: no commit in the page")
            continue
        try:
            if build_at(root, parse_quarter(page.stem), commit.group(1)) != text:
                faults.append(f"{FOLDER}/{page.name}: the page differs from its rebuild at commit {commit.group(1)}")
        except ReportError as e:
            faults.append(f"{FOLDER}/{page.name}: {e}")
        for pdf in sorted(page.parent.glob(f"{page.stem}_*.pdf")):
            faults += [f"{FOLDER}/{pdf.name}: {f}" for f in compare_words(text, pdf)]
            faults += [f"{FOLDER}/{pdf.name}: {f}" for f in pdf_metadata_faults(pdf, html.unescape(title.group(1)) if title else "")]
    return faults


def issues(root: Path = None) -> list:
    """The published issues, newest first, each with its PDFs: (label, page path, [pdf paths])."""
    root = Path(root or config.ROOT)
    found = []
    for page in sorted((root / FOLDER).glob("[0-9][0-9][0-9][0-9]-Q[1-4].html"), reverse=True):
        found.append((page.stem, page, sorted(page.parent.glob(f"{page.stem}_*.pdf"))))
    return found
