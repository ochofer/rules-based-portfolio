# Mandate

The portfolio is run for the highest long-run growth over five to ten years, with no withdrawals, within a worst fall (the largest fall in its value from a previous peak to a later low) of about one third. The limit sets the split, the pair of weights the rules aim for, written equity/bonds. On monthly euro returns from 1999 to 2025, 70 per cent is the largest equity target weight whose worst fall stayed within 35 per cent, a split of 70/30. The rules in `rules/RULES.md` put the mandate into practice.

## Risk limit

The risk limit is a worst fall of about one third, measured on returns with contributions removed. A worst fall above 40 per cent is outside the mandate. The test reads "about one third" as at most 35 per cent, one third rounded up to the next 5 points, which leaves 5 points between the test and the outer bound of 40 per cent.

The limit sets the target weights and never triggers a sale. In a fall, rule 8 applies and the cycle runs as written.

## Constraints

- The portfolio is long-only and holds two exchange-traded funds (ETFs) traded in euro on Xetra, one on a global equity index of developed and emerging markets and one on a euro government bond index. Both are UCITS (Undertakings for Collective Investment in Transferable Securities) funds, the European Union standard for funds sold to the public.
- Both ETFs are accumulating: they reinvest the income they receive and pay nothing out.
- At most five orders are placed in a month, the number the account's plan carries without commission.
- The rules change only by a dated amendment under rule 9.

## How the split follows from the risk limit

Each sleeve is the part of the portfolio held in one ETF. The test builds monthly euro returns for both sleeves from February 1999, the second month of the euro, to December 2025:

- Equity: Kenneth French's market returns for developed and emerging markets, weighted 90 and 10, close to their shares of a global index, and converted from US dollars to euro at the month-end reference rate of the European Central Bank (ECB).
- Bonds: a euro area government bond with a duration, the average time to its payments weighted by their present value, of seven years, close to that of a euro government bond index. From October 2004 it is a seven-year zero-coupon bond priced from the ECB's yield curve. Before that date, the change in the ECB's ten-year government bond yield, a monthly average, is applied to a bond of that duration.

For each split from 40/60 to 100/0, in steps of 5 points, the test starts at the target weights and checks the equity weight at each month end. When the equity weight is outside the band, the interval of 5 points either side of the equity target weight that rule 5 uses, the test goes back to the target weights. It then measures the worst fall. Costs and taxes are left out. The portfolio holds the split with the largest equity target weight whose worst fall is within 35 per cent.

| Split | Worst fall | Peak | Low | Fall 2007-2010 | Growth per year |
|---|---|---|---|---|---|
| 65/35 | 30.9% | 2000-08 | 2003-03 | 30.7% | 6.6% |
| 70/30 | 34.7% | 2000-08 | 2003-03 | 33.4% | 6.8% |
| 75/25 | 37.8% | 2000-08 | 2003-03 | 36.5% | 6.9% |
| 80/20 | 40.5% | 2000-08 | 2003-03 | 38.6% | 7.2% |

The result is 70/30. Its worst fall, 34.7 per cent from August 2000 to March 2003, is 0.3 points inside the limit, and its fall from October 2007 to February 2009 is 33.4 per cent. Growth per year is the compound annual return over the 27 years. The full grid is in `mandate/allocation_check_results.md`.

The constructed returns are close to those of funds on the same markets. From 2021 to 2025 the equity series differed by less than 2 percentage points in every calendar year from an MSCI ACWI fund that reports its returns in euro, and the bond series by less than 1 point from the bond ETF the portfolio holds.

## What the test does not show

- The 27 years contain two deep falls in equity markets, and deeper falls are possible.
- Month-end values miss falls that reverse within a month.
- Before October 2004 the bond returns rest on monthly average yields, a rougher construction, and the worst fall of 2000 to 2003 lies in that period. The fall of 2007 to 2009 rests on the ECB curve and on its own selects the same split: 70/30 fell 33.4 per cent and 75/25 fell 36.5 per cent.
- The result depends on bonds rising while equities fell. Bonds rose by 24.6 per cent from the peak of August 2000 to the low of March 2003, and by 9.8 per cent from October 2007 to February 2009. In 2022 bonds fell with equities, and every split fell between 13.3 and 15.9 per cent from its previous peak.
- The test has no contributions, so it leaves out rule 4, under which each top-up, the fixed monthly contribution, buys the sleeve furthest below its target weight.
- The growth figures describe one history and are not a forecast.
