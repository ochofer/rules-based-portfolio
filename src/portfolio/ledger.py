"""Reading and checking the private ledger.

The ledger is two CSV files kept outside git: transactions.csv, one row per order, and
contributions.csv, one row per contribution. read() loads both and checks them before anything else
runs. A malformed row, a sale of more units than are held or cash below zero stops the program with the
row named. An order outside rule 7's window or on a day Xetra is closed is a breach of rule 7: it is
reported and kept as recorded, never corrected.

Rows marked pre_book = yes (the sale of a holding before the first purchase) are kept for the record of
rule 10 and play no part in the portfolio.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path

import pandas as pd

from . import config, trading_days

TRANSACTION_FIELDS = [
    "date",
    "time_amsterdam",
    "isin",
    "instrument",
    "side",
    "units",
    "price",
    "price_currency",
    "fee",
    "fee_currency",
    "gross_amount",
    "net_amount",
    "amount_currency",
    "usd_per_eur",
    "net_amount_eur",
    "bid",
    "ask",
    "pre_book",
    "cost_basis_eur",
    "realised_gain_eur",
    "source",
    "note",
    "rule",
    "parts",
]
CONTRIBUTION_FIELDS = ["date", "time_amsterdam", "amount_eur", "kind", "source", "note"]
RULES_OF_AN_ORDER = {"start", "4", "5", "4+5"}
KINDS = {"start", "top-up"}


class LedgerError(ValueError):
    """A ledger row the program cannot use. The message names the file and the row."""


@dataclass
class Ledger:
    orders: pd.DataFrame  # the portfolio's orders in time order
    contributions: pd.DataFrame  # every contribution, in time order
    pre_book: pd.DataFrame  # rows recorded before the portfolio started (pre_book = yes)
    breaches: list = field(default_factory=list)  # breaches of rule 7, as text
    gaps: list = field(default_factory=list)  # fields rules 7 and 10 ask for that are missing or differ


def _time_of(text: str, where: str) -> time:
    """A recorded time: "15:52:10", "15:52", or "before 16:02:05" (taken as one second earlier)."""
    text = (text or "").strip()
    before = text.startswith("before ")
    m = re.fullmatch(r"(?:before )?(\d{2}):(\d{2})(?::(\d{2}))?", text)
    if not m:
        raise LedgerError(f"{where}: time {text!r} is not HH:MM or HH:MM:SS")
    h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    seconds = h * 3600 + mi * 60 + s - (1 if before else 0)
    return time(seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def _number(row: dict, name: str, where: str, required: bool = True) -> float:
    value = (row.get(name) or "").strip()
    if not value:
        if required:
            raise LedgerError(f"{where}: {name} is empty")
        return float("nan")
    try:
        return float(value)
    except ValueError:
        raise LedgerError(f"{where}: {name} {value!r} is not a number") from None


def _read_csv(path: Path, fields: list, label: str) -> pd.DataFrame:
    if not Path(path).exists():
        raise LedgerError(f"{label}: file not found at {path}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [f for f in fields if f not in frame.columns]
    if missing:
        raise LedgerError(f"{label}: missing columns {missing}")
    return frame


def read_transactions(path: Path = config.TRANSACTIONS) -> tuple:
    """The portfolio's orders and the rows recorded before it started, each checked field by field."""
    frame = _read_csv(path, TRANSACTION_FIELDS, "transactions.csv")
    orders, pre_book = [], []
    for i, row in enumerate(frame.to_dict("records"), start=2):
        where = f"transactions.csv, line {i}"
        if row["pre_book"].strip().lower() == "yes":
            pre_book.append(row)
            continue
        if row["isin"] not in config.SLEEVE_OF_ISIN:
            raise LedgerError(f"{where}: ISIN {row['isin']} is not one of the two ETFs")
        if row["side"] not in ("buy", "sell"):
            raise LedgerError(f"{where}: side {row['side']!r} is neither buy nor sell")
        if row["rule"] not in RULES_OF_AN_ORDER:
            raise LedgerError(f"{where}: rule {row['rule']!r} is not one of {sorted(RULES_OF_AN_ORDER)}")
        for name in ("price_currency", "fee_currency", "amount_currency"):
            if row[name] != "EUR":
                raise LedgerError(
                    f"{where}: {name} is {row[name]!r}; every order of the portfolio is in euro"
                )
        units = _number(row, "units", where)
        price = _number(row, "price", where)
        fee = _number(row, "fee", where)
        gross = _number(row, "gross_amount", where)
        if units <= 0 or price <= 0:
            raise LedgerError(f"{where}: units and price must be positive")
        if fee < 0:
            raise LedgerError(f"{where}: fee is negative")
        if abs(units * price - gross) > max(0.01, 1e-6 * gross):
            raise LedgerError(
                f"{where}: units times price is {units * price:.4f}, gross_amount is {gross:.2f}"
            )
        moment = datetime.combine(pd.Timestamp(row["date"]).date(), _time_of(row["time_amsterdam"], where))
        sleeve = config.SLEEVE_OF_ISIN[row["isin"]]
        cash_change = -(gross + fee) if row["side"] == "buy" else gross - fee
        orders.append(
            dict(
                moment=moment,
                sleeve=sleeve,
                isin=row["isin"],
                side=row["side"],
                units=units if row["side"] == "buy" else -units,
                price=price,
                fee=fee,
                gross=gross,
                cash_change=cash_change,
                rule=row["rule"],
                parts=row["parts"],
                bid=_number(row, "bid", where, required=False),
                ask=_number(row, "ask", where, required=False),
                cost_basis_eur=_number(row, "cost_basis_eur", where, required=False),
                realised_gain_eur=_number(row, "realised_gain_eur", where, required=False),
                line=i,
            )
        )
    columns = [
        "moment",
        "sleeve",
        "isin",
        "side",
        "units",
        "price",
        "fee",
        "gross",
        "cash_change",
        "rule",
        "parts",
        "bid",
        "ask",
        "cost_basis_eur",
        "realised_gain_eur",
        "line",
    ]
    orders = pd.DataFrame(orders, columns=columns).sort_values("moment", kind="stable").reset_index(drop=True)
    return orders, pd.DataFrame(pre_book)


