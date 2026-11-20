"""The cycle report, cycles/YYYY-MM.md: the ticket of a cycle day.

Before any order is placed, the report takes each rule that bears on the proposed orders and gives its
figure and a pass or a fail. After the orders are in the ledger, one line compares what was placed with
what was proposed. python3 -m portfolio cycle writes the report on the cycle day, and python3 -m portfolio
post adds the line after the orders. The check command keeps its job on the ledger after the fact.

The report is public. It carries weights, shares of the portfolio's value and counts, and no euro amount
or unit count. Each line is computed on its own, so a proposal or a ledger that breaks one rule fails that
line and no other: rule 4 is judged without the budget of rule 6, which has a line of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from . import config, ledger as ledger_module, risk, rule_11, rules_engine, trading_days
from . import formatting as fmt

E, B = config.EQUITY, config.BONDS
CENT = 0.005
NAME = {E: "equity", B: "bonds"}
ETF = {E: "the equity ETF", B: "the bond ETF"}
PENDING = "This line is added once the orders of the day are in the ledger."
# The listed terms are defined where a file first uses them, so that each report reads on its own.
CYCLE_DAY = "Cycle day (the day each month on which the rules are applied)"
WRITTEN = re.compile(r"\bWritten (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) Amsterdam time")


@dataclass(frozen=True)
class Check:
    rule: str
    subject: str
    figure: str
    passed: bool


def path_for(day: date):
    return config.CYCLES_DIR / f"{day:%Y-%m}.md"


def _parts(orders: list, rule: str) -> dict:
    """The signed euro amounts of one rule's parts, by sleeve."""
    out = {E: 0.0, B: 0.0}
    for o in orders:
        for r, amount in o.parts:
            if r == rule:
                out[o.sleeve] += amount
    return out


def _signed(o) -> float:
    return o.amount_eur if o.side == "buy" else -o.amount_eur


def orders_before(records, day: date, moment: datetime = None) -> int:
    """Orders already placed in the month of day: before moment on the day itself, and on the days before it."""
    m = records.orders["moment"]
    cut = pd.Timestamp(moment) if moment is not None and moment.date() == day else pd.Timestamp(day)
    same = (m.dt.year == day.year) & (m.dt.month == day.month) & (m < cut)
    return int(same.sum())


def check_rule_2(records, day: date) -> Check:
    contributions = records.contributions
    month = contributions["moment"].dt.to_period("M") == pd.Period(day, "M")
    subject = "A top-up (the fixed monthly contribution) recorded by the 2nd of the month"
    if (month & (contributions["kind"] == "start")).any():
        return Check("2", subject, "The starting amount was paid this month, so no top-up is due", True)
    top_ups = contributions[month & (contributions["kind"] == "top-up")]
    if not len(top_ups):
        return Check("2", subject, "No top-up recorded this month", False)
    first = top_ups["moment"].min().date()
    on_time = first <= date(day.year, day.month, 2)
    return Check("2", subject, f"Recorded {first}" + ("" if on_time else ", after the 2nd"), on_time)


def check_rule_3(day: date) -> Check:
    expected = trading_days.cycle_day(day.year, day.month)
    subject = "The cycle day"
    if day == expected:
        when = "the 5th" if day.day == config.CYCLE_DAY_OF_MONTH else "the first trading day after the 5th"
        return Check("3", subject, f"{day}, {when}", True)
    return Check("3", subject, f"{day}, and the cycle day of {day:%Y-%m} is {expected}", False)


def _matches(proposed: dict, expected: dict, left_out: set, allowed: float = CENT) -> bool:
    """Each sleeve's proposed part equals the rule's, or the rule's order for that sleeve is below one euro
    and is left out under the reading of 8 October."""
    return all(
        abs(proposed[s] - expected[s]) < allowed or (s in left_out and abs(proposed[s]) < CENT)
        for s in config.SLEEVES
    )


def check_rule_4(values: dict, proposed: list, reference, budget_binds: bool, target: dict = None) -> Check:
    target = target or config.TARGET
    total = values[E] + values[B] + values["cash"]
    cash = values["cash"]
    subject = (
        "The cash buys the sleeve (the part of the portfolio held in one ETF) furthest below its target weight "
        f"({round(target[E] * 100)} per cent equity, {round(target[B] * 100)} per cent bonds), and the remainder "
        "buys the other"
    )
    gap = ", ".join(
        f"{NAME[s]} {fmt.points((values[s] / total - target[s]) * 100)}" for s in config.SLEEVES
    )
    raw = reference.orders + reference.below_minimum
    left_out = {o.sleeve for o in reference.below_minimum}
    p4, r4 = _parts(proposed, "4"), _parts(raw, "4")
    if budget_binds and all(abs(p4[s]) < CENT for s in config.SLEEVES):
        return Check(
            "4",
            subject,
            f"Weight minus target: {gap}. The top-up waits for the next cycle day (rule 6)",
            True,
        )
    if cash < CENT:
        return Check(
            "4", subject, f"Weight minus target: {gap}. No cash to invest", all(abs(p4[s]) < CENT for s in p4)
        )
    passed = _matches(p4, r4, left_out)
    figure = (
        f"Weight minus target: {gap}. Proposed: {fmt.pct(p4[E] / cash)} of the cash to equity, "
        f"{fmt.pct(p4[B] / cash)} to bonds"
    )
    if not passed:
        figure += f". The rule gives {fmt.pct(r4[E] / cash)} and {fmt.pct(r4[B] / cash)}"
    return Check("4", subject, figure, passed)


