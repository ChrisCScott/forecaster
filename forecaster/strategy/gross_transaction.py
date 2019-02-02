""" Provides classes for determining the total sum of transactions. """

from decimal import Decimal
from forecaster.ledger import Money
from forecaster.strategy.base import Strategy, strategy_method


class LivingExpensesStrategy(Strategy):
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

        base_amount (Money): A user-supplied amount of money, used in
            some strategies as a baseline for contributions.
        rate (Decimal): A user-supplied contribution rate. Must be a
            percentage (e.g. Decimal('0.03') means 3%).
        refund_reinvestment_rate (Decimal): The percentage of each tax
            refund that is reinvested in the year it's received.
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

    # pylint: disable=too-many-arguments
    # We need to pass the strategy's state variables at init time. There
    # are 6 of them (including self). Refactoring to use a dict or
    # similar would hurt readability.
    def __init__(
        self, strategy, base_amount=0, rate=0, refund_reinvestment_rate=1,
        inflation_adjust=None
    ):
        """ Constructor for ContributionStrategy. """
        super().__init__(strategy)

        self.base_amount = Money(base_amount)
        self.rate = Decimal(rate)
        self.refund_reinvestment_rate = Decimal(refund_reinvestment_rate)

        # If no inflation_adjustment is specified, create a default
        # value so that methods don't need to test for None
        if inflation_adjust is not None:
            self.inflation_adjust = inflation_adjust
        else:
            self.inflation_adjust = lambda *args, **kwargs: 1

        # Types are enforced by explicit conversion; no need to check.

    # Begin defining subclass-specific strategies
    # pylint: disable=W0613
    @strategy_method('Constant contribution')
    def strategy_const_contribution(self, people, year=None, *args, **kwargs):
        """ Contribute a constant amount (in real terms) and live off the rest. """
        total_income = sum(person.net_income for person in people)
        contributions = Money(self.base_amount * self.inflation_adjust(year))
        return total_income - contributions

    @strategy_method('Constant living expenses')
    def strategy_const_living_expenses(
            self, year=None, *args, **kwargs
    ):
        """ Living expenses remain constant, in real terms. """
        return Money(self.base_amount * self.inflation_adjust(year))

    @strategy_method('Percentage of net income')
    def strategy_net_percent(self, people, *args, **kwargs):
        """ Live off a percentage of net income. """
        return self.rate * sum(person.net_income for person in people)

    @strategy_method('Percentage of gross income')
    def strategy_gross_percent(self, people, *args, **kwargs):
        """ Live off a percentage of gross income. """
        return self.rate * sum(person.gross_income for person in people)

    @strategy_method('Percentage of earnings growth')
    def strategy_earnings_percent(
        self, people, year=None, *args, **kwargs
    ):
        """ Live off a base amount plus a percentage of earnings above it. """
        base_amount = self.base_amount * self.inflation_adjust(year)
        total_income = sum(person.net_income for person in people)
        return base_amount + (total_income - base_amount) * self.rate

    def __call__(
        self, people=None, year=None, *args, **kwargs
    ):
        """ Returns the living expenses for the year. """
        # Determine how much to spend on living expenses:
        living_expenses = super().__call__(
            people=people, year=year, *args, **kwargs)
        # Ensure we return non-negative value:
        return max(living_expenses, Money(0))

# TODO: Merge WithdrawalStrategy with LivingExpensesStrategy.

