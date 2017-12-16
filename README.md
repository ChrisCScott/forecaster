# forecaster
A financial forecasting tool for Canadians planning retirement.

This is a let's-learn-Python project. It targets Python 3.6. It's based
on a financial forecasting Excel spreadsheet, which provides the basic
math and important constants (elgibility ages, benefit rates, etc.) so
that development can focus on implementation. The data model has been
reworked for the Python implementation and is not a direct port of the
Excel table structure.

The Excel sheet was terribly inefficient for Monte Carlo simulations, so
one of the goals of the software is to implement these at least somewhat
efficiently.

The GitHub repo has a list of milestones that provides a high-level
overview of each version's functionality.
