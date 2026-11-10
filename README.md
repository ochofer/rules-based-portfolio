# Rules-based portfolio

I run a real-money portfolio under written rules: 70 per cent in a global equity ETF and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. The mandate sets the objective and the risk limit, and a test on monthly data from 1999 to 2025 derives the split from that limit. The rules produce the orders the portfolio places, and every departure from them is kept in a register. The rules were fixed before the first order and are tagged `rules-v1.0`.

Each sleeve is an ETF, and the record looks through both to the companies and bonds inside them.

The dashboard is at https://www.carlohofer.com/rules-based-portfolio/. It is rebuilt every Monday and on each cycle day, and its header gives the dates of its prices and of its holdings. Its Method view explains [what the portfolio does not do, and why](https://www.carlohofer.com/rules-based-portfolio/#method-not-done): no optimiser, no single market index as its benchmark, no views and no signal. The [guide to the dashboard](guide/guide.pdf) explains every view, tile, figure and table for readers with or without a background in finance: what each shows, how to read it and where its numbers come from.

## How the portfolio is run

On the cycle day, the 5th of each month or the first trading day after it when the 5th is not one, the weights are computed from the ledger. The top-up, with any cash left from earlier orders, buys the sleeve furthest below its target weight, up to that target weight, and any remainder buys the other sleeve up to its target weight. If the equity weight is then below 65 or above 75 per cent, the portfolio is brought back to 70/30 the same day. Nothing else triggers an order, and a fall in prices does not pause the cycle. At most five orders are placed in a month, each between 15:45 and 17:00 Amsterdam time on a trading day. A rule changes only by a dated amendment, which applies from the first cycle day at least 30 days after it is committed.

## Contents

| Path | What it holds |
|---|---|
| `mandate/MANDATE.md` | The objective, the risk limit and how the split follows from the limit. |
| `mandate/allocation_check.py` | The test that derives the split, with its data sources. |
| `mandate/allocation_check_results.md` | The output of the test for every split from 40/60 to 100/0. |
| `mandate/allocation_check_us_results.csv` | The same test with the US stock market in place of the global equity series, added in November 2026 after the first cycle day. Nothing is chosen from it. |
| `mandate/allocation_check_us_periods.csv` | The cumulative return in US dollars, dividends included, of the US stock market and of the developed markets outside the United States, from Kenneth French's data library, over 2000 to 2009 and 2010 to 2024. |
| `mandate/simulations.py` | The bootstrap of the allocation test, and the rules applied to its returns and to resampled paths. |
| `mandate/simulation_*.csv` | The three tables of the simulations, which the dashboard draws. |
| `mandate/sleeve_correlation.csv` | The rolling 36-month correlation of the two sleeves' monthly returns in the allocation test. |
| `mandate/REVIEW_2027.md` | The agenda of the review of the rules in October 2027: the figures it uses and the questions it answers. |
| `rules/RULES.md` | The ten rules, the two ETFs and how they were chosen. |
| `src/portfolio/` | The program: it checks the ledger, computes the orders the rules produce on a cycle day, and builds the record and the dashboard. |
| `tests/` | The program's tests, run on invented ledgers and simulated returns. |
| `outputs/` | The figures the dashboard draws: weights, percentages, basis points, loadings and indices. |
| `outputs/comparisons.csv`, `outputs/comparisons_daily.csv`, `outputs/comparison_effects.csv` | The comparisons: one row per comparator with every measure, the growth of 100 of each by day, and the effects of each difference by month and over the record. |
| `outputs/ex_ante_risk.csv` | The estimated volatility at each month end, kept as first written, for the forecast's calibration. |
| `cycles/` | The cycle report of each cycle day, written before the orders, with the line after them. |
| `notes/` | The monthly note written after each cycle day. |
| `quarterly/` | The quarterly report: each issue's page, built once from the tables of the commit it names and never rebuilt, the PDF printed from it, the commentary it carries and any errata. |
| `method/` | The fixed tables the program applies: MSCI's regions, the funds the equity ETF holds, share classes of one company, the ETF selection, the choice of the S&P 500 alternative's ETF, the funds of the comparisons with the date each was fixed, and the controls. |
| `guide/` | The guide to the dashboard: its text, `source.md`, the page built from it with the dashboard, and the PDF printed from that page. |
| `index.html`, `site/` | The dashboard, the style, script and colour palette it is built with, and the style of the quarterly report. |


