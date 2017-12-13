""" This module provides the `Strategy` class and subclasses, which
define contribution and withdrawal strategies and associated flags. """

import inspect
from forecaster.ledger import Money, Decimal


def strategy_method(key):
    """ A decorator for strategy methods, used by Strategy subclasses

    Methods decorated with this decorator will be automatically added
    to the dict `strategies`, which is an attribute of the subclass.
    This happens at class definition time; you need to manually register
    strategy methods that are added dynamically.

    Example:
        class ExampleStrategy(Strategy):
            @strategy_method('method key')
            def _strategy_method(self):
                return

        ExampleStrategy.strategies['method key'] == \
            ExampleStrategy._strategy_method
    """
    def decorator(function):
        """ Decorator returned by strategy_method.

        Adds strategy_key attribute.
        """
        function.strategy_key = key
        return function
    return decorator


class StrategyType(type):
    """ A metaclass for Strategy classes.

    This metaclass inspects the class for any @strategy(key)-decorated
    methods and generates a `strategies` dict of {key, func} pairs. This
    `strategies` dict is then accessible from the class interface.

    NOTE: One side-effect of this approach is that strategy methods are
    collected only once, at definition time. If you want to add a
    strategy to a class later, you'll need to manually add it to the
    subclass's `strategies` dict.
    TODO: Add static class methods to Strategy to register/unregister
    strategy methods? (consider using signature `(func [, key])`)
    """
    def __init__(cls, *args, **kwargs):
        # First, build the class normally...
        super().__init__(*args, **kwargs)
        # ... then add a `strategies` dict by looking up every attribute
        # that has a `strategy_key` attribute of its own.
        cls.strategies = {
            s[1].strategy_key: s[1]
            for s in inspect.getmembers(
                cls, lambda x: hasattr(x, 'strategy_key')
            )
        }


# pylint: disable=too-few-public-methods
class Strategy(object, metaclass=StrategyType):
    """ An abstract callable class for determining a strategy.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function. All functions have the same call signature and
            return value; this is the call signature of the Strategy
            object.
            See each subclass's documentation for more information on
            the call signature for the subclass.
    """

    def __init__(self, strategy):
        # NOTE: `strategy` is required here, but providing a suitable
        # default value in __init__ of each subclass is recommended.

        # If the method itself was passed, translate that into the key
        if (
            not isinstance(strategy, str) and hasattr(strategy, 'strategy_key')
        ):
            strategy = strategy.strategy_key
        self.strategy = strategy

        # Check types and values:
        if not isinstance(self.strategy, str):
            raise TypeError('Strategy: strategy must be a str')
        if self.strategy not in type(self).strategies:
            raise ValueError('Strategy: Unsupported strategy ' +
                             'value: ' + self.strategy)

    def __call__(self, *args, **kwargs):
        """ Makes the Strategy object callable. """
        # Call the selected strategy method.
        # The method is unbound (as it's assigned at the class level) so
        # technically it's a function. We must pass `self` explicitly.
        return type(self).strategies[self.strategy](self, *args, **kwargs)

    @staticmethod
    def _param_check(var, var_name, var_type=None):
        """ Checks that `var` is not None and is of type(s) var_type. """
        if var is None:
            raise ValueError('Strategy: ' + var_name + ' is required.')
        if var_type is not None:
            if not isinstance(var, var_type):
                raise TypeError('Strategy: ' + var_name + ' must be of ' +
                                'type(s) ' + str(var_type))


