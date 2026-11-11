# Guide to the dashboard

## About the portfolio and this guide

The rules-based portfolio is a real-money portfolio run under written rules, fixed and tagged before its first order on 8 October 2026. It holds two exchange-traded funds, or ETFs, which are funds whose shares are bought and sold on a stock exchange like the shares of a company: a global equity ETF and a euro government bond ETF. A starting amount, paid in before the first purchase, and a fixed contribution every month fund it. The rules produce the orders the portfolio places, and every departure from them is kept in a register. A program in the public repository computes every figure on the dashboard from the private record of orders and contributions and from the data the ETFs' issuers publish.

The dashboard is where that record is published. It is rebuilt every Monday and on each day the rules are applied, and it is organised in five views: Overview, Performance, Portfolio, Risk and Method. The Overview says where the portfolio stands against its rules. Performance gives what the portfolio has returned, what was paid in and what running it costs, and Portfolio what it holds and how the rules keep its weights near their targets. Risk estimates how far the portfolio could fall and applies the rules to a longer history, and Method explains how the portfolio was set up and holds the terms and the written record of each month.

This guide explains every view, part, key figure and exhibit of the dashboard for readers with or without a background in finance: what each one shows, how to read it, where its numbers come from and what it cannot tell. The guide is built with the dashboard, so its figure and table numbers are the dashboard's. Each entry opens with a link to its place on the dashboard, the references in the text link to the entry they name, and the terms at the end define every word the dashboard uses in a sense of its own.

## Before you start

The entries that follow assume twelve ideas, which recur across the views of the dashboard.

**The portfolio, its sleeves and their weights.** The portfolio is the two ETFs held under the rules, plus any contribution not yet invested, which is held as cash. A sleeve is the part of the portfolio held in one ETF: the equity sleeve holds the iShares MSCI ACWI UCITS ETF, whose index covers large and mid-sized companies in developed and emerging markets, and the bond sleeve holds the Vanguard EUR Eurozone Government Bond UCITS ETF, whose index covers euro area government bonds. A sleeve's weight is its value divided by the value of the portfolio, in per cent.

**Target weights, the split and the band.** A target weight is the weight the rules aim for: 70 per cent for equity and 30 per cent for bonds. A split is the pair of target weights, written equity/bonds, so the portfolio's split is 70/30. The band is the interval from 65 to 75 per cent for the equity weight. Inside it the rules sell nothing, and when the equity weight is outside it on the day the rules are applied, the portfolio is brought back to 70/30 that day.

**The cycle day, the top-up and the orders.** The cycle day is the day each month on which the rules are applied: the 5th, or the first trading day after it when the 5th is not one. The top-up is the fixed monthly contribution, 5 per cent of the starting amount, paid in by the 2nd and invested on the cycle day in the sleeve furthest below its target weight. The rules allow at most five orders a month, each placed between 15:45 and 17:00 Amsterdam time.

**Net asset value.** An ETF's net asset value is the value of one of its shares at the close of a day, as its issuer publishes it, usually on the next working day. The dashboard values the portfolio at these values, the equity ETF's converted from US dollars at the reference rate of the European Central Bank (ECB). Because the values arrive a day late, the record ends at the last day for which both ETFs have published one, and the date under the dashboard's title is that day.

**Growth of 100, with contributions removed.** Most charts of returns start at 100 and show what 100 of the starting amount would have become. Contributions are removed from these lines, so a top-up does not count as a gain: each day's change is the return on the money the portfolio held that day, and the days are chained together. This is the time-weighted return. The money-weighted return counts the timing of the contributions as well, since it is the rate at which the contributions, each from its own date, grow to the portfolio's value. The two differ when money arrives just before a rise or a fall.

**Reference portfolios A and B.** A reference portfolio is a portfolio computed from the same contributions and the same prices as the portfolio, without costs. Reference portfolio A follows the same rules and buys at net asset value, so it is the portfolio as the rules would have run it if placing an order cost nothing. Reference portfolio B receives the same contributions and goes back to 70/30 on every cycle day.

**The implementation cost and the basis point.** The implementation cost is reference portfolio A's value relative to the portfolio's, with contributions removed: what running the portfolio has cost against the rules followed at no cost. It is given in basis points, and a basis point is one hundredth of a percentage point, so 10 basis points are 0.1 per cent. The implementation cost is positive when the portfolio is worth less than reference portfolio A and negative when it is worth more, as when a purchase was filled below the day's net asset value.

**Drawdown, worst fall and the risk limit.** A drawdown is the fall in the portfolio's value below its previous peak on a given day, with contributions removed, in per cent. The worst fall is the largest drawdown over a period. The risk limit is the worst fall the mandate, the document that sets the portfolio's objective, aims to stay within: about one third, tested as 35 per cent, with 40 per cent as an outer bound.

**Look-through.** The look-through is the portfolio's exposure to the securities inside the two ETFs, each ETF's holdings weighted by the ETF's weight in the portfolio. It turns two funds into the companies, countries, sectors, currencies and bonds that the portfolio holds through them.

**The record, history and simulations.** The dashboard shows three kinds of numbers, and each exhibit says which kind it shows. The record is what the program computes from the ledger, the private record of every contribution and order, and from the prices, since the first purchase. The allocation test and the simulations use index returns from February 1999 to December 2025, which run back before the two ETFs existed, to show how the rules behave over a longer history, and they are never part of the record. A record of five to ten years cannot show that one set of rules is better than another, so the dashboard does not offer its returns as evidence for the rules.

**Growth per year, volatility and correlation.** Growth per year is the compound annual return, with contributions removed. Volatility is the standard deviation of returns, a measure of how widely they spread around their average, and the dashboard gives it for a year. A correlation runs from −1, when two returns always move in opposite directions, through 0, when they are unrelated, to 1, when they always move together.

**Exhibits and their parts.** Every chart is a figure, and every table that stands on its own is a table, each numbered in page order across the views. Under the title, a line gives the unit or the dates and the basis of the numbers. A note explains what the exhibit shows, a source line names the file in the repository that holds its numbers, and a Table toggle opens the numbers behind the chart. Nothing depends on hovering over a chart, since every value is in its table.

## The page around the views

The navy band and title block at the top, the bar of views and the footer stay the same on every view.

**The band and the title block.** The navy band carries the site's menu. Under it, the title block gives a line on what the dashboard covers, the date of the figures and the day of the last build, and links to the rules, the mandate, this guide and the code. When the prices and the holdings have different dates, as after a cycle day whose orders are not yet valued, both dates are written.

**The bar of views.** The five views are tabs in one bar, which stays at the top of the screen as the page scrolls, and each view opens with one line that says what it answers. On a narrow phone the bar scrolls sideways, and a fade marks each edge beyond which more tabs lie. A link to a part of a view opens that view at that part, and a link to a part keeps working when the page is rearranged.

**The footer.** The footer states the basis of the returns: in euro, at the issuers' net asset values, after costs, time-weighted except where the money-weighted return is named, and not offered as evidence for the rules, since past performance is no guide to future returns. It closes with the date of the last build and a link to the code.

## ⟦view:overview⟧ Overview

The Overview answers where the portfolio stands against its rules. Four key figures run across the top, a sentence on the returns sits under them, and two figures side by side follow. The key facts stand beside them, and after them on a phone.

### The key figures