def read_contributions(path: Path = config.CONTRIBUTIONS) -> pd.DataFrame:
    frame = _read_csv(path, CONTRIBUTION_FIELDS, "contributions.csv")
    rows = []
    for i, row in enumerate(frame.to_dict("records"), start=2):
        where = f"contributions.csv, line {i}"
        if row["kind"] not in KINDS:
            raise LedgerError(f"{where}: kind {row['kind']!r} is neither start nor top-up")
        amount = _number(row, "amount_eur", where)
        if amount <= 0:
            raise LedgerError(f"{where}: amount_eur must be positive")
        moment = datetime.combine(pd.Timestamp(row["date"]).date(), _time_of(row["time_amsterdam"], where))
        rows.append(dict(moment=moment, amount_eur=amount, kind=row["kind"], line=i))
    contributions = pd.DataFrame(rows, columns=["moment", "amount_eur", "kind", "line"])
    contributions = contributions.sort_values("moment", kind="stable").reset_index(drop=True)
    starts = contributions[contributions["kind"] == "start"]
    if len(starts) != 1 or (len(contributions) and contributions["kind"].iloc[0] != "start"):
        raise LedgerError(
            "contributions.csv: there must be exactly one contribution of kind start, and it comes first"
        )
    return contributions


def rule_7_breaches(orders: pd.DataFrame) -> list:
    """Orders placed on a day Xetra is closed or outside 15:45 to 17:00 Amsterdam time."""
    out = []
    start, end = config.ORDER_WINDOW
    for row in orders.itertuples():
        day, clock = row.moment.date(), row.moment.time()
        if not trading_days.is_trading_day(day):
            out.append(
                f"{day} {clock}: order on a day Xetra is closed (rule 7), transactions.csv line {row.line}"
            )
        elif not (start <= clock <= end):
            out.append(
                f"{day} {clock}: order outside 15:45 to 17:00 Amsterdam time (rule 7), "
                f"transactions.csv line {row.line}"
            )
    return out


