"""The program that keeps the record of the rules-based portfolio.

Pipeline, each step a function with a file in and a file out:
  1. positions.build: the ledger to units and cash by day
  2. valuations.build: units, cash and net asset values to values and weights by day
  3. metrics, references, lookthrough, factors: values and the issuers' data to returns, costs, the
     reference portfolios, the look-through and the factor loadings; outputs.build writes them to outputs/
  4. site.build: outputs/ to the dashboard, index.html

The cycle command (python3 -m portfolio cycle) prints the orders rules 4 to 6 produce on a cycle day.
"""

__version__ = "0.2.0"