The four key figures are the ones a reader checks first, each with a line under it that names what it is measured against.

**Equity weight.** The equity sleeve's weight on the record's date. The line under it gives the target weight of 70 per cent and the band from 65 to 75 per cent.

**Drift from target.** The equity weight minus its target weight of 70 per cent, in percentage points. The band allows a drift from −5 to +5 points before the rules sell anything.

**Drawdown now.** The fall of the growth of 100 below its previous peak on the record's date, in per cent. Zero means that the portfolio is at a new peak.

**Orders this month.** The orders placed in the current month, against the allowance of five set by rule 6. Unlike the record, this figure also counts orders placed after the last net asset values, since the allowance applies to orders as they are placed.

The sentence under the key figures gives the return since the first purchase in two forms, both in euro and after costs. The time-weighted return is the growth of 100 of ⟦c3⟧, less 100, in per cent, with contributions removed. The money-weighted return counts the timing of the contributions as well, which the time-weighted return removes. Within the first year both are cumulative and not annualised, and no annual figure is shown, since past performance is shown for complete twelve-month periods only. From the first full year on, both are given per year.

### ⟦c2⟧ Allocation against the target and the band

⟦c2⟧ shows the weights of the two sleeves on the record's date against their target weights. Each bar is a sleeve's weight, navy for equity and slate grey for bonds, with its value at its end, and the black tick on each bar is its target weight. The shaded interval behind the equity bar is the band, from 65 to 75 per cent, labelled above it. The bond sleeve has no band of its own, since its weight is what the equity weight and the cash leave. Cash, the contributions not yet invested, is given in the note, and the table lists all three weights.

The figure tells a reader what the next cycle day would do at these weights. When the equity bar ends inside the shaded interval, the rules sell nothing on that day and the top-up alone moves the weights towards their targets. When it ends outside, the next cycle day brings the portfolio back to 70/30 (rule 5). An order placed after the last net asset values enters the figure with the next ones, and the note names it.

### ⟦c4⟧ Drawdown against the mandate's limit

⟦c4⟧ shows how far the portfolio has been below its previous peak on each day since the first purchase. The filled navy area is the drawdown, drawn downwards, so the deeper the area, the larger the fall, and the end of the line carries the latest value. The axis runs to the mandate's outer bound of 40 per cent, or deeper once a fall passes it, and the dashed line is its test limit of 35 per cent. The grey line, from the second month end, is the index blend's drawdown at month ends, and the note gives the worst fall to date.

The figure and the mandate measure falls differently. The mandate's test used month-end values, which miss falls that reverse within a month, while the figure uses daily values, so the worst daily fall is at least as deep as the worst month-end fall. A drawdown is never a reason to act: under rule 8 a fall in prices neither pauses the cycle nor adds an order.

### ⟦#key-facts⟧ Key facts

The key facts set out the portfolio's terms in ten rows: the two sleeves with the full names of their ETFs and their target weights, the band, the contributions, the rebalancing, the risk limit, the ongoing costs of the two ETFs at the sleeve weights with each ETF's own, the valuation in euro at the issuers' net asset values, the day of the first purchase, and the benchmark, the portfolio against which a manager's work is measured. Each ETF also has a distributing share class under another ISIN, so the full name identifies the fund held. An ETF's ongoing costs are its TER plus its transaction costs, which is why the equity ETF's figure here is above its TER of 0.20 per cent. The benchmark is the blend of the two funds' own indices at 70/30, rebalanced at each month end, which the dashboard calls the index blend, and the row links to the part of the Method view that explains it. The rules and the mandate, linked under the title, set out each of the terms in full.

## ⟦view:performance⟧ Performance

The Performance view answers what the portfolio has returned since the first purchase, how that sets against its comparators, what was paid in and what running it costs. It opens with the growth of 100, followed by three parts, Comparisons, Contributions and Costs.

### ⟦c3⟧ Growth of 100: the portfolio, the reference portfolios and the index blend

⟦c3⟧ shows what 100 of the starting amount has become since it was invested, beside the two reference portfolios and the index blend, all with contributions removed. The navy line is the portfolio, labelled with its last value. The dark grey line is reference portfolio A, the same rules without costs: the same contributions, and the rules applied to its own values on the same cycle days, with its orders filled at the day's net asset value in fractional units and no commission or spread. The mid grey dotted line is reference portfolio B, back to 70/30 on every cycle day. On a cycle day on which the top-up alone brings reference portfolio A back to 70/30, the two end the day alike, so the dotted line lies on the dark grey one until a month in which the top-up is not enough, and the note under the figure says so while it does. The light grey line is the index blend, the portfolio's benchmark: 70 per cent MSCI ACWI net total return and 30 per cent the Bloomberg Euro-Aggregate Treasury index, in euro, rebalanced at each month end. The blend is monthly, starts at the portfolio's level on the first month end and is drawn once a second month's returns are published.

Three comparisons sit on this chart, and each answers its own question. The gap between the portfolio and reference portfolio A is the implementation cost, which ⟦c8⟧ follows. The gap between reference portfolio A and reference portfolio B is the drift effect, the effect on returns of letting the weights drift inside the band, before costs. The gap between the portfolio and the index blend adds the tracking difference of the two ETFs, each fund's calendar-year return minus its index's, and from the twelfth month end ⟦attribution⟧ splits it into these three parts. Over a record this short, none of the gaps says whether the rules are good ones.

