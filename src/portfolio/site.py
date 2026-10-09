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

from . import config
from . import formatting as fmt

SITE_URL = "https://www.carlohofer.com/"
PROJECTS_URL = SITE_URL + "projects/"
PROJECT_PAGE_URL = PROJECTS_URL + "rules-based-portfolio/"
FAVICON_URL = SITE_URL + "images/favicon.svg"
WRAP_FIRST_ABOVE = 28  # characters: a longer label in a table's first column wraps on a phone
PLOTLY = "https://cdn.plot.ly/plotly-basic-2.35.2.min.js"
PLOTLY_INTEGRITY = "sha384-wQ3lfCxuvLfhHGiSdHF5+e3NZ1zNwEMd8/nII+K7VKChF9llO/OwOcn/aVRkB7az"
VIEWS = [
    ("overview", "Overview"),
    ("rebalancing", "Rebalancing"),
    ("costs", "Costs"),
    ("contributions", "Contributions"),
    ("lookthrough", "Look-through"),
    ("factors", "Factor exposures"),
    ("method", "Method"),
    ("simulations", "Simulations"),
    ("log", "Log"),
]
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
    """Collects the charts of each view and their HTML."""

    def __init__(self):
        self.charts = []
        self.sections = {v: [] for v, _ in VIEWS}

    def add(self, view, html_block, chart=None):
        self.sections[view].append(html_block)
        if chart:
            chart["view"] = view
            self.charts.append(chart)


def _read(name: str, folder: Path = None) -> pd.DataFrame:
    path = (folder or config.OUTPUTS_DIR) / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _esc(text) -> str:
    return html.escape(str(text), quote=True)


def _table(columns, rows, numeric=()) -> str:
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
    wrap = ' class="wrapfirst"' if longest > WRAP_FIRST_ABOVE else ""
    return (f'<div class="tw"><div class="tablewrap"><table{wrap}><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div></div>')


def _card(cid, title, asof, source, plot=True, table=None, note=None, wide=False, height=300, empty=None,
          anchor=None) -> str:  # fmt: skip
    target = f' id="{anchor}"' if anchor else ""
    parts = [f'<article class="card{" wide" if wide else ""}"{target}>', f"<h3>{_esc(title)}</h3>"]
    if asof:
        parts.append(f'<p class="asof">{_esc(asof)}</p>')
    if empty:
        parts.append(f'<div class="empty">{_esc(empty)}</div>')
    elif plot:
        parts.append(f'<div class="plot" id="{cid}" style="height:{height}px" role="img" aria-label="{_esc(title)}"></div>')
    if note:
        parts.append(f'<p class="note">{_esc(note)}</p>')
    if source:
        files = ", ".join(f"<code>{_esc(s)}</code>" for s in ([source] if isinstance(source, str) else source))
        parts.append(f'<p class="source">Source: {files}</p>')
    if table:
        parts.append(f'<details class="twin"><summary>Table</summary>{table}</details>')
    parts.append("</article>")
    return "".join(parts)


def _hover(texts) -> dict:
    return {"customdata": list(texts), "hovertemplate": "%{customdata}<extra></extra>"}


def _hline(y, role="@axis", dash=None, label=None, xref="paper"):
    shape = {"type": "line", "xref": xref, "x0": 0, "x1": 1, "yref": "y", "y0": y, "y1": y,
             "line": {"color": role, "width": 1}}  # fmt: skip
    return shape


def _vline(x, role="@axis"):
    return {"type": "line", "yref": "paper", "y0": 0, "y1": 1, "xref": "x", "x0": x, "x1": x,
            "line": {"color": role, "width": 1}}  # fmt: skip


def _label(x, y, text, xref="x", yref="y", anchor="left", role="@ink2", xshift=6, yshift=0):
    return {"x": x, "y": y, "xref": xref, "yref": yref, "text": _esc(text), "showarrow": False,
            "xanchor": anchor, "xshift": xshift, "yshift": yshift, "font": {"color": role, "size": 11}}  # fmt: skip


def _section(title: str, anchor: str, sub: str = "", tone: str = "") -> str:
    """A heading that groups the cards after it, across the whole width of the view, with an anchor for links."""
    line = f'<p class="sub">{_esc(sub)}</p>' if sub else ""
    return f'<div class="section wide {tone}" id="{anchor}"><h2>{_esc(title)}</h2>{line}</div>'


def _link(anchor: str, text: str) -> str:
    return f'<a href="#{anchor}">{_esc(text)}</a>'