class ContributionStrategy(Strategy):
    """ Determines an annual gross contribution, before reductions.

    This class is callable. Its call signature has this form:
    `obj(year, refund, other_contribution, net_income, gross_income)`.
    Arguments may be omitted if the selected strategy does not require
    it; otherwise, an error is raised.

    Attributes:
        strategy (str): A string corresponding to a particular
            contribution strategy. See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            gross_contribution(). See its documentation for more info.
            Acceptable keys include:
                "Constant contribution"
                "Constant living expenses"
                "Percentage of gross income"
                "Percentage of net income"
        base_amount (Money): A user-supplied amount of money, used in
            some strategies as a baseline for contributions.
        rate (Decimal): A user-supplied contribution rate. Must be a
            percentage (e.g. Decimal('0.03') means 3%).
        refund_reinvestment_rate (Decimal): The percentage of each tax
            refund that is reinvested in the year it's received.
        inflation_adjust (callable): If provided, `base_amount` is
            interpreted as a real (i.e. inflation-adjusted) currency
            value. This callable object will be called as
            `inflation_adjust(year[, base_year])` to receive the
            inflation-adjustment factor between real and nominal values
            for that year (relative to base_year, if provided).
            Optional. If not provided, `base_amount` is not
            inflation_adjusted.

    Args:
        refund (Money): The sum total of tax refunds and other
            carryforward amounts from previous years. May be
            fully or partially included in gross contributions,
            depending on refund_reinvestment_rate.
        other_contribution (Money): An additional amount to include
            in the gross contribution (e.g. proceeds from the sale
            of one's home)
        net_income (Money): Net family income for the year.
        gross_income (Money): Gross family income for the year.

    Returns:
        A Money object corresponding to the gross contribution amount
        for the family for the year.

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
    def strategy_const_contribution(self, year=None, *args, **kwargs):
        """ Contribute a constant amount each year. """
        return Money(self.base_amount * self.inflation_adjust(year))

    @strategy_method('Constant living expenses')
    def strategy_const_living_expenses(
            self, net_income, year=None, *args, **kwargs
    ):
        """ Contribute the money remaining after living expenses. """
        return max(
            net_income - Money(self.base_amount * self.inflation_adjust(year)),
            Money(0)
        )

    @strategy_method('Percentage of net income')
    def strategy_net_percent(self, net_income, *args, **kwargs):
        """ Contribute a percentage of net income. """
        return self.rate * net_income

    @strategy_method('Percentage of gross income')
    def strategy_gross_percent(self, gross_income, *args, **kwargs):
        """ Contribute a percentage of gross income. """
        return self.rate * gross_income

    @strategy_method('Percentage of earnings growth')
    def strategy_earnings_percent(
        self, net_income, year=None, *args, **kwargs
    ):
        """ Contribute a percentage of earnings above the base amount. """
        return self.rate * (
            net_income - (self.base_amount * self.inflation_adjust(year)))

    def __call__(self, year=None, refund=0, other_contribution=0,
                 net_income=None, gross_income=None,
                 retirement_year=None, *args, **kwargs):
        """ Returns the gross contribution for the year. """
        # NOTE: We layer on refund and other_contribution amounts on top
        # of what the underlying strategy dictates.
        # TODO: Consider reimplementing with list (dict?) arguments for
        # consistency with WithdrawalStrategy.

        # We always contribute carryover/refunds/etc:
        contribution = refund * self.refund_reinvestment_rate + \
            other_contribution
        # Don't make contributions if we've retired:
        if (
            year is not None and retirement_year is not None and
            year > retirement_year
        ):
            return contribution
        # If we're not yet retired, determine what to contribute:
        return contribution + super().__call__(
            year=year, net_income=net_income, gross_income=gross_income,
            *args, **kwargs
        )


class WithdrawalStrategy(Strategy):
    """ Determines an annual gross withdrawal.

    This class is callable. Its call signature has this form:
    `obj(year, benefits, net_income, gross_income, principal,
    retirement_year)`.

    Arguments may be omitted if the selected strategy does not require
    it; otherwise, an error is raised.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            gross_contribution(). See its documentation for more info.
            Acceptable keys include:
                "Constant withdrawal"
                "Percentage of principal"
                "Percentage of gross income"
                "Percentage of net income"
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
            value. This callable object will be called as
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
        self, principal_history, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of principal (as of retirement). """
        return self.rate * principal_history[retirement_year] * \
            self.inflation_adjust(year, retirement_year)

    @strategy_method('Percentage of net income')
    def strategy_net_percent(
        self, net_income_history, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of max. net income (as of retirement). """
        return self.rate * net_income_history[retirement_year] * \
            self.inflation_adjust(year, retirement_year)

    @strategy_method('Percentage of gross income')
    def strategy_gross_percent(
        self, gross_income_history, retirement_year, year=None, *args, **kwargs
    ):
        """ Withdraw a percentage of gross income. """
        return self.rate * gross_income_history[retirement_year] * \
            self.inflation_adjust(year, retirement_year)

    # TODO: Add another strategy that tweaks the withdrawal rate
    # periodically (e.g. every 10 years) based on actual portfolio
    # performance? (This sort of thing is why this class was redesigned
    # to take dicts as inputs instead of a handful of scalar values.)

    def __call__(
        self, year=None, other_income=Money(0),
        net_income_history=None, gross_income_history=None,
        principal_history=None, retirement_year=None, *args, **kwargs
    ):
        """ Returns the gross withdrawal for the year. """
        # If we're not yet retired, no withdrawals:
        if (
            year is not None and retirement_year is not None and
            year <= retirement_year
        ):
            return Money(0)

        # First determine what the strategy recommends, before
        # adjusting for other income.
        strategy_result = super().__call__(
            year=year,
            net_income_history=net_income_history,
            gross_income_history=gross_income_history,
            principal_history=principal_history,
            retirement_year=retirement_year,
            *args, **kwargs)
        # Determine whether to (and how much to) reduce the
        # withdrawal due to other income:
        income_adjustment = Money(
            other_income if self.income_adjusted else 0
        )
        # We want to deduct other income from the withdrawal amount,
        # but we don't want to return a negative value.
        return max(strategy_result - income_adjustment, Money(0))


