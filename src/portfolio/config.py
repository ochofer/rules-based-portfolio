"""Fixed values: the rules' numbers, the two ETFs and the paths of the private files.

Every number of rules 1 to 7 that the program uses is defined here once. The euro amounts of rule 2 are
not: they are private and come from the ledger's contributions file.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER_DIR = ROOT / "ledger"  # private, ignored by git
CACHE_DIR = ROOT / "cache"  # downloaded source files, ignored by git
PRIVATE_DIR = ROOT / "private"  # private outputs, ignored by git
TRANSACTIONS = LEDGER_DIR / "transactions.csv"
CONTRIBUTIONS = LEDGER_DIR / "contributions.csv"

EQUITY, BONDS = "equity", "bonds"
SLEEVES = (EQUITY, BONDS)
ISIN = {EQUITY: "IE00B6R52259", BONDS: "IE00BH04GL39"}
SLEEVE_OF_ISIN = {isin: sleeve for sleeve, isin in ISIN.items()}
TICKER = {EQUITY: "IUSQ", BONDS: "VGEA"}
NAME = {
    EQUITY: "iShares MSCI ACWI UCITS ETF USD (Acc)",
    BONDS: "Vanguard EUR Eurozone Government Bond UCITS ETF (EUR) Accumulating",
}
NAV_CURRENCY = {EQUITY: "USD", BONDS: "EUR"}

# Rule 1: target weights. Rule 5: the band for the equity weight.
TARGET = {EQUITY: 0.70, BONDS: 0.30}
BAND = (0.65, 0.75)

# Rule 3: the cycle day is the 5th, or the first trading day after it.
CYCLE_DAY_OF_MONTH = 5

# Rule 6: orders a month that the account's plan carries without commission.
ORDERS_PER_MONTH = 5

# Rule 7: the window for orders, Amsterdam time.
TIMEZONE = "Europe/Amsterdam"
ORDER_WINDOW = (time(15, 45), time(17, 0))

# Orders are placed by euro amount and executed in fractional units. The broker's minimum order is one
# euro. A smaller order is not placed, and its cash waits for the next cycle day.
MIN_ORDER_EUR = 1.00

# Tradegate Exchange's quote page for each ETF: the real-time bid and ask recorded under rule 7.
QUOTE_PAGE = {sleeve: f"https://www.tradegate.de/orderbuch.php?isin={isin}" for sleeve, isin in ISIN.items()}