The line under the figure links to the part of the Method view that explains [what the portfolio does not do](#method-not-done): why it has no optimiser, no single market index as its benchmark, no views and no signal.

### ⟦#comparisons⟧ Comparisons

The Comparisons part sets the record beside comparators: portfolios that receive the same contributions on the same days, valued in euro at the issuers' net asset values or at a published rate, without costs. Each comparator answers one question about the portfolio's choices, and every return or difference in the part stands beside its volatility, its worst fall and the band chance alone produces over the same span. The part opens with a summary table and a pair of charts, always shown, and seven panes below them open on a tap and print open. The benchmark, the index blend, has values at month ends only, so its statistics, its difference and its place on the charts start at the sixth month end. A daily comparator's volatility, correlation, difference and band start at its 20th daily return, about a month.

### ⟦comparisons⟧ The portfolio and its comparators since the first purchase

⟦comparisons⟧ gives one row for the portfolio and one for each comparator: the benchmark, reference portfolios A and B, the same two ETFs at 100/0, 90/10, 80/20 and 60/40 under the same rules, 70/30 under the same rules with the first-ranked equity fund, six single funds held in place of the two ETFs, the global market portfolio, savings at the euro short-term rate, and a bank's managed 70/30 profile, which has no return to show. The euro short-term rate is the rate at which banks borrow euro overnight without collateral, which the European Central Bank publishes each working day. For each row it gives the time-weighted return since the first purchase, cumulative and not annualised, the volatility, the worst fall, the difference to the portfolio's return in percentage points, the band chance alone produces, and the window of days both series cover. The volatility here is the standard deviation of daily returns times the square root of 252, so a figure for a year.

The band answers whether a difference is larger than chance alone would make it over the same span. The tracking error is the standard deviation of the daily differences between the two series' returns times the square root of 252, and the band's half-width is two tracking errors times the square root of the years. It ignores compounding and treats the daily differences as independent. A difference inside the band is one that chance alone produces often over a span this long. Volatility, worst falls and correlations become informative within months, and differences of return over years, so over the record's first months a difference says nothing about either rule set.

### ⟦comparisons-differences⟧ The difference of each comparator to the portfolio, and its band

⟦comparisons-differences⟧ shows each comparator's difference as a navy bar from zero, over a light bar for its band, centred on zero. A navy bar that ends inside its light bar is a difference chance alone would produce over the same span. The table gives each difference with its band, the comparator's volatility and its worst fall.

### ⟦comparisons-ladder⟧ Volatility against return since the first purchase

⟦comparisons-ladder⟧ places each comparator by its volatility on the horizontal axis and its return since the first purchase on the vertical axis. The splits under the same rules lie on one grey line, from 60/40 through reference portfolio A, which is 70/30, to 100/0, and the navy dot is the portfolio. Each other comparator is a dot in its own colour, named in the legend. Savings sit near zero volatility. More equity always means more volatility, while the return of these few weeks can fall as equity rises, as it does when stock markets fall, so the chart shows the risk each split took and the return it earned over these days. The return to expect from a split is a question for decades of data, which the allocation test in the Method view holds. The table adds each worst fall and band.

### ⟦comparisons-same-rules⟧ The same rules without costs

The first pane holds reference portfolios A and B. ⟦comparisons-same-rules⟧ shows each one's return minus the portfolio's over time, in percentage points, with the portfolio at zero. Reference portfolio A's line is the implementation cost of ⟦c8⟧ with the opposite sign and in percentage points, and the gap between the lines of A and B is the drift effect. The rows under the chart give every measure, with the dates of each worst fall and each comparator's correlation of daily returns with the portfolio's. The benchmark joins this pane at the sixth month end.

### ⟦comparisons-splits⟧ The same rules with other funds or splits

The second pane runs the portfolio's own rules around other target weights: 100/0, 90/10, 80/20 and 60/40, each with the band of rule 5 five points either side of its target, which never binds for 100/0, on the same two ETFs, contributions and cycle days, without costs. It also runs them at 70/30 with the first equity fund of the rules' own ranking, SPDR MSCI ACWI, which the account does not offer, in place of the iShares fund held, and the bond fund held, which ranks first. ⟦comparisons-splits⟧ shows each one's difference to the portfolio over time, and the rows under it give every measure. A split with more equity moves further from the portfolio whenever equities move, and the first-ranked funds stay close to reference portfolio A, since both equity funds track the same index. While the pane holds the splits alone, its headline is The same rules at other splits.

### ⟦comparisons-one-fund⟧ One fund instead of two

The third pane asks what a single fund would have done with the same money. Each fund takes the same contributions on the same days at its net asset value in euro and is held throughout without costs: the S&P 500 alternative of the Method view, an MSCI World fund, Vanguard's LifeStrategy 60% and 80% Equity, which hold stocks and bonds in one fund, a Nasdaq-100 fund and the Mag7 fund, which holds seven large US companies. ⟦comparisons-one-fund⟧ shows each one's difference to the portfolio over time, and the rows under it give every measure. The Mag7 fund publishes net asset values from 4 November 2026, so its line starts on that day, with the portfolio's value at that close, and each of its figures runs over that window. A fund that holds only US companies moves with one market, so its line can move far from the portfolio's within weeks.

### ⟦comparisons-selection⟧ How the one-fund comparators' funds were chosen

⟦comparisons-selection⟧ lists the funds the rules' own criteria ranked for the S&P 500, the MSCI World and the Nasdaq-100, with the index in place of the global index, and the comparator takes the first one the account offers. Each row gives the fund's TER, its tracking difference in each of the three calendar years and their average, whether the account offers it and the date of its factsheet. The funds were fixed with their ISINs on 10 November 2026, before any of their values was read, as the ETF selection of the Method view did for the two ETFs held.

### ⟦comparisons-market⟧ Every asset class at its market value

The fourth pane holds the global market portfolio, every asset class at its share of the world's invested market value, a comparator the portfolio's design names. The benchmark remains the index blend. Its weights are those of Doeswijk, Lam and Swinkels at the end of 2023, from version 6 of the data update of their 2014 paper on the global multi-asset market portfolio, for eight classes: equities, government bonds, investment-grade credits, private equity, real estate, emerging-market debt, inflation-linked bonds and high-yield bonds. The comparator takes the same contributions on the same days. It bought the published weights carried to the day before the first purchase by each class fund's return in euro, holds them as they move with prices, as the market holds them, and invests each top-up in proportion to what it holds. Carried weights are not the market's weights of that day, since issuance and repayment also move the market's. Each class is held through one ETF at its net asset value in euro without costs, and government bonds and investment-grade credits share one global aggregate bond fund. ⟦comparisons-market⟧ shows its difference to the portfolio over time, and the rows under it give every measure. Its equity-like share, equities, private equity and real estate together, is about 55 per cent in the published weights and about 64 per cent once carried to the comparator's start, against the portfolio's 70, and nothing scales it to the portfolio's risk, so its line moves with equities as a split's does.

### ⟦comparisons-market-weights⟧ The global market portfolio's weights and funds, by asset class

⟦comparisons-market-weights⟧ gives each asset class with its fund, the fund's ISIN and TER, and the class's weight three times: as published for the end of 2023, carried to the comparator's start, and at the last close. Each fund is the first in its class's ranking under the rules' own criteria that the account offers (method/selection_market_portfolio.csv), and equities are held in the portfolio's own equity ETF. The funds were fixed with their ISINs on 10 November 2026, and the ranking's last column records each value seen of a fund before it was fixed. The account offers the aggregate fund only in its distributing class, so its distributions are added back on their ex-dates. It offers no inflation-linked fund that passes the criteria, so that class is held in the aggregate fund. Listed private equity companies and listed property companies stand in for the private funds and the invested real estate the dataset counts. The last row gives the TERs weighted by the published weights, a cost the comparator does not carry, since every comparator is valued without costs.

### ⟦comparisons-savings⟧ The money left in the bank

The fifth pane holds the contributions at the euro short-term rate, compounded daily on calendar days at the rate divided by 360, the convention of the money market. ⟦comparisons-savings⟧ shows its difference to the portfolio over time. Its volatility is above zero only because interest lands in three-day steps over weekends, and its correlation with the portfolio is not shown, since the rate barely moves from day to day.

### ⟦comparisons-managed⟧ Not like for like: a bank's managed profile

The sixth pane sets the portfolio beside what a bank charges to run the same split. Rabobank's Rabo Beheerd Beleggen Basis manages index funds in four profiles, and its profile Offensief holds 70 per cent equity and 30 per cent bonds. Rabobank publishes no return for its profiles, so the profile has no figures in the comparisons and is not like for like. Costs are therefore all this pane compares. ⟦comparisons-managed⟧ gives one row each for the portfolio, the two LifeStrategy funds and the profile, with the costs a year in basis points, what they are made up of, and their source and date. The profile's costs are read from Rabobank's published cost overview at each build. The portfolio's implementation cost since the first purchase is in a sentence under the table, since it is cumulative and not a cost a year.

### ⟦comparisons-effects⟧ Where each difference came from

The seventh pane splits each comparator's difference into named effects. ⟦comparisons-effects⟧ starts at the portfolio's money-weighted return, adds each effect as a bar to the right or to the left, and ends at the comparator's money-weighted return. The selector above it picks the comparator, and the table under it gives every comparator's effects side by side, with both returns of both and each comparator's difference, band, volatility and worst fall.

The effects are computed day by day and summed by month and over the record. Implementation is reference portfolio A's return minus the portfolio's, the cost of running the portfolio with the opposite sign. Drift is reference portfolio B's return minus reference portfolio A's. The invested part of a portfolio is its value less its cash. Split is the difference in the share of equity in the invested part times the equity ETF's return in US dollars minus the bond ETF's return, and the dollar is the same difference times the gap between the equity ETF's return in euro and in US dollars, so the two together are the split in euro. Cash is the difference in cash weight times the return of the invested part. For a comparator that holds other funds, the difference runs through the two ETFs held at the comparator's own equity share, which gives cash, split and the dollar by the same definitions. Regions is then the comparator's equity share times the sum over the four MSCI regions of its weight in the region minus the held ETF's, times the region's index return in euro, the allocation term of Brinson and Fachler. Within each region is the rest: which companies each fund holds inside a region, its costs and its timing against the indices. For the global market portfolio, the difference runs through the two ETFs held at its equity-like share. Equity classes is the weight of private equity and of real estate times each fund's return in euro minus the equity ETF's, and bond classes is the weight of each bond class times its fund's return in euro minus the bond ETF's. Each dollar fund's conversion to euro goes to the dollar, less the equity ETF's for an equity-like class, so the currencies inside a bond fund's dollar return stay in bond classes. For savings, the bond ETF's return against the rate is split three ways at the yield of the ECB's curve at the bond ETF's duration: the rate against the yield the bonds earn over the days, the duration times the change in that yield, and the rest of the bond return. The LifeStrategy funds hold global bonds hedged to the euro, which that curve does not price, so their bond rows are n/a. Timing of contributions is the comparator's money-weighted return minus its time-weighted return, less the portfolio's, and compounding is what the daily sums leave of the difference over the whole record. On each day the effects sum exactly to the difference of that day's returns. An effect that does not apply to a comparator is zero.

### ⟦#contributions⟧ Contributions

The Contributions part separates the money paid in from the gains and losses on it. Its figures are in units of the starting amount, which counts as 100, so the part shows the portfolio's money without publishing a euro amount.

### ⟦c9⟧ Money paid in and the value of the portfolio

⟦c9⟧ compares what has been paid into the portfolio with what it is worth. The starting amount counts as 100 units and each top-up adds 5. The grey line is the money paid in, which steps up with each top-up, the navy line is the portfolio's value, and the shaded area between them is the gain or loss on the money paid in. Unlike ⟦c3⟧, this figure keeps the contributions in, since it shows money and not returns.

### ⟦c10⟧ Market effect and contribution by month

⟦c10⟧ shows, for each month, how much the portfolio's value changed through markets and how much through new money. The upper panel is the market effect, the month's change in value that did not come from contributions, in per cent of the value at the start of the month. The lower panel is the contribution, the money paid in during the month, in the same unit, and the table gives both by month. Together the two make up the month's change in value. While the portfolio is young, a top-up of 5 per cent of the starting amount can be large against a month's market effect.

### ⟦#costs⟧ Costs

The Costs part measures what running the portfolio costs. It separates two kinds of cost: the cost of placing the portfolio's orders, measured against reference portfolio A, and the ETFs' own yearly costs, which are taken inside their net asset values.

### ⟦c7⟧ Cost per month by source

⟦c7⟧ splits each month's implementation cost into four sources. Each bar is a month, in basis points of the portfolio's value on the day of each order, and its four parts are shades of navy, from the darkest for the price paid against net asset value, through the currency conversion and the half-spread at execution, to the lightest for the commissions. A part below zero is a saving. The table adds the orders without a recorded bid and ask and the month's total.

The four sources have exact meanings. The half-spread is half the gap between the ask and the bid quoted when an order is placed, which is what buying or selling at once costs at that moment. The commissions are the broker's fees, and the currency conversion is the cost of changing euro into another currency, which neither ETF needs, since both are bought in euro, so this part is zero. The price paid against net asset value is the gap between each order's price and the ETF's net asset value of that day, beyond the half-spread. It is computed as the month's implementation cost minus the other three, so the four parts of a month add up to that month's implementation cost in ⟦c8⟧. For an order without a recorded bid and ask the half-spread cannot be measured, and it stays inside the price paid against net asset value.

One month's sign says little. An order fills at a price during the day while the net asset value is set at the close, so the price paid against net asset value can be negative as well as positive.

### ⟦c8⟧ Implementation cost, cumulative

⟦c8⟧ follows the implementation cost since the first purchase, cumulative, in basis points. The line is reference portfolio A's value relative to the portfolio's, with contributions removed, and it is positive when reference portfolio A is worth more, that is, when running the portfolio has cost money. The line at zero marks no cost at all, and the end of the line carries its last value.

The line and ⟦c7⟧ are two views of the same cost. A cost of 10 basis points in one month of ⟦c7⟧ moves this line up by 10 basis points in that month, so the slope of the line is the cost of each month. The ETFs' yearly costs are not in it, since reference portfolio A pays them too, inside the same net asset values.

### ⟦ownership⟧ What the portfolio costs a year

⟦ownership⟧ sets the ETFs' yearly costs beside the implementation cost. For each ETF it gives the ongoing costs, its TER, or total expense ratio, plus its transaction costs, as the ETF's key information document states them, with the document's date and the ETF's weight. The portfolio's row weights the two ETFs by their sleeve weights, and a cash row completes the weights.

The note sets the implementation cost of ⟦c8⟧ beside the ongoing costs and explains its sign order by order. The two numbers measure different things: the ongoing costs are what holding the ETFs costs every year, taken inside their values, and the implementation cost is what placing the portfolio's own orders has cost since the first purchase.

## ⟦view:portfolio⟧ Portfolio

The Portfolio view answers what the portfolio holds and how the rules keep the equity weight in its band. Its three parts are Rebalancing, Look-through and the equity ETF's exposures.

### ⟦#rebalancing⟧ Rebalancing

The Rebalancing part shows the equity weight against its band and every order against the rules. Rebalancing means moving the weights back towards the target weights, through the top-ups (rule 4) or through the band (rule 5).

### ⟦c5⟧ Equity weight in its band, with every order

⟦c5⟧ follows the equity weight day by day since the first purchase and marks each order on the day it was placed. The navy line is the equity weight, the shaded interval is the band from 65 to 75 per cent, and the black line is the target of 70 per cent. A navy dot marks a purchase of the equity ETF and a smaller slate dot a purchase of the bond ETF, drawn smaller so that a day with both purchases shows both. A red diamond labelled "Band order" marks a day on which the band brought the portfolio back to 70/30, and an open orange circle marks an order that the rules called for and that was not placed. The table gives each day's weights of equity, bonds and cash.

Between cycle days the line moves with markets alone, since no order is placed. On a cycle day the top-up moves it towards 70 per cent, and only when the weight has left the band does the cycle day bring it back to 70 exactly. An order placed after the last net asset values enters the figure with the next ones, and the note names it.

### ⟦c6⟧ Orders per month against the allowance of five

⟦c6⟧ counts the orders placed in each month. Each bar is a month's orders, and the line at five is the allowance of rule 6, the number of orders a month that the account's plan carries without commission. The table lists every order with its date, sleeve, side and the rule that called for it, whether it was placed inside rule 7's window of 15:45 to 17:00 Amsterdam time, and whether the bid and ask were recorded when it was placed.

Apart from the first purchases, the rules call for orders on the cycle day only, at most two, so any other order, or an order outside the window, departs from the rules. The note names each departure, and the departures register in the Method view's Log, ⟦departures⟧, keeps it with its consequence.

### ⟦#lookthrough⟧ Look-through

The Look-through part shows what the portfolio owns through its two ETFs, in three sections: the equity sleeve, the bond sleeve and the whole portfolio. The risk of the whole portfolio, estimated at the look-through weights, opens the Risk view. Each holding is weighted by its weight in its ETF and by the ETF's weight in the portfolio, so the shares add up across the two sleeves. The "as of" line of each exhibit gives two dates, that of the issuer's holdings file and that of the sleeve weights.

### ⟦#lookthrough-equity⟧ Equity sleeve

The first section covers the equity sleeve, the iShares MSCI ACWI UCITS ETF, and its heading gives the sleeve's share of the portfolio on the record's date. iShares publishes the fund's holdings every day, so the holdings and the weights share a date. Every figure in this section gives shares of the whole portfolio, and its table adds the shares of the sleeve.

### ⟦c11a⟧ Equity by region

⟦c11a⟧ groups the equity holdings into MSCI's regions under its market classification: North America, Europe and the Middle East, the Pacific and emerging markets, with the fund's cash and derivatives on their own. Each bar is a region's share of the portfolio. The four regions are also the equity components of the risk estimates in ⟦c30⟧ to ⟦c32⟧.

### ⟦c11b⟧ Equity by country: the largest

⟦c11b⟧ gives the countries with the largest shares of the portfolio, by the location of each company as iShares reports it. Where the fund holds another iShares ETF that itself holds one market, that holding counts under its market, and the note names those markets.

### ⟦c12⟧ Equity by sector

⟦c12⟧ groups the equity holdings by sector under GICS, the industry classification that MSCI and S&P publish, as iShares reports it. The single-market ETFs that the fund holds have no single sector, so they form a bar of their own.

### ⟦c14⟧ The ten largest companies

⟦c14⟧ lists the ten companies with the largest shares of the portfolio, with the share classes of one company summed, so that a company with two listed classes of shares counts once. The title gives their combined share of the portfolio, which shows how much of it depends on ten companies.

### ⟦#lookthrough-bonds⟧ Bond sleeve

The second section covers the bond sleeve, the Vanguard EUR Eurozone Government Bond UCITS ETF, and its heading gives the sleeve's share of the portfolio. Vanguard publishes the fund's holdings and its factsheet once a month, so these exhibits are as of the last month end the issuer has published, while the sleeve weight is the record's.

### ⟦c15⟧ Bonds by issuing country

⟦c15⟧ groups the bonds by the government that issued them. Each bar is a country's share of the portfolio, and the table adds its share of the sleeve. The bars follow the size of each government's bond market in the fund's index, so they show which governments the portfolio lends to and in what proportion.

### ⟦c16⟧ Bonds by maturity, and duration

⟦c16⟧ groups the bonds by years to maturity, the time until each bond repays, measured from the date of the holdings file. Each bar is a group's share of the bond sleeve, and the grey bar is the cash the fund holds. A longer bond moves more when interest rates change, which the two tiles under the figure measure.

**Duration of the bond sleeve.** The duration is a bond's average time to its payments, weighted by their value, in years. It is also, approximately, the percentage fall in the bond's price when its yield rises by one percentage point. This tile gives the bond sleeve's average duration from Vanguard's factsheet, so a duration of 7 years means that a rise of one percentage point in yields would lower the sleeve's value by about 7 per cent.

**Duration contribution to the portfolio.** The sleeve weight times its duration: the same sensitivity to yields, measured for the whole portfolio.

### ⟦c17⟧ Credit quality of the bond sleeve

⟦c17⟧ gives the credit ratings of the bond sleeve as Vanguard's factsheet reports them, with each issue rated by the median of its Moody's, Fitch and S&P ratings. A rating grades the issuer's ability to repay, from AAA, the highest, down to BBB, the lowest grade still counted as investment grade. Each bar is a rating's share of the bond sleeve. The fund's index holds investment-grade bonds only, so no bar falls below BBB.

### ⟦#lookthrough-portfolio⟧ Whole portfolio

The third section puts both sleeves and cash together, for the one exposure that both sleeves carry: currency.

### ⟦c13⟧ Currency exposure, by sleeve

⟦c13⟧ gives the portfolio's exposure to each currency, each bar split by where the exposure comes from: navy from the equity sleeve, slate grey from the bond sleeve and a lighter grey from cash. Each holding counts in the currency of its market, as the issuers report it, so a US company's shares are an exposure to the US dollar whichever currency they were bought in. Buying the equity ETF in euro on Xetra therefore does not change the exposure. Currencies are named until the rest is below 10 per cent of the portfolio, and the rest is grouped as Other. The share outside the euro is the part of the portfolio whose value in euro moves with exchange rates.

### ⟦#factors⟧ Factor exposures

The Factor exposures part describes the equity ETF by its factors. A factor is one of the return series in Kenneth French's data library for developed markets: the market's return minus the risk-free rate, the one-month US Treasury bill return in French's files, and the returns of long-short portfolios for size, value, profitability, investment and momentum. A long-short portfolio holds one group of stocks and sells another short, so its return is the difference between the two groups: small companies against large ones for size, companies whose shares are cheap relative to their accounting value against expensive ones for value, profitable against unprofitable ones for profitability, companies that invest little against those that invest heavily for investment, and recent winners against recent losers for momentum.

A loading is the coefficient of the ETF's return minus the risk-free rate on a factor's return, which says how far the ETF moves when the factor moves by one. A fund that holds the market at market weights should load close to 1 on the market and close to 0 on the other five factors.

### ⟦c18⟧ Factor loadings of the equity ETF

⟦c18⟧ gives the ETF's loading on each factor, estimated on weekly returns over the last three years. A standard error is the estimated standard deviation of an estimate, and each loading carries a horizontal line of two standard errors on either side, so a loading whose line crosses zero cannot be told apart from zero. Weeks run from Wednesday to Wednesday, to avoid effects at the start and the end of a week. The regression uses the ETF's net asset value in US dollars and French's factors, also in US dollars, so no exchange rate enters it, and its standard errors are Newey-West, which allow for returns that are correlated from one week to the next.

The table adds a daily estimate as a check, with each factor's return of the same day and of the day before (Dimson's correction), since the fund's valuation point and French's daily returns may not be timed alike. The bond sleeve is not regressed on equity factors. A market loading close to 1 and small loadings on the rest describe a fund that holds the market at its weights, which is what the equity sleeve is meant to be.