class TransactionStrategy(Strategy):
    """ Determines account-specific transactions.

    If there are multiple accounts of the same type, the behaviour
    of this class, when called, is undefined.

    If any account has a contribution limit that is lower than the
    weighted amount to be contributed, the excess contribution is
    redistributed to other accounts using the same strategy.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.
            Acceptable keys include:
                "Ordered"
                "Weighted"
        weights (dict): {str, weight} pairs, where keys identify account
            types (as class names, e.g. 'RRSP', 'SavingsAccount') and
            weight values indicate how much to prioritize the
            corresponding account.
        timing (str, Decimal): Transactions are modelled as lump sums
            which take place at this time.
            This is expressed according to the `when` convention
            described in `ledger.Account`.

    Args:
        total (Money): The sum of transactions (positive, for
            contributions, or negative, for withdrawals) across
            all accounts.
        accounts (list): Accounts to contribute to/withdraw from.

    Returns:
        A dict of {Account, Money} pairs where each Account object
        is one of the input accounts and each Money object is a
        transaction for that account.
    """
    def __init__(self, strategy, weights, timing='end'):
        """ Constructor for TransactionStrategy. """
        super().__init__(strategy)

        self.weights = weights
        self.timing = timing

        self._param_check(self.weights, 'weights', dict)
        for key, val in self.weights.items():
            self._param_check(key, 'account type (key)', str)
            # TODO: Check that val is Decimal-convertible instead of
            # a rigid type check?
            self._param_check(
                val, 'account weight (value)', (Decimal, float, int)
            )
        # NOTE: We leave it to calling code to interpret str-valued
        # timing. (We could convert to `When` here - consider it.)
        self._param_check(self.timing, 'timing', (Decimal, str))

    # pylint: disable=W0613
    @strategy_method('Ordered')
    def strategy_ordered(self, total, accounts, *args, **kwargs):
        """ Contributes/withdraws in order of account priority.

        The account with the lowest-valued priority is contributed to
        (or withdrawn from) first. Thus, if three accounts have weights
        1, 2, and 3, then account with weight 1 will go first, followed
        by 2, then 3.
        """
        # TODO: Handle the case where multiple objects of the same type
        # are passed via `accounts`. (Ideally, treat them as a single
        # account and split contributions/withdrawals between them in a
        # reasonable way; e.g. proportional to current balance)

        # Build a dict of {Account, weight} pairs
        adict = {account: self.weights[type(account).__name__]
                 for account in accounts
                 if type(account).__name__ in self.weights}
        # Build a sorted list based on the above pairings
        accounts_ordered = sorted(adict, key=adict.get)

        # Build a dummy dict that we'll fill with values to return
        transactions = {account: Money(0) for account in accounts}

        # Now fill up (or drain) the accounts in order of priority
        # until we hit the total.
        for account in accounts_ordered:
            # First, determine the largest possible contribution/withdrawal
            transaction = max(total, account.max_outflow(self.timing)) \
                if total < 0 else min(total, account.max_inflow())
            # Allocate that amount and reduce total remaining to be allocated
            transactions[account] = transaction
            total -= transaction

        return transactions

    # pylint: disable=W0613
    @strategy_method('Weighted')
    def strategy_weighted(self, total, accounts, *args, **kwargs):
        """ Contributes to/withdraws from all accounts based on weights. """
        # TODO: Handle the case where multiple objects of the same type
        # are passed via `accounts`. (Ideally, treat them as a single
        # account and split contributions/withdrawals between them in a
        # reasonable way; e.g. proportional to current balance)

        # Due to recursion, there's no guarantee that weights will sum
        # to 1, so we'll need to normalize weights.
        normalization = sum([self.weights[type(account).__name__]
                             for account in accounts])

        transactions = {}

        # Determine per-account contributions based on the weight:
        for account in accounts:
            transactions[account] = total * \
                self.weights[type(account).__name__] / normalization

        return transactions

    def _recurse_min(self, total, accounts, transactions, *args, **kwargs):
        """ Recursively assigns minimum inflows/outflows to accounts. """
        # Check to see whether any accounts have minimum inflows or
        # outflows that aren't met by the allocation in `transactions`.
        if total > 0:  # For inflows, check min_inflow and max_inflow
            override_accounts = {
                account: account.min_inflow() for account in transactions
                if account.min_inflow() > transactions[account]
            }
        else:
            # For outflows, check min_outflow.
            # (Recall that outflows are negative-valued)
            override_accounts = {
                account: account.min_outflow() for account in transactions
                if account.min_outflow() < transactions[account]
            }

        # If there are no accounts that need to be tweaked, we're done.
        if not override_accounts:
            return transactions

        # If we found some such accounts, set their transaction amounts
        # manually and recurse onto the remaining accounts.

        # First, manually add the minimum transaction amounts to the
        # identified accounts:
        transactions.update(override_accounts)
        # Identify all accounts that haven't been manually set yet:
        remaining_accounts = [account for account in accounts
                              if account not in override_accounts]

        # Determine the amount remaining to be allocated:
        remaining_total = total - sum(override_accounts.values())

        # If we've already allocated more than the original total
        # (just on the overridden accounts!) then there's no room left
        # to recurse on the strategy. Simply allocate the minimum
        # inflow/outflow for each remaining accounts and terminate:
        if (total > 0 and remaining_total < 0) or \
           (total < 0 and remaining_total > 0) or \
           remaining_total == 0:
            if total > 0:  # Inflows
                override_accounts = {account: account.min_inflow()
                                     for account in remaining_accounts}
            else:  # Outflows
                override_accounts = {account: account.min_outflow()
                                     for account in remaining_accounts}
            transactions.update(override_accounts)
            return transactions

        # Otherwise, if there's still money to be allocated,
        # recurse onto the remaining accounts:
        remaining_transactions = super().__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # Now recurse to ensure that non of the non-maxed accounts have
        # exceeded their max after applying the strategy.
        return self._recurse_min(
            remaining_total, remaining_accounts, transactions,
            *args, **kwargs)

    def _recurse_max(self, total, accounts, transactions, *args, **kwargs):
        """ Recursively assigns minimum inflows/outflows to accounts. """
        # Check to see whether any accounts have minimum inflows or
        # outflows that aren't met by the allocation in `transactions`.
        if total > 0:  # For inflows, check min_inflow and max_inflow
            override_accounts = {
                account: account.max_inflow() for account in transactions
                if account.max_inflow() < transactions[account]
            }
        else:
            # For outflows, check max_outflow.
            # (Recall that outflows are negative-valued)
            override_accounts = {
                account: account.max_outflow() for account in transactions
                if account.max_outflow() > transactions[account]
            }

        # If there are no accounts that need to be tweaked, we're done.
        if not override_accounts:
            return transactions

        # First, manually add the minimum transaction amounts to the
        # identified accounts:
        transactions.update(override_accounts)
        # Identify all accounts that haven't been manually set yet:
        remaining_accounts = [account for account in accounts
                              if account not in override_accounts]

        # Determine the amount to be allocated to the non-maxed accounts:
        remaining_total = total - sum(override_accounts.values())

        # Reassign money to non-maxed accounts according to the selected
        # strategy.
        remaining_transactions = super().__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # Now recurse to ensure that non of the non-maxed accounts have
        # exceeded their max after applying the strategy.
        return self._recurse_max(
            remaining_total, remaining_accounts, transactions,
            *args, **kwargs)

    def __call__(self, total, accounts, *args, **kwargs):
        """ Returns a dict of accounts mapped to transactions. """
        # Get an initial proposal for the transactions based on the
        # selected strategy:
        transactions = super().__call__(total=total, accounts=accounts,
                                        *args, **kwargs)
        # Recursively ensure that minimum in/outflows are respected:
        transactions = self._recurse_min(total, accounts, transactions,
                                         *args, **kwargs)
        # Recursively ensure that maximum in/outflows are respected:
        transactions = self._recurse_max(total, accounts, transactions,
                                         *args, **kwargs)
        return transactions