class WithdrawalStrategy(Strategy):
    """ Determines an annual gross withdrawal.

    This class is callable. Its call signature has this form::

        obj(
            year, benefits, net_income, gross_income, principal,
            retirement_year
        )

    Arguments may be omitted if the selected strategy does not require
    it; otherwise, an error is raised. All arguments are keyword
    arguments.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            gross_contribution(). See its documentation for more info.

            Acceptable keys include:

            * "Constant withdrawal"
            * "Percentage of principal"
            * "Percentage of gross income"
            * "Percentage of net income"

        base_amount (Money): A user-supplied amount of money, used in
            some strategies as a baseline for withdrawals.
        rate (Decimal): A user-supplied withdrawal rate. Must be a
            percentage (e.g. Decimal('0.03') means 3%).
        timing (str, Decimal): Withdrawals are modelled as a lump sum
            which takes place at this time. If you're using a
            TransactionStrategy to determine per-account withdrawals,
            it's recommended that it use the same timing.

            This is expressed according to the `when` convention
            described in `ledger.Account`.
        inflation_adjust (callable): If provided, `base_amount` is
            interpreted as a real (i.e. inflation-adjusted) currency
            value.

            This callable object will be called as
            `inflation_adjust(year[, base_year])` to receive the
            inflation-adjustment factor between real and nominal values
            for that year (relative to base_year, if provided).

            Optional. If not provided, `base_amount` is not
            inflation_adjusted.
        income_adjusted (bool): If True, withdrawals are reduced to
            account for income from other sources.

    Args:
        year (int): The current year. Optional, but if inflation_adjust
            requires a year parameter than an error will be raised.
        benefits (Money): Other income for the year.
            If `benefits_adjusted` is True, withdrawals will be reduced
            accordingly to maintain the target living standard.
        net_income (dict): {year: Money} pairs. Provides the family's
            total net income for each year.
        gross_income (dict): {year: Money} pairs. Provides the family's
            total gross income for each year.
        principal (dict): {year: Money} pairs. Provides the total
            principal saves for each year.
        retirement_year (int): The year in which the family retired.
            Used as a reference date to set withdrawals for some
            strategies.

    Returns:
        A Money object corresponding to the gross withdrawal amount
        for the family for the year.

    Raises:
        ValueError: A required value was not provided for the given
            strategy.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, strategy, base_amount=0, rate=0, timing='end',
        income_adjusted=False, inflation_adjust=None
    ):
        """ Constructor for ContributionStrategy. """
        super().__init__(strategy)

        self.base_amount = Money(base_amount)
        self.rate = Decimal(rate)
        self.timing = timing
        self.income_adjusted = bool(income_adjusted)

        # If no inflation_adjustment is specified, create a default
        # value so that methods don't need to test for None
        if inflation_adjust is not None:
            self.inflation_adjust = inflation_adjust
        else:
            self.inflation_adjust = lambda *args, **kwargs: 1

        if not isinstance(self.timing, (Decimal, str)):
            raise TypeError('WithdrawalStrategy: timing must be Decimal ' +
                            'or str type.')
        elif isinstance(self.timing, str) and not (self.timing == 'start' or
                                                   self.timing == 'end'):
            raise ValueError('WithdrawalStrategy: timing must be \'start\' ' +
                             'or \'end\' if of type str')

    # Begin defining subclass-specific strategies
    # pylint: disable=W0613
    @strategy_method('Constant withdrawal')
    def strategy_const_withdrawal(self, year=None, *args, **kwargs):
        """ Withdraw a constant amount each year. """
        return Money(self.base_amount * self.inflation_adjust(year))

    @strategy_method('Percentage of principal')
    def strategy_principal_percent(
        self, accounts, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of principal (as of retirement). """
        retirement_balance = sum(
            account.balance_history[retirement_year] for account in accounts)
        return (
            self.rate * retirement_balance
            * self.inflation_adjust(year, retirement_year))

    @strategy_method('Percentage of net income')
    def strategy_net_percent(
        self, people, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of max. net income (as of retirement). """
        retirement_income = sum(
            person.net_income_history[retirement_year] for person in people)
        return (
            self.rate * retirement_income
            * self.inflation_adjust(year, retirement_year))

    @strategy_method('Percentage of gross income')
    def strategy_gross_percent(
        self, people, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of gross income. """
        retirement_income = sum(
            person.gross_income_history[retirement_year] for person in people)
        return (
            self.rate * retirement_income
            * self.inflation_adjust(year, retirement_year))

    # TODO: Add another strategy that tweaks the withdrawal rate
    # periodically (e.g. every 10 years) based on actual portfolio
    # performance? (This sort of thing is why this class was redesigned
    # to take dicts as inputs instead of a handful of scalar values.)

    def __call__(
        self, people=None, accounts=None, year=None,
        retirement_year=None, total_available={}, *args, **kwargs
    ):
        """ Returns the gross withdrawal for the year. """
        # If we're not yet retired, no withdrawals:
        # TODO: Determine whether this is necessary after the
        # move to `available`-based methods. (Maybe we should
        # allow withdrawals pre-retirement from accounts which
        # allow it?)
        if (
            year is not None and retirement_year is not None and
            year <= retirement_year
        ):
            return Money(0)

        # First determine what the strategy recommends, before
        # adjusting for other income.
        strategy_result = super().__call__(
            year=year,
            people=people,
            accounts=accounts,
            retirement_year=retirement_year,
            *args, **kwargs)
        # Determine whether to (and how much to) increase or reduce
        # withdrawals due to an excess or shortfall in cashflow:
        if self.income_adjusted:
            income_adjustment = total_available
        else:
            income_adjustment = Money(0)

        # A negative withdrawal makes no sense in this context;
        # if we have more money then we need, simply avoid
        # withdrawing anything.
        return max(strategy_result - income_adjustment, Money(0))