## What the record measures

The record covers the running of the portfolio: the orders and their costs, the drift of the weights away from the target weights, the rebalancing the rules produce, and the look-through of the two ETFs. For equity the look-through gives the weights of regions, countries, sectors, currencies and the largest companies, and for bonds the weights of issuing countries, maturities and credit ratings, and the duration of the bond sleeve. Returns are time-weighted, so contributions do not count as gains. From the first month end the money-weighted return stands beside them, which counts the timing of the contributions.

The risk of the whole portfolio is estimated on index returns at the latest look-through weights, and is not part of the record. The look-through's four equity regions and the bond sleeve's three maturity groups are its components. Over the last 120 months the dashboard gives their correlations, each component's risk contribution beside its weight, the efficient frontier of the components with the portfolio's point beside it, the estimated volatility, and the value at risk and expected shortfall over one month, both kept at each month end so that, from the twelfth month, the realised returns can be set against them. It also gives today's portfolio held through five historical episodes. The two ETFs' ongoing costs stand beside the implementation cost, and from the twelfth month end the difference to the index blend is split into three parts that sum to it: the portfolio against reference portfolio A, the drift effect and the tracking difference.

Two reference portfolios, computed from the same contributions and prices without costs, sit beside the portfolio. The first follows the same rules, so the difference between it and the portfolio is the cost of implementation. The second goes back to its target weights on every cycle day, so the difference between the two reference portfolios is the effect on returns of letting the weights drift inside the band, before costs. On the Method view the S&P 500 alternative stands beside reference portfolio A, two rule sets on the same contributions without costs. The portfolio's benchmark is the index blend, 70 per cent MSCI ACWI net total return and 30 per cent the Bloomberg Euro-Aggregate Treasury index in euro, rebalanced monthly, the policy the rules implement. The equity part is MSCI's published end-of-day levels of the index in euro. Bloomberg publishes no public series of the bond index, so the bond part is the index's one-month return as Vanguard's monthly factsheet reports it, and the blend is a monthly series that starts at the first month end after the first purchase. A record of five to ten years is too short to show that one set of rules is better than another, so the returns are not offered as evidence for the rules.

The Comparisons part of the Performance view sets the record beside comparators that receive the same contributions on the same days, in euro and without costs: the benchmark, the two reference portfolios, the same two ETFs at 100/0, 90/10, 80/20 and 60/40 under the same rules, with the band five points either side of each target, and savings at the euro short-term rate. For each it gives the time-weighted and money-weighted return since the first purchase, the volatility of daily returns, the worst fall, the correlation of daily returns with the portfolio's, and the difference to the portfolio's return beside the band chance alone produces over the same span. Each difference is split into effects computed day by day and summed by month: implementation, drift, split, the dollar, cash and, for savings, bonds against the rate, with the timing of contributions and compounding over the record. The benchmark has values at month ends only, so its statistics and its difference start at the sixth month end. Over the record's first months a difference says nothing about either rule set.

## What is published and what is not