### ⟦c19⟧ Rolling loadings

⟦c19⟧ repeats the estimate over rolling windows of 36 months of weekly returns, stepped at each month end, in one panel per factor, so that a reader can see whether the loadings have stayed stable. The five panels after the market share one scale, so their lines can be compared directly, and each has a line at zero. Small movements are expected, since 36 months of returns estimate a loading with error. A lasting move away from zero would indicate that the index itself had shifted towards a factor.

### ⟦c20⟧ Where the difference to the index blend came from

⟦c20⟧ will split the portfolio's monthly return against the index blend into its factor exposures times the factors' returns, and a residual. It starts at the October 2027 month end, when twelve months of returns exist, and until then it holds a line saying so.

### ⟦attribution⟧ The difference to the index blend in three parts

⟦attribution⟧ will split the difference between the portfolio and the index blend into three parts that sum to it, over the period of ⟦c20⟧: the portfolio against reference portfolio A, which is the implementation cost, the drift effect, which is reference portfolio A against reference portfolio B, and the tracking difference of the two ETFs. It starts at the October 2027 month end as well.

## ⟦view:risk⟧ Risk

The Risk view answers how far the portfolio could fall. Its first part estimates the risk of the whole portfolio at today's weights on index returns, and its second, Simulations, applies the rules to the allocation test's history and to paths resampled from it. None of its figures is the portfolio's record.