def check_minimum(proposed: list, reference) -> Check:
    small = [o for o in proposed if o.amount_eur < config.MIN_ORDER_EUR]
    figure = "None proposed" if not small else f"{len(small)} proposed"
    if reference.below_minimum:
        n = len(reference.below_minimum)
        figure += f". The rules give {n} below one euro, left out, and the cash waits for the next cycle day"
    return Check("4, reading", "No order below one euro", figure, not small)


def check_rule_5(values: dict, proposed: list, reference, waits: bool, target: dict = None, band: tuple = None) -> Check:
    target, band = target or config.TARGET, band or config.BAND
    low, high = (round(x * 100) for x in band)
    total = values[E] + values[B] + values["cash"]
    subject = (
        f"The equity weight against the band, the interval from {low} to {high} per cent, before and after the orders"
    )
    p5 = _parts(proposed, "5")
    left_out = {o.sleeve for o in reference.below_minimum}
    if waits:
        expected = rules_engine.rule_5(
            {s: values[s] for s in config.SLEEVES}, values["cash"], invest_cash=False, target=target, band=band
        )
        expected = {s: expected[s] if abs(expected[s]) >= CENT else 0.0 for s in config.SLEEVES}
        triggered = any(abs(a) >= CENT for a in expected.values())
        allowed = 0.011  # the band orders alone are rounded to the cent on their own
    else:
        expected = _parts(reference.orders + reference.below_minimum, "5")
        triggered = reference.band_triggered
        allowed = CENT
    after = values[E] + sum(_signed(o) for o in proposed if o.sleeve == E)
    passed = _matches(p5, expected, left_out, allowed)
    figure = f"Equity {fmt.pct(values[E] / total)} before and {fmt.pct(after / total)} after. "
    figure += (
        f"Outside {low} to {high} after the top-up, so back to {rule_11.split_name(target[E])}" if triggered
        else "Band not triggered"
    )
    if not passed:
        figure += ". The proposed band orders differ from the rule's"
    return Check("5", subject, figure, passed)


def check_rule_11(row: dict, record: pd.DataFrame = None) -> Check:
    """Rule 11: the two month ends the cycle day reads, the reading of each, and the target and the band in force."""
    return Check("11", "The target follows the allocation test, read at the two month ends before the cycle day",
                 rule_11.line(row, record), True)


def check_rule_6(used: int, proposed: list) -> Check:
    n = len(proposed)
    figure = f"{used} placed earlier this month and {n} proposed: {used + n} of {config.ORDERS_PER_MONTH}"
    return Check(
        "6", "Orders this month against the allowance of five", figure, used + n <= config.ORDERS_PER_MONTH
    )


def check_rule_7(day: date, at: datetime) -> Check:
    start, end = config.ORDER_WINDOW
    subject = "Orders placed between 15:45 and 17:00 Amsterdam time, with the bid and ask saved first"
    trading = trading_days.is_trading_day(day)
    figure = f"Written {at:%H:%M}, window {start:%H:%M} to {end:%H:%M}"
    if at.date() != day:
        figure = f"Written on {at.date()}, and the window is on {day}"
    elif not trading:
        figure += f". {day} is not a trading day"
    elif at.time() > end:
        figure += ", after the window closed"
    elif not trading_days.us_market_open(day):
        figure += ". The US equity market is closed today, and the orders are still placed in the window (reading of 8 October)"
    figure += ". Bid and ask from Tradegate before each order"
    return Check("7", subject, figure, trading and at.date() == day and at.time() <= end)


def check_rule_10(records, proposed: list) -> Check:
    subject = "The average cost basis a sale would use"
    gaps = ledger_module.rule_10_gaps(records.orders)
    if gaps:
        return Check(
            "10",
            subject,
            f"{len(gaps)} field{'s' if len(gaps) > 1 else ''} of earlier sales missing or off",
            False,
        )
    sales = [o for o in proposed if o.side == "sell"]
    if not sales:
        return Check(
            "10",
            subject,
            "No sale proposed. Every earlier sale carries its cost basis and realised gain",
            True,
        )
    known = all(pd.notna(ledger_module.average_cost(records.orders, o.sleeve)) for o in sales)
    names = " and ".join(ETF[o.sleeve] for o in sales)
    figure = (f"A sale of {names} is proposed. The average cost per unit, fees included, is in the private file of the day"
              if known else f"A sale of {names} is proposed, and the ledger holds no purchase to average")  # fmt: skip
    return Check("10", subject, figure, known)


