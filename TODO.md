# TODO
This list sets out various changes or additions that are planned for the
next release version.

## High Priority
* `Forecast`: Implement basic tests for each unit of functionality.
* `Forecast`: Determine refunds and other contributions
* `Forecast`: Revise tax treatment to deal with insufficient tax
withheld (include a contribution reduction in the following year to pay
for taxes owing?)
* `Forecast`, `WithdrawalStrategy`, `Tax`: Provide means to increase
withdrawals based on tax liability (e.g. allow user to indicate whether
withdrawals are pre-tax or post-tax and, if the latter, provide a way to
determine how much must must be withdrawn to cover the existing tax
liability and any additional liability for the increased withdrawals).
* `TransactionStrategy`: Handle contribution groups (i.e. accounts that
share contribution room)
* `TransactionStrategy`: Handle the case where multiple objects of the
same type are given as input.
    * Ideally, treat them as one account and split transactions between
    them in a reasonable way (e.g. proportional to balance)

## Medium Priority
* `RRSP`: Inflation-adjust RRSP withholding tax rates (e.g. by changing
`RRSPWithholdingTaxRate` to a `{year: {bracket: rate}}` dict?)
* `Person`: Subclass `Person` into `CanadianResident`, override
`_tax_credit` to provide the spousal tax credit, and replace the
`tax_treatment` arg with a `province` (str) arg that's passed through to
`TaxCanada`.
* `Debt`: Allow user to specify maximum rate of accelerated debt
repayment (replace `accelerate_payment` with a `Money` arg that
defaults to `Money('Infinity')`, which should yield the same behaviour
as `accelerate_payment=True`?)
* `Forecaster`: Enable generation of statistics from `Forecast`
* `Forecast`: Improve `living_standard` calculation
* `RRSP`: Implement and test Spousal RRSPs (potentially as a subclass,
but with the current contributor/owner model that may not be necessary.)
* `Settings`: Read defaults from a file, fall back to hardcoded values
only where the .ini doesn't provide a value.

## Low Priority
* `Forecaster`: Reimplement code to provide generic logic for taking in
a mapping of `{type: {'argname': defaultval}}` and building objects
based on that mapping.
    * It might be necessary for defaultval to be a str-encoded input
    to `eval` so that we can accomodate things like `self.scenario`.
    * Consider whether we need to import operator.attrgetter to allow
    for dynamically resolving nested attributes (is this necessary?)
    * It will still be necessary to provide, e.g., an `add_account`
    method to ensure that the appropriate `assets` and `debts` objects
    are populated, but it may be practical to avoid the various
    `set_*_strategy` methods. (Have the methods return strategy objects
    and assign manually?)
* `Person`: Add `life_expectancy` and `estimated_retirement_date`
properties (methods?) and allow `retirement_date` to be `None` (or
perhaps return an estimated date).
    * This can be used with `AllocationStrategy` once it's being used by
    `Forecast`.
    * Add defaults for this value to `Settings`
* `Account`: Add `add_inflow` and `add_outflow` methods that wrap
`add_transaction` and handle sign so that users aren't tripped up?
* `RRSP`: Handle explicit RRIF conversion dates?
* `RRSP`: Handle implicit RRSP conversion dates (e.g. upon withdrawal)?
* `RRSP`: Reduce contribution room based on a pension adjustment?
* `Tax`: Implement pension credits and pension income splitting.
* `TaxableAccount`: Track asset allocation and apportion growth in the
account between capital gains, dividends, etc.
* `TaxableAccount`: Implement foreign withholding taxes and Canadian
dividend credit.
* `Scenario`: Memoize `accumulation_function` and/or `inflation_adjust`
(at least for `base_year=Settings.displayYear`?)
* `Strategy`: Add static class methods to `Strategy` to register or
unregister strategy methods? (e.g. using signature `(func [, key])`)
* `ContributionStrategy`: Reimplement strategy methods to take *_history
dict arguments for consistency with `WithdrawalStrategy`.
* `WithdrawalStrategy`: Add a setting that allows for reevaluating
withdrawal rates periodically (every 10 years?) rather than keeping them
constant based on the portfolio on the retirement date.
    * Consider adding as a flag to `__init__`
    (e.g. `reevaluate_freq=Decimal('Infinity')`)?
    * Re-implement `minimum_living_standard` (as it's more relevant in
    this context)?
* `AllocationStrategy`: Move `min_equity` and `max_equity` logic to
`__call__` to simplify the logic of each strategy.
* `AllocationStrategy`: Add strategy that rebalances based on current
withdrawal rate and portfolio balance.
* `Person`, `Forecast`: Make `Strategy` objects properties of `Person`,
thus allowing different people to follow different strategies.