### ⟦#lookthrough-risk-section⟧ Risk of the whole portfolio

This part estimates the risk of the whole portfolio at its look-through weights. The record is too short to measure risk, so the estimates use index returns over the last 120 months. These index returns price the components, the parts into which the look-through divides the portfolio: MSCI's regional indices in euro for the four equity regions, and three maturity groups of the bond sleeve, each priced as a zero-coupon euro area government bond from the European Central Bank's yield curve. Cash is a component with no return. None of the estimates is part of the record, and none is a limit, since the mandate binds on the worst fall over years.

### The risk tiles

Seven tiles give the risk estimates, each with its basis in the line under it.

**Estimated volatility.** The standard deviation of the portfolio's return over a year, estimated from the components' monthly returns over the last 120 months, at the latest look-through weights.

**Estimated worst fall over ten years.** The median worst fall over ten years in the bootstrap of the allocation test (⟦c25⟧), at the split nearest the equity weight on the record's date. The line under it adds the 95th percentile, the fall exceeded in one path in twenty.

**The forecast's calibration.** The standard deviation, over the months that have a forecast, of each month's return divided by the volatility estimated for it at the end of the month before. A value of 1 means that the estimates matched the returns, and a value above 1 that they were too low. It needs twelve months of returns, so it starts at the October 2027 month end. Every estimate is kept as first written, in `outputs/ex_ante_risk.csv`, so it cannot be revised after the event.

