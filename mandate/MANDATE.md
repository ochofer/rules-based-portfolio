# Mandate

The portfolio is run for the highest long-run growth over five to ten years, with no withdrawals, within a worst fall (the largest fall in its value from a previous peak to a later low) of about one third. The limit sets the split, the pair of weights the rules aim for, written equity/bonds. On monthly euro returns from 1999 to 2025, at the equity ETF's weights by region in its holdings file of 13 November 2026, 70 per cent is the largest equity target weight whose worst fall stayed within 35 per cent, a split of 70/30. From 5 January 2027, rule 11 moves the target weights when the test, run again at each month end on the equity ETF's weights by region, gives the same split, other than the target, at two month ends in a row. The rules in `rules/RULES.md` put the mandate into practice.

## Risk limit

The risk limit is a worst fall of about one third, measured on returns with contributions removed. A worst fall above 40 per cent is outside the mandate. The test reads "about one third" as at most 35 per cent, one third rounded up to the next 5 points, which leaves 5 points between the test and the outer bound of 40 per cent.

Added on 19 November 2026: read as one third, 33.3 per cent, the limit gives 65/35, with a worst fall of 30.71 per cent at the weights by region of 13 November 2026. The reading of 35 per cent, the limit in `mandate/allocation_check.py` and the grid of splits entered the repository in the same commit, so the history cannot show that the reading was fixed before the grid was seen.

The limit sets the target weights and never triggers a sale. A change of the target weights under rule 11 places no order of its own. In a fall, rule 8 applies and the cycle runs as written.

## Constraints

- The portfolio is long-only and holds two exchange-traded funds (ETFs) traded in euro on Xetra, one on a global equity index of developed and emerging markets and one on a euro government bond index. Both are UCITS funds.
- Both ETFs accumulate their income.
- No currency is hedged. Both ETFs are unhedged share classes, and the look-through, the portfolio's exposure to the securities inside the two ETFs, shows its exposure to each currency, the euro included.
- At most five orders are placed in a month.
- The rules change only by a dated amendment under rule 9.

## How the split follows from the risk limit

Each sleeve is the part of the portfolio held in one ETF. The test builds monthly euro returns for both sleeves from February 1999, the second month of the euro, to December 2025:

- Equity: Kenneth French's market returns for five regions, North America, Europe, Japan, Asia Pacific ex Japan and emerging markets, at the equity ETF's weights by region in the holdings file of 13 November 2026, the same weights in every month of the history, and converted from US dollars to euro at the month-end reference rate of the European Central Bank (ECB). The series answers what French's regional markets, at the weights by region the fund had on that date, would have lost over 1999 to 2025, and not what the index lost with the weights it had then. Each holding goes to the region of French's lists that holds its country, in `method/french_regions.csv`, and Greece, which French lists among both developed and emerging markets, goes where MSCI classifies it. Israel, 0.23 per cent of the fund, Russia, at a weight that rounds to zero, and the fund's cash and derivatives, 0.50 per cent, are in none of French's lists, so the five weights are scaled to sum to one. In the holdings file of 13 November 2026 the weights are North America 67.9 per cent, Europe 13.9, Japan 5.0, Asia Pacific ex Japan 2.1 and emerging markets 11.1, in `mandate/allocation_check_regions.csv`. Until 19 November 2026 the series was French's developed and emerging markets at 90 and 10 in every month, and the construction was changed on that day after its outcome was known: 70/30's worst fall is 34.55 per cent on the new series against 34.67 on the old. The weights, the tables built on them and the figures below are refreshed to a month end's weights at the review of October 2027 and on a day on which rule 11 changes the target weights, and in between the record of rule 11 gives the test at each month end.
- Bonds: a euro area government bond with a duration of seven years, close to that of a euro government bond index. From October 2004 it is a seven-year zero-coupon bond priced from the ECB's yield curve. Before that date, the change in the ECB's ten-year government bond yield, a monthly average, is applied to a bond of that duration.

For each split from 40/60 to 100/0, in steps of 5 points, the test starts at the target weights and checks the equity weight at each month end. When the equity weight is outside the band, the interval of 5 points either side of the equity target weight that rule 5 uses, the test goes back to the target weights. It then measures the worst fall. Costs and taxes are left out. The portfolio holds the split with the largest equity target weight whose worst fall is within 35 per cent.

