# forecaster
A financial forecasting tool for Canadians planning retirement.

## Functionality
The project is designed as a library for use by client code.
It provides a `Forecaster` object which generates `Forecast`
objects based on some set of strategies (e.g. for determining
living expenses, debt repayment, contributions and withdrawals,
etc.), assumptions about future market returns, and some
`Person` and `Account` objects representing the plannees and
their assets and debts. The end result is that you can track
the plannees' financial picture from year-to-year at low- or
high-resolution (e.g. net worth vs. specific account balances).

The top-level modules are all generic and designed to be extensible
and country-agnostic. For example, Canadian functionality is carved
out into a subpackage to show how to extend the code via subclasses.
Other countries can be added by client code in the same way.

## Background
This is a let's-learn-Python project. It targets Python 3.7. For the
most part, it adheres to Google's Python style guide and uses pylint
to keep it that way. (The big exception is its use of certain "power
features", such metaclasses, which are too fun not to use.) Along
with learning Python, one of the goals is learning best practices, so
it also aims to provide extensive comments and tests, provide
informative commit messages, and just generally maintain a tidy
little package of nicely-documented code.

This project is grew out of an Excel spreadsheet. Most of the relevant
financial concepts are taken from there (e.g. elgibility ages, benefit
rates, tax rates, etc.), but the design of the Python project is
all-new. The Excel sheet was terribly inefficient for Monte Carlo
simulations, so one of the goals of the software is to implement these
at least somewhat efficiently.

## Future Objectives
As noted above, enabling efficient Monte Carlo simulations (across
many simulated futures and/or backtesting to historic data) is an
eventual goal. Providing a basic UI (e.g. a web UI) is also on the
roadmap - although that might wind up being an entirely new package!

In the meantime, though, the goal is to provide a minimally-functional
working implementation and then expand it version-after-version until
it reaches feature parity with the original Excel spreadsheet.
("Parity" might be the wrong term - the package already does lots of
things that the spreadsheet didn't do, but the goal is to make this
package's functionality a strict superset of the spreadsheet's.)

## More Reading
The GitHub repo has a list of milestones that provides a high-level
overview of each version's functionality. There's also a ReadTheDocs
instance with documentation (generated with sphinx-apidocs).
