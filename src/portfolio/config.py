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
OUTPUTS_DIR = ROOT / "outputs"  # public: shares, percentages and basis points only
METHOD_DIR = ROOT / "method"  # public: the fixed tables the program applies
CYCLES_DIR = ROOT / "cycles"  # public: the cycle report of each cycle day, shares and counts only
NOTES_DIR = ROOT / "notes"  # public: the monthly notes, written by hand after each cycle day
SITE_DIR = ROOT / "site"  # public: the page template, its script and the palette
REPOSITORY_URL = "https://github.com/ochofer/rules-based-portfolio"
DASHBOARD_URL = "https://www.carlohofer.com/rules-based-portfolio/"
PREVIEW_IMAGE = "og-portfolio.png"  # the link-preview picture at the root, for the dashboard and each quarterly issue
# The visit counter of the site, in the head of every page the repository publishes: GoatCounter, which sets no
# cookies and does not count a page opened from a file. Its fifth version is pinned with its integrity hash. The
# second script is the site's own, written without the conditional operator: a click on a PDF, or on a link to
# another site, is counted as an event.
COUNTER = ('<script data-goatcounter="https://carlohofer.goatcounter.com/count" async src="https://gc.zgo.at/count.v5.js" '
           'crossorigin="anonymous" integrity="sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"></script>\n'
           """<script>
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a[href]');
  if (!a || !window.goatcounter || !window.goatcounter.count) return;
  var u = new URL(a.href, location.href);
  var pdf = /\\.pdf$/i.test(u.pathname);
  if (!pdf && u.hostname === location.hostname) return;
  var path = 'PDF ' + u.hostname + u.pathname;
  if (!pdf) path = 'Link ' + (u.hostname || u.protocol) + u.pathname;
  window.goatcounter.count({path: path, title: a.textContent.trim(), event: true});
});
</script>""")
COUNTER_HOST = "https://gc.zgo.at/**"  # not loaded when a page is printed

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

# Tradegate Exchange's quote page for each ETF: the bid and ask it shows at the time, recorded under rule 7.
QUOTE_PAGE = {sleeve: f"https://www.tradegate.de/orderbuch.php?isin={isin}" for sleeve, isin in ISIN.items()}

# The mandate's limits, drawn on chart 4: the test reads "about one third" as 35 per cent, and a worst
# fall above 40 per cent is outside the mandate.
RISK_LIMIT_TEST = 0.35
RISK_LIMIT_OUTER = 0.40

# The factor model of charts 18 and 19: French's developed five factors and momentum, in this order.
FACTORS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "WML")
FACTOR_NAME = {
    "Mkt-RF": "Market",
    "SMB": "Size",
    "HML": "Value",
    "RMW": "Profitability",
    "CMA": "Investment",
    "WML": "Momentum",
}
FACTOR_WINDOW_MONTHS = 36