The repository publishes weights, percentages, the metrics the program computes and the charts drawn from them. A contribution appears only as a share of the portfolio. After each quarter a report on it is published in `quarterly/`, as a page and a PDF printed from it, and neither is rebuilt later: a correction goes in the next issue as an erratum. Euro amounts, units and the broker's statements are kept private and never committed. Executed prices, fees and units come from the broker's statements, which are also the monthly check on the ledger. The portfolio and the reference portfolios are valued at the net asset values the ETF issuers publish, the equity ETF's converted from US dollars at the ECB reference rate of the same day or the last one before it. The S&P 500 alternative is valued at its ETF's net asset values in US dollars, converted the same way, up to the last day on which all three ETFs have published one. The look-through uses the holdings files the issuers publish, and the bond sleeve's credit ratings and duration are the figures of the issuer's monthly factsheet, with its date. The risk estimates use MSCI's month-end levels of its regional indices in euro and the ECB's yield curve of euro area government bonds, the savings comparator the ECB's euro short-term rate, and the ongoing costs are those of the two ETFs' key information documents. All are cached locally and not redistributed, and only the figures computed from them are published. The bid and ask recorded with each order are the quotes Tradegate Exchange showed at the time, saved before the order and not those of the venue where it executes. Each order's half-spread is measured against them.

## Running the code

From the repository root:

```
pip install -r requirements.txt pytest
python3 mandate/allocation_check.py
python3 mandate/simulations.py
python3 -m pytest tests
```

`allocation_check.py` downloads its seven source files into `cache/`, which is not committed, and rewrites `mandate/allocation_check_results.md`, the two tables of every split, `mandate/allocation_check_results.csv` for the global equity series and `mandate/allocation_check_us_results.csv` for the US stock market, and `mandate/allocation_check_us_periods.csv`, the two markets' returns over 2000 to 2009 and 2010 to 2024. The US run was added in November 2026, after the first cycle day, to answer a question readers ask, and the split was set on the global series alone. Its sample ends in December 2025, so a later run differs only where a source revises its history. `simulations.py` reads the same files, checks that its code reproduces the allocation test, and rewrites the three simulation tables with one fixed seed, so a run reproduces them, and the table of the rolling correlation. The tests run on invented ledgers and simulated returns. The program reads the private ledger: with `PYTHONPATH=src`, `python3 -m portfolio check` checks the ledger against rules 7 and 10, `status` shows the holdings and weights, `cycle` gives the orders of a cycle day and, on that day, writes the cycle report, `post` adds the line after the orders, `note` drafts the monthly note's figures, `build` writes `outputs/`, `index.html` and the guide's page, `guide/guide.html`, `guide --print` prints the guide's PDF from that page with Playwright's Chromium, `quarterly 2026-Q4 --commit <commit>` writes the issue of a quarter from the tables of that commit, `quarterly 2026-Q4 --print` prints its PDF with Playwright's Chromium, and `quarterly --check` rebuilds every issue from its commit and checks that each PDF carries its page's words, title and author.

## Terms