**Value at risk, historical.** The loss over one month that the portfolio, at its weights on the record's date, exceeded in one month in twenty of the 120-month window: the sixth worst of the 120 months.

**Expected shortfall, historical.** The mean loss of those six worst months, which says how large a loss is once the value at risk is passed.

**Value at risk, normal.** The same loss read from the normal distribution with the estimated volatility and a mean of zero: 1.645 times the monthly volatility.

**Expected shortfall, normal.** The normal distribution's mean loss beyond that value at risk.

The historical figures depend on which crises the 120-month window holds, and the note under the tiles names them. ⟦stress⟧ adds the older crises. Each month end's value at risk is kept as first written, so that the months in which the loss passed it can be counted against the one in twenty expected. Twelve months give that count almost no power, and it starts to say something at about sixty.

### ⟦c30⟧ Correlation of the components' monthly returns

⟦c30⟧ gives the correlation of the monthly returns of each pair of components over the 120-month window. Each cell of the grid prints the correlation of its row and its column, coloured from blue for negative through white to red for positive. The table gives each component's weight, its volatility a year and the series that prices it. MSCI publishes no series for Europe and the Middle East together, so that region is priced by MSCI Europe, and the note says so.

The grid shows where diversification comes from. The equity regions tend to move together, and the correlation between equity and bonds decides how much the bond sleeve offsets a fall in equity.

### ⟦c31⟧ Each component's share of the estimated variance

⟦c31⟧ sets each component's share of the portfolio's estimated risk beside its weight. The variance is the volatility squared, and a component's risk contribution is its weight times the covariance of its return with the portfolio's return (how far the two move together, in the units of variance), divided by the portfolio's variance, so the contributions sum to 100 per cent. The pale bars are the weights and the navy bars the risk contributions. Equity is far more volatile than government bonds, so its share of the risk is larger than its share of the weight, and the note gives the two shares for the equity regions and for the maturity groups.

### ⟦c32⟧ The efficient frontier of the components, and the portfolio's point

⟦c32⟧ places the portfolio among the portfolios that could be built from the components. The efficient frontier is the set of long-only, fully invested portfolios of the components with the lowest estimated volatility for each estimated return. The horizontal axis is the estimated volatility and the vertical axis the estimated return, both in per cent a year. The dark grey curve is the frontier of the 120-month window and the light grey curve that of the 120 months before it. The open circle is the minimum-variance portfolio, the portfolio on the frontier with the lowest estimated volatility, and the navy dot is the portfolio at its look-through weights.

The portfolio's point lies away from the curve because its two ETFs are cap-weighted, that is, they hold each security in proportion to its market value, and no optimiser chose the weights. The distance from the curve is how far the cap weights sat from the frontier estimated on that window. It is no cost that the portfolio paid, since the frontier rests on the window's own estimated mean returns, the least reliable input, and the two curves show how far it moves from one window to the next. The Method view's section on [what the portfolio does not do](#method-not-done) explains why the rules do not follow the curve.

### ⟦stress⟧ Today's portfolio in five historical episodes

⟦stress⟧ estimates what the portfolio, at its weights on the record's date, would have lost in five historical crises: 2000 to 2003, 2007 to 2009, the euro crisis of 2011, February to March 2020, and 2022. Each episode holds today's look-through weights from the end of its first month to the end of its last, without rebalancing, so the two sleeves' contributions add up to the total. The table gives each sleeve's part in per cent of the portfolio, the episode's month ends and the series used. The components' series start in 2001 and 2004, so the fall of 2000 to 2003 uses the allocation test's two series at the sleeve weights. These are estimates on index returns at today's weights and form no part of the record, and month-end values miss falls that reverse within a month.

### ⟦#simulations⟧ Simulations

The Simulations part applies the rules to the allocation test's returns and to paths resampled from them, to show how the rules behave over a longer history than the record. Every chart in it is a simulation on index returns, gross of costs, and none is the portfolio's record.

### ⟦#simulations-mechanics⟧ Mechanics simulation

The first section shows how often the rules act. It runs them on the allocation test's returns with a starting amount of 100 and a top-up of 5 a month, with the cycle at each month end in place of the 5th.

### ⟦c26⟧ Simulation: the equity weight in its band under the rules

⟦c26⟧ follows the equity weight at each month end from February 1999 to December 2025, before the top-up, with the band and the target. Each top-up buys the sleeve furthest below its target weight, and the band brings the portfolio back to 70/30 when the weight leaves it. The red diamonds mark the months with a band order. The table counts the cycle days with one and with two orders and the band orders, and gives the most orders on one cycle day against the allowance of five. Every purchase counts as an order, whatever its size.

### ⟦#simulations-history⟧ Historical simulation

The second section runs the whole history as one path, from February 1999 to December 2025.

### ⟦c27a⟧ Simulation: growth of 100 under the rules

