# Rules-based portfolio

I run a real-money portfolio under written rules: 70 per cent in a global equity ETF and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. The mandate states the objective and the risk limit, and the split is derived from that limit by a test on monthly data from 1999 to 2025, the *allocation test*. The orders follow from the rules, and every *departure*, i.e., every order placed or left unplaced other than as the rules require, is kept in a register. The rules were fixed before the first order and are tagged `rules-v1.0`. Rule 11, added by amendment and tagged `rules-v1.1`, moves the target weights with the allocation test from the cycle day of 5 January 2027.

Each sleeve is an ETF, and the record looks through both to the companies and bonds inside them.

The [dashboard](https://www.carlohofer.com/rules-based-portfolio/) is rebuilt every Monday and on each cycle day, and its header gives the dates of its prices and of its holdings. Its Method view explains [what the portfolio does not do, and why](https://www.carlohofer.com/rules-based-portfolio/#method-not-done): no optimiser, no single market index as its benchmark, no views and no signal. The [guide to the dashboard](guide/guide.pdf) explains every view, tile, figure and table, what each shows, how to read it and where its numbers come from, and defines every term the dashboard uses.

## How the portfolio is run

On the cycle day, the 5th of each month or the first trading day after it when the 5th is not one, the weights are computed from the ledger. The top-up, with any cash left from earlier orders, is spent on the sleeve furthest below its target weight, up to that target weight, and any remainder on the other sleeve up to its target weight. If the equity weight is then below 65 or above 75 per cent, the portfolio is brought back to 70/30 the same day. Nothing else triggers an order, and a fall in prices does not pause the cycle. From the cycle day of 5 January 2027, rule 11 moves the target weights when the allocation test, run again at each month end on the equity ETF's weights by region, gives the same split, other than the target, at two month ends in a row, and no order follows from the change itself. At most five orders are placed in a month, each between 15:45 and 17:00 Amsterdam time on a trading day.

A rule changes only by a dated amendment, which applies from the first cycle day at least 30 days after it is committed, and a correction that changes an order counts as an amendment. `rules/RULES.md` dates every amendment and erratum.

On each cycle day a *cycle report*, `cycles/YYYY-MM.md`, is written before any order, with each rule that bears on the proposed orders, its figure and a pass or a fail. From the cycle day of 7 December 2026 it is committed and pushed before the first order of the day, and the line after the orders, which compares them with the proposal, is a second commit, so that the history shows the order. A *monthly note* of 120 to 200 words follows in `notes/YYYY-MM.md`, written by hand.

## The split

The mandate's risk limit is a worst fall of about one third, tested as 35 per cent, and the allocation test measures each split's worst fall on monthly euro returns from February 1999 to December 2025. Its *deciding series* for equity is Kenneth French's market returns for five regions at the equity ETF's weights by region, and two MSCI series stand beside it and choose nothing. At the equity ETF's weights by region of 13 November 2026, 70/30's worst fall is 34.55 per cent on the deciding series, 0.45 points inside the limit, and 35.75 to 36.53 per cent on the two MSCI series, so the test does not decide between 70/30 and 65/35 across the two sources. On the deciding series 65/35 is also the result if the limit is read as one third, 33.3 per cent, or if the bond's maturity is five years in place of the test's seven. Rule 1 sets the target at 70/30. Rule 1 sets the split on the global series alone. The tables of the allocation test that were added after its outcome was known are marked as such in `mandate/allocation_check.py`, and none of them chooses anything.

## What the record measures

The record covers the running of the portfolio: the orders and their costs, the drift of the weights away from the target weights, the rebalancing the rules require, and the look-through of the two ETFs. For equity the look-through gives the weights of regions, countries, sectors, currencies and the largest companies, and for bonds the weights of issuing countries, maturities and credit ratings, and the bond sleeve's duration. Returns are time-weighted, so contributions do not count as gains, and the money-weighted return, which counts the timing of the contributions, stands beside them from the first month end.

The portfolio's risk is estimated on index returns at the latest look-through weights, over the last 120 months, and is not part of the record. Its components are the look-through's four equity regions and the bond sleeve's three maturity groups. The dashboard gives their correlations, each component's risk contribution beside its weight, the efficient frontier of the components with the portfolio's point beside it, the estimated volatility, the value at risk and expected shortfall over one month, the estimated tracking error against the benchmark and the value at risk of the active return, and today's portfolio held through five historical episodes. The estimates are kept at each month end, so that the realised figures can be set against them, the tracking error from the sixth month end and the rest from the twelfth.

Two *reference portfolios*, computed from the same contributions and prices without costs, sit beside the portfolio. Reference portfolio A follows the same rules, so the difference between it and the portfolio is the cost of implementation. Reference portfolio B goes back to its target weights on every cycle day, so the difference between the two is the effect of letting the weights drift inside the band, before costs. From the twelfth month end the difference to the benchmark is split into three parts that sum to it: the portfolio against reference portfolio A, the drift effect and the ETFs' tracking difference.

The portfolio's benchmark is the *index blend*, i.e., MSCI ACWI net total return and the Bloomberg Euro-Aggregate Treasury index in euro at the target weights, rebalanced at each month end to the target weights in force on that day. The equity part is MSCI's published end-of-day levels in euro. Bloomberg publishes no public series of the bond index, so the bond part is the index's one-month return as Vanguard's monthly factsheet reports it, and the blend is a monthly series from the first month end after the first purchase.

The Comparisons part of the Performance view sets the record beside *comparators*, i.e., portfolios that receive the same contributions on the same days, in euro and without costs:

- the benchmark and the two reference portfolios
- the same rules with the first-ranked equity fund, and the same two ETFs at 100/0, 90/10, 80/20 and 60/40, each with its band five points either side of the target, and at 70/30 held fixed once rule 11 changes the target weights
- one fund in place of the two: the S&P 500 alternative, i.e., one S&P 500 ETF, an MSCI World fund, Vanguard's LifeStrategy 60% and 80% Equity, a Nasdaq-100 fund and the Mag7 fund
- the global market portfolio, every asset class at its share of the world's invested market value by the weights of Doeswijk, Lam and Swinkels for the end of 2023, held through one ETF per class
- savings at the euro short-term rate
- a bank's managed profile at 70 and 30 per cent, with its published costs, by calendar year only

Each fund was fixed, with its ISIN and the date, in `method/` before its values were read for the comparisons, and the ranking of the market portfolio's funds records each value seen on a fund's own pages before it was fixed. For each comparator the dashboard gives the time-weighted and money-weighted return since the first purchase, the volatility of daily returns, the worst fall, the correlation with the portfolio, and the difference to the portfolio's return beside the band chance alone produces over the same span. Each difference is split into effects computed day by day and summed by month, i.e., implementation, drift, split, the dollar, cash, regions and within each region, with the asset classes for the global market portfolio and the bond yield for savings. Over the record's first months a difference says nothing about either rule set, and a record of five to ten years is too short to show that one set of rules is better than another, so the returns are not offered as evidence for the rules.

## What is published and what is not

The repository publishes weights, percentages, the metrics the program computes and the charts drawn from them. A contribution appears only as a share of the portfolio. Euro amounts, units and the broker's statements are kept private and never committed. After each quarter a report is published in `quarterly/`, as a page and a PDF printed from it, and neither is rebuilt later: a correction goes in the next issue as an erratum.

Executed prices, fees and units come from the broker's statements, which are also the monthly check on the ledger. The portfolio and the reference portfolios are valued at the net asset values the ETF issuers publish, the equity ETF's converted from US dollars at the ECB reference rate of the same day or the last one before it. The look-through uses the issuers' holdings files, and the bond sleeve's credit ratings and duration are those of the issuer's monthly factsheet, with its date. The risk estimates use MSCI's month-end levels of its regional indices in euro and the ECB's yield curve of euro area government bonds, and the comparators use the net asset values their issuers publish. The ongoing costs are those of the two ETFs' key information documents. Every source is cached locally and not redistributed, and only the figures computed from them are published. The bid and ask recorded with each order are the quotes Tradegate Exchange showed at the time, saved before the order, and each order's half-spread is measured against them.

## Contents

| Path | What it holds |
|---|---|
| `mandate/MANDATE.md` | The objective, the risk limit and how the split follows from the limit |
| `mandate/allocation_check.py` | The allocation test, with its data sources |
| `mandate/allocation_check_results.md` | The test's output for every split from 40/60 to 100/0 |
| `mandate/allocation_check_us_results.csv`, `mandate/allocation_check_us_periods.csv` | The same test with the US stock market in place of the global equity series, and the two markets' returns over 2000 to 2009 and 2010 to 2024. Nothing is chosen from them |
| `mandate/allocation_check_history.csv`, `mandate/allocation_check_history_windows.csv` | The split and the dollar effects of 70/30 against 100/0, 60/40 and the US stock market at 70/30, by calendar year, over the two periods, over the whole test and over rolling ten-year windows |
| `mandate/allocation_check_split_gap.csv` | The gap in growth per year between the 100/0 and the 40/60 split, with its standard error and 95 per cent interval from a block bootstrap |
| `mandate/allocation_check_regions.csv` | The equity ETF's weights by country, with each country's region in French's lists and in MSCI's, which weight the deciding series |
| `mandate/allocation_check_comparison.csv` | The test on the deciding series beside MSCI's regional returns at the same weights and MSCI ACWI. Nothing is chosen from it |
| `mandate/allocation_check_maturities.csv` | The test with the bond at 5, 6.7, 7 and 9 years |
| `mandate/allocation_check_weights.csv` | The test at other weights by region. Nothing is chosen from it |
| `mandate/allocation_check_settings.csv`, `mandate/allocation_check_settings_turning.csv` | The test with the emerging markets' share of its equity series fixed in place of the fund's weights by region, at 24 settings of that share and of the bond's maturity, and the share at which 70/30's worst fall equals the limit. Nothing is chosen from them |
| `mandate/allocation_check_files.csv` | The hashes of French's five regional files and digests of the ECB series the test reads |
| `mandate/allocation_check_fund_documents.csv` | The two factsheets whose calendar-year returns the test sets beside its series, each with its date, page and hash. The documents are kept outside the repository |
| `mandate/simulations.py`, `mandate/simulation_*.csv` | The bootstrap of the allocation test and the rules applied to its returns and to resampled paths, and the three tables the dashboard draws |
| `mandate/sleeve_correlation.csv` | The rolling 36-month correlation of the two sleeves in the allocation test |
| `mandate/REVIEW_2027.md` | The agenda of the review of the rules in October 2027 |
| `rules/RULES.md` | The eleven rules, the two ETFs, how they were chosen, and every dated amendment and erratum |
| `src/portfolio/` | The program, which checks the ledger, computes the orders the rules require on a cycle day, and builds the record and the dashboard |
| `tests/` | The program's tests, run on invented ledgers and simulated returns |
| `outputs/` | The figures the dashboard draws, i.e., weights, percentages, basis points, loadings and indices, and the comparisons |
| `outputs/ex_ante_risk.csv` | The estimated volatility at each month end, kept as first written, for the forecast's calibration |
| `outputs/allocation_record.csv` | The allocation test run again at each month end from 30 November 2026, each row written once before the rules are applied on the next cycle day. Rule 11 is applied to these readings |
| `outputs/allocation_targets.csv` | One row for each cycle day from 5 January 2027, kept as first written: the two month ends rule 11 uses, their readings, the target weights before and after, and the band in force |
| `cycles/`, `notes/` | The cycle report of each cycle day and the monthly note |
| `quarterly/` | The quarterly reports, each built once from the commit it names and never rebuilt, with its PDF and any errata |
| `method/` | The fixed tables the program applies, e.g., MSCI's regions, the ETF selection, the funds of the comparisons with the date each was fixed, and the controls |
| `guide/` | The guide to the dashboard: its text, the page built from it and its PDF |
| `index.html`, `site/` | The dashboard and the style it is built with |

## Running the code

From the repository root:

```
pip install -r requirements.txt pytest
python3 mandate/allocation_check.py
python3 mandate/simulations.py
python3 -m pytest tests
```

`allocation_check.py` downloads its 26 source files into `cache/`, which is not committed, and rewrites the allocation test's tables in `mandate/`. Its sample ends in December 2025, so a later run differs only where a source revises its history. French's library serves only its latest files, and those it served on 19 November 2026 carry the hashes in `mandate/allocation_check_files.csv`. The ECB serves each of its three series whole, and the same file holds a digest of the values the test reads, so that a revised value shows. `simulations.py` checks that its code reproduces the allocation test and rewrites the simulation tables with one fixed seed.

The program reads the private ledger. With `PYTHONPATH=src`, `python3 -m portfolio check` checks the ledger against rules 7 and 10, `status` shows the holdings and weights, `cycle` gives the orders of a cycle day and writes its cycle report, `post` adds the line after the orders, `note` drafts the monthly note's figures, `regions` writes the equity ETF's weights by country from its holdings file, `build` writes `outputs/`, the dashboard and the guide's page, `guide --print` prints the guide's PDF, `quarterly 2026-Q4 --commit <commit>` writes a quarter's issue from the tables of that commit, `quarterly 2026-Q4 --print` prints its PDF, and `quarterly --check` rebuilds every issue from its commit and checks each PDF against its page.

## Terms

- **Sleeve**: the part of the portfolio held in one ETF.
- **Weight**: a sleeve's value divided by the portfolio's.
- **Target weight**: the weight the rules aim for in a sleeve. Rule 1 sets 70 and 30 per cent for equity and bonds, rule 11 can change them, and the dashboard gives those in force.
- **Band**: the interval five points either side of the equity target weight, from 65 to 75 per cent at the target weights of rule 1.
- **Split**: a pair of target weights, written equity/bonds, e.g., 60/40.
- **Contribution**: money paid into the portfolio, i.e., the starting amount and each top-up, which is 5 per cent of the starting amount.
- **Cycle day**: the day each month on which the rules are applied.
- **Trading day**: a day on which Xetra, the Frankfurt exchange where both ETFs are listed in euro, is open.
- **Ledger**: the private record of every contribution and every order.
- **Record**: what the program computes from the ledger and the prices.
- **Look-through**: the portfolio's exposure to the securities inside the two ETFs, each ETF's holdings weighted by its weight in the portfolio.
- **Risk limit**: the worst fall the mandate aims to stay within, about one third, tested as 35 per cent.
- **Worst fall**: the largest fall in value from a previous peak to a later low, with contributions removed.
- **Implementation cost**: reference portfolio A's value relative to the portfolio's, with contributions removed, in basis points, positive when the portfolio's value is below reference portfolio A's.
- **Drift effect**: reference portfolio A's return minus reference portfolio B's.
- **Tracking difference**: an ETF's return minus its index's return over a calendar year, in percentage points.
- **Tracking error**: the standard deviation of the difference between the portfolio's return and a named reference's, as a figure for a year.
- **Band chance alone produces**: plus or minus twice the tracking error against a comparator, times the square root of the years, around zero. It ignores compounding and treats the daily differences as independent.
- **Time-weighted return**: the return with contributions removed, chained from day to day.
- **Money-weighted return**: the rate at which the contributions, each from its date, grow to the portfolio's value.
- **Component**: one of the four equity regions and three maturity groups into which the look-through divides the portfolio to estimate its risk, with cash, which has no return.
- **Value at risk**: the loss over one month at 95 per cent at today's weights.
- **Expected shortfall**: the mean loss at or beyond the value at risk.
- **Ongoing costs**: what an ETF takes from its assets each year, as its key information document states them, inside its net asset value.

## Other projects

- **Optimal versus naive diversification.** Under a long-only index-tracking mandate on French's 49 industries, 1979 to 2026, each of five covariance estimators forecasts less tracking error than its portfolio realises: the realised active return is 22 to 61 per cent more volatile than forecast. The replication of DeMiguel, Garlappi and Uppal (2009) reproduces 29 of the 30 out-of-sample Sharpe ratios within 0.03 of the published values. [Page](https://www.carlohofer.com/projects/optimal-vs-naive-diversification/), [dashboard](https://www.carlohofer.com/optimal-vs-naive-diversification/dashboard/B-P_dashboard.html), [note](https://www.carlohofer.com/optimal-vs-naive-diversification/note/B-P_note_2026-10.pdf), [code](https://github.com/ochofer/optimal-vs-naive-diversification)
- **Climate risk as an equity signal.** An ownership graph linking 328 ownership entities in the US and developed Europe, 302 of them listed companies with a price series, to 5,115 asset holdings, built from Global Energy Monitor's free tracker. Of 19 apparent ownership changes drawn at random and checked by hand, 12 had no corporate event behind them. [Page](https://www.carlohofer.com/projects/climate-risk-equity-signal/), [note](https://github.com/ochofer/paper1-hazard-exposure-data/releases/download/note-v1.3/what-a-vintage-difference-measures.pdf), [code](https://github.com/ochofer/paper1-hazard-exposure-data)
- **Volatility-managed portfolios: a replication, the real-time critique, and the months after the sample.** Volatility estimation and position sizing on Ken French's equity factors, replicating Moreira and Muir (2017) and the real-time critique of Cederburg, O'Doherty, Wang and Yan (2020). Scaled by the inverse of last month's realised variance, a factor's Sharpe ratio is higher than the original's by a margin that is statistically significant at the 5 per cent level for momentum alone when each of the six factors is tested on its own, and for no factor after Holm's correction for the six tests. In the 136 months after Moreira and Muir's sample no factor's difference is statistically significant, and the intervals are too wide to rule out the differences found on their sample. [Page](https://www.carlohofer.com/projects/volatility-managed-portfolios/), [dashboard](https://www.carlohofer.com/volatility-managed-portfolios/dashboard/B-Q_dashboard.html), [note](https://www.carlohofer.com/volatility-managed-portfolios/note/B-Q_note_2026-11.pdf), [code](https://github.com/ochofer/volatility-managed-portfolios)
- **Stock-level index tracking: a point-in-time benchmark, a long-only mandate, and its performance attribution by sector.** Rebuilds the S&P 500 month by month from CRSP's list of members, at a tracking error of 11.5 basis points a year against CRSP's own return of the same list, and runs a long-only index-tracking mandate on it from 1999 to 2024, with its active return attributed by sector. The portfolios realise 78.9 to 83.6 basis points a year of tracking error, and each of four covariance estimators forecasts less: the realised active return is 48 to 85 per cent more volatile than forecast. Index changes require 11.4 per cent of the turnover of the portfolio built with Ledoit-Wolf shrinkage. [Page](https://www.carlohofer.com/projects/stock-level-tracking/), [dashboard](https://www.carlohofer.com/stock-level-tracking/dashboard/), [note](https://www.carlohofer.com/stock-level-tracking/note/stock-level-tracking_note_2026-11.pdf), [code](https://github.com/ochofer/stock-level-tracking)
