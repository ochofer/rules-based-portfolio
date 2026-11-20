# Rules, version 1.1, with version 1.0 in force until 5 January 2027

These are the rules the portfolio runs under. Version 1.0 was fixed on 7 October 2026, before the first order, and the git tag `rules-v1.0` marks it. Version 1.1 adds rule 11 by the amendment of 20 November 2026, and the git tag `rules-v1.1` marks it. Version 1.0 applies until 5 January 2027, and version 1.1 from that day. A rule changes only through rule 9.

The portfolio is long-only and holds two exchange-traded funds in a euro brokerage account. An ETF (exchange-traded fund) is a fund whose shares are listed on a stock exchange. Both ETFs held here are UCITS funds, the European Union standard for funds sold to the public. One ETF holds global equities and the other holds euro government bonds.

## Terms used in the rules

- **Sleeve**: the part of the portfolio held in one ETF. The portfolio has an equity sleeve and a bond sleeve.
- **Weight**: a sleeve's value divided by the value of the portfolio. The value of the portfolio is the value of both ETFs plus any contribution not yet invested.
- **Target weight**: 70 per cent for the equity sleeve and 30 per cent for the bond sleeve.
- **Band**: the interval from 65 to 75 per cent for the equity weight.
- **Worst fall**: the largest fall in the portfolio's value from a previous peak to a later low, measured on returns with contributions removed.
- **Contribution**: money paid into the portfolio, meaning the starting amount and each top-up.
- **Top-up**: the fixed monthly contribution.
- **Cycle day**: the day each month on which the rules are applied.
- **Trading day**: a day on which Xetra, the Frankfurt exchange where both ETFs are listed in euro, is open.
- **Order**: an instruction to the broker to buy or sell one ETF.
- **Ledger**: the private record of every contribution and every order.

## Objective and risk

The mandate in `mandate/MANDATE.md` sets the objective and the risk limit. The objective is the highest long-run growth within a worst fall of about one third, over a horizon of five to ten years with no withdrawals, and a worst fall above 40 per cent is outside it. The target weights follow from the limit: 70 per cent is the largest equity target weight whose worst fall, in euro from February 1999 to December 2025 and rebalanced by a band as in rule 5, stayed within 35 per cent (34.7 per cent, from August 2000 to March 2003). The test and its data sources are in `mandate/allocation_check.py`, and its output is in `mandate/allocation_check_results.md`. The limit is the basis of the target weights and never a reason to sell. In a fall, rule 8 applies and the cycle runs as written.

## The rules

1. **Target weights.** The portfolio holds two sleeves, each in one ETF, at target weights of 70 per cent equity and 30 per cent bonds. There is no cash target. Cash is whatever part of a contribution has not yet been invested.

2. **Contributions.** A starting amount is fixed before the first order. Every month after that, a top-up equal to 5 per cent of the starting amount is paid into the account by the 2nd. The euro amounts are private, and the fingerprint in the last section fixes them.

3. **The cycle.** The cycle day is the 5th of each month, or the first trading day after the 5th when the 5th is not a trading day. On the cycle day the weights are computed from the ledger and the orders the rules produce are placed the same day.

4. **Top-ups rebalance first.** The top-up buys the sleeve furthest below its target weight, up to the amount that brings that sleeve to its target weight. Any remainder buys both sleeves in proportion to their target weights. Nothing is sold while the equity weight is inside the band. With two sleeves, this places the portfolio at its target weights whenever the top-up is large enough, and otherwise moves it as close to them as buying alone allows. For example, with the starting amount set to 100, equity worth 68 and bonds worth 32 before a top-up of 5, the portfolio is worth 105 after the top-up and the equity target is 73.5. Equity is 5.5 short, more than the top-up, so all 5 buy equity and the equity weight moves from 68.0 to 69.5 per cent.

5. **The band.** If the equity weight is below 65 or above 75 per cent after the top-up, the portfolio is brought back to exactly 70 and 30 per cent on the same day, by selling the sleeve above its target weight and buying the other. Inside the band nothing is sold. There is no calendar rebalancing. The band is the only trigger.

6. **Order budget.** At most five orders are placed in a month, the number the account's plan carries without commission. If the rules call for more, the band orders come first and the top-up waits for the next cycle day. Rules 4 and 5 never need more than two orders on a cycle day.

7. **Execution.** Orders are placed on a trading day between 15:45 and 17:00 Amsterdam time, when Xetra and the US equity market are both open, outside the first fifteen minutes of the US session and the last thirty minutes of the Xetra session. For each order the ledger records the date, the time, the ISIN, the side, the units, the price, the fee, the currency, and the bid and ask quoted when the order was placed.

8. **No discretion.** No order is placed outside these rules. News does not add a purchase, a fall in prices does not pause the cycle, and no ETF is changed. When in doubt, the cycle is run as written and the doubt is recorded in the monthly log.

