# Mandate

The mandate states what the portfolio is run for and the limits it is run within. The rules in `rules/RULES.md` put it into practice, and the split between the two sleeves follows from its risk limit through the test in `mandate/allocation_check.py`, whose output is `mandate/allocation_check_results.md`.

## Objective

The objective is the highest long-run growth within the risk limit, over a horizon of five to ten years, with no withdrawals during that horizon.

## Risk limit

The risk limit is a worst fall of about one third. The worst fall is the largest fall in the portfolio's value from a previous peak to a later low, measured on returns with contributions removed. A worst fall above 40 per cent is outside the mandate. The test reads "about one third" as at most 35 per cent: one third rounded up to the next 5 points, which leaves 5 points between the test and the outer bound of 40 per cent.

The limit sets the target weights. It never triggers a sale: in a fall, rule 8 applies and the cycle runs as written.

## Constraints

- The portfolio is long-only and holds two UCITS exchange-traded funds in euro, one on a global equity index of developed and emerging markets and one on a euro government bond index.
- Both ETFs are accumulating: they reinvest the income they receive and pay nothing out.
- At most five orders are placed in a month, the number the account's plan carries without commission.
- Euro amounts and units stay private. Weights, percentages and metrics are public.
- The rules change only by a dated amendment under rule 9.

## How the split follows from the risk limit

A split is the pair of target weights, written equity/bonds. The test builds monthly returns in euro for the two sleeves from February 1999 to December 2025:

- Equity: Kenneth French's developed-market and emerging-market returns, weighted 90 and 10, converted from US dollars to euro at the European Central Bank's month-end reference rate.
- Bonds: a seven-year euro area government bond priced from the European Central Bank's yield curve from October 2004, and from the European Central Bank's euro area ten-year government bond yield, a monthly average, before that date.

For every split from 40/60 to 100/0 in steps of 5 points, the test starts the portfolio at its target weights, rebalances it by its band, the interval of 5 points either side of the equity target weight, checked at each month end, and measures the worst fall. Costs are left out. The split held is the one with the largest equity target weight whose worst fall is within 35 per cent.

The result is 70/30. Its worst fall was 34.7 per cent, from August 2000 to March 2003, and its fall from October 2007 to February 2009 was 33.4 per cent. The worst fall of 75/25 was 37.8 per cent and that of 80/20 was 40.5 per cent. Growth per year over the period was 6.8 per cent at 70/30, 6.9 per cent at 75/25 and 7.2 per cent at 80/20.

The constructed returns follow two funds held in euro on the same markets. From 2021 to 2025 the equity series was within 2.0 percentage points of an MSCI ACWI fund in every calendar year, and the bond series within 0.9 points of the bond ETF the portfolio holds.

## What the test does not show

- The 27 years contain two deep falls in equity markets. Deeper falls are possible.
- Month-end values miss falls that reverse within a month.
- Before October 2004 the bond returns rest on monthly average yields, a rougher construction. The fall of 2007 to 2009 rests on the ECB curve and ranks the splits in the same order.
- Bonds rose during both equity falls of the period, by 24.6 per cent from September 2000 to March 2003 and by 9.8 per cent from November 2007 to February 2009. In 2022 they fell with equities, and every split lost between 13.3 and 15.9 per cent.
- The growth figures describe one history and are not a forecast.

## Rerunning the test

From the repository root, `pip install -r requirements.txt`, then `python3 mandate/allocation_check.py`. The script downloads its five source files into `cache/`, which is not committed, and rewrites `mandate/allocation_check_results.md`. The sample ends in December 2025, so a later run differs only where a source revises its history.