def before_orders(records, day: date, at: datetime, values: dict, proposed: list, target: dict = None,
                  band: tuple = None, rule11: dict = None) -> list:  # fmt: skip
    """Every check of the report, in the order of the rules. values are euro values of each sleeve and of
    cash at the last net asset values; proposed are the orders the cycle command gives. target and band are those
    in force on the day under rule 11, and rule11 the day's row of its table, from 5 January 2027."""
    used = orders_before(records, day, at)
    reference = rules_engine.plan(values[E], values[B], values["cash"], target=target, band=band)  # without the budget
    budget_binds = used + len(reference.orders) > config.ORDERS_PER_MONTH
    waits = budget_binds and all(abs(_parts(proposed, "4")[s]) < CENT for s in config.SLEEVES)
    return [
        check_rule_2(records, day),
        check_rule_3(day),
        check_rule_4(values, proposed, reference, budget_binds, target),
        check_minimum(proposed, reference),
        check_rule_5(values, proposed, reference, waits, target, band),
        check_rule_6(used, proposed),
        check_rule_7(day, at),
        check_rule_10(records, proposed),
    ] + ([check_rule_11(rule11)] if rule11 else [])


def _cell(text: str) -> str:
    return str(text).replace("|", "/")


def _table(columns: list, rows: list) -> str:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def proposal_rows(values: dict, proposed: list) -> list:
    total = values[E] + values[B] + values["cash"]
    rows = []
    for k, o in enumerate(proposed, start=1):
        if len(o.parts) == 2:
            shares = " and ".join(fmt.pct(a / _signed(o)) for _, a in o.parts)
            rules = f"rules {o.parts[0][0]} and {o.parts[1][0]}, {shares}"
        else:
            rules = f"rule {o.parts[0][0]}"
        rows.append([str(k), NAME[o.sleeve].capitalize(), o.side, fmt.pct(o.amount_eur / total), rules])
    return rows


def write_before(records, day: date, at: datetime, values: dict, proposed: list, nav_day, target: dict = None,
                 band: tuple = None, rule11: dict = None) -> str:  # fmt: skip
    """The text of the report before the orders."""
    checks = before_orders(records, day, at, values, proposed, target, band, rule11)
    failed = [c for c in checks if not c.passed]
    lines = [
        f"# Cycle report, {day:%B %Y}",
        "",
        f"{CYCLE_DAY}: {day}. Written {at:%Y-%m-%d %H:%M} Amsterdam time by the program, before any "
        f"order of the day, at the net asset values of {pd.Timestamp(nav_day):%Y-%m-%d}.",
        "",
        "## Before the orders",
        "",
        _table(["Rule", "Check", "Figure", "Result"], [[c.rule, c.subject, c.figure, "pass" if c.passed else "fail"]
                                                       for c in checks]),  # fmt: skip
        "",
        f"{len(checks) - len(failed)} of {len(checks)} checks pass."
        + ("" if not failed else " Failed: rule " + ", rule ".join(c.rule for c in failed) + "."),
        "",
    ]
    if proposed:
        lines += ["Proposed orders, in shares of the portfolio's value:", "",
                  _table(["Order", "Sleeve", "Side", "Share of the portfolio", "Rule"], proposal_rows(values, proposed)), ""]  # fmt: skip
    else:
        lines += ["No order is proposed.", ""]
    tracking = tracking_line(values, proposed)
    if tracking:
        lines += [tracking, ""]
    lines += ["## After the orders", "", PENDING, ""]
    return "\n".join(lines)