⟦c27a⟧ compares the growth of 100 under the rules, the navy line, with the same portfolio taken back to 70/30 on every cycle day, the grey line, with contributions removed. The gap between them is the drift effect over 27 years of history. The simulation is in-sample, that is, computed on the data on which the split was chosen, and its index series run back before the two ETFs existed. The table gives the year ends, and the months are in the source file.

### ⟦c27b⟧ Simulation: fall from the previous peak under the rules

⟦c27b⟧ shows the same two simulations as falls below the previous peak, month by month, with the test limit of 35 per cent and the outer bound of 40 per cent.

### ⟦#simulations-paths⟧ Resampled paths

The third section carries the bootstrap's paths forward from the first purchase.

### ⟦c28⟧ Resampled paths of the portfolio's value over ten years

⟦c28⟧ shows the range of values the portfolio could reach over ten years from the first purchase if the future repeated the test's history, reshuffled in twelve-month blocks. Values are in units of the starting amount, with the top-up of 5 a month and the rules applied at each month end. The pale band holds the middle 90 per cent of the 10,000 paths, from the 5th to the 95th percentile, the darker band the middle half, and the grey line is the median. The dashed line is the money paid in, and the navy line, from the first month end, is the record itself.

The bands say what the test's sample implies and assume nothing beyond it. The record's place inside the range says where markets have taken it and is no evidence about the rules, which a record of this length cannot give. A record below the lower band is a question for the review of the rules in October 2027.

## ⟦view:method⟧ Method

The Method view answers how the portfolio was set up: how the split and the two ETFs were chosen and what the portfolio does not do, with the data sources, the controls and the rules. It then holds the terms the dashboard uses and the Log, the written record of each quarter and month. Its exhibits use history, and each says which history.

### ⟦c21⟧ The allocation test: growth per year against the worst fall of each split, on the global and the US equity series

⟦c21⟧ shows how the split was chosen. The allocation test, in `mandate/allocation_check.py`, runs every split from 40/60 to 100/0, in steps of five points, through monthly euro returns from February 1999 to December 2025. The equity series combines Kenneth French's developed-market and emerging-market returns, 90 and 10 per cent, converted to euro, and the bond series is a seven-year euro area government bond priced from the European Central Bank's yields. Each split is rebalanced by its band, and for each the test measures the growth per year and the worst fall.

Each grey dot is a split, placed by its worst fall on the horizontal axis and its growth per year on the vertical axis, and the curve joins the splits from 40/60 to 100/0. The navy dot is 70/30, the split held, and the red lines are the risk limit of 35 per cent and the outer bound of 40 per cent. The mandate's rule is the largest equity target weight whose worst fall stayed within 35 per cent, and on this history that is 70/30, with a worst fall of 34.7 per cent from August 2000 to March 2003. With two assets every split lies on this one curve, so the limit picks the point and no estimate of future returns enters. The test is in-sample, that is, computed on the data on which the choice was made: the split was chosen on the returns the chart shows.

The teal curve repeats the test with the US stock market in euro in place of the global equity series, with the same bonds, band rule, splits and months, and its 70/30 point is marked as well. On this history the US series grew more per year at every split, and fell further at every split from 60/40 to 100/0. The split was set on the global series alone.

### ⟦c25⟧ Simulated worst fall of each split over resampled ten-year paths

⟦c25⟧ asks how often each split could fall more than the limit over ten years if the test's history were reshuffled. The bootstrap, a resampling of the allocation test's returns, builds 10,000 paths of ten years, each joining blocks of twelve consecutive months that start at random months, and applies the band at each month end. A block keeps its twelve months in their order, so a fall and the correlation of the two sleeves within a year stay as they happened.

For each split, a line runs from the median worst fall over the paths, a filled dot, to the 95th percentile, an open circle, which is the fall exceeded in one path in twenty. The black diamond is the allocation test's single historical path, 70/30 is in navy, and the red lines are 35 and 40 per cent. The note gives how often 70/30 and 60/40 fall more than 35 per cent, and the table adds paths of five years and blocks of 6, 24 and 36 months. The paths reuse the same returns, so they say nothing about years unlike those, and the split was chosen on this sample. The results are an input to the review of the rules in October 2027 and change no rule.

### ⟦c29⟧ Rolling 36-month correlation of the two sleeves' monthly returns

⟦c29⟧ follows the correlation between the returns of equity and of bonds over rolling windows of 36 months. The grey line uses the allocation test's index series from 1999, and the navy line the two ETFs' net asset values from March 2019, the first full month of the bond ETF's share class. A negative correlation means that bonds tended to rise when equity fell, which keeps the worst fall of a 70/30 portfolio below that of equity alone. The years in which the line turned positive are the ones in which bonds did not offset the falls of equity. The test's worst fall and the bootstrap's bands rest on this correlation, which the block resampling keeps within each block.

### ⟦#method-not-done⟧ What the portfolio does not do, and why

This section answers the questions readers ask of a portfolio like this one: why it has no optimiser, what its benchmark is and why it does not hold the S&P 500 alone, why it takes no views and why it follows no signal. It changes no rule. Each answer is a paragraph with a run-in label, the values in the text are computed from the repository's files, and two figures sit inside the section.

**No optimiser.** An optimiser chooses weights from estimates of each asset's expected return and risk. The section compares the standard error of the equity series' mean yearly return with the difference in growth per year between the 40/60 and the 100/0 split, and the two are of the same size, so the data cannot tell the splits apart by their returns. It cites the study of DeMiguel, Garlappi and Uppal (2009) on how much history an optimiser needs, and a replication of it.

**The benchmark, and why not the S&P 500.** A benchmark is the portfolio a client would hold without a manager, against which the manager's contribution is measured. This portfolio's benchmark is the blend of its two funds' own indices at 70/30, rebalanced at each month end, the policy its rules implement. The rules take no position against it, so the difference to it is the cost of implementing that policy, and the two reference portfolios split that difference into its parts. No single market index is the benchmark. The S&P 500 holds US companies only, which the global fund already holds at about two thirds of its weight, so holding the index alone puts the whole portfolio into one country and one currency.

**No views and no signal.** A view is a statement that an asset's expected return differs from what its price implies, and a signal is a view produced by a rule and tested on history. The rules take neither, and a signal could enter only through the yearly review of the rules, with its test fixed in advance.

The section's notes, numbered from 1, give the full reference for each source with a link.

### ⟦c33⟧ The allocation test on the US stock market

⟦c33⟧ repeats the allocation test with the US stock market in euro in place of the global equity series, with the same bonds, the same band rule, the same splits and the same months. For each split, the upper bar is the global series, as in ⟦c21⟧, with 70/30 in navy and the other splits in grey, and the lower bar, in teal, is the US series. The red lines are 35 and 40 per cent, and the table gives both series' worst falls, their growth per year and whether each split stayed within 35 per cent.

The split was set on the global series alone, so this figure chooses nothing. It shows how a single-country equity sleeve would have fared under the same limit, and the section's second paragraph gives the largest US split within 35 per cent and the US worst fall at 70/30.

### ⟦c34⟧ Growth of 100: reference portfolio A and the S&P 500 alternative

⟦c34⟧ shows the S&P 500 alternative beside reference portfolio A, each as a growth of 100 since the first purchase. The S&P 500 alternative is the same contributions on the same days in one S&P 500 ETF at its net asset value in euro, in fractional units and without costs, starting as reference portfolio A starts. Its fund is the S&P 500 ETF that the rules' own selection criteria pick, named in the caption and ranked in `method/selection_sp500.csv`. The dark grey line is reference portfolio A, the teal line is the alternative, and the table gives the gap between them in points of the growth of 100, with its sign.