- **portfolio**: the two ETFs held under these rules, plus any contribution not yet invested.
- **sleeve**: the part of the portfolio held in one ETF.
- **weight**: a sleeve's value divided by the value of the portfolio.
- **target weight**: the weight the rules aim for, 70 per cent equity and 30 per cent bonds.
- **band**: the interval from 65 to 75 per cent for the equity weight. When the equity weight is outside it on a cycle day, after the top-up, the portfolio is brought back to its target weights.
- **rebalancing**: moving the weights back towards the target weights, through top-ups (rule 4) or through the band (rule 5).
- **contribution**: money paid into the portfolio, meaning the starting amount and each top-up.
- **starting amount**: the first contribution, fixed before the first order.
- **top-up**: the fixed monthly contribution, 5 per cent of the starting amount.
- **cycle day**: the day each month on which the rules are applied.
- **trading day**: a day on which Xetra, the Frankfurt exchange where both ETFs are listed in euro, is open.
- **ledger**: the private record of every contribution and every order, kept outside the repository.
- **record**: what the program computes from the ledger and the prices: holdings, weights, orders and their costs, returns, the look-through and the reference portfolios.
- **net asset value**: the value of one share of an ETF at the close of a day, as its issuer publishes it.
- **look-through**: the portfolio's exposure to the securities inside the two ETFs, each ETF's holdings weighted by the ETF's weight in the portfolio.
- **reference portfolio**: a portfolio computed from the same contributions and prices as the portfolio, without costs. Reference portfolio A follows the same rules, and reference portfolio B goes back to the target weights on every cycle day.
- **S&P 500 alternative**: the same contributions on the same days into one S&P 500 ETF at its net asset value in euro, in fractional units and without costs, starting with the starting amount at the net asset value of the day of the first purchase, exactly as reference portfolio A starts. It stands for the rule "hold the S&P 500 and nothing else" with no costs, so that it is compared with reference portfolio A like for like, two rule sets on the same money.
- **index blend**: 70 per cent MSCI ACWI net total return and 30 per cent the Bloomberg Euro-Aggregate Treasury index, in euro, rebalanced at each month end, the portfolio's benchmark.
- **implementation cost**: reference portfolio A's value relative to the portfolio's, with contributions removed, in basis points, positive when the portfolio's value is below reference portfolio A's and negative when it is above.
- **half-spread**: half the gap between the ask and the bid quoted when an order is placed.
- **basis point**: one hundredth of a percentage point.
- **split**: the pair of target weights, written equity/bonds, for example 70/30.
- **risk limit**: the worst fall the mandate aims to stay within, about one third, tested as 35 per cent.
- **growth per year**: the compound annual return, with contributions removed.
- **drawdown**: the fall in the portfolio's value below its previous peak on a given day, with contributions removed, in per cent.
- **worst fall**: the largest drawdown, meaning the largest fall in the portfolio's value from a previous peak to a later low, with contributions removed.
- **tracking difference**: an ETF's return minus its index's return over a calendar year, in percentage points.
- **comparator**: a portfolio that receives the same contributions on the same days as the portfolio, valued in euro without costs and set beside the record in the Comparisons part, such as a reference portfolio, another split under the same rules, or savings at the euro short-term rate.
- **euro short-term rate**: the rate at which banks borrow euro overnight without collateral, which the European Central Bank publishes each working day.
- **tracking error**: the standard deviation of the daily differences between two series' returns, times the square root of 252, so a figure for a year.
- **band chance alone produces**: plus or minus two tracking errors times the square root of the years, around zero, the difference between two series that chance alone produces over the same span. It ignores compounding and treats the daily differences as independent.
- **duration**: a bond's average time to its payments, weighted by their value, in years. It is also, approximately, the percentage fall in the bond's price when its yield rises by one percentage point. For the bond sleeve it is the average duration in the issuer's factsheet.
- **factor**: one of the return series in Kenneth French's data library for developed markets: the market's return minus the risk-free rate, and the returns of long-short portfolios for size, value, profitability, investment and momentum.
- **loading**: the coefficient of the ETF's return minus the risk-free rate on a factor's return.
- **risk-free rate**: the one-month US Treasury bill return in French's files.
- **standard error**: the estimated standard deviation of an estimate.
- **allocation test**: the historical test in `mandate/allocation_check.py` that derived the split from the risk limit, on monthly euro returns from February 1999 to December 2025.
- **bootstrap**: the resampling of the allocation test's returns in blocks of twelve consecutive months, each starting at a random month, into paths of five and ten years, with the worst fall measured on each path.
- **mechanics simulation**: the rules applied to the allocation test's returns, with a starting amount of 100 and a top-up of 5 a month, for the counts of their orders.
- **resampled paths**: the bootstrap's ten-year paths carried forward from the first purchase with the top-up and the rules, in units of the starting amount.
- **in-sample**: computed on the data on which a choice was made, here the returns from 1999 to 2025 on which the split was chosen.
- **time-weighted return**: the return with contributions removed, chained from day to day, so the timing and the size of the contributions do not affect it.
- **market effect**: a month's change in the portfolio's value that did not come from contributions, in per cent of the value at the start of the month.
- **money-weighted return**: the rate at which the contributions, each from its date, grow to the portfolio's value, so the timing of the contributions counts. Cumulative in the first year and per year after it.
- **cycle report**: the file `cycles/YYYY-MM.md` written on a cycle day before any order, with each rule that bears on the proposed orders, its figure and a pass or a fail, and one line after the orders that compares them with the proposal.
- **monthly note**: the note of 120 to 200 words, in `notes/YYYY-MM.md`, written by hand after each cycle day.
- **departure**: an order placed, or left unplaced, other than as the rules require. The departures register lists each one with its rule and its consequence.
- **rolling correlation**: the correlation of two series of monthly returns over the 36 months to each month end.
- **component**: one of the parts into which the look-through divides the portfolio to estimate its risk: the four equity regions, the bond sleeve's three maturity groups, and cash, which has no return.
- **maturity group**: the bonds of the bond sleeve with 1 to 5, 5 to 10 or over 10 years to maturity, each priced as a zero-coupon euro area government bond at 3, 7.5 or 20 years from the European Central Bank's yield curve.
- **estimated volatility**: the standard deviation of the portfolio's return over a year, estimated from the components' monthly returns over the last 120 months at the latest look-through weights.
- **realised volatility**: the standard deviation of the portfolio's last 12 monthly time-weighted returns, times the square root of 12, so a figure for a year.
- **value at risk**: the loss over one month that the portfolio, at today's weights, exceeded in one month in twenty of the 120-month window, read from those months or from the normal distribution with the estimated volatility.
- **expected shortfall**: the mean loss over one month in the months beyond the value at risk, from the window or from the normal distribution.
- **forecast's calibration**: the standard deviation, over the months that have a forecast, of each month's return divided by the monthly volatility estimated for it at the end of the month before. 1 means the estimates matched the returns, and above 1 that they were too low.
- **covariance**: how far two returns move together, in the units of variance, the square of volatility: their correlation times the product of their standard deviations.
- **risk contribution**: a component's weight times the covariance of its return with the portfolio's return, divided by the portfolio's variance. The contributions sum to 100 per cent.
- **efficient frontier**: the long-only, fully invested portfolios of the components with the lowest estimated volatility for each estimated return, on the means and covariances of one window of 120 months.
- **minimum-variance portfolio**: the portfolio on the efficient frontier with the lowest estimated volatility.
- **Sharpe ratio**: the mean of a portfolio's return above the risk-free rate, divided by the standard deviation of that excess return, so the return earned per unit of volatility.
- **cap-weighted**: holding each security in proportion to its market value, as the indices of both ETFs do.
- **TER**: total expense ratio, the management and other operating costs an ETF takes from its assets each year, as a percentage of them.
- **ongoing costs**: what an ETF takes from its assets each year, its TER plus its transaction costs, as its key information document states them. They are inside its net asset value.
- **drift effect**: reference portfolio A's return minus reference portfolio B's, the effect of letting the weights drift inside the band, before costs.

## Other projects

- **Optimal versus naive diversification.** Under an index-tracking mandate on French's 49 industries, five covariance estimators understate their own tracking error, by 22 to 61 per cent. The replication of DeMiguel, Garlappi and Uppal (2009) reproduces 29 of the 30 Sharpe ratios that carry a band. [Page](https://www.carlohofer.com/projects/optimal-vs-naive-diversification/), [dashboard](https://www.carlohofer.com/optimal-vs-naive-diversification/dashboard/B-P_dashboard.html), [code](https://github.com/ochofer/optimal-vs-naive-diversification)
- **Climate risk as an equity signal.** An ownership graph linking 328 listed companies to the 5,115 tracked assets they own. Of 19 apparent ownership changes checked by hand, 12 had no transaction behind them. [Page](https://www.carlohofer.com/projects/climate-risk-equity-signal/), [note](https://github.com/ochofer/paper1-hazard-exposure-data/releases/download/note-v1.2/what-a-vintage-difference-measures.pdf), [code](https://github.com/ochofer/paper1-hazard-exposure-data)