def tracking_line(values: dict, proposed: list, out_dir=None) -> str:
    """One information line: the estimated tracking error against the benchmark at the weights before the orders
    and at the weights the proposed orders give, at the covariance and look-through of the last build. It is no
    check and triggers nothing. Empty when the build's risk tables are missing."""
    out_dir = out_dir or config.OUTPUTS_DIR
    try:
        components = pd.read_csv(out_dir / "risk_components.csv")
        pairs = pd.read_csv(out_dir / "risk_correlation.csv")
    except FileNotFoundError:
        return ""
    cov = risk.covariance_from_tables(components, pairs)
    shares = risk.shares_from_components(components)
    total = values[E] + values[B] + values["cash"]
    after = {s: values[s] + sum(_signed(o) for o in proposed if o.sleeve == s) for s in config.SLEEVES}
    before_te = risk.tracking_error(risk.active_weights(values[E] / total, values[B] / total, shares), cov)
    after_te = risk.tracking_error(risk.active_weights(after[E] / total, after[B] / total, shares), cov)
    as_of = components["as_of"].iloc[0]
    start, end = (pd.Period(str(components[c].iloc[0]), "M") for c in ("window_start", "window_end"))
    months = (end - start).n + 1
    return (f"Information, no check. The benchmark is the index blend: 70 per cent MSCI ACWI net total return and 30 per "
            f"cent the Bloomberg Euro-Aggregate Treasury index, in euro, rebalanced at each month end. The estimated "
            f"tracking error against it is the standard deviation over a year of the portfolio's return less the "
            f"benchmark's, computed from the covariance of index returns over the {months} months from {start} to {end} "
            f"and the look-through (the portfolio's exposure to the securities inside the two ETFs) of {as_of}. A basis "
            f"point is one hundredth of a percentage point. The estimated tracking error is {round(before_te * 1e4)} "
            f"basis points at the weights before the orders and {round(after_te * 1e4)} at the weights the proposed "
            f"orders give. It triggers nothing.")  # fmt: skip


def state_before(records, day: date) -> dict:
    """Units and cash after every contribution to the end of day and every order before day."""
    units = {E: 0.0, B: 0.0}
    cash = sum(c.amount_eur for c in records.contributions.itertuples() if c.moment.date() <= day)
    for o in records.orders.itertuples():
        if o.moment.date() < day:
            units[o.sleeve] += o.units
            cash += o.cash_change
    return {"units": units, "cash": cash}


def proposal_on(records, navs_eur: pd.DataFrame, day: date) -> tuple:
    """The values before the orders of day and the orders the rules give for them, recomputed from the ledger
    as the cycle command computed them."""
    last_close = pd.Timestamp(trading_days.previous_trading_day(day))
    state = state_before(records, day)
    unit_value = navs_eur.loc[:last_close].iloc[-1]
    values = {s: state["units"][s] * float(unit_value[s]) for s in config.SLEEVES}
    values["cash"] = state["cash"]
    used = orders_before(records, day)
    target, band, _ = rule_11.in_force(records, navs_eur, day)
    plan = rules_engine.plan(values[E], values[B], values["cash"], orders_used_this_month=used, target=target, band=band)
    return values, plan


def after_orders(records, day: date, values: dict, proposed: list, written: datetime) -> str:
    """The line after the orders: proposed against placed, the window, the quotes and the half-spread."""
    placed = records.orders[records.orders["moment"].dt.date == day]
    placed = placed[placed["rule"].isin(["4", "5", "4+5"])]
    if not len(proposed) and not len(placed):
        return "After the orders: none was proposed and none was placed."
    start, end = config.ORDER_WINDOW
    wanted = sorted((o.sleeve, o.side) for o in proposed)
    done = sorted((o.sleeve, o.side) for o in placed.itertuples())
    parts = [f"After the orders: {len(placed)} placed against {len(proposed)} proposed"]
    parts.append("the same sleeves and sides" if wanted == done else "different sleeves or sides")
    if wanted == done and len(placed):
        amount = {(o.sleeve, o.side): o.amount_eur for o in proposed}
        ratios = [(o.gross + o.fee if o.side == "buy" else o.gross) / amount[(o.sleeve, o.side)]
                  for o in placed.itertuples()]  # fmt: skip
        parts.append("at " + " and ".join(fmt.pct(r) for r in ratios) + " of the proposed amounts")
    inside = sum(start <= o.moment.time() <= end for o in placed.itertuples())
    quoted = [o for o in placed.itertuples() if pd.notna(o.bid) and pd.notna(o.ask)]
    line = ", ".join(parts) + ". "
    if len(placed):
        line += f"Inside {start:%H:%M} to {end:%H:%M}: {inside} of {len(placed)}. "
        line += f"Bid and ask recorded: {len(quoted)} of {len(placed)}."
        if quoted:
            spreads = [(o.ask - o.bid) / (o.ask + o.bid) * 1e4 for o in quoted]
            line += " Half-spread " + " and ".join(fmt.bps(x, signed=False) for x in spreads) + "."
        first = placed["moment"].min()
        line += " The report was written before the first order: " + ("yes." if written < first else "no.")
    return line.strip()


def written_at(text: str) -> datetime:
    m = WRITTEN.search(text)
    if not m:
        raise ValueError("the cycle report has no line 'Written YYYY-MM-DD HH:MM Amsterdam time'")
    return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")


def add_after(text: str, line: str) -> str:
    if PENDING in text:
        return text.replace(PENDING, line)
    head, _, _ = text.partition("## After the orders")
    return head + "## After the orders\n\n" + line + "\n"
