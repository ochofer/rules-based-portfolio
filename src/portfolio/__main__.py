"""Command line: python3 -m portfolio <command>, run from the repository root with PYTHONPATH=src.

Commands:
  check              read and check the ledger; list breaches of rule 7 and the fields rules 7 and 10
                     ask for that are missing or differ from the rule
  status [--date D]  units, values and weights at the last net asset values on or before D
  cycle  [--date D]  the orders rules 4 to 6 produce on the cycle day D (default: this month's); run on
                     the cycle day itself, it also saves them to private/orders/
  build  [--date D]  the public files in outputs/ and the dashboard, index.html at the root
  privacy            check that no figure in outputs/ is a private amount of the ledger
Add --refresh to download every source again first.

Every command prints euro amounts and units, which are private: the output is for the terminal and for
files under private/, never for the repository.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime

import pandas as pd

from . import config, ledger as ledger_module, positions, prices, rules_engine, trading_days, valuations


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def _load(refresh: bool, end: date):
    records = ledger_module.read()
    held = positions.build(records, end)
    series = prices.load(refresh=refresh)
    return records, held, prices.navs_in_euro(series), series


def _stale(series: dict, day: pd.Timestamp) -> list:
    """A note for each fund whose last net asset value on or before day is from an earlier day."""
    out = []
    for sleeve, name in ((config.EQUITY, "equity_usd"), (config.BONDS, "bonds_eur")):
        last = series[name].loc[:day].index.max()
        if last < day:
            out.append(
                f"Note: the last net asset value of {config.TICKER[sleeve]} on or before {day:%Y-%m-%d} is "
                f"from {last:%Y-%m-%d}. If the fund has published one since, run again with --refresh."
            )
    return out


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def cmd_check(args) -> int:
    records = ledger_module.read()
    print(
        f"Ledger read: {_count(len(records.orders), 'order', 'orders')}, "
        f"{_count(len(records.contributions), 'contribution', 'contributions')}, "
        f"{_count(len(records.pre_book), 'row', 'rows')} recorded before the portfolio started."
    )
    for line in records.breaches:
        print("  breach of rule 7:", line)
    for line in records.gaps:
        print("  not recorded:", line)
    if not records.breaches and not records.gaps:
        print("  No breach of rule 7 and nothing missing.")
    return 0


def cmd_status(args) -> int:
    day = args.date or date.today()
    records, held, navs, series = _load(args.refresh, day)
    v = valuations.at(held, navs, pd.Timestamp(day))
    total = v[config.EQUITY] + v[config.BONDS] + v["cash"]
    print(f"Values at the net asset values of {v['nav_date']:%Y-%m-%d} (positions at the end of {day}):")
    for sleeve in config.SLEEVES:
        units = held.loc[: pd.Timestamp(day)].iloc[-1][sleeve]
        print(
            f"  {config.TICKER[sleeve]:5} {units:16.10f} units x {v['navs'][sleeve]:9.4f} EUR = "
            f"{v[sleeve]:10.2f} EUR  {_pct(v[sleeve] / total):>6}"
        )
    print(f"  cash  {v['cash']:44.2f} EUR  {_pct(v['cash'] / total):>6}")
    print(f"  total {total:44.2f} EUR")
    return 0


def cmd_cycle(args) -> int:
    today = date.today()
    day = args.date or trading_days.cycle_day(today.year, today.month)
    expected = trading_days.cycle_day(day.year, day.month)
    if day != expected:
        print(f"Note: the cycle day of {day:%Y-%m} under rule 3 is {expected}, not {day}.")
    records, held, navs, series = _load(args.refresh, day)
    # Units and cash as recorded up to the cycle day (a late top-up included), valued at the net asset
    # values of the last trading day before it: the latest published when the orders are placed.
    last_close = pd.Timestamp(trading_days.previous_trading_day(day))
    v = valuations.at(held, navs, pd.Timestamp(day), nav_day=last_close)
    month_top_ups = records.contributions[
        (records.contributions["kind"] == "top-up")
        & (records.contributions["moment"].dt.year == day.year)
        & (records.contributions["moment"].dt.month == day.month)
    ]
    used = positions.orders_in_month(records, day.year, day.month)
    plan = rules_engine.plan(v[config.EQUITY], v[config.BONDS], v["cash"], orders_used_this_month=used)
    lines = [f"Cycle day {day} (rule 3). Values at the net asset values of {v['nav_date']:%Y-%m-%d}.", ""]
    stale = _stale(series, last_close)
    if not trading_days.us_market_open(day):
        stale.append(
            "Note: the US equity market is closed today. The orders are still placed today between "
            "15:45 and 17:00 Amsterdam time (rules/RULES.md, Amendments, rule 7)."
        )
    lines += stale + ([""] if stale else [])
    if month_top_ups.empty:
        lines.append(
            f"Warning: no top-up recorded in contributions.csv for {day:%Y-%m} (rule 2: by the 2nd)."
        )
    wb = plan.weights("before")
    lines.append(
        f"Before: equity {_pct(wb[config.EQUITY])}, bonds {_pct(wb[config.BONDS])}, "
        f"cash {_pct(wb['cash'])} ({plan.before['cash']:.2f} EUR not yet invested)."
    )
    lines.append(
        f"Band of rule 5 (65 to 75 per cent): {'triggered' if plan.band_triggered else 'not triggered'}."
    )
    lines.append(f"Orders this month before today: {used} of {config.ORDERS_PER_MONTH}.")
    lines.append("")
    if not plan.orders:
        lines.append("No order today.")
    for k, o in enumerate(plan.orders, start=1):
        unit_value = v["navs"][o.sleeve]
        parts = ", ".join(f"rule {r}: {a:+.2f} EUR" for r, a in o.parts)
        lines.append(
            f"{k}. {o.side.upper()} {config.TICKER[o.sleeve]} ({config.ISIN[o.sleeve]}) "
            f"for {o.amount_eur:.2f} EUR  [{parts}]  "
            f"about {o.amount_eur / unit_value:.4f} units at the last net asset value"
        )
        lines.append(f"   Before placing it, screenshot the bid and ask: {config.QUOTE_PAGE[o.sleeve]}")
        if o.side == "sell":
            average = ledger_module.average_cost(records.orders, o.sleeve)
            lines.append(
                f"   Rule 10: average cost {average:.4f} EUR per unit, fees included. "
                f"Record cost_basis_eur = units sold x {average:.4f} "
                f"and realised_gain_eur = net proceeds minus cost_basis_eur."
            )
        if len(o.parts) == 2:
            share = {r: a / (o.amount_eur if o.side == "buy" else -o.amount_eur) for r, a in o.parts}
            lines.append(
                f"   Ledger: rule 4+5, and parts splits the executed units "
                f"{100 * share['4']:.2f} per cent to rule 4 and {100 * share['5']:.2f} per cent to rule 5, "
                f"written 4:units|5:units."
            )
        else:
            lines.append(f"   Ledger: rule {o.parts[0][0]}.")
    if plan.orders:
        wa = plan.weights("after")
        lines += [
            "",
            f"After: equity {_pct(wa[config.EQUITY])}, bonds {_pct(wa[config.BONDS])}, "
            f"cash {_pct(wa['cash'])}.",
            "Place the orders on this trading day between 15:45 and 17:00 Amsterdam time (rule 7), in the "
            "order listed: a sale comes first and the purchase uses its proceeds.",
        ]
    lines += plan.notes
    text = "\n".join(lines)
    print(text)
    if day != today:
        print(f"\nNot saved: {day} is not today. The file of a cycle day is written only on that day.")
        return 0
    out = config.PRIVATE_DIR / "orders" / f"ORDERS_{day}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + f"\n\nWritten {datetime.now():%Y-%m-%d %H:%M} by python3 -m portfolio cycle.\n")
    print(f"\nSaved to {out.relative_to(config.ROOT)}")
    return 0


def cmd_build(args) -> int:
    from . import outputs, site

    result = outputs.build(refresh=args.refresh, today=args.date)
    page = site.build()
    print(f"Outputs as of {result['as_of']:%Y-%m-%d}: {len(result['files'])} files in outputs/.")
    print(f"Dashboard written to {page.relative_to(config.ROOT)}.")
    return 0


def cmd_privacy(args) -> int:
    from . import outputs

    outputs.privacy(ledger_module.read())
    print("No private figure in outputs/.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m portfolio")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "status", "cycle", "build", "privacy"):
        p = sub.add_parser(name)
        p.add_argument("--date", type=lambda s: datetime.strptime(s, "%Y-%m-%d").date())
        p.add_argument("--refresh", action="store_true")
    args = parser.parse_args(argv)
    try:
        commands = {"check": cmd_check, "status": cmd_status, "cycle": cmd_cycle, "build": cmd_build,
                    "privacy": cmd_privacy}  # fmt: skip
        return commands[args.command](args)
    except (ledger_module.LedgerError, rules_engine.BudgetError, RuntimeError, ValueError) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