At the equity ETF's weights by region in its holdings file of 13 November 2026:

| Split | Worst fall | Peak | Low | Fall 2007-2010 | Growth per year |
|---|---|---|---|---|---|
| 65/35 | 30.71% | 2000-08 | 2003-03 | 29.59% | 6.9% |
| 70/30 | 34.55% | 2000-08 | 2003-03 | 32.56% | 7.1% |
| 75/25 | 37.63% | 2000-08 | 2003-03 | 35.03% | 7.3% |
| 80/20 | 40.09% | 2000-08 | 2003-03 | 36.92% | 7.6% |

The result is 70/30. Its worst fall, 34.55 per cent from August 2000 to March 2003, is 0.45 points inside the limit, and its fall from October 2007 to February 2009 is 32.56 per cent. The figure moves in jumps as the weights by region move, because a month in which the test goes back to the target weights is added or dropped: with North America at 69.30 per cent and the other regions in proportion, 70/30's worst fall is 34.60 per cent, and at 69.35 it is 33.73 (`mandate/allocation_check_weights.csv`). The target is 70/30. Growth per year is the compound annual return over the 27 years. The full grid is in `mandate/allocation_check_results.md`.

The constructed returns are close to those of funds on the same markets. From 2021 to 2025 the equity series differed by at most 1.8 percentage points in every calendar year from an MSCI ACWI fund that reports its returns in euro, the most in 2021, and the bond series by at most 0.8 points from the bond ETF the portfolio holds, the most in 2025.

The same test on two series built from MSCI's indices in euro, with the same bonds, band rule and months, added on 19 November 2026 after its outcome was known:

| Equity series | Worst fall of 70/30 | Largest split within 35 per cent |
|---|---|---|
| French's regional returns at the fund's weights by region, the deciding series | 34.55% | 70/30 |
| MSCI's regional net returns in euro at the same weights | 35.75% to 35.88% | 65/35 |
| MSCI ACWI, the fund's own index, with the weights it had in each month | 36.39% to 36.53% | 65/35 |

The fund tracks MSCI ACWI. On that index's own history 70/30 fell 36.39 to 36.53 per cent, above the test's line of 35 and inside the mandate's outer bound of 40, and the largest split within 35 per cent is 65/35. The two sources disagree about the split. On French's returns 70/30 passes by 0.45 points, and on MSCI's it misses by 0.75 to 1.53. So the test does not decide between 70/30 and 65/35 across the two sources.

French's series decides because Kenneth French's library was the test's source fixed on 7 October 2026, before the first order. MSCI's net returns in euro start in December 2000, four months after the peak of the worst fall, and with an estimated dividend in the months before or without one, 70/30's worst fall on MSCI's indices moves by 0.13 to 0.14 points. Both sources can be downloaded and the test run again: MSCI's series from its public tool, and French's files from his library, which serves only its latest files. The files his library served on 19 November 2026 carry the hashes committed in `mandate/allocation_check_files.csv`. The European Central Bank serves each of its three series whole, and the same file holds a digest of the values the test reads from each. Rule 11 takes a reading on those values alone. Where a download gives another value, it takes no reading until an amendment names the new values.

French's market returns include dividends and every stock for which his data hold a market value, and his description names no tax on the dividends (Kenneth French, Data Library, the description of his returns for developed and for emerging markets, read on 19 November 2026). MSCI's indices cover large and mid-sized companies, about 85 per cent of the investable market (MSCI ACWI Index factsheet of 30 October 2026), and their net returns reinvest dividends after withholding tax at the maximum rate, that of a foreign institutional investor with no tax treaty (MSCI, Index Calculation Methodology for the MSCI Equity Indexes, May 2015, section 2.2). At the same weights, 70/30's worst fall is 1.2 to 1.3 points deeper on MSCI's net returns than on French's. On MSCI's gross returns, before the tax, it is 35.33 to 35.50 per cent and the test still gives 65/35, so the tax is not what separates the two sources' splits. It accounts for 0.4 of the points, and the other 0.8 to 1.0 points are not measured: the code does not separate the small companies from the other differences between the two sources. Among those differences, MSCI's Pacific enters as one index, with Japan's share of it as it was in each month, where French's series holds Japan and Asia Pacific ex Japan at their weights of 13 November 2026, and MSCI Europe prices Israel, which French's series leaves out. Between MSCI's regional returns at the weights of 13 November 2026 and MSCI ACWI with the weights it had in each month, the weights by region account for 0.6 points.