Both lines are rule sets without costs, so the comparison is like for like, and the portfolio's own line is left off because reference portfolio A stands for it. The difference between the portfolio and reference portfolio A is the implementation cost, shown under Costs in the Performance view. A record of months is far too short for the gap to say anything about either rule set, which is the same limit that applies to every return on the dashboard.

### ⟦history⟧ The same effects on 1999 to 2025

The pane "The same effects on 1999 to 2025" runs the split and the dollar effects of the Comparisons part on history. It is history and in-sample: the allocation test's own monthly euro series from February 1999 to December 2025, with no contributions and no costs, each split rebalanced by its band at month ends. 70/30 stands against three comparators: 100/0 and 60/40 on the global series, and the US stock market at 70/30, the test's US run, with the same bonds and the same band and the US stock market in place of the global equity series, so that the choice of region is kept apart from the choice of split.

⟦history⟧ gives one block of rows per comparator: first the whole test and the two periods already used in the Method view, 2000 to 2009 and 2010 to 2024, then each calendar year. Split and the dollar are defined as on the record, from the equity weights at the previous month end. For the US stock market at 70/30 a third effect, the US stock market in dollars, is its equity weight times the US market's return in dollars less the global series'. Calendar years are in points, and the longer spans in points a year: the difference of the two growth rates per year, with each effect divided by the span's years. Over a decade, effects summed month by month leave a large remainder when they are set against cumulative returns, and the figures per year keep that remainder, compounding, small. Each row carries the comparator's volatility and worst fall within the span and the band chance alone produces, from one tracking error per comparator over the whole test.

### ⟦history-windows⟧ The difference per year over rolling ten-year windows

⟦history-windows⟧ shows, for each comparator, its growth per year minus 70/30's over each window of ten calendar years, from 2000 to 2009 to 2016 to 2025, plotted at the window's last year. The 17 windows overlap, so the chart smooths the same 26 full years and adds no evidence. Its table gives each window's effects per year, the comparator's volatility and worst fall, and the band.

### ⟦c22⟧ The ETF selection: tracking difference by fund and year

⟦c22⟧ shows how the two ETFs were chosen. For each sleeve the funds that meet the criteria of the rules, such as the index tracked, the costs and the fund size, are ranked in an order fixed before they were compared. Equity ETFs rank first by Irish domicile, which lowers the tax the fund pays on US dividends, then by the highest average tracking difference over 2023 to 2025, then by the lowest TER. Bond ETFs rank by the highest average tracking difference, then by the lowest TER. The tracking difference is a fund's calendar-year return minus its index's return, from the issuers' factsheets, so a higher figure means a smaller shortfall against the index.

Each row is a fund, numbered in rank order, and each mark is one calendar year: a circle for 2023, a square for 2024 and a diamond for 2025. The short vertical bar is the three-year average. The held funds are in navy and the others in grey, and hollow marks are funds the account does not offer. The held fund of each sleeve is the first in rank order that the account offers, and the table gives every value, the factsheet dates and which funds are offered and held.

### ⟦sources⟧ Data sources

⟦sources⟧ lists every source the program reads, with the last date each one covers and the day it was downloaded: the issuers' net asset values, holdings, factsheets and key information documents, the European Central Bank's exchange rate and yield curve, MSCI's index levels and Kenneth French's factors. Every source is downloaded when the dashboard is built, cached locally and not redistributed, and only the figures computed from it are published.

### ⟦controls⟧ Controls

⟦controls⟧ lists the checks on the record, each with how often it runs and where its evidence is: the ledger against the broker's statements each month, the ledger against rules 7 and 10 at each build, the cycle report written before the orders, the departures register, the test that no private value appears in a public file, the fingerprint of the private values, the checks on the public text, and the rebuild of the page from the committed tables.

### ⟦#method-rules⟧ The rules

The rules card shows `rules/RULES.md`, the ten rules as fixed before the first order and tagged `rules-v1.0`, with its table of amendments. Rule 1 sets the target weights of 70 and 30 per cent and rule 2 the starting amount and the top-up. Rule 3 sets the cycle day, rule 4 how the top-up rebalances and rule 5 the band. Rule 6 sets the allowance of five orders a month and rule 7 the window for orders and what the ledger records for each. Rule 8 forbids any order outside the rules, so news adds no purchase and a fall in prices does not pause the cycle. Rule 9 sets how a rule changes, by a dated amendment that applies from the first cycle day at least 30 days after its commit, with the first review in October 2027, and rule 10 how a sale is recorded. The card also explains how the two ETFs were chosen and how the private euro amounts are fixed by a fingerprint without being published.

### ⟦#method-projects⟧ Other projects

The card after the rules links to the author's other investment research projects, each with its page, its dashboard or note, and its code.

### ⟦#glossary⟧ Terms

The Terms part lists every term the dashboard uses in a sense of its own, with its definition. The same list closes this guide.

### ⟦#log⟧ Log

The Log keeps the written record of each quarter and month in five sections, newest first: the quarterly reports, the monthly notes, the cycle reports, the departures register and the monthly table.

### ⟦#log-quarterly⟧ Quarterly reports

One report covers each quarter. Each report is a page, with a PDF printed from it, built once from the tables of the commit it names and never rebuilt, so it stays as issued while the dashboard moves on. A correction goes into the next issue as an erratum. The first report covers 8 October to 31 December 2026 and is published after the cycle day of 5 January 2027.

### ⟦#log-notes⟧ Monthly notes

After each cycle day a note of 120 to 200 words, written by hand, says what happened and why. Its first line gives the cycle day, and a line of figures written by the program gives the day the top-up was recorded, the equity weight before and after the cycle day, whether the band was triggered, the orders placed against those proposed, the implementation cost of the month before and any departure from the rules.

### ⟦#log-cycles⟧ Cycle reports

On each cycle day, before any order, the program writes the cycle report: each rule that bears on the proposed orders, its figure and a pass or a fail, and the orders proposed. After the orders, one line compares what was placed with what was proposed, and under each report the dashboard lists that day's orders as the record holds them.

### ⟦departures⟧ ⟦#log-departures⟧ Departures register

⟦departures⟧ lists every departure from the rules since the first purchase, that is, every order placed, or left unplaced, other than as the rules require. Each row gives the date, the rule, what happened and its consequence. A departure stays in the record as it happened and is never corrected after the event.

### ⟦c24⟧ ⟦#log-table⟧ The monthly table

⟦c24⟧ holds every figure behind the key figures and charts, by month, in three blocks. The first block gives returns and risk: the month's return, the time-weighted return since the first purchase, the money-weighted return, cumulative and per year, the drawdown, the worst fall to date and, from the twelfth month, the volatility of the last twelve monthly returns. The second gives the weights at the month end, the drift, the orders, the money paid in and the value in units, and the market effect and the contribution. The third gives the costs in basis points: commissions, half-spread, the price paid against net asset value, and the implementation cost of the month and cumulative. Every key figure is a cell of these tables or of `outputs/portfolio_daily.csv`, except that the orders figure also counts orders placed after the last net asset values.
