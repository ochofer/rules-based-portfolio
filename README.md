# Rules-based portfolio

I run a small real-money portfolio of two exchange-traded funds under written rules: 70 per cent in a global equity ETF and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. This repository holds the mandate, the rules and the test that derives the split from the mandate's risk limit, and it will hold the program that keeps the record of the portfolio and the dashboard built from the program's outputs.

## Status

Work in progress. The mandate and the test behind the split are in `mandate/`. The rules and the choice of the two ETFs are in `rules/RULES.md`, fixed on 7 October 2026 before the first order and tagged `rules-v1.0`. A rule changes only by a dated amendment to that file, which applies from the first cycle day at least 30 days later. The monitoring program and the dashboard are being written.

## What the record measures

The record covers the running of the portfolio: the orders and their costs, the drift of the weights away from the target weights, and the rebalancing the rules produce. Two reference portfolios, built from the same contributions and without costs, will sit beside it. The first follows the same rules, so the difference between it and the portfolio is the cost of implementation. The second goes back to its target weights on every cycle day, so the difference between the two reference portfolios is what the band saves or costs. At this size the returns cannot distinguish one set of rules from another, and they are reported as a record of the portfolio only.

## What is published and what is not

The repository publishes weights, percentages, the metrics the program computes and the charts drawn from them. A contribution appears only as a share of the portfolio. Euro amounts, units, broker statements and price histories stay outside the repository. Executed prices, fees and month-end valuations come from the broker's statements. The daily prices behind the charts are the net asset values the ETF issuers publish, the value of one share at each day's close, cached locally and not redistributed.

## Terms

- **portfolio**: the two ETFs held under these rules, plus any contribution not yet invested.
- **ETF**: exchange-traded fund, a fund whose shares are listed on a stock exchange. Each ETF held here is a single share class with its own ISIN.
- **sleeve**: the part of the portfolio held in one ETF.
- **weight**: a sleeve's value divided by the value of the portfolio.
- **target weight**: the weight the rules aim for, 70 per cent equity and 30 per cent bonds.
- **band**: the interval from 65 to 75 per cent for the equity weight. Outside it, the portfolio is brought back to its target weights.
- **rebalancing**: moving the weights back towards the target weights, through top-ups (rule 4) or through the band (rule 5).
- **contribution**: money paid into the portfolio, meaning the starting amount and each top-up.
- **starting amount**: the first contribution, fixed before the first order.
- **top-up**: the fixed monthly contribution, 5 per cent of the starting amount.
- **cycle day**: the day each month on which the rules are applied, the 5th or the next trading day.
- **order**: an instruction to the broker to buy or sell one ETF.
- **ledger**: the private record of every contribution and every order, kept outside the repository.
- **reference portfolio**: a portfolio computed from the same contributions and prices as the portfolio, without costs.
- **split**: the pair of target weights, written equity/bonds, for example 70/30.
- **risk limit**: the largest worst fall the mandate accepts, about one third, tested as 35 per cent.
- **growth per year**: the compound annual growth of the portfolio's value.
- **worst fall**: the largest fall in the portfolio's value from a previous peak to a later low, with contributions removed.
- **tracking difference**: an ETF's calendar-year return minus the return of the index it tracks.
