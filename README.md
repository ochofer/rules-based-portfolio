# Rules-based portfolio

I run a real-money portfolio under written rules: 70 per cent in a global equity ETF and 30 per cent in a euro government bond ETF, funded by a starting amount and a fixed monthly top-up. The mandate sets the objective and the risk limit, a test on monthly data from 1999 to 2025 derives the split from that limit, and the rules determine every order the portfolio places. The rules were fixed before the first order and are tagged `rules-v1.0`.

The portfolio is too small to hold a whole market in single securities, so each sleeve is an ETF and the record looks through both ETFs to the companies and bonds inside them.

## How the portfolio is run

On the cycle day, the 5th of each month or the first trading day after it when the 5th is not one, the weights are computed from the ledger. The monthly top-up buys the sleeve furthest below its target weight, up to that target weight, and any remainder buys both sleeves at 70/30. If the equity weight is then below 65 or above 75 per cent, the portfolio is brought back to 70/30 the same day. Nothing else triggers an order, and a fall in prices does not pause the cycle. At most five orders are placed in a month, each between 15:45 and 17:00 Amsterdam time on a trading day. A rule changes only by a dated amendment, which applies from the first cycle day at least 30 days after it is committed.

## Contents

| Path | What it holds |
|---|---|
| `mandate/MANDATE.md` | The objective, the risk limit and how the split follows from the limit. |
| `mandate/allocation_check.py` | The test that derives the split, with its data sources. |
| `mandate/allocation_check_results.md` | The output of the test for every split from 40/60 to 100/0. |
| `rules/RULES.md` | The ten rules, the two ETFs and how they were chosen. |

The program that computes the record from the ledger, and the dashboard drawn from its outputs, are not yet written.

## What the record measures

The record covers the running of the portfolio: the orders and their costs, the drift of the weights away from the target weights, the rebalancing the rules produce, and the look-through of the two ETFs. For equity the look-through gives the weights of regions, countries, sectors, currencies and the largest companies, and for bonds the weights of issuing countries and maturities, and the duration of the bond sleeve. Returns are time-weighted, so contributions do not count as gains.

Two reference portfolios, computed from the same contributions and prices without costs, sit beside the portfolio. The first follows the same rules, so the difference between it and the portfolio is the cost of implementation. The second goes back to its target weights on every cycle day, so the difference between the two reference portfolios is the effect on returns of letting the weights drift inside the band, before costs. A record of five to ten years is too short to show that one set of rules is better than another, so the returns are not offered as evidence for the rules.

## What is published and what is not

The repository publishes weights, percentages, the metrics the program computes and the charts drawn from them. A contribution appears only as a share of the portfolio. Euro amounts, units and the broker's statements are kept private and never committed. Executed prices, fees and month-end valuations come from the broker's statements. The daily prices behind the charts are the net asset values the ETF issuers publish, and the look-through uses the holdings files the issuers publish. Both are cached locally and not redistributed, and only the figures computed from them are published.

## Rerunning the test

From the repository root:

```
pip install -r requirements.txt
python3 mandate/allocation_check.py
```

The script downloads its five source files into `cache/`, which is not committed, and rewrites `mandate/allocation_check_results.md`. The sample ends in December 2025, so a later run differs only where a source revises its history.

## Terms

- **portfolio**: the two ETFs held under these rules, plus any contribution not yet invested.
- **ETF**: exchange-traded fund, a fund whose shares are listed on a stock exchange. Each ETF held here is a single share class with its own ISIN, the 12-character code that identifies a security.
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
- **order**: an instruction to the broker to buy or sell one ETF.
- **ledger**: the private record of every contribution and every order, kept outside the repository.
- **record**: what the program computes from the ledger and the prices: holdings, weights, orders and their costs, returns, the look-through and the reference portfolios.
- **look-through**: the portfolio's exposure to the securities inside the two ETFs, each ETF's holdings weighted by the ETF's weight in the portfolio.
- **reference portfolio**: a portfolio computed from the same contributions and prices as the portfolio, without costs.
- **split**: the pair of target weights, written equity/bonds, for example 70/30.
- **risk limit**: the worst fall the mandate aims to stay within, about one third, tested as 35 per cent.
- **growth per year**: the compound annual return, with contributions removed.
- **worst fall**: the largest fall in the portfolio's value from a previous peak to a later low, with contributions removed.
- **duration**: the average time to a bond's payments, weighted by their present value. For a bond fund it is close to the per cent fall in price when yields rise by one percentage point.
- **net asset value**: the value of one share of a fund, computed by the issuer from the fund's holdings at the day's close.
- **tracking difference**: an ETF's calendar-year return minus the return of the index it tracks.
