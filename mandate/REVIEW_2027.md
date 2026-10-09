# Review of the rules, October 2027

The first review of the rules is on the cycle day (the day each month on which the rules are applied) of October 2027, twelve months after version 1.0, and rule 9 allows no review before it. This agenda was written on 9 October 2026. It changes only by a dated addition at its end, and nothing above an addition is edited.

## The figures the review uses

1. The bootstrap of the allocation test: for each split, the share of ten-year paths whose worst fall is beyond 35 per cent and beyond 40 per cent, in `mandate/simulation_bootstrap.csv`, beside the allocation test in `mandate/allocation_check_results.csv`.
2. The orders of rule 5, placed when the equity weight is outside the band (65 to 75 per cent) on a cycle day, in the record's first twelve months, in `outputs/band_events.csv`, against the mechanics simulation in `mandate/simulation_history.csv`, which placed them on 5 of 323 cycle days on the test's returns.
3. The orders of each month against the allowance of five, in `outputs/orders.csv`, beside the mechanics simulation, which needed at most two orders on a cycle day.
4. The costs of the twelve months: the implementation cost in `outputs/implementation_cost.csv` and its sources by month in `outputs/costs_monthly.csv`, against the cost that the two ETFs' TERs, each at its target weight (70 and 30 per cent), and the half-spreads measured at the orders lead one to expect.
5. The ETF selection run again under the criteria and the ranking of `rules/RULES.md`, with the calendar years 2024 to 2026 in place of 2023 to 2025.
6. The departures register in `outputs/departures.csv`: each departure, its rule, and whether the rule's wording led to it.
7. The tax and residence facts that bear on holding the two ETFs, as they stand at the review.

## The questions it answers

1. Whether the risk limit stands: a worst fall of about one third, tested as 35 per cent, with the outer bound of 40 per cent.
2. Whether the band of 65 to 75 per cent for the equity weight stands.
3. Whether the allowance of five orders a month stands.
4. Whether the two ETFs stand, given the selection run again.
5. Whether a rule's wording needs an erratum or a reading, given the departures.

An answer that changes a rule is a dated amendment under rule 9, and it applies from the first cycle day at least 30 days after its commit.

## Additions

Each addition is dated, and the first is listed first.

- 9 October 2026. Figure 4 compares two different things, so it is read as two. (a) The implementation cost of the twelve months, in `outputs/implementation_cost.csv`, and its sources by month, in `outputs/costs_monthly.csv`, against what the half-spreads measured at the orders, the broker's commission schedule and the currency conversion lead one to expect. (b) The two ETFs' tracking difference against their TERs, which is the cost of owning them.