9. **Changing the rules.** A rule changes only by a dated amendment committed to this file. An amendment applies from the first cycle day at least 30 days after its commit. The first review of the rules is on the cycle day of October 2027, twelve months after this version, and there is no review before it.

10. **Sales.** Every sale is recorded in the ledger on its day with the units sold, the proceeds, the cost basis and the realised gain or loss. The cost basis is the average price paid per unit, fees included, times the units sold.

11. **The target follows the allocation test.** Added by the amendment of 20 November 2026, this rule applies from the cycle day of 5 January 2027. Each month end from 30 November 2026 gives a reading of the allocation test of `mandate/allocation_check.py`, or gives none. A reading is the test run on the equity ETF's weights by region in the issuer's holdings file dated the month's last trading day on Xetra's calendar, or, where the issuer publishes none for that day, in the first file dated after it and before the cycle day that follows the month end. Its row is written to `outputs/allocation_record.csv` on that cycle day at the latest and before the rules are applied on it, and is not rewritten. The rules count as applied on a cycle day once its cycle report or its row of `outputs/allocation_targets.csv` is written. A month end gives no reading when it has no such file or no row written in time, when the test runs on files of Kenneth French's library other than the five whose hashes are committed in `mandate/allocation_check_files.csv`, or on values of the European Central Bank's three series other than those whose digests are committed there, or when the holdings file has a country that `method/french_regions.csv` does not place. The record says so in a row for that month end, with the reason, and later month ends are still read. A row written after that is read on no cycle day. French's library serves only its latest files, so a lost file can be downloaded again only while the library serves the same database. Once it does not, no month end gives a reading until an amendment names new files. The European Central Bank serves each of its series whole, so a lost file can be downloaded again. If a value the test reads has been revised by then, no month end gives a reading until an amendment names the new values. Where no split, a pair of target weights on the test's grid, has a worst fall within 35 per cent, the reading is none. On each cycle day the two month ends before it are read, and both must give a reading: a month end without one breaks the pair, so the two cycle days that read it change nothing. When both give a reading of the same split, other than none, and it differs from the target weights, that split becomes the target weights from that cycle day, in either direction, the band becomes the interval 5 points either side of the new equity target weight, and rules 1, 4 and 5 are read with them. In every other case the target weights do not change. The change itself adds no order and places no sale. The top-ups of rule 4 move the equity weight towards the new target, and rule 5 applies with the new band from the first cycle day on which the equity weight is inside it. Until then the edge, on that side, of the last band the equity weight was inside stays in force, and beyond it rule 5 brings the portfolio to the new target weights. The test's limit, its history, its sources and its settings change only by an amendment, and a country is added to `method/french_regions.csv` only by an amendment.

## The two ETFs

| Sleeve | ETF | ISIN | Index | TER | Domicile | Replication | Fund size | Listing | Income |
|---|---|---|---|---|---|---|---|---|---|
| Equity, 70% | iShares MSCI ACWI UCITS ETF USD (Acc) | IE00B6R52259 | MSCI All Country World Index, net total return | 0.20% | Ireland | physical, optimised sampling | USD 35.6 billion, 31 July 2026 | Xetra, IUSQ, in euro | accumulating |
| Bonds, 30% | Vanguard EUR Eurozone Government Bond UCITS ETF (EUR) Accumulating | IE00BH04GL39 | Bloomberg Euro-Aggregate: Treasury Index | 0.07% | Ireland | physical, sampling | EUR 5.5 billion, 31 August 2026 | Xetra, VGEA, in euro | accumulating |

The TER (total expense ratio) is the yearly fee the fund deducts from its assets. An accumulating ETF reinvests the dividends or coupons it receives and pays nothing out. Physical replication means the fund holds the securities of its index: all of them under full replication, or a representative subset under sampling. The equity index covers large and mid-sized companies in developed and emerging markets. The bond index covers fixed-rate, investment-grade bonds of eurozone governments with more than one year to maturity. Fund size counts all share classes of the fund, as the issuer's factsheet reports it on the date shown.

## How the two ETFs were chosen

**Criteria.** An equity ETF qualifies if it tracks a global index of developed and emerging markets (FTSE All-World, MSCI ACWI, MSCI ACWI IMI, or an equivalent global index tracked by a Vanguard, iShares or SPDR fund), is a UCITS fund, accumulates, is listed in euro on a European exchange, replicates physically, charges a TER of at most 0.25%, has a fund size above EUR 1 billion and is offered in euro on the account. A bond ETF qualifies if it tracks a euro aggregate or euro government index of investment-grade bonds, either across all maturities or capped at 10 years, is a UCITS fund, accumulates, holds bonds denominated in euro, charges a TER of at most 0.20%, has a fund size above EUR 500 million and is offered in euro on the account. Versions of an index that change its exposure fail: ESG and other screened indices, indices built on a factor (a company characteristic, such as dividend yield, by which an index selects or weights companies) and currency-hedged share classes. An index of short maturities only or long maturities only fails. Synthetic replication, in which the fund holds other securities and receives the index return from a bank through a swap contract, fails.

