"""Reading and checking the ledger: what stops the program, and what is reported as a breach of rule 7."""

import pytest

from conftest import BD, EQ, contribution, order
from portfolio import ledger

START = [contribution("2026-10-08", "before 09:30:00", 100, "start")]


def test_valid_ledger_reads_with_no_breach(start_ledger):
    t, c = start_ledger
    records = ledger.read(t, c)
    assert len(records.orders) == 2 and records.breaches == [] and records.gaps == []
    assert records.orders["cash_change"].sum() == pytest.approx(-100)


def test_fractional_units_are_accepted(write_ledger):
    t, c = write_ledger([order("2026-10-08", "16:00:00", EQ, "buy", "4.1234567891", "12.50")], START)
    assert ledger.read(t, c).orders["units"].iloc[0] == pytest.approx(4.1234567891)


@pytest.mark.parametrize(
    "clock, breach",
    [("15:44:59", True), ("15:45:00", False), ("17:00:00", False), ("17:00:01", True), ("09:31:00", True)],
)
def test_rule_7_window(write_ledger, clock, breach):
    t, c = write_ledger([order("2026-10-08", clock, EQ, "buy", 1, 10)], START)
    assert bool(ledger.read(t, c).breaches) is breach


def test_order_on_a_closed_day_is_a_breach(write_ledger):
    t, c = write_ledger([order("2026-10-10", "16:00:00", EQ, "buy", 1, 10)], START)  # a Saturday
    assert "Xetra is closed" in ledger.read(t, c).breaches[0]


def test_missing_bid_and_ask_is_reported(write_ledger):
    t, c = write_ledger([order("2026-10-08", "16:00:00", EQ, "buy", 1, 10)], START)
    assert "bid and ask not recorded" in ledger.read(t, c).gaps[0]


def test_negative_cash_stops(write_ledger):
    t, c = write_ledger([order("2026-10-08", "16:00:00", EQ, "buy", 11, 10)], START)
    with pytest.raises(ledger.LedgerError, match="cash would be"):
        ledger.read(t, c)


def test_sale_beyond_holdings_stops(write_ledger):
    t, c = write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 1, 10),
            order("2026-10-09", "16:00:00", EQ, "sell", 2, 10, rule="5"),
        ],
        START,
    )
    with pytest.raises(ledger.LedgerError, match="sale of more"):
        ledger.read(t, c)


def test_units_times_price_must_match_gross(write_ledger):
    row = order("2026-10-08", "16:00:00", EQ, "buy", 1, 10)
    row["gross_amount"] = "10.50"
    t, c = write_ledger([row], START)
    with pytest.raises(ledger.LedgerError, match="units times price"):
        ledger.read(t, c)


def test_rows_before_the_portfolio_started_are_kept_apart(write_ledger):
    t, c = write_ledger(
        [
            order(
                "2026-09-29",
                "15:50:00",
                "US9999999999",
                "sell",
                3,
                3,
                currency="USD",
                pre_book="yes",
                rule="",
            ),
            order("2026-10-08", "16:00:00", BD, "buy", 1, 3),
        ],
        START,
    )
    records = ledger.read(t, c)
    assert len(records.orders) == 1 and len(records.pre_book) == 1


def test_exactly_one_start_contribution_first(write_ledger):
    t, c = write_ledger([], [contribution("2026-10-02", "10:00", 5, "top-up")])
    with pytest.raises(ledger.LedgerError, match="kind start"):
        ledger.read(t, c)


def test_order_of_another_isin_stops(write_ledger):
    t, c = write_ledger([order("2026-10-08", "16:00:00", "IE00BK5BQT80", "buy", 1, 10)], START)
    with pytest.raises(ledger.LedgerError, match="not one of the two ETFs"):
        ledger.read(t, c)


def test_rule_10_average_cost_with_fees(write_ledger):
    # Two purchases: 2 units at 10 with a fee of 1 and 2 units at 12 with no fee: 45 for 4 units, 11.25 each.
    # A sale of 1 unit at 13 with a fee of 0.50: cost basis 11.25, realised gain 13 - 0.50 - 11.25 = 1.25.
    t, c = write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 2, 10, fee="1.00"),
            order("2026-10-09", "16:00:00", EQ, "buy", 2, 12),
            dict(
                order("2026-10-12", "16:00:00", EQ, "sell", 1, 13, fee="0.50", rule="5"),
                cost_basis_eur="11.25",
                realised_gain_eur="1.25",
            ),
        ],
        START,
    )
    records = ledger.read(t, c)
    sale = ledger.average_costs(records.orders)[-1]
    assert sale["average_before"] == pytest.approx(11.25) and sale["gain"] == pytest.approx(1.25)
    assert not [g for g in records.gaps if "rule 10" in g]


def test_rule_10_missing_or_wrong_values_are_reported(write_ledger):
    t, c = write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 2, 10, fee="1.00"),
            dict(order("2026-10-12", "16:00:00", EQ, "sell", 1, 13, rule="5"), cost_basis_eur="10.00"),
        ],
        START,
    )
    gaps = [g for g in ledger.read(t, c).gaps if "rule 10" in g]
    assert any("cost_basis_eur is 10.00, rule 10 gives 10.50" in g for g in gaps)
    assert any("realised_gain_eur not recorded (rule 10 gives 2.50)" in g for g in gaps)


def test_average_cost_of_the_units_held(write_ledger):
    t, c = write_ledger(
        [
            order("2026-10-08", "16:00:00", EQ, "buy", 2, 10, fee="1.00"),
            order("2026-10-09", "16:00:00", EQ, "buy", 2, 12),
            dict(
                order("2026-10-12", "16:00:00", EQ, "sell", 1, 13, rule="5"),
                cost_basis_eur="11.25",
                realised_gain_eur="1.75",
            ),
        ],
        START,
    )
    assert ledger.average_cost(ledger.read(t, c).orders, "equity") == pytest.approx(11.25)
