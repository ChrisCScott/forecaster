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

## Version Roadmap
### Version 0.1
A basic working implementation of Forecast and its various supporting
classes (Account, Person, Tax, Strategy, Scenario, and subclasses) such
that a Forecast can be prepared with some initial conditions and can
iterate toward an end state. Employment income, savings contributions,
debt repayment, investment growth, withdrawal strategies, and tax
treatment should all behave correctly (following any applicable
application-level settings) so that the growth and drawing down of
retirement assets accurately reflect a simple financial model.

Other forms of income (pensions, government programs, asset sales, etc.)
are not implemented at this stage, nor are non-retirement savings (e.g.
education or health savings).

Retirement scenarios are straightforward: retirement dates are fixed and
known at the start of the forecast.

Only a programmatic interface is provided; a command-line interface or
GUI is out of scope.

### Version 0.2
Implement more sophisticated scenario management features, including:
* allowing users to provide input values for any year of the forecast
that override automatically-calculated projections,
* allowing for "floating" retirement dates, wherein retirement occurs
once certain criteria are met and strategies shift annually based on
current retirement age projections,
* implementing Monte Carlo simulation and basic statistical summaries.

### Version 0.3
Implement other forms of income, such as pensions and government
benefits.

### Version 0.4
Implement family-related features, such as education savings (including
RESPs for Canadian plannees), parental leave (including parental leave
benefits), and childcare.

### Version 0.5
Implement a basic GUI that supports user input of application-level
settings and time-series data. The GUI should show be able to show at
least the key values of projects (principle, contributions, withdrawals,
etc.) in tabular form.

The GUI should provide at least basic graphs illustrating statistical
information, such as account balances over time, net worth over time,
income sources over time, and standard of living over time.

### Version 1.0
Refine UX to not-horrible levels, "officially" release.

(This isn't a commercial project, so it's not clear what that even means
beyond not being embarassed if someone tries to use it.)
