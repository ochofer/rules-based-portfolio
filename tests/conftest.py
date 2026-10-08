"""Shared helpers for the tests. Every ledger here is synthetic: a starting amount of 100 and small orders."""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from portfolio import config, ledger  # noqa: E402

EQ, BD = config.ISIN[config.EQUITY], config.ISIN[config.BONDS]


def order(
    date,
    time,
    isin,
    side,
    units,
    price,
    fee="0.00",
    rule="start",
    pre_book="no",
    currency="EUR",
    bid="",
    ask="",
):
    gross = f"{float(units) * float(price):.2f}"
    return dict(
        date=date,
        time_amsterdam=time,
        isin=isin,
        instrument="",
        side=side,
        units=str(units),
        price=str(price),
        price_currency=currency,
        fee=fee,
        fee_currency=currency,
        gross_amount=gross,
        net_amount=gross,
        amount_currency=currency,
        usd_per_eur="",
        net_amount_eur=gross,
        bid=bid,
        ask=ask,
        pre_book=pre_book,
        cost_basis_eur="",
        realised_gain_eur="",
        source="test",
        note="",
        rule=rule,
        parts="",
    )


def contribution(date, time, amount, kind):
    return dict(date=date, time_amsterdam=time, amount_eur=str(amount), kind=kind, source="test", note="")


def write(path, fields, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return path


@pytest.fixture
def write_ledger(tmp_path):
    def _write(orders, contributions):
        t = write(tmp_path / "transactions.csv", ledger.TRANSACTION_FIELDS, orders)
        c = write(tmp_path / "contributions.csv", ledger.CONTRIBUTION_FIELDS, contributions)
        return t, c

    return _write


@pytest.fixture
def start_ledger(write_ledger):
    """A starting amount of 100 on Thursday 2026-10-08, invested 70 and 30 at 16:00 and 16:01."""
    return write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 7, 10, bid="9.99", ask="10.01"),
            order("2026-10-08", "16:01:00", BD, "buy", 10, 3, bid="2.99", ask="3.01"),
        ],
        [contribution("2026-10-08", "before 15:59:00", 100, "start")],
    )