class RateFunction(object):
    """ A callable object with accessible state attributes. """

    # We do provide public methods, but they're overrides of magic
    # methods (init and call). Anyways, the purpose of this class is
    # to expose its state (which a method/function/lambda does not do).
    # pylint: disable=too-few-public-methods

    def __init__(self, scenario, person, allocation_strategy):
        """ Inits the RateFunction object. """
        self.scenario = scenario
        self.person = person
        self.allocation_strategy = allocation_strategy

    def __call__(self, year) -> Decimal:
        """ Rate of return for `year` based on asset allocation.

        Args:
            year (int): The year for which the rate of return will be
                determined.

        Returns:
            Decimal: The rate of return. For example, `Decimal('0.05')`
            means a 5% return.
        """
        allocation = self.allocation_strategy(
            age=self.person.age(year),
            retirement_age=self.person.retirement_age
        )
        # Extract stocks/bonds/other returns:
        if 'stocks' in allocation:
            stocks = allocation['stocks']
        else:
            stocks = Decimal(0)
        if 'bonds' in allocation:
            bonds = allocation['bonds']
        else:
            bonds = Decimal(0)
        if 'other' in allocation:
            other = allocation['other']
        else:
            other = Decimal(0)

        # Weight the returns of the various asset classes by each
        # class's allocation:
        return (
            (
                stocks * self.scenario.stock_return[year]
                + bonds * self.scenario.bond_return[year]
                + other * self.scenario.other_return[year]
            ) / (stocks + bonds + other)
        )