def _and(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _start_label(day, i) -> str:
    """The first row of a daily series is the starting amount at the close before the first order."""
    return f"{day}, start" if i == 0 else str(day)


def _date_axis(dates, most: int = 5) -> dict:
    """A date axis. Over two weeks or less Plotly ticks by the hour and repeats each date, so the ticks are
    then valuation days, at most `most` of them, the last day always among them."""
    axis = {"type": "date", "tickformat": "%Y-%m-%d", "hoverformat": "%Y-%m-%d"}
    days = sorted({str(d)[:10] for d in dates})
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
    built = fmt.day(now_row["positions_as_of"])
    return (f'<p class="colophon">Carlo Hofer &middot; Data: the issuers\' published data &middot; '
            f'<a href="{config.REPOSITORY_URL}">Code on GitHub</a> &middot; Built {_esc(built)}</p>')


def _asof(day, extra="") -> str:
    return f"As of {fmt.day(day)}" + (f". {extra}" if extra else "")


def _two_dates(now_row) -> str:
    """The date of the prices and the date of the holdings, for figures that combine the two."""
    return f"Prices as of {fmt.day(now_row['weights_as_of'])}, holdings as of {fmt.day(now_row['positions_as_of'])}"


# Overview ------------------------------------------------------------------------------------------


def overview(page: Page, daily: pd.DataFrame, monthly: pd.DataFrame, now: pd.DataFrame, orders: pd.DataFrame):
    history = daily.iloc[1:] if len(daily) else daily
    last = history.iloc[-1] if len(history) else None
    w_now = now.iloc[0]
    month_orders = 0
    if len(orders):
        current = pd.Timestamp(w_now["positions_as_of"]).to_period("M")
        month_orders = int((pd.to_datetime(orders["date"]).dt.to_period("M") == current).sum())
    previous = monthly[monthly["complete"] == "yes"].iloc[-1] if len(monthly) and (monthly["complete"] == "yes").any() else None

    def change(now_value, before_value, f):
        if before_value is None or pd.isna(before_value):
            return "No month end yet"
        return f"{f(now_value - before_value)} since {before_value_label}"

    before_value_label = previous["month"] if previous is not None else ""
    tiles = [
        ("Equity weight", fmt.pct(w_now["weight_equity"]),
         change(w_now["weight_equity"] * 100, None if previous is None else previous["weight_equity"] * 100,
                lambda d: fmt.points(d))),
        ("Drift from 70%", fmt.points((w_now["weight_equity"] - config.TARGET[config.EQUITY]) * 100),
         "Equity weight minus the target weight"),
        ("Return since the first purchase", fmt.pct(last["growth_portfolio"] / 100 - 1, signed=True) if last is not None else "n/a",
         "Time-weighted, contributions removed" if last is not None else "From the first valuation day"),
        ("Drawdown now", fmt.pct(-last["drawdown_portfolio"]) if last is not None else "n/a",
         "Below the previous peak" if last is not None else "From the first valuation day"),
        ("Orders this month", f"{month_orders} of {config.ORDERS_PER_MONTH}", "The allowance of rule 6"),
    ]  # fmt: skip
    tile_html = "".join(
        f'<div class="tile"><p class="name">{_esc(n)}</p><div class="value">{_esc(v)}</div>'
        f'<div class="change">{_esc(c)}</div></div>'
        for n, v, c in tiles
    )
    asof = _two_dates(w_now)
    page.add("overview", f'<div class="wide"><div class="tiles">{tile_html}</div><p class="source">{_esc(asof)}. '
             f'Source: <code>outputs/allocation_now.csv</code>, <code>outputs/portfolio_daily.csv</code></p></div>')

    # Chart 2: allocation now, a bullet chart: the weight as a bar, the target as a tick, the band shaded.
    low, high = config.BAND
    band_text = f"Band {fmt.count(round(low * 100))} to {fmt.count(round(high * 100))}"
    rows2 = [("Equity", w_now["weight_equity"], config.TARGET[config.EQUITY], "@equity", band_text),
             ("Bonds", w_now["weight_bonds"], config.TARGET[config.BONDS], "@bonds", "No band of its own")]  # fmt: skip
    traces, annotations = [], []
    for name, w, target, role, band in rows2:
        hover = f"{name} {fmt.pct(w)}<br>Target {fmt.pct(target)}<br>{band}"
        traces.append({"type": "bar", "orientation": "h", "y": [name], "x": [fmt.rounded(w * 100, 2)], "name": name,
                       "width": 0.32, "marker": {"color": role}, "showlegend": False, **_hover([hover])})  # fmt: skip
        annotations.append(_label(max(w, target) * 100, name, fmt.pct(w), anchor="left", role="@ink", xshift=8))
    traces.append({"type": "scatter", "mode": "markers", "name": "Target weight", "y": [r[0] for r in rows2],
                   "x": [r[2] * 100 for r in rows2], "showlegend": False,
                   "marker": {"symbol": "line-ns", "size": 30, "color": "@ink", "line": {"color": "@ink", "width": 3}},
                   **_hover([f"{r[0]} target {fmt.pct(r[2])}" for r in rows2])})  # fmt: skip
    # Each target is labelled above its tick: a legend there would sit over a point of the axis.
    for row, (name, w, target, role, band) in enumerate(rows2):
        text = f"Target {fmt.count(round(target * 100))}%" + (f", {band_text[0].lower()}{band_text[1:]}" if row == 0 else "")
        annotations.append(_label(target * 100, row - 0.42, text, anchor="center", xshift=0, yshift=2))
        annotations[-1]["yanchor"] = "bottom"
    layout = {
        "barmode": "overlay", "showlegend": False, "height": 210,
        "xaxis": {"range": [0, 100], "title": {"text": "Per cent of the portfolio"}, "dtick": 10},
        "yaxis": {"type": "category", "range": [1.55, -0.78], "showline": False, "showgrid": False,
                  "tickfont": {"size": 12}},
        "shapes": [{"type": "rect", "xref": "x", "yref": "y", "x0": low * 100, "x1": high * 100, "y0": -0.4, "y1": 0.4,
                    "fillcolor": "@band", "line": {"width": 0}, "layer": "below"}],
        "annotations": annotations, "margin": {"t": 8},
    }  # fmt: skip
    cash = w_now["weight_cash"]
    table = _table(["Sleeve", "Weight", "Target weight", "Band"],
                   [["Equity", fmt.pct(w_now["weight_equity"]), fmt.pct(config.TARGET[config.EQUITY]), band_text],
                    ["Bonds", fmt.pct(w_now["weight_bonds"]), fmt.pct(config.TARGET[config.BONDS]), ""],
                    ["Cash", fmt.pct(cash), "", ""]], numeric=("Weight", "Target weight"))  # fmt: skip
    note2 = f"Cash {fmt.pct(cash)}. The band applies to the equity weight only."
    page.add("overview", _card("c2", "Allocation now against the target and the band", asof,
             "outputs/allocation_now.csv", table=table, note=note2, height=210, wide=True),
             {"id": "c2", "traces": traces, "layout": layout})  # fmt: skip

    # Chart 3: growth of 100.
    first_order = orders["date"].min() if len(orders) else None
    empty = None if len(history) >= 1 else (f"The series starts with the net asset values of {first_order}, the day of "
                                            "the first purchase, which the issuers publish the next working day.")
    series = [("Portfolio", "growth_portfolio", "@accent", 2),
              ("Reference A, same rules", "growth_reference_a", "@reference_a", 2),
              ("Reference B, 70/30 each cycle day", "growth_reference_b", "@reference_b", 2),
              ("Index blend", "growth_index_blend", "@index_blend", 2)]  # fmt: skip
    traces, annotations, rows = [], [], []
    for name, column, role, width in series:
        data = daily[["date", column]].dropna()
        if len(data) < 2:
            continue
        traces.append({"type": "scatter", "mode": "lines+markers" if len(data) < 3 else "lines", "name": name,
                       "x": list(data["date"]), "y": [fmt.rounded(v, 1) for v in data[column]],
                       "line": {"color": role, "width": width}, "marker": {"size": 8, "color": role},
                       **_hover([f"{d}<br>{name}: {fmt.index(v)}" for d, v in zip(data["date"], data[column])])})  # fmt: skip
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
    asof3 = _asof(daily["date"].iloc[-1] if len(daily) else w_now["weights_as_of"],
                  "100 is the starting amount before the first order. The index blend starts at the first month end")  # fmt: skip
    page.add("overview", _card("c3", "Growth of 100: the portfolio, the two reference portfolios and the index blend",
             asof3, "outputs/portfolio_daily.csv", table=None if empty else table, height=340, wide=True, empty=empty),
             None if empty else {"id": "c3", "traces": traces, "layout": layout,
                                 "layout_narrow": {"annotations": [], "margin": {"r": 12}, **narrow}})  # fmt: skip

    # Chart 4: drawdown, as a positive fall below the previous peak on a reversed axis scaled to the data.
    traces = []
    if len(history):
        traces.append({"type": "scatter", "mode": "lines", "name": "Portfolio", "x": list(daily["date"]),
                       "y": [fmt.rounded(-v * 100, 1) for v in daily["drawdown_portfolio"]], "fill": "tozeroy",
                       "line": {"color": "@accent", "width": 2}, "fillcolor": "@ring",
                       **_hover([f"{d}<br>Portfolio: {fmt.pct(-v)} below the previous peak" for d, v in
                                 zip(daily["date"], daily["drawdown_portfolio"])])})  # fmt: skip
        blend = daily[["date", "drawdown_index_blend"]].dropna()
        if len(blend) >= 2:
            traces.append({"type": "scatter", "mode": "lines+markers", "name": "Index blend", "x": list(blend["date"]),
                           "y": [fmt.rounded(-v * 100, 1) for v in blend["drawdown_index_blend"]],
                           "line": {"color": "@index_blend", "width": 2}, "marker": {"size": 8},
                           **_hover([f"{d}<br>Index blend: {fmt.pct(-v)} below the previous peak" for d, v in
                                     zip(blend["date"], blend["drawdown_index_blend"])])})  # fmt: skip
    worst = -daily["drawdown_portfolio"].min() if len(daily) else 0.0
    deepest = max(10.0, 1.3 * worst * 100)
    shapes, annotations = [], []
    for level, text in ((35, "Test limit of the mandate, 35%"), (40, "Outer bound, 40%")):
        if level <= deepest:
            shapes.append(_hline(level))
            annotations.append(_label(0, level, text, xref="paper", yshift=8, xshift=0))
    wide, narrow = _date_axes(daily["date"])
    layout = {"showlegend": len(traces) > 1, "yaxis": {"title": {"text": "Per cent below the previous peak"},
              "range": [deepest, -1]}, **wide, "shapes": shapes, "annotations": annotations}  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.pct(-r["drawdown_portfolio"]), fmt.pct(-r["drawdown_index_blend"])]
            for i, (_, r) in enumerate(daily.iterrows())]  # fmt: skip
    table = _table(["Date", "Portfolio", "Index blend"], rows, numeric=("Portfolio", "Index blend"))
    asof4 = _asof(daily["date"].iloc[-1] if len(daily) else w_now["weights_as_of"],
                  f"Worst fall to date {fmt.pct(worst)}. The mandate's test limit is 35 per cent and its outer bound 40 per cent")  # fmt: skip
    page.add("overview", _card("c4", "Drawdown against the mandate's limit", asof4,
             "outputs/portfolio_daily.csv", table=None if empty else table, height=300, wide=True, empty=empty,
             note="Daily values. The mandate's 35% test used month-end values, which miss falls that reverse within "
                  "a month; the worst daily fall is at least as deep."),
             None if empty else {"id": "c4", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip


# Rebalancing ---------------------------------------------------------------------------------------


def rebalancing(page, daily, orders, band, compliance, monthly):
    history = daily.iloc[1:]
    empty = None if len(history) else "The equity weight starts on the first valuation day."
    low, high = config.BAND
    traces = []
    if len(history):
        traces.append({"type": "scatter", "mode": "lines", "name": "Equity weight", "x": list(history["date"]),
                       "y": [fmt.rounded(v * 100, 1) for v in history["weight_equity"]],
                       "line": {"color": "@equity", "width": 2},
                       **_hover([f"{d}<br>Equity weight {fmt.pct(v)}" for d, v in
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
                               **_hover([f"{d}<br>{label}" for d, _ in pts])})  # fmt: skip
        annotations = []
        if len(band):
            pts = [(d, weight_on.get(d)) for d in band["date"] if d in weight_on]
            traces.append({"type": "scatter", "mode": "markers", "name": "Band order",
                           "x": [p[0] for p in pts], "y": [fmt.rounded(p[1] * 100, 1) for p in pts],
                           "marker": {"size": 11, "symbol": "diamond", "color": "@status_breach"},
                           **_hover([f"{d}<br>Band order, rule 5" for d, _ in pts])})  # fmt: skip
            annotations += [_label(p[0], fmt.rounded(p[1] * 100, 1), "◆ Band order") for p in pts]
        missed = compliance[compliance["issue"] == "called for by the rules and not placed"] if len(compliance) else compliance
        if len(missed):
            pts = [(d, weight_on.get(d)) for d in missed["date"] if d in weight_on]
            traces.append({"type": "scatter", "mode": "markers", "name": "Order not placed",
                           "x": [p[0] for p in pts], "y": [fmt.rounded(p[1] * 100, 1) for p in pts],
                           "marker": {"size": 11, "symbol": "circle-open", "color": "@status_missed",
                                      "line": {"width": 2}},
                           **_hover([f"{d}<br>Order called for by the rules and not placed" for d, _ in pts])})  # fmt: skip
            annotations += [_label(p[0], fmt.rounded(p[1] * 100, 1), "○ Not placed") for p in pts]
    wide, narrow = _date_axes(history["date"])
    layout = {"showlegend": True, "yaxis": {"title": {"text": "Equity weight, per cent"}, "range": [60, 80], "dtick": 5},
              **wide,
              "shapes": [{"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": low * 100,
                          "y1": high * 100, "fillcolor": "@band", "line": {"width": 0}, "layer": "below"},
                         _hline(70, "@ink")]}  # fmt: skip
    if len(history):
        layout["annotations"] = annotations
    rows = [[r["date"], fmt.pct(r["weight_equity"]), fmt.pct(r["weight_bonds"]), fmt.pct(r["weight_cash"])]
            for _, r in history.iterrows()]  # fmt: skip
    table = _table(["Date", "Equity", "Bonds", "Cash"], rows, numeric=("Equity", "Bonds", "Cash"))
    first_cycle = "No cycle day yet: the line covers the days since the first purchase" if not len(band) and (
        not len(orders) or (orders["rule"].isin(["4", "5", "4+5"])).sum() == 0) else ""  # fmt: skip
    page.add("rebalancing", _card("c5", "Equity weight in its band, with every order",
             _asof(daily["date"].iloc[-1], first_cycle), ["outputs/portfolio_daily.csv", "outputs/orders.csv",
             "outputs/band_events.csv", "outputs/compliance.csv"], table=table, height=320, wide=True, empty=empty),
             None if empty else {"id": "c5", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip

    # Chart 6: orders against the allowance.
    if len(orders):
        months = pd.to_datetime(orders["date"]).dt.strftime("%Y-%m")
        counts = months.value_counts().sort_index()
    else:
        counts = pd.Series(dtype=int)
    traces = [{"type": "bar", "x": list(counts.index), "y": [int(v) for v in counts.values], "name": "Orders",
               "width": 0.45, "marker": {"color": "@accent"},
               **_hover([f"{m}: {v} of {config.ORDERS_PER_MONTH}" for m, v in counts.items()])}]
    shown = max(len(counts), 6)
    layout = {"yaxis": {"title": {"text": "Orders in the month"}, "range": [0, 6], "dtick": 1},
              "xaxis": {"type": "category", "title": {"text": "Month"}, "range": [-0.5, shown - 0.5]},
              "shapes": [_hline(config.ORDERS_PER_MONTH, "@ink")],
              "annotations": [_label(1, config.ORDERS_PER_MONTH, "Allowance, 5", xref="paper", anchor="right",
                                     xshift=0, yshift=8)]}  # fmt: skip
    rows = [[r["date"], r["sleeve"], r["side"], r["rule"], r["inside_rule_7_window"], r["bid_and_ask_recorded"]]
            for _, r in orders.iterrows()] if len(orders) else []  # fmt: skip
    table = _table(["Date", "Sleeve", "Side", "Rule", "Inside 15:45 to 17:00", "Bid and ask recorded"], rows)
    note = _departures(compliance, orders)
    page.add("rebalancing", _card("c6", "Orders per month against the allowance of five",
             _asof(daily["date"].iloc[-1]), "outputs/orders.csv", table=table, note=note, height=260),
             {"id": "c6", "traces": traces, "layout": layout})  # fmt: skip


def _orders_named(group: pd.DataFrame, orders: pd.DataFrame) -> str:
    """'The equity and bond orders of 2026-10-08, the first purchases,' for the departures of one day."""
    day = group["date"].iloc[0]
    sleeves = sorted(set(group["sleeve"]), key=lambda x: config.SLEEVES.index(x))
    words = {"equity": "equity", "bonds": "bond"}
    what = " and ".join(words[x] for x in sleeves) + (" orders" if len(sleeves) > 1 else " order")
    first = len(orders) and (orders[orders["date"] == day]["rule"] == "start").all()
    return f"The {what} of {day}" + (", the first purchases," if first else "")


def _departures(compliance: pd.DataFrame, orders: pd.DataFrame) -> str:
    """One plain sentence per kind of departure from the rules, with the orders it concerns."""
    if not len(compliance):
        return "Every order so far was placed as the rules require."
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
            traces.append({"type": "bar", "name": name, "x": list(monthly["month"]), "width": 0.45,
                           "y": [fmt.rounded(v, 0) for v in monthly[column]],
                           "marker": {"color": role, "line": {"color": "@surface", "width": 2}},
                           **_hover([f"{m}<br>{name}: {fmt.bps(v, signed=False)}<br>Implementation cost of the month: "
                                     f"{fmt.bps(t, signed=False)}" for m, v, t in
                                     zip(monthly["month"], monthly[column], monthly["implementation_cost_month_bps"])])})  # fmt: skip
    layout = {"barmode": "relative", "showlegend": True, "bargap": 0.45, "legend": {"traceorder": "normal"},
              "yaxis": {"title": {"text": "Basis points of the portfolio's value"}},
              "xaxis": {"type": "category", "title": {"text": "Month"},
                        "range": [-0.5, max(len(monthly), 6) - 0.5]}, "shapes": [_hline(0, "@ink")]}  # fmt: skip
    rows = [[r["month"], fmt.bps(r["commissions_bps"], False), fmt.bps(r["half_spread_bps"], False),
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
            "so the four sources of a month add up to that month's implementation cost in chart 8.")  # fmt: skip
    if missing:
        which = f"the {NUMBER_WORD[missing].lower()} orders" if missing > 1 else "the one order"
        note += (f" For {which} without a recorded bid and ask, the half-spread is not measured and is part of the "
                 "price paid against net asset value.")  # fmt: skip
    empty = None if len(monthly) else "Costs start with the first valuation day."
    page.add("costs", _card("c7", "Cost per month by source", _asof(daily["date"].iloc[-1]),
             "outputs/costs_monthly.csv", table=table, note=note, height=280, empty=empty),
             None if empty else {"id": "c7", "traces": traces, "layout": layout})  # fmt: skip

    data = implementation.dropna(subset=["implementation_cost_bps"]) if len(implementation) else implementation
    empty = None if len(data) > 1 else "The comparison starts on the first valuation day."
    traces, layout, narrow = [], {}, {}
    if not empty:
        traces = [{"type": "scatter", "mode": "lines+markers" if len(data) < 3 else "lines",
                   "name": "Portfolio against reference portfolio A", "x": list(data["date"]),
                   "y": [fmt.rounded(v, 0) for v in data["implementation_cost_bps"]],
                   "line": {"color": "@accent", "width": 2}, "marker": {"size": 8, "color": "@accent"},
                   **_hover([f"{d}<br>{fmt.bps(v)}" for d, v in zip(data["date"], data["implementation_cost_bps"])])}]
        end = data.iloc[-1]
        wide, narrow = _date_axes(data["date"])
        layout = {"yaxis": {"title": {"text": "Basis points, cumulative"}}, **wide, "shapes": [_hline(0, "@ink")],
                  "annotations": [_label(end["date"], fmt.rounded(end["implementation_cost_bps"], 0),
                                         fmt.bps(end["implementation_cost_bps"]))], "margin": {"r": 56}}  # fmt: skip
    rows = [[_start_label(r["date"], i), fmt.bps(r["implementation_cost_bps"])]
            for i, (_, r) in enumerate(data.iterrows())]  # fmt: skip
    table = _table(["Date", "Implementation cost"], rows, numeric=("Implementation cost",))
    page.add("costs", _card("c8", "Implementation cost, cumulative: the portfolio against reference portfolio A",
             _asof(daily["date"].iloc[-1], "Negative when the portfolio trails the reference"),
             "outputs/implementation_cost.csv", table=None if empty else table, height=280, empty=empty,
             note="Reference portfolio A applies the same rules at net asset value and without costs, so the gap "
                  "between the portfolio and reference portfolio A is the cumulative cost of running the portfolio. "
                  "A cost of 10 basis points in one month of chart 7 moves this line down by 10 basis points in that "
                  "month."),
             None if empty else {"id": "c8", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip


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
             **_hover([f"{d}<br>Paid in: {fmt.index(p)}" for d, p in zip(x, daily["contributions_in_units"])])},
            {"type": "scatter", "mode": "lines+markers" if len(x) < 4 else "lines", "name": "Value of the portfolio",
             "x": x, "y": value, "line": {"color": "@accent", "width": 2}, "marker": {"size": 8, "color": "@accent"},
             **_hover([f"{d}<br>Value: {fmt.index(v)}" for d, v in zip(x, daily["value_in_units"])])},
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
             "outputs/portfolio_daily.csv", table=None if empty else table, height=320, wide=True, empty=empty),
             None if empty else {"id": "c9", "traces": traces, "layout": layout, "layout_narrow": narrow})  # fmt: skip

    empty = None if len(monthly) else "The first month starts with the first valuation day."
    rows = [[r["month"] + ("" if r["complete"] == "yes" else " (to date)"), fmt.pct(r["market_effect"], True),
             fmt.pct(r["contribution_effect"], True)] for _, r in monthly.iterrows()] if len(monthly) else []  # fmt: skip
    table = _table(["Month", "Market effect", "Contribution"], rows, numeric=("Market effect", "Contribution"))
    chart_a = chart_b = None
    if not empty:
        m = list(monthly["month"])
        months_shown = [-0.5, max(len(m), 6) - 0.5]
        chart_a = {"id": "c10a", "traces": [{"type": "bar", "name": "Market effect", "x": m, "width": 0.45,
                   "y": [fmt.rounded(v * 100, 1) for v in monthly["market_effect"]],
                   "marker": {"color": "@accent"},
                   **_hover([f"{a}<br>Market effect {fmt.pct(v, True)}" for a, v in zip(m, monthly["market_effect"])])}],
                   "layout": {"yaxis": {"title": {"text": "Market effect, per cent"}, "zeroline": True},
                              "xaxis": {"type": "category", "range": months_shown}, "shapes": [_hline(0, "@ink")]}}  # fmt: skip
        chart_b = {"id": "c10b", "traces": [{"type": "bar", "name": "Contribution", "x": m, "width": 0.45,
                   "y": [fmt.rounded(v * 100, 1) for v in monthly["contribution_effect"]], "marker": {"color": "@ink2"},
                   **_hover([f"{a}<br>Contribution {fmt.pct(v, True)}" for a, v in zip(m, monthly["contribution_effect"])])}],
                   "layout": {"yaxis": {"title": {"text": "Contribution, per cent"}}, "xaxis": {"type": "category",
                              "title": {"text": "Month"}, "range": months_shown}}}  # fmt: skip
    body = "" if empty else ('<div class="plot" id="c10a" style="height:200px" role="img" aria-label="Market effect by month"></div>'
                             '<div class="plot" id="c10b" style="height:200px" role="img" aria-label="Contribution by month"></div>')  # fmt: skip
    block = _card("c10", "Market effect and contribution by month, in per cent of the value at the start of the month",
                  _asof(daily["date"].iloc[-1]), "outputs/metrics_monthly.csv", plot=False, table=table, empty=empty)
    block = block.replace('<p class="source">', body + '<p class="source">', 1)
    page.add("contributions", block, chart_a)
    if chart_b:
        chart_b["view"] = "contributions"
        page.charts.append(chart_b)


# Look-through --------------------------------------------------------------------------------------


def _bars(cid, frame, label, role, title, asof, source, page, view, note=None, share_col="share_of_portfolio",
          sleeve=True, sort=True):
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
    table = _table(cols, rows, numeric=tuple(cols[1:]))
    page.add(view, _card(cid, title, asof, source, table=table, note=note, height=height),
             {"id": cid, "traces": traces, "layout": layout})


def lookthrough(page, out):
    def asof(frame):
        r = frame.iloc[0]
        return f"Holdings as of {fmt.day(r['holdings_as_of'])}, sleeve weights as of {fmt.day(r['weights_as_of'])}"

    held = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv")
    held = held[held["held"] == "yes"].drop_duplicates("sleeve").set_index("sleeve")["fund"]
    markets = list(pd.read_csv(config.METHOD_DIR / "funds_held.csv")["country"])
    weights = out["allocation_now.csv"].iloc[0]
    page.add("lookthrough", _section("Equity sleeve", "lookthrough-equity", tone="equity",
             sub=f"{held['equity']}, {fmt.pct(weights['weight_equity'])} of the portfolio"))  # fmt: skip
    region, country, sector = out["lookthrough_equity_region.csv"], out["lookthrough_equity_country.csv"], out["lookthrough_equity_sector.csv"]
    _bars("c11a", region, "region", "@equity", "Equity by region", asof(region),
          "outputs/lookthrough_equity_region.csv", page, "lookthrough",
          note="Regions follow MSCI's market classification (method/msci_regions.csv).")
    _bars("c11b", country, "country", "@equity", "Equity by country: the ten largest", asof(country),
          "outputs/lookthrough_equity_country.csv", page, "lookthrough",
          note=f"Country is the issuer's location as iShares reports it. {NUMBER_WORD[len(markets)]} of the fund's holdings are iShares "
               f"ETFs that each hold one market ({_and(markets)}), and each is counted under that market.")
    _bars("c12", sector, "sector", "@equity", "Equity by sector", asof(sector), "outputs/lookthrough_equity_sector.csv",
          page, "lookthrough", note="GICS sectors as iShares reports them. The single-market ETFs held by the fund have no single sector.")
    top = out["lookthrough_top10.csv"]
    total = top["share_of_portfolio"].sum()
    _bars("c14", top, "company", "@equity", f"The ten largest companies: {fmt.pct(total)} of the portfolio", asof(top),
          "outputs/lookthrough_top10.csv", page, "lookthrough",
          note="Share classes of one company are summed (method/companies.csv).")
    page.add("lookthrough", _section("Bond sleeve", "lookthrough-bonds", tone="bonds",
             sub=f"{held['bonds']}, {fmt.pct(weights['weight_bonds'])} of the portfolio"))  # fmt: skip
    bonds = out["lookthrough_bonds_country.csv"]
    _bars("c15", bonds, "country", "@bonds", "Bonds by issuing country", asof(bonds),
          "outputs/lookthrough_bonds_country.csv", page, "lookthrough")
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
                   numeric=("Share of the sleeve", "Share of the portfolio"))
    tiles = (f'<div class="duo"><div class="tile"><p class="name">Duration of the bond sleeve</p>'
             f'<div class="value">{_esc(fmt.years(dur["duration_years"]))}</div><div class="change">Vanguard factsheet of '
             f'{_esc(fmt.day(dur["holdings_as_of"]))}</div></div><div class="tile"><p class="name">Duration contribution to the portfolio</p>'
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
                   numeric=("Share of the sleeve", "Share of the portfolio"))
    page.add("lookthrough", _card("c17", "Credit quality of the bond sleeve, as the issuer reports it",
             f"Vanguard factsheet as of {fmt.day(rating['holdings_as_of'].iloc[0])}", "outputs/lookthrough_bonds_rating.csv",
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
                   rows, numeric=("Share of the portfolio", "From the equity sleeve", "From the bond sleeve", "From cash"))
    note = ("Each holding counts in the currency of its market, as the issuers report it, so buying the equity ETF's "
            "US dollar share class in euro on Xetra does not change the exposure. Currencies are named until the rest "
            "is below 10 per cent of the portfolio.")  # fmt: skip
    page.add("lookthrough", _card("c13", "Currency exposure, by sleeve", asof(currency),
             "outputs/lookthrough_currency.csv", table=table, note=note, height=80 + 30 * len(names), wide=True),
             {"id": "c13", "traces": traces, "layout": layout})  # fmt: skip


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
            f"{fmt.day(first['window_start'])} to {fmt.day(first['window_end'])}, {int(first['observations'])} weeks")  # fmt: skip
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
                   **_hover([f"{fmt.month(d)}<br>{name}: {fmt.loading(v)}" for d, v in
                             zip(data["window_end"], data["loading"])])}]  # fmt: skip
        yaxis = {"zeroline": False} if f == "Mkt-RF" else {"zeroline": False, "range": shared}
        layout = {"xaxis": {"type": "date", "tickformat": "%Y", "hoverformat": "%Y-%m"}, "yaxis": yaxis,
                  "shapes": [_hline(0, "@ink")] if f != "Mkt-RF" else [], "margin": {"t": 4, "b": 4}}  # fmt: skip
        page.charts.append({"id": cid, "view": "factors", "traces": traces, "layout": layout})
    wide = rolling.pivot(index="window_end", columns="factor", values="loading")[list(config.FACTORS)]
    rows = [[fmt.month(d)] + [fmt.loading(v) for v in r] for d, r in wide.iterrows()]
    table = _table(["Window end"] + names, rows, numeric=tuple(names))
    block = _card("c19", "Rolling loadings: 36-month windows of weekly returns, stepped at each month end",
                  f"Windows ending {fmt.month(rolling['window_end'].min())} to {fmt.month(rolling['window_end'].max())}. "
                  "The five panels after the market share one scale",
                  "outputs/factor_rolling.csv", plot=False, table=table, wide=True)
    block = block.replace('<p class="source">', f'<div class="multiples">{"".join(blocks)}</div><p class="source">', 1)
    page.add("factors", block)
    page.add("factors", _card("c20", "Where the difference to the index blend came from",
             _asof(as_of),
             None, plot=False, wide=True, empty="From the October 2027 month end, when twelve months exist, this chart splits the "
             "portfolio's monthly return against the index blend into exposures times factor returns and a residual."))  # fmt: skip


# Method --------------------------------------------------------------------------------------------


def method(page, allocation: pd.DataFrame, selection: pd.DataFrame, rules_html: str, sources: pd.DataFrame,
           bootstrap: pd.DataFrame):  # fmt: skip
    splits = list(allocation["split"])
    colors = ["@accent" if c == "yes" else "@other" for c in allocation["chosen"]]
    fall = {"id": "c21a", "traces": [{"type": "bar", "x": splits, "y": [fmt.rounded(v * 100, 1) for v in allocation["worst_fall"]],
            "marker": {"color": colors}, **_hover([f"{s}: worst fall {fmt.pct(v)}" for s, v in zip(splits, allocation["worst_fall"])])}],
            "layout": {"xaxis": {"type": "category", "title": {"text": "Split, equity/bonds"}},
                       "yaxis": {"title": {"text": "Worst fall, per cent"}}, "shapes": [_hline(35, "@ink")],
                       "annotations": [_label(0, 35, "35%", xref="paper", xshift=0, yshift=8)]}}  # fmt: skip
    growth = {"id": "c21b", "traces": [{"type": "bar", "x": splits, "y": [fmt.rounded(v * 100, 1) for v in allocation["growth_per_year"]],
              "marker": {"color": colors}, **_hover([f"{s}: growth per year {fmt.pct(v)}" for s, v in zip(splits, allocation["growth_per_year"])])}],
              "layout": {"xaxis": {"type": "category", "title": {"text": "Split, equity/bonds"}},
                         "yaxis": {"title": {"text": "Growth per year, per cent"}, "rangemode": "tozero"}}}  # fmt: skip
    rows = [[r["split"], fmt.pct(r["worst_fall"]), fmt.pct(r["growth_per_year"]), r["within_limit"], r["chosen"]]
            for _, r in allocation.iterrows()]  # fmt: skip
    table = _table(["Split", "Worst fall", "Growth per year", "Within 35%", "Held"], rows, numeric=("Worst fall", "Growth per year"))
    body = ('<div class="duo"><div class="plot" id="c21a" style="height:260px" role="img" aria-label="Worst fall by split"></div>'
            '<div class="plot" id="c21b" style="height:260px" role="img" aria-label="Growth per year by split"></div></div>')
    block = _card("c21", "The allocation test: worst fall and growth per year by split",
                  "Monthly euro returns, February 1999 to December 2025, rebalanced by the band",
                  "mandate/allocation_check_results.csv", plot=False, table=table, wide=True, anchor="method-allocation",
                  note="The split held is the largest equity target weight whose worst fall stayed within 35 per cent.")
    block = block.replace('<p class="note">', body + '<p class="note">', 1)
    page.add("method", block, fall)
    growth["view"] = "method"
    page.charts.append(growth)
    if len(bootstrap):
        _bootstrap(page, bootstrap)

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
             r["offered_on_the_account"], r["held"], r["factsheet_date"]] for _, r in selection.iterrows()]  # fmt: skip
    table = _table(["Rank", "Fund", "ISIN", "Year", "Tracking difference", "Average", "Offered", "Held", "Factsheet"], rows,
                   numeric=("Tracking difference", "Average"))  # fmt: skip
    block = _card("c22", "The ETF selection: tracking difference by fund and year", "Calendar years 2023 to 2025, "
                  "fund return minus index return, from the issuers' factsheets", "method/selection_tracking_difference.csv",
                  plot=False, table=table, wide=True, anchor="method-selection",
                  note="Tracking difference is the fund's calendar-year return minus "
                  "the return of its index, so a higher figure means a smaller shortfall. Each mark is one year, with the "
                  "shape given in the legend, and the bar is the three-year average. The funds are numbered in the rank order fixed before they were "
                  "compared: equity ETFs by Irish domicile, then the highest average tracking difference, then the lowest "
                  "TER, and bond ETFs by the highest average tracking difference, then the lowest TER. The held funds, "
                  "in the primary ink, are the first in rank order that the account offers. Hollow marks are funds the "
                  "account does not offer.")  # fmt: skip
    block = block.replace('<p class="note">', "".join(blocks) + '<p class="note">', 1)
    page.add("method", block)

    rows = [[r["source"], r["last_date_covered"], r["downloaded"] if isinstance(r["downloaded"], str) else ""]
            for _, r in sources.iterrows()]  # fmt: skip
    page.add("method", _card("sources", "Data sources", "", "outputs/sources.csv", plot=False, wide=True, anchor="method-sources",
             table=_table(["Source", "Last date covered", "Downloaded"], rows),
             note="Every source is downloaded at build time, cached locally and not redistributed. Only the figures "
             "computed from them are published."))  # fmt: skip
    page.add("method", f'<article class="card wide rules" id="method-rules"><h3>The rules</h3><p class="asof">Rendered from '
             f'rules/RULES.md at build time, with the amendments table</p>{rules_html}</article>')


# Simulations -----------------------------------------------------------------------------------------

SIMULATION_BASIS = "This is not the portfolio's record, which starts in October 2026."
SAMPLE = "the allocation test's monthly euro returns from February 1999 to December 2025"


def _one_in(share: float) -> str:
    """A share of paths as "one in N", N in words up to nine."""
    n = int(round(1 / share)) if share > 0 else 0
    return NUMBER_WORD.get(n, str(n)).lower() if n else "none"


def _month_end(month: str) -> str:
    return pd.Period(month, freq="M").end_time.strftime("%Y-%m-%d")


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
            "five years and block lengths of 6, 24 and 36 months. The results are an input to the review of the rules "
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
    traces = [{"type": "scatter", "mode": "lines", "name": "Equity weight at the month end, before the top-up", "x": x,
               "y": [fmt.rounded(v * 100, 1) for v in data["equity_weight_before_top_up"]],
               "line": {"color": "@equity", "width": 1.5},
               **_hover([f"{m}: {fmt.pct(v)}" for m, v in zip(data["month"], data["equity_weight_before_top_up"])])},
              {"type": "scatter", "mode": "markers", "name": "Band order", "x": [_month_end(m) for m in band["month"]],
               "y": [fmt.rounded(v * 100, 1) for v in band["equity_weight_before_top_up"]],
               "marker": {"size": 11, "symbol": "diamond", "color": "@status_breach"},
               **_hover([f"{m}: band order, rule 5" for m in band["month"]])}]  # fmt: skip
    layout = {"showlegend": True, "yaxis": {"title": {"text": "Equity weight, per cent"}, "range": [60, 80], "dtick": 5},
              "xaxis": {"type": "date", "tickformat": "%Y", "hoverformat": "%Y-%m"},
              "shapes": [{"type": "rect", "xref": "paper", "yref": "y", "x0": 0, "x1": 1, "y0": low * 100,
                          "y1": high * 100, "fillcolor": "@band", "line": {"width": 0}, "layer": "below"},
                         _hline(70, "@ink")]}  # fmt: skip
    orders = data["orders"].astype(int)
    outside = ((data["equity_weight_before_top_up"] < low) | (data["equity_weight_before_top_up"] > high)).sum()
    rows = [["Cycle days", fmt.count(len(data))],
            ["Cycle days with one order", fmt.count((orders == 1).sum())],
            ["Cycle days with two orders", fmt.count((orders == 2).sum())],
            ["Cycle days with a band order", fmt.count(len(band))],
            ["Months of the band orders", ", ".join(band["month"])],
            ["Months with the equity weight outside the band before the top-up", fmt.count(outside)],
            ["Most orders on a cycle day, against the budget of five", fmt.count(orders.max())]]  # fmt: skip
    table = _table(["Count", "Value"], rows)
    note = (f"Simulation on index returns, monthly, in euro, gross of costs, with a starting amount of 100 and a top-up of "
            f"5 a month: {SAMPLE}, with the cycle at each month end in place of the 5th. Each top-up buys the sleeve "
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
                              **_hover([f"{m}<br>{name}: {fmt.index(v)}" for m, v in zip(history["month"], history[g])])})
        fall_traces.append({"type": "scatter", "mode": "lines", "name": name, "x": xs,
                            "y": [fmt.rounded(-v * 100, 1) for v in history[d]], "line": {"color": role, "width": 2},
                            **_hover([f"{m}<br>{name}: {fmt.pct(-v)} below the previous peak" for m, v in
                                      zip(history["month"], history[d])])})  # fmt: skip
    year_axis = {"type": "date", "tickformat": "%Y", "hoverformat": "%Y-%m"}
    growth_layout = {"showlegend": True, "yaxis": {"title": {"text": "Growth of 100"}}, "xaxis": year_axis}
    deepest = max(10.0, 1.3 * float(-history[["drawdown_rules", "drawdown_every_cycle_day"]].min().min()) * 100)
    shapes, annotations = [], []
    for level, text in ((35, "Test limit of the mandate, 35%"), (40, "Outer bound, 40%")):
        if level <= deepest:
            shapes.append(_hline(level))
            annotations.append(_label(1, level, text, xref="paper", anchor="right", yshift=8, xshift=0))
    fall_layout = {"showlegend": True, "xaxis": year_axis, "shapes": shapes, "annotations": annotations,
                   "yaxis": {"title": {"text": "Per cent below the previous peak"}, "range": [deepest, -1]}}  # fmt: skip
    year_ends = history[(history["month"].str.endswith("-12")) | (history.index == 0) | (history.index == len(history) - 1)]
    rows = [[r["month"] + (", start" if i == 0 else ""), fmt.index(r["growth_rules"]), fmt.index(r["growth_every_cycle_day"]),
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
             table=table, note=note, height=320, wide=True), {"id": "c27a", "traces": growth_traces, "layout": growth_layout})  # fmt: skip
    page.add("simulations", _card("c27b", "Simulation: fall from the previous peak under the rules and with the target "
             "weights restored on every cycle day, 1999 to 2025", "Monthly, February 1999 to December 2025",
             "mandate/simulation_history.csv", note="The same simulation as the growth of 100, month by month. " + SIMULATION_BASIS,
             height=300, wide=True), {"id": "c27b", "traces": fall_traces, "layout": fall_layout})  # fmt: skip

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