**Ranking.** Among the ETFs that qualify, the order was fixed before the funds were compared. Equity ETFs rank first by Irish domicile, then by the highest average tracking difference over 2023, 2024 and 2025, then by the lowest TER. Bond ETFs rank by the highest average tracking difference over the same years, then by the lowest TER. Tracking difference is an ETF's calendar-year return minus the return of its index, both taken from the issuer's factsheet, so a higher figure means a smaller shortfall. An ETF with fewer than three full calendar years of returns ranks after the others, by TER. Irish domicile comes first for equity because a fund domiciled in Ireland pays 15 per cent tax on US dividends under the treaty between the two countries, where a fund domiciled in Luxembourg pays 30 per cent. With the United States at about 60 per cent of a global index and a dividend yield near 1.3 per cent, the difference is about 0.12 percentage points a year.

**Equity ETFs that qualify, in rank order.** Tracking difference in percentage points.

| Rank | ETF | ISIN | TER | 2023 | 2024 | 2025 | Average | Offered on the account |
|---|---|---|---|---|---|---|---|---|
| 1 | SPDR MSCI All Country World UCITS ETF (Acc) | IE00B44Z5B48 | 0.12% | −0.19 | −0.13 | +0.47 | +0.050 | no |
| 2 | iShares MSCI ACWI UCITS ETF USD (Acc) | IE00B6R52259 | 0.20% | +0.15 | −0.14 | +0.07 | +0.027 | yes, held |
| 3 | Vanguard FTSE All-World UCITS ETF (USD) Accumulating | IE00BK5BQT80 | 0.14% | +0.03 | −0.01 | −0.06 | −0.013 | yes |
| 4 | SPDR MSCI ACWI IMI UCITS ETF (Acc) | IE00B3YLTY66 | 0.17% | −0.48 | −0.24 | +0.14 | −0.193 | yes |
| 5 | Invesco FTSE All-World UCITS ETF Acc | IE000716YHJ7 | 0.15% | | +0.40 | −0.09 | under three years | yes |

**Bond ETFs that qualify, in rank order.**

| Rank | ETF | ISIN | TER | 2023 | 2024 | 2025 | Average | Offered on the account |
|---|---|---|---|---|---|---|---|---|
| 1 | Vanguard EUR Eurozone Government Bond UCITS ETF (EUR) Accumulating | IE00BH04GL39 | 0.07% | +0.02 | −0.11 | +0.01 | −0.027 | yes, held |
| 2 | Amundi Prime Euro Government Bond UCITS ETF Acc | LU2089238898 | 0.05% | −0.01 | −0.05 | −0.03 | −0.030 | yes |
| 3 | SPDR Bloomberg Euro Government Bond UCITS ETF (Acc) | IE00BMYHQM42 | 0.07% | −0.10 | −0.12 | +0.10 | −0.040 | yes, as SPF0 |
| 4 | Xtrackers II Eurozone Government Bond UCITS ETF 1C | LU0290355717 | 0.07% | −0.09 | −0.06 | −0.04 | −0.063 | yes |
| 5 | HSBC Euro Government Bond UCITS ETF | IE00066KZ5B5 | 0.06% | | | | under three years | no |
| 6 | iShares Core EUR Govt Bond UCITS ETF EUR (Acc) | IE0008U15456 | 0.07% | | | | under three years | no |
| 7 | UBS Core BBG EUR Gov 1-10 UCITS ETF EUR acc | LU0969639474 | 0.09% | | | | under three years | yes |

**Result.** The first equity ETF in rank order is not offered on the account, so the equity sleeve holds the second. The first bond ETF is held. The top two bond ETFs differ by 0.003 percentage points, less than the 0.01 to which the issuers publish returns, and the ranking was applied as fixed. No accumulating ETF on the plain Bloomberg Euro Aggregate index was found, so the bond sleeve holds a euro government ETF, which the criteria allow. Every other share class examined failed a criterion: it distributes its income, is currency-hedged, tracks a screened, factor or other index, replicates synthetically, holds a maturity band outside the criteria, or is below the minimum fund size. The figures in the two tables come from the issuers' factsheets and product pages, dated July to October 2026.

## The private values

The euro amounts behind rule 2 are in a private file. Its SHA-256 fingerprint, a 64-character code computed from the file's contents that changes if any character of the file changes, is:

`cf0ebd0140a5d235ac5621dd0d6f49df787179860e9281c29e603974a1608534`

