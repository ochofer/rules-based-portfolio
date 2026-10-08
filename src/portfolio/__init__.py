"""The program that keeps the record of the rules-based portfolio.

Pipeline, each step a function with a file in and a file out:
  1. positions.build: the ledger to units and cash by day
  2. valuations.build: units, cash and net asset values to values and weights by day
  3. metrics (to follow): values to the published shares, percentages and basis points
  4. site and report (to follow): metrics to the dashboard and the monthly report

The cycle command (python3 -m portfolio cycle) runs steps 1 and 2 to the last close and prints the
orders rules 4 to 6 produce on a cycle day.
"""

__version__ = "0.1.0"