def log(page, monthly):
    if not len(monthly):
        page.add("log", _card("c24", "The monthly table", "", None, plot=False, wide=True,
                 empty="The first row appears with the first valuation day."))
        return
    month = ("Month", lambda r: r["month"] + ("" if r["complete"] == "yes" else " to date"))
    groups = [
        ("Returns and risk", [month, ("Last day", lambda r: r["last_day"]),
         ("Return", lambda r: fmt.pct(r["return_month"], True)),
         ("Since the first purchase", lambda r: fmt.pct(r["return_since_start"], True)),
         ("Money-weighted, cumulative", lambda r: fmt.pct(r["money_weighted_since_start"], True)),
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
        tables.append(f'<p class="label">{_esc(heading)}</p>' + _table(names, rows, numeric=numeric))
    page.add("log", _card("c24", "The monthly table", "Months since the first purchase. Drawdown and worst fall are "
             "per cent below the previous peak. Volatility from month 12", "outputs/metrics_monthly.csv", plot=False,
             wide=True, table=None, note="Each chart's own table is under it, and every tile is a cell of these tables or "
             "of outputs/portfolio_daily.csv.").replace('<p class="note">', "".join(tables) + '<p class="note">', 1))  # fmt: skip


# The page ------------------------------------------------------------------------------------------

TERM_LINE = re.compile(r"^- \*\*(.+?)\*\*: (.+)$")


def terms() -> list:
    """The terms of the README's Terms section, the one list the page's footer shows."""
    text = (config.ROOT / "README.md").read_text()
    section = text.split("\n## Terms\n", 1)[1].split("\n## ", 1)[0]
    found = [TERM_LINE.match(line.strip()) for line in section.splitlines() if line.strip()]
    if not found or not all(found):
        raise ValueError("README.md: every line of the Terms section must read '- **term**: definition'")
    return [(m.group(1)[0].upper() + m.group(1)[1:], m.group(2).replace("`", "")) for m in found]


DESCRIPTION = ("A real-money portfolio run under written rules, 70/30 equity and euro government bonds: allocation, "
               "rebalancing, costs, look-through and factor exposures.")  # fmt: skip
PREVIEW_IMAGE = "og-portfolio.png"


def _link_preview() -> str:
    """The tags that give a link to the page a title, a description and a picture, once the picture is in the root."""
    if not (config.ROOT / PREVIEW_IMAGE).exists():
        return ""
    tags = [("property", "og:type", "website"), ("property", "og:title", "Rules-based portfolio"),
            ("property", "og:description", DESCRIPTION), ("property", "og:url", config.DASHBOARD_URL),
            ("property", "og:image", config.DASHBOARD_URL + PREVIEW_IMAGE), ("name", "twitter:card", "summary_large_image")]  # fmt: skip
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
    import markdown

    text = (config.ROOT / "rules" / "RULES.md").read_text()
    body = markdown.markdown(text, extensions=["tables"])
    body = re.sub(r"<h1>.*?</h1>", "", body, count=1)
    return body.replace("<table>", '<div class="tw"><div class="tablewrap"><table>').replace("</table>", "</table></div></div>")


def build(out_dir: Path = None) -> Path:
    out = {p.name: pd.read_csv(p) for p in sorted(config.OUTPUTS_DIR.glob("*.csv"))}
    palette = json.loads((config.SITE_DIR / "palette.json").read_text())
    daily, monthly = out["portfolio_daily.csv"], out.get("metrics_monthly.csv", pd.DataFrame())
    if "month" in monthly and monthly["month"].isna().all():
        monthly = pd.DataFrame()
    orders = out["orders.csv"]
    page = Page()
    overview(page, daily, monthly, out["allocation_now.csv"], orders)
    rebalancing(page, daily, orders, out["band_events.csv"], out["compliance.csv"], monthly)
    costs(page, monthly, out["implementation_cost.csv"], daily)
    contributions(page, daily, monthly)
    lookthrough(page, out)
    factor_view(page, out["factor_loadings.csv"], out["factor_rolling.csv"], daily["date"].iloc[-1])
    allocation = pd.read_csv(config.ROOT / "mandate" / "allocation_check_results.csv")
    selection = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv")
    simulated = {name: _read(f"simulation_{name}.csv", config.ROOT / "mandate") for name in ("bootstrap", "history", "paths")}
    method(page, allocation, selection, _rules_html(), out["sources.csv"], simulated["bootstrap"])
    simulations(page, simulated["history"], simulated["paths"], monthly)
    log(page, monthly)
    _check_roles(page.charts, palette)

    first = daily["date"].iloc[1] if len(daily) > 1 else None
    leads = {
        "overview": "Where the portfolio stands and how it has done since the first purchase, with contributions removed.",
        "rebalancing": "The equity weight against its band, and every order against the rules.",
        "costs": "What running the portfolio costs, measured against reference portfolio A, which follows the same rules "
                 "at net asset value without costs.",
        "contributions": "Money paid in against gains and losses, in units of the starting amount.",
        "lookthrough": "The holdings of the two ETFs, weighted by each sleeve's weight in the portfolio, in three parts: "
                       + _link("lookthrough-equity", "the equity sleeve") + ", " + _link("lookthrough-bonds", "the bond sleeve")
                       + " and " + _link("lookthrough-portfolio", "the whole portfolio") + ", where currency exposure "
                       "combines both.",
        "factors": "The equity ETF's loadings on Kenneth French's developed-market factors.",
        "method": "How the split and the two ETFs were chosen, the data behind the charts, and the rules, in five "
                  "parts: " + _link("method-allocation", "the allocation test") + ", "
                  + _link("method-bootstrap", "its bootstrap") + ", "
                  + _link("method-selection", "the ETF selection") + ", " + _link("method-sources", "the data sources")
                  + " and " + _link("method-rules", "the rules") + ".",
        "simulations": "The rules applied to the allocation test's returns and to paths resampled from them, in three parts: "
                       + _link("simulations-mechanics", "the mechanics simulation") + ", "
                       + _link("simulations-history", "the historical simulation") + " and "
                       + _link("simulations-paths", "the resampled paths")
                       + ". Every chart here is a simulation on index returns, gross of costs. None is the portfolio's "
                       "record, which starts in October 2026.",
        "log": "Every figure behind the tiles and charts, by month.",
    }  # fmt: skip
    leads = {v: (text if v in ("lookthrough", "method", "simulations") else _esc(text)) for v, text in leads.items()}
    tabs = "".join(f'<button type="button" data-view="{v}" aria-selected="false">{_esc(t)}</button>' for v, t in VIEWS)
    sections = []
    for v, t in VIEWS:
        sections.append(f'<section class="view" id="view-{v}" aria-label="{_esc(t)}"><p class="lead">{leads[v]}</p>'
                        f'<div class="grid">{"".join(page.sections[v])}</div></section>')  # fmt: skip
    glossary = "".join(f"<dt>{_esc(a)}</dt><dd>{_esc(b)}</dd>" for a, b in terms())
    data = {"palette": palette, "charts": page.charts, "views": [{"id": v, "title": t} for v, t in VIEWS]}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    css = _palette_css(palette) + (config.SITE_DIR / "style.css").read_text()
    script = (config.SITE_DIR / "app.js").read_text()
    intro = ("A real-money portfolio run under written rules: 70 per cent in a global equity ETF and 30 per cent in a "
             "euro government bond ETF, funded by a starting amount and a fixed monthly top-up. Every figure is computed "
             "from the ledger and the issuers' published data.")  # fmt: skip
    started = f"First purchase {first}" if first else "First purchase 2026-10-08"
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
</head>
<body>
<header class="ch-band"><div class="ch-band__in">
<a class="ch-word" href="{SITE_URL}">Carlo Hofer</a>
<div class="ch-menu" role="navigation" aria-label="Site"><a href="{PROJECTS_URL}">Projects</a></div>
</div></header>
<p class="ch-back"><a href="{PROJECT_PAGE_URL}">&larr; Rules-based portfolio</a> &middot; <a href="{PROJECTS_URL}">All projects</a></p>
<header class="top"><div class="wrap">
<h1>Rules-based portfolio</h1>
<p>{_esc(intro)}</p>
<div class="meta"><span>{_esc(_two_dates(out["allocation_now.csv"].iloc[0]))}</span><span>{_esc(started)}</span>
<a href="{config.REPOSITORY_URL}">Repository</a><a href="{config.REPOSITORY_URL}/blob/main/rules/RULES.md">Rules</a>
<a href="{config.REPOSITORY_URL}/blob/main/mandate/MANDATE.md">Mandate</a></div>
</div></header>
<div class="viewtabs" role="navigation" aria-label="Views"><div class="wrap">{tabs}</div></div>
<main class="wrap">
{"".join(sections)}
</main>
<footer><div class="wrap">
<p>Returns are time-weighted and in euro, valued at the issuers' net asset values. A record of five to ten years cannot show that one set of rules is better than another, so the returns are not offered as evidence for the rules.</p>
<dl class="terms">{glossary}</dl>
{_colophon(out["allocation_now.csv"].iloc[0])}
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