def check_cash_and_units(orders: pd.DataFrame, contributions: pd.DataFrame) -> None:
    """Replays contributions and orders in time order: cash never below zero, no sale beyond holdings."""
    events = [
        (c.moment, 0, "contribution", c.amount_eur, None, 0.0, c.line) for c in contributions.itertuples()
    ]
    events += [(o.moment, 1, "order", o.cash_change, o.sleeve, o.units, o.line) for o in orders.itertuples()]
    cash, units = 0.0, {s: 0.0 for s in config.SLEEVES}
    for moment, _, kind, amount, sleeve, du, line in sorted(events, key=lambda e: (e[0], e[1])):
        cash += amount
        if sleeve is not None:
            units[sleeve] += du
            if units[sleeve] < -1e-9:
                raise LedgerError(f"transactions.csv, line {line}: sale of more {sleeve} units than are held")
        if cash < -0.005:
            raise LedgerError(
                f"{'transactions' if kind == 'order' else 'contributions'}.csv, line {line}: "
                f"cash would be {cash:.2f} euro after this row"
            )


def record_gaps(orders: pd.DataFrame) -> list:
    """Fields rule 7 asks the ledger to record that are missing: the bid and the ask at the order."""
    return [
        f"{row.moment:%Y-%m-%d %H:%M:%S}: bid and ask not recorded, transactions.csv line {row.line}"
        for row in orders.itertuples()
        if pd.isna(row.bid) or pd.isna(row.ask)
    ]


def average_costs(orders: pd.DataFrame) -> list:
    """Rule 10, order by order: the average price paid per unit, fees included, before each order, and
    for a sale the cost basis (that average times the units sold) and the realised gain (net proceeds
    minus the cost basis)."""
    cost, units, out = {s: 0.0 for s in config.SLEEVES}, {s: 0.0 for s in config.SLEEVES}, []
    for o in orders.itertuples():
        average = cost[o.sleeve] / units[o.sleeve] if units[o.sleeve] > 0 else float("nan")
        if o.side == "buy":
            cost[o.sleeve] += o.gross + o.fee
            units[o.sleeve] += o.units
            out.append(dict(line=o.line, average_before=average, cost_basis=None, gain=None))
        else:
            basis = average * -o.units
            cost[o.sleeve] -= basis
            units[o.sleeve] += o.units
            out.append(
                dict(line=o.line, average_before=average, cost_basis=basis, gain=o.gross - o.fee - basis)
            )
    return out


def average_cost(orders: pd.DataFrame, sleeve: str) -> float:
    """Rule 10: the average price paid per unit of a sleeve held after every recorded order, fees included."""
    cost = units = 0.0
    for o, c in zip(orders.itertuples(), average_costs(orders)):
        if o.sleeve == sleeve:
            cost += o.gross + o.fee if o.side == "buy" else -c["cost_basis"]
            units += o.units
    return cost / units if units > 1e-12 else float("nan")


def rule_10_gaps(orders: pd.DataFrame) -> list:
    """Sales whose cost basis or realised gain is missing, or differs by more than a cent from rule 10."""
    out = []
    for o, c in zip(orders.itertuples(), average_costs(orders)):
        if o.side != "sell":
            continue
        for name, recorded, expected in (
            ("cost_basis_eur", o.cost_basis_eur, c["cost_basis"]),
            ("realised_gain_eur", o.realised_gain_eur, c["gain"]),
        ):
            if pd.isna(recorded):
                out.append(
                    f"transactions.csv line {o.line}: {name} not recorded (rule 10 gives {expected:.2f})"
                )
            elif abs(recorded - expected) > 0.01:
                out.append(
                    f"transactions.csv line {o.line}: {name} is {recorded:.2f}, rule 10 gives {expected:.2f}"
                )
    return out


def read(transactions: Path = config.TRANSACTIONS, contributions: Path = config.CONTRIBUTIONS) -> Ledger:
    orders, pre_book = read_transactions(transactions)
    contrib = read_contributions(contributions)
    check_cash_and_units(orders, contrib)
    ledger = Ledger(orders=orders, contributions=contrib, pre_book=pre_book, breaches=rule_7_breaches(orders))
    ledger.gaps = record_gaps(orders) + rule_10_gaps(orders)
    return ledger
