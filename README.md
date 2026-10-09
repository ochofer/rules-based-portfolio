# Rules-based portfolio

I run a real-money portfolio under written rules: 70 per cent in a global equity ETF and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. The mandate sets the objective and the risk limit, a test on monthly data from 1999 to 2025 derives the split from that limit, and the rules determine every order the portfolio places. The rules were fixed before the first order and are tagged `rules-v1.0`.

Each sleeve is an ETF, and the record looks through both to the companies and bonds inside them.

The dashboard is at https://www.carlohofer.com/rules-based-portfolio/. It is rebuilt every Monday and on each cycle day, and its header gives the dates of its prices and of its holdings.

## How the portfolio is run

On the cycle day, the 5th of each month or the first trading day after it when the 5th is not one, the weights are computed from the ledger. The top-up, with any cash left from earlier orders, buys the sleeve furthest below its target weight, up to that target weight, and any remainder buys the other sleeve up to its target weight. If the equity weight is then below 65 or above 75 per cent, the portfolio is brought back to 70/30 the same day. Nothing else triggers an order, and a fall in prices does not pause the cycle. At most five orders are placed in a month, each between 15:45 and 17:00 Amsterdam time on a trading day. A rule changes only by a dated amendment, which applies from the first cycle day at least 30 days after it is committed.

## Contents

| Path | What it holds |
|---|---|
| `mandate/MANDATE.md` | The objective, the risk limit and how the split follows from the limit. |
| `mandate/allocation_check.py` | The test that derives the split, with its data sources. |
| `mandate/allocation_check_results.md` | The output of the test for every split from 40/60 to 100/0. |
| `mandate/simulations.py` | The bootstrap of the allocation test, and the rules applied to its returns and to resampled paths. |
| `mandate/simulation_*.csv` | The three tables of the simulations, which the dashboard draws. |
| `rules/RULES.md` | The ten rules, the two ETFs and how they were chosen. |
| `src/portfolio/` | The program: it checks the ledger, computes the orders the rules produce on a cycle day, and builds the record and the dashboard. |
| `tests/` | The program's tests, run on invented ledgers and simulated returns. |
| `outputs/` | The figures the dashboard draws: weights, percentages, basis points, loadings and indices. |
| `method/` | The fixed tables the program applies: MSCI's regions, the funds the equity ETF holds, share classes of one company, and the ETF selection. |
| `index.html`, `site/` | The dashboard, and the style, script and colour palette it is built with. |


## What the record measures

The record covers the running of the portfolio: the orders and their costs, the drift of the weights away from the target weights, the rebalancing the rules produce, and the look-through of the two ETFs. For equity the look-through gives the weights of regions, countries, sectors, currencies and the largest companies, and for bonds the weights of issuing countries, maturities and credit ratings, and the duration of the bond sleeve. Returns are time-weighted, so contributions do not count as gains.

Two reference portfolios, computed from the same contributions and prices without costs, sit beside the portfolio. The first follows the same rules, so the difference between it and the portfolio is the cost of implementation. The second goes back to its target weights on every cycle day, so the difference between the two reference portfolios is the effect on returns of letting the weights drift inside the band, before costs. An index blend, 70 per cent MSCI ACWI net total return and 30 per cent the Bloomberg Euro-Aggregate Treasury index in euro, rebalanced monthly, is shown for information. The equity part is MSCI's published end-of-day levels of the index in euro. Bloomberg publishes no public series of the bond index, so the bond part is the benchmark's one-month return as Vanguard's monthly factsheet reports it, and the blend is a monthly series that starts at the first month end after the first purchase. A record of five to ten years is too short to show that one set of rules is better than another, so the returns are not offered as evidence for the rules.

## What is published and what is not

The repository publishes weights, percentages, the metrics the program computes and the charts drawn from them. A contribution appears only as a share of the portfolio. Euro amounts, units and the broker's statements are kept private and never committed. Executed prices, fees and units come from the broker's statements, which are also the monthly check on the ledger. The portfolio and the reference portfolios are valued at the net asset values the ETF issuers publish, the equity ETF's converted from US dollars at the ECB reference rate of the same day or the last one before it. The look-through uses the holdings files the issuers publish, and the bond sleeve's credit ratings and duration are the figures of the issuer's monthly factsheet, with its date. All are cached locally and not redistributed, and only the figures computed from them are published. The bid and ask recorded with each order are Tradegate Exchange's real-time quotes, saved before the order and not those of the venue where it executes. Each order's half-spread is measured against them.

## Running the code

From the repository root:

```
pip install -r requirements.txt pytest
python3 mandate/allocation_check.py
python3 mandate/simulations.py
python3 -m pytest tests
```

`allocation_check.py` downloads its five source files into `cache/`, which is not committed, and rewrites `mandate/allocation_check_results.md`. Its sample ends in December 2025, so a later run differs only where a source revises its history. `simulations.py` reads the same files, checks that its code reproduces the allocation test, and rewrites the three simulation tables with one fixed seed, so a run reproduces them. The tests run on invented ledgers and simulated returns. The program reads the private ledger: with `PYTHONPATH=src`, `python3 -m portfolio check` checks the ledger against rules 7 and 10, `status` shows the holdings and weights, `cycle` gives the orders of a cycle day, and `build` writes `outputs/` and `index.html`.

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
- **index blend**: 70 per cent MSCI ACWI net total return and 30 per cent the Bloomberg Euro-Aggregate Treasury index, in euro, rebalanced at each month end.
- **implementation cost**: the portfolio's value relative to reference portfolio A, with contributions removed, in basis points, negative when the portfolio trails.
- **half-spread**: half the gap between the ask and the bid quoted when an order is placed.
- **basis point**: one hundredth of a percentage point.
- **split**: the pair of target weights, written equity/bonds, for example 70/30.
- **risk limit**: the worst fall the mandate aims to stay within, about one third, tested as 35 per cent.
- **growth per year**: the compound annual return, with contributions removed.
- **drawdown**: the fall in the portfolio's value below its previous peak on a given day, with contributions removed, in per cent.
- **worst fall**: the largest drawdown, meaning the largest fall in the portfolio's value from a previous peak to a later low, with contributions removed.
- **tracking difference**: an ETF's return minus its index's return over a calendar year, in percentage points.
- **duration**: the approximate percentage change in a bond's price for a change of one percentage point in its yield, in years. For the bond sleeve it is the average duration in the issuer's factsheet.
- **factor**: the return of one of the developed-market factors in Kenneth French's data library: the market's return minus the risk-free rate, and long-short portfolios for size, value, profitability, investment and momentum.
- **loading**: the coefficient of the ETF's return minus the risk-free rate on a factor's return.
- **risk-free rate**: the one-month US Treasury bill return in French's files.
- **standard error**: the estimated standard deviation of an estimate.
- **allocation test**: the historical test in `mandate/allocation_check.py` that derived the split from the risk limit, on monthly euro returns from February 1999 to December 2025.
- **bootstrap**: the resampling of the allocation test's returns in blocks of twelve consecutive months, each starting at a random month, into paths of five and ten years, with the worst fall measured on each path.
- **mechanics simulation**: the rules applied to the allocation test's returns, with a starting amount of 100 and a top-up of 5 a month, for the counts of their orders.
- **resampled paths**: the bootstrap's ten-year paths carried forward from the first purchase with the top-up and the rules, in units of the starting amount.
- **in-sample**: computed on the data on which a choice was made, here the returns from 1999 to 2025 on which the split was chosen.