Each MSCI range runs from a series with an estimated dividend before December 2000 to one without. Before that month MSCI gives only its price return, and the estimate adds to it the mean monthly difference between the net and the price return from January 2001 to December 2005, 1.5 per cent a year for the regional indices at the fund's weights and 1.6 for MSCI ACWI. The full table, with the gross rows, is in `mandate/allocation_check_results.md` and `mandate/allocation_check_comparison.csv`. MSCI's series are read from its public tool and are not committed, and `outputs/sources.csv` lists them. Under rule 11 the comparison changes no target.

At each month end the program runs the test again as rule 11 sets out and writes one row for the month end to `outputs/allocation_record.csv` before the rules are applied on the next cycle day, the day each month on which they are applied, and on that day at the latest: the day the row was written, the date of the holdings file, the five weights, French's database and whether the five regional files carry the hashes committed in `mandate/allocation_check_files.csv`, whether the values read from the European Central Bank's three series are those whose digests are committed there, the worst fall of 65/35, 70/30 and 75/25 and the largest split within 35 per cent on the deciding series, and the same on the two MSCI series, or, for a month end that gives no reading, the reason. The rules count as applied on a cycle day once its cycle report or its row of `outputs/allocation_targets.csv` is written. Rule 11 reads the deciding series' split from that table, and `outputs/allocation_targets.csv` keeps, as first written, a row for each cycle day from 5 January 2027 with the two month ends it reads, the reading of each, the target weights before and after, and the band in force.

The rule is there for the case in which the fund's weights by region move far enough to change the split. Rolled back by French's regional returns to each month end from December 2009 to September 2026, with no issuance and no change of the index's members, the fund's weights of 13 November 2026 give 70/30 at all 202 month ends, with 70/30's worst fall from 33.57 to 34.58 per cent. In steps of a tenth of a point, the smallest shift between two regions that gives 65/35 is 4.3 points from emerging markets to Japan (`mandate/allocation_check_weights.csv`).

## What the test does not show

- The 27 years contain two deep falls in equity markets, and deeper falls are possible. The history ends in December 2025, and extending it at a review is an amendment under rule 9.
- Month-end values miss falls that reverse within a month.
- The bond's maturity is a setting that the test fixes at 7 years. With the bond at 5, 6.7 and 9 years, 70/30's worst fall is 35.16, 34.64 and 33.93 per cent, so at 5 years the test gives 65/35, and at 6.7 years, the duration in the bond fund's factsheet of 30 September 2026, it gives 70/30 (`mandate/allocation_check_maturities.csv`).
- Until 19 November 2026 the test fixed the emerging markets' share of its equity series at 10 per cent in every month, and `mandate/allocation_check_settings.csv` and `mandate/allocation_check_settings_turning.csv` keep that test at other shares and maturities as the record of how it stood.
- Before October 2004 the bond returns rest on monthly average yields, a rougher construction, and the worst fall of 2000 to 2003 lies in that period. The fall of 2007 to 2009 rests on the ECB curve and on its own selects the same split: 70/30 fell 32.56 per cent and 75/25 fell 35.03 per cent.
- The result depends on bonds rising while equities fell. Bonds rose by 24.6 per cent from the peak of August 2000 to the low of March 2003, and by 9.8 per cent from October 2007 to February 2009. In 2022 bonds fell with equities, and every split fell between 13.1 and 16.2 per cent from its previous peak.
- The test has no contributions, so it leaves out rule 4, under which each monthly top-up buys the sleeve furthest below its target weight.
- The growth figures describe one history and are not a forecast.

A block bootstrap of the test, in the dashboard's Method view, reports the distribution of the worst fall over resampled paths, and the dashboard's Simulations view shows the rules on the historical sample and on resampled paths, both as inputs to the review of the rules in October 2027. The agenda of that review is in `mandate/REVIEW_2027.md`.
