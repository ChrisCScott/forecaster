""" Provides classes for determining the total sum of transactions. """

from forecaster.strategy.base import Strategy, strategy_method
from forecaster.utility.precision import (
    HighPrecisionOptionalPropertyCached, HighPrecisionOptional)


class LivingExpensesStrategy(Strategy, HighPrecisionOptional):
    """ Determines annual living expenses.

    This class is callable. Its call signature has this form::

        obj(year, refund, other_contribution, net_income, gross_income)

    Arguments may be omitted if the selected strategy does not require
    it; otherwise, an error is raised. All arguments are keyword
    arguments.

    Attributes:
        strategy (str): A string corresponding to a particular
            contribution strategy. See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            gross_contribution(). See its documentation for more info.

            Acceptable keys include:

            * "Constant contribution"
            * "Constant living expenses"
            * "Percentage of gross income"
            * "Percentage of net income"
            * "Percentage of principal at retirement"
            * "Percentage of gross income at retirement"
            * "Percentage of net income at retirement"

        base_amount (Money): A user-supplied amount of money, used in
            some strategies as a baseline for contributions.
        rate (float): A user-supplied contribution rate. Must be a
            percentage (e.g. float('0.03') means 3%).
        inflation_adjust (callable): If provided, `base_amount` is
            interpreted as a real (i.e. inflation-adjusted) currency
            value.

            This callable object will be called as
            `inflation_adjust(year[, base_year])` to receive the
            inflation-adjustment factor between real and nominal values
            for that year (relative to base_year, if provided).

            Optional. If not provided, `base_amount` is not
            inflation_adjusted.

    Args:
        people (set[Person]): The plannees (one or more people) with
            at least `net_income` and `gross_income` attributes.

    Returns:
        A Money object corresponding to the living expenses incurred
        by the plannees for the year.

    Raises:
        ValueError: A required value was not provided for the given
            strategy.
    """

    # These properties can be floats or a high-precision type:
    base_amount = HighPrecisionOptionalPropertyCached()
    rate = HighPrecisionOptionalPropertyCached()

    def __init__(
            self, strategy, base_amount=0, rate=0, inflation_adjust=None):
        """ Constructor for LivingExpensesStrategy. """
        super().__init__(strategy)

        self.base_amount = base_amount # Money value
        self.rate = rate

        # If no inflation_adjustment is specified, create a default
        # value so that methods don't need to test for None
        if inflation_adjust is not None:
            self.inflation_adjust = inflation_adjust
        else:
            self.inflation_adjust = lambda *args, **kwargs: 1

        # Types are enforced by explicit conversion; no need to check.

    # These methods all have the same signature, though they don't
    # all use every argument. Accordingly, some unused arguments are
    # to be expected.
    # pylint: disable=unused-argument

    # Begin defining subclass-specific strategies
    @strategy_method('Constant contribution')
    def strategy_const_contribution(self, people, *args, year=None, **kwargs):
        """ Contribute a constant (real) amount and live off the rest. """
        total_income = sum(person.net_income for person in people)
        contributions = (
            self.base_amount * self.inflation_adjust(year)) # Money value
        return total_income - contributions

    @strategy_method('Constant living expenses')
    def strategy_const_living_expenses(self, *args, year=None, **kwargs):
        """ Living expenses remain constant, in real terms. """
        return self.base_amount * self.inflation_adjust(year) # Money value

    @strategy_method('Percentage of net income')
    def strategy_net_percent(self, people, *args, **kwargs):
        """ Live off a percentage of net income. """
        return self.rate * sum(person.net_income for person in people)

    @strategy_method('Percentage of gross income')
    def strategy_gross_percent(self, people, *args, **kwargs):
        """ Live off a percentage of gross income. """
        return self.rate * sum(person.gross_income for person in people)

    @strategy_method('Percentage of earnings growth')
    def strategy_percent_over_base(self, people, *args, year=None, **kwargs):
        """ Live off a base amount plus a percentage of earnings above it. """
        base_amount = self.base_amount * self.inflation_adjust(year)
        total_income = sum(person.net_income for person in people)
        return base_amount + (total_income - base_amount) * self.rate

    @strategy_method('Percentage of principal at retirement')
    def strategy_principal_percent_ret(
            self, accounts, retirement_year, *args, year=None, **kwargs):
        """ Withdraw a percentage of principal (as of retirement). """
        retirement_balance = sum(
            account.balance_history[retirement_year] for account in accounts)
        return (
            self.rate * retirement_balance
            * self.inflation_adjust(year, retirement_year))

    @strategy_method('Percentage of net income at retirement')
    def strategy_net_percent_ret(
            self, people, retirement_year, *args, year=None, **kwargs):
        """ Withdraw a percentage of max. net income (as of retirement). """
        retirement_income = sum(
            person.net_income_history[retirement_year] for person in people)
        return (
            self.rate * retirement_income
            * self.inflation_adjust(year, retirement_year))

    @strategy_method('Percentage of gross income at retirement')
    def strategy_gross_percent_ret(
            self, people, retirement_year, *args, year=None, **kwargs):
        """ Withdraw a percentage of gross income. """
        retirement_income = sum(
            person.gross_income_history[retirement_year] for person in people)
        return (
            self.rate * retirement_income
            * self.inflation_adjust(year, retirement_year))

    # pylint: enable=unused-argument

    def __call__(
            self, *args,
            people=None, year=None, retirement_year=None, **kwargs):
        """ Returns the living expenses for the year. """
        # Collect the accounts owned by `people` into a flat
        # `set[Account]` object:
        if people is not None:
            accounts = set.union(*[person.accounts for person in people])
        else:
            accounts = None
        # Determine how much to spend on living expenses:
        living_expenses = super().__call__(
            people=people, year=year,
            accounts=accounts,
            retirement_year=retirement_year,
            *args, **kwargs)
        # Ensure we return non-negative value:
        return max(
            living_expenses,
            0) # Money value