class AllocationStrategy(Strategy):
    """ Generates an asset allocation for a point in time. Callable.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.
            Acceptable keys include:
                "n-age"
                "Transition to constant"
        min_equity (Decimal): The minimum percentage of a portfolio that
            may be invested in equities. (All non-equity investments
            are included in `fixed_income`)
        max_equity (Decimal): The maximum percentage of a portfolio that
            may be invested in equities.
        target (Decimal): A target value used by strategies to affect
            their behaviour.
            For example, for the `n-age` strategy, this is the value `n`
            (e.g. `target=100` -> `100-age`).
            For the `Transition to constant` strategy, this is the
            percentage of equities to transition to (e.g. for
            `Transition to 50-50`, use `Decimal('0.5')`)
        standard_retirement_age (int): The typical retirement age used
            in retirement planning. This is used if
            adjust_for_retirement_plan is False, otherwise the actual
            (estimated) retirement age for the person is used.
        risk_transition_period (int): The period of time over which the
            `Transition to constant` strategy transitions. For example,
            if set to 20, the strategy will transition from max_equity
            to transition_strategy_target over 20 years, ending on the
            retirement date.
        adjust_for_retirement_plan (bool): If True, the allocation will
            be adjusted to increase risk for later retirement or
            decrease risk for later retirement. If False, the standard
            retirement age will be used.

    Args:
        age (int): The current age of the plannee.
        retirement_age (int): The (estimated) retirement age of the
            plannee.

    Returns:
        dict[str, Decimal]: `{asset: allocation}` pairs, where `asset`
        is a string in `{'stocks', 'bonds'}` and `allocation` is the
        percentage of a portfolio that is made up of that asset class.
        Allocations sum to 1 (e.g. `Decimal(0.03` means 3%).
    """
    # pylint: disable=too-many-arguments
    def __init__(
        self, strategy, target, min_equity=0, max_equity=1,
        standard_retirement_age=65, risk_transition_period=20,
        adjust_for_retirement_plan=True
    ):
        """ Constructor for AllocationStrategy. """
        super().__init__(strategy)

        self.min_equity = Decimal(min_equity)
        self.max_equity = Decimal(max_equity)
        self.standard_retirement_age = int(standard_retirement_age)
        self.target = Decimal(target)
        self.risk_transition_period = int(risk_transition_period)
        self.adjust_for_retirement_plan = bool(adjust_for_retirement_plan)

        # All of the above are type-converted; no need to check types!

        if self.max_equity < self.min_equity:
            raise ValueError('AllocationStrategy: min_equity must not be ' +
                             'greater than max_equity.')

    @strategy_method('n-age')
    # pylint: disable=W0613
    def strategy_n_minus_age(
        self, age, retirement_age=None, *args, **kwargs
    ):
        """ Used for 100-age, 110-age, 125-age, etc. strategies. """
        # If we're adjusting for early/late retirement,
        # pretend we're a few years younger if we're retiring later
        # (or that we're older if retiring earlier)
        self._param_check(age, 'age')
        if self.adjust_for_retirement_plan:
            self._param_check(retirement_age, 'retirement age')
            age += self.standard_retirement_age - retirement_age
        else:
            retirement_age = self.standard_retirement_age
        # The formula for `n-age` is just that (recall that
        # n=constant_strategy_target). Insert the adjustment factor too.
        target = Decimal(self.target - age) / 100
        # Ensure that we don't move past our min/max equities
        target = min(max(target, self.min_equity), self.max_equity)
        # Bonds is simply whatever isn't in equities
        return {'stocks': target, 'bonds': 1 - target}

    @strategy_method('Transition to constant')
    # pylint: disable=W0613
    def strategy_transition_to_const(
        self, age, retirement_age=None, *args, **kwargs
    ):
        """ Used for `Transition to 50-50`, `Transition to 70-30`, etc. """
        self._param_check(age, 'age')
        # Assume we're retiring at the standard retirement age unless
        # adjust_for_retirement_plan is True
        if self.adjust_for_retirement_plan:
            self._param_check(retirement_age, 'retirement age')
        else:
            retirement_age = self.standard_retirement_age

        # If retirement is outside our risk transition window (e.g. if
        # it's more than 20 years away), maximize stock holdings.
        if age <= retirement_age - self.risk_transition_period:
            return {'stocks': self.max_equity, 'bonds': 1 - self.max_equity}
        # If we've hit retirement, keep equity allocation constant at
        # our target
        elif age >= retirement_age:
            min_equity = max(self.min_equity, self.target)
            return {'stocks': min_equity, 'bonds': 1 - min_equity}
        # Otherwise, smoothly move from max_equity to target over
        # the risk_transition_period
        target = self.target + \
            (self.max_equity - self.target) * \
            (retirement_age - age) / self.risk_transition_period
        return {'stocks': target, 'bonds': 1 - target}

    def rate_function(self, person, scenario):
        """ A rate function usable by Person or Account objects.

        Args:
            person (Person): A person. The method builds a portfolio for
                the person based on this object's allocation strategy
                (in particular, based on the person's age and/or
                projected retirement date).
            scenario (Scenario): A scenario providing information on
                returns on investment for stocks, bonds, etc.

        Returns:
            An object callable with the form
            `rate_function(year) -> Decimal` that provides a rate of
            return for a given year based on the person's age and the
            investment returns for various asset classes provided by
            `scenario`.
        """
        # We need to return an object rather than a function or lambda
        # because we need Forecaster to be able to swap out any of those
        # attributes when running a forecast.
        return RateFunction(scenario, person, self)

    def __call__(self, age, retirement_age=None, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        # TODO: Move min_equity and max_equity logic here to simplify
        # the logic of each strategy.
        # In the meantime, suppress Pylint's complaints about how this
        # method is useless:
        # pylint: disable=useless-super-delegation
        return super().__call__(age, retirement_age, *args, **kwargs)


class DebtPaymentStrategy(Strategy):
    """ Determines payments for a group of debts.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.
            Acceptable keys include:
                "Snowball"
                "Avalanche"
        timing (str, Decimal): Transactions are modelled as lump sums
            which take place at this time.
            This is expressed according to the `when` convention
            described in `ledger.Account`.

    Args:
        available (Money): The total amount available for repayment
            across all accounts.
        debts (list): Debts to repay.

    Returns:
        A dict of {Debt, Money} pairs where each Debt object
        is one of the input accounts and each Money object is a
        transaction for that account.
    """

    def __init__(self, strategy, timing='end'):
        """ Constructor for DebtPaymentStrategy. """

        super().__init__(strategy)

        self.timing = timing

        # NOTE: We leave it to calling code to interpret str-valued
        # timing. (We could convert to `When` here - consider it.)
        self._param_check(self.timing, 'timing', (Decimal, str))

    # pylint: disable=W0613
    @strategy_method('Snowball')
    def strategy_snowball(self, available, debts, *args, **kwargs):
        """ Pays off the smallest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {
            debt: debt.min_inflow(when=self.timing)
            for debt in debts
        }

        available -= sum(transactions[debt] * debt.reduction_rate
                         for debt in debts)

        if available <= 0:
            return transactions

        accelerated_debts = {debt for debt in debts if debt.accelerate_payment}
        # Now we increase contributions to any accelerated debts
        # (non-accelerated debts can just have minimum payments made,
        # handled above). Here, increase contributions of the smallest
        # debt first, then the next, and so on until there's no money
        # left to allocate to debt repayment:
        for debt in sorted(
            accelerated_debts, key=lambda x: abs(x.balance), reverse=False
        ):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                continue

            # Payment is either the outstanding balance or the total of
            # the available money remaining for payments
            payment = min(
                debt.max_inflow(self.timing) - transactions[debt],  # balance
                available / debt.reduction_rate  # money available
            )
            transactions[debt] += payment
            # `available` is at least partially taken from savings;
            # only deduct that portion of the payment from `available`
            available -= payment * debt.reduction_rate

        return transactions

    @strategy_method('Avalanche')
    def strategy_avalanche(self, available, debts, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {
            debt: debt.min_inflow(when=self.timing)
            for debt in debts
        }

        available -= sum(transactions[debt] * debt.reduction_rate
                         for debt in debts)

        if available <= 0:
            return transactions

        accelerated_debts = {debt for debt in debts if debt.accelerate_payment}
        # Now we increase contributions to any accelerated debts
        # (non-accelerated debts can just have minimum payments made,
        # handled above). Here, increase contributions of the largest
        # rate first, then the next, and so on until there's no money
        # left to allocate to debt repayment:
        for debt in sorted(
            accelerated_debts, key=lambda x: x.rate, reverse=True
        ):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                continue

            # Payment is either the outstanding balance or the total of
            # the available money remaining for payments
            payment = min(
                debt.max_inflow(self.timing) - transactions[debt],  # balance
                available / debt.reduction_rate  # money available
            )
            transactions[debt] += payment
            # `available` is at least partially taken from savings;
            # only deduct that portion of the payment from `available`
            available -= payment * debt.reduction_rate

        return transactions

    # Overriding __call__ solely for intellisense purposes.
    # pylint: disable=W0235
    def __call__(self, available, debts, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(available, debts, *args, **kwargs)