The file holds the starting amount, the top-up and a random line that prevents anyone from recovering the amounts by trying values. Anyone shown the file can check it against this fingerprint.

## Amendments

The first amendment under rule 9 was committed and made public on 20 November 2026. An erratum corrects wording and a reading settles a case the text leaves open, and neither has waited the 30 days of rule 9. A note says what a statement of this file rests on and changes no rule and no order. One erratum decided orders. The erratum of rule 4, committed on 8 October 2026 at 11:24, 28 days before the first cycle day, decided the orders of 5 November: 83.6 per cent of the cash went to equity and 16.4 to bonds, where the sentence as tagged gives 95.1 and 4.9. The rule as tagged had two sentences that could not both hold, and the erratum chose between them without waiting the 30 days. Since the reading of rule 9 of 19 November 2026, a correction that changes an order is an amendment.

| Committed | Rule | Type | Text |
|---|---|---|---|
| 2026-10-07 | 2 | Erratum | "the fingerprint in the last section" should read "the fingerprint under The private values". |
| 2026-10-08 | 4 | Erratum | "Any remainder buys both sleeves in proportion to their target weights" should read "Any remainder buys the other sleeve up to its target weight". With two sleeves the remainder equals the other sleeve's shortfall, so the original wording could not give the outcome the rule states. |
| 2026-10-08 | 4 | Reading | Rule 4 applies to all cash not yet invested. An order below the broker's minimum of 1 euro is not placed, and its cash waits for the next cycle day. |
| 2026-10-08 | 6 | Reading | A top-up purchase and a band purchase of the same sleeve on one cycle day are placed as one order, so rules 4 and 5 need at most two orders. |
| 2026-10-08 | 7 | Reading | The broker shows no bid or ask. The bid and ask recorded are the quotes Tradegate Exchange showed at the time, saved just before the order. They are not the quotes of the venue where the order executes, and each order's half-spread is measured against them. |
| 2026-10-08 | 7 | Reading | On a cycle day when the US equity market is closed, the orders are placed that day between 15:45 and 17:00 Amsterdam time, as rule 3 requires. |
| 2026-10-09 | 7 | Erratum | The reading of 8 October on the bid and ask now calls them the quotes Tradegate Exchange showed at the time, the words of the dashboard. The reading is unchanged. |
| 2026-10-09 | 1 | Erratum | The two tables of the ETFs that qualify print negative tracking differences with the minus sign. The figures are unchanged. |
| 2026-11-19 | 2 | Reading | Written on 19 November 2026, after the first purchases of 8 October 2026: the starting amount is invested once, at the target weights, and the rules name no day for it. |
| 2026-11-19 | 9 | Reading | A correction that changes an order is an amendment, and it applies from the first cycle day at least 30 days after its commit. |
| 2026-11-19 | Opening | Erratum | The opening's sentence on what an ETF is, which joined two sentences with a semicolon, is written as two sentences: "listed on a stock exchange. Both ETFs held here are UCITS funds". The words are unchanged. |
| 2026-11-19 | Ranking | Note | "The order was fixed before the funds were compared" rests on the date written in this file: the ranking and the ranked funds entered the repository in the same commit, on 7 October 2026. |
| 2026-11-20 | 11 | Amendment | Adds rule 11, a new rule adopted before the first review, from the cycle day of 5 January 2027. The allocation test is run on the equity ETF's weights by region, and the rule moves the target weights when those weights have moved far enough to change its split, where until now each such change needed an amendment. Rolled back by French's regional returns to each month end from December 2009 to September 2026, with no issuance and no change of the index's members, the fund's weights of 13 November 2026 give 70/30 at all 202 month ends, with 70/30's worst fall from 33.57 to 34.58 per cent. In steps of a tenth of a point, the smallest shift between two regions that gives 65/35 is 4.3 points from emerging markets to Japan (`mandate/allocation_check_weights.csv`). |
| 2026-11-20 | 9 | Reading | The sentence on the first review sets the date of the scheduled review and does not bar an amendment before it. This reading was written for the amendment of the same day, which adds rule 11. |
| 2026-11-20 | 9 | Reading | The 30 days of an amendment run from the day its commit is public. The commit and its push are made on one day, and that day is the amendment's date. |
| 2026-11-20 | Objective and risk | Note | "34.7 per cent" rests on the test's equity series as it stood until 19 November 2026, French's developed and emerging markets at 90 and 10. On French's five regions at the equity ETF's weights by region of 13 November 2026, the series of `mandate/allocation_check.py` since that day, 70/30's worst fall is 34.55 per cent, from August 2000 to March 2003, and 70 per cent is still the largest equity target weight within 35 per cent on French's returns. On MSCI's indices the same test gives 65/35 (`mandate/MANDATE.md`). |