class LivingExpensesStrategySchedule(object):
    """ Determines living expenses while working and retired.

    This class is callable, like `LivingExpensesStrategy`, and
    accepts all of the same arguments when called.

    Objects of this class wrap `LivingExpensesStrategy`
    objects - one for working life and one for retirement.
    The appropriate object is called depending on the current
    year.

    An additional `LivingExpensesStrategy` may also, optionally,
    be provided as a minimum level of expenses. This lets you
    avoid perverse situations where annual fluctuations in
    income or assets reduce living expenses unacceptably low.

    Attributes:
        working (LivingExpensesStrategy): The strategy to use
            during the plannees' working life.
        retirement (LivingExpensesStrategy): The strategy to
            use during the plannees' retirement.
        minimum (LivingExpensesStrategy): Provides a minimum
            living standard that must be met. Optional. May
            be a `LivingExpensesStrategySchedule` if you want
            to use different minima for working and retired
            phases of life.

    Args:
        year (int): The current year.
        retirement_year (int): The plannees' retirement year.
            Optional; if not provided, it's assumed that the
            plannees are still working.

    Returns:
        A Money object corresponding to the living expenses incurred
        by the plannees for the year.

    Raises:
        ValueError: A required value was not provided for the given
            strategy.
    """

    def __init__(self, working, retirement, minimum=None):
        """ Inits LivingExpensesStrategySchedule. """
        self.working = working
        self.retirement = retirement
        self.minimum = minimum

    def __call__(self, *args, year=None, retirement_year=None, **kwargs):
        """ Returns the living expenses for the year. """
        # First determine whether we're using the working
        # or retirement living expenses formula:
        if (
                year is not None
                and retirement_year is not None
                and year > retirement_year):
            living_expenses = self.retirement(
                year=year, retirement_year=retirement_year,
                *args, **kwargs)
        else:
            living_expenses = self.working(
                year=year, retirement_year=retirement_year,
                *args, **kwargs)

        # Then, if there's a minimum living expenses formula,
        # ensure that we meet at least that:
        if self.minimum is not None:
            minimum = self.minimum(
                year=year, retirement_year=retirement_year,
                *args, **kwargs)
            return max(living_expenses, minimum)
        else:
            return living_expenses
