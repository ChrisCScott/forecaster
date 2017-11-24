""" This module provides the `Strategy` class and subclasses, which
define contribution and withdrawal strategies and associated flags. """

from collections import namedtuple
import inspect
from ledger import *
from settings import Settings


def strategy(key):
    """ A decorator for strategy methods, used by Strategy subclasses

    Methods decorated with this decorator will be automatically added
    to the dict `strategies`, which is an attribute of the subclass.
    This happens at class definition time; you need to manually register
    strategy methods that are added dynamically.

    Example:
        class ExampleStrategy(Strategy):
            @strategy('method key')
            def _strategy_method(self):
                return

        ExampleStrategy.strategies['method key'] == \
            ExampleStrategy._strategy_method
    """
    def decorator(function):
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
            for s in inspect.getmembers(cls,
                                        lambda x: hasattr(x, 'strategy_key')
                                        )
        }


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

    def __init__(self, strategy, settings=Settings):
        # NOTE: `strategy` is required here, but providing a suitable
        # default value in __init__ of each subclass is recommended.

        # If the method itself was passed, translate that into the key
        if (not isinstance(strategy, str)) \
          and hasattr(strategy, 'strategy_key'):
            strategy = strategy.strategy_key
        self.strategy = strategy

        # Check types and values:
        if not isinstance(self.strategy, str):
            raise TypeError('Strategy: strategy must be a str')
        if self.strategy not in self.strategies:
            raise ValueError('Strategy: Unsupported strategy ' +
                             'value: ' + self.strategy)
        if not (settings == Settings or isinstance(settings, Settings)):
            raise TypeError('Strategy: settings must be Settings object.')

    def __call__(self, *args, **kwargs):
        """ Makes the Strategy object callable. """
        # Call the selected strategy method.
        # The method is unbound (as it's assigned at the class level) so
        # technically it's a function. We must pass `self` explicitly.
        return self.strategies[self.strategy](self, *args, **kwargs)

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
    `obj(refund, other_contribution, net_income, gross_income,
    inflation_adjustment)`. Arguments may be omitted if the selected
    strategy does not require it; otherwise, an error is raised.

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
        inflation_adjusted (bool): If True, `rate` is interpreted as a
            real (i.e. inflation-adjusted) currency value, unless the
            current strategy interprets it as a percentage.
            Optional. Defaults to True.

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
        inflation_adjustment (Decimal): The inflation adjustment for
            the year. If `inflation_adjusted` is True, this will
            be used to inflation-adjust any non-percentage-based
            strategy.

    Returns:
        A Money object corresponding to the gross contribution amount
        for the family for the year.

    Raises:
        ValueError: A required value was not provided for the given
            strategy.
    """

    # TODO: Reimplement inflation-adjustment to use a method.
    # (Replace inflation_adjusted? Instead of bool, maybe client code
    # can simply test for whether inflation_adjust is None? Or perhaps
    # add a non-passed attribute that returns True iff inflation_adjust
    # is not None?)

    def __init__(self, strategy=None, base_amount=None, rate=None,
                 refund_reinvestment_rate=None, inflation_adjusted=None,
                 settings=Settings):
        """ Constructor for ContributionStrategy. """
        # Use the subclass-specific default strategy if none provided
        if strategy is None:
            strategy = settings.contribution_strategy
        super().__init__(strategy, settings)

        # Use default values from settings if none are provided.
        self.base_amount = Money(base_amount) if base_amount is not None \
            else settings.contribution_base_amount
        self.rate = Decimal(rate) if rate is not None \
            else settings.contribution_rate
        self.refund_reinvestment_rate = Decimal(refund_reinvestment_rate) \
            if refund_reinvestment_rate is not None \
            else settings.contribution_refund_reinvestment_rate
        self.inflation_adjusted = bool(inflation_adjusted) \
            if inflation_adjusted is not None \
            else settings.contribution_inflation_adjusted

        # Types are enforced by explicit conversion; no need to check.

    # Begin defining subclass-specific strategies
    @strategy('Constant contribution')
    def _strategy_constant_contribution(self, inflation_adjustment=None,
                                        *args, **kwargs):
        """ Contribute a constant amount each year. """
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(inflation_adjustment, 'inflation adjustment')
        return Money(self.base_amount * inflation_adjustment)

    @strategy('Constant living expenses')
    def _strategy_constant_living_expenses(self, net_income,
                                           inflation_adjustment=None,
                                           *args, **kwargs):
        """ Contribute the money remaining after living expenses. """
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(inflation_adjustment, 'inflation adjustment')
        self._param_check(net_income, 'net income')
        return max(net_income - Money(self.base_amount * inflation_adjustment),
                   Money(0))

    @strategy('Percentage of net income')
    def _strategy_net_percent(self, net_income, *args, **kwargs):
        """ Contribute a percentage of net income. """
        # net_income is required for this strategy. Check explicitly:
        self._param_check(net_income, 'net income')
        return self.rate * net_income

    @strategy('Percentage of gross income')
    def _strategy_gross_percent(self, gross_income, *args, **kwargs):
        """ Contribute a percentage of gross income. """
        # gross_income is required for this strategy. Check explicitly:
        self._param_check(gross_income, 'gross income')
        return self.rate * gross_income

    @strategy('Percentage of earnings growth')
    def _strategy_earnings_percent(self, net_income, inflation_adjustment=None,
                                   *args, **kwargs):
        """ Contribute a percentage of earnings above the base amount. """
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(inflation_adjustment, 'inflation adjustment')
        self._param_check(net_income, 'net income')
        return self.rate * (net_income - (self.base_amount *
                                          inflation_adjustment))

    def __call__(self, refund=0, other_contribution=0, net_income=None,
                 gross_income=None, inflation_adjustment=None,
                 *args, **kwargs):
        """ Returns the gross contribution for the year. """
        # NOTE: We layer on refund and other_contribution amounts on top
        # of what the underlying strategy dictates.
        # TODO: Consider reimplementing with list (dict?) arguments for
        # consistency with WithdrawalStrategy.
        return refund * self.refund_reinvestment_rate + other_contribution + \
            super().__call__(net_income=net_income, gross_income=gross_income,
                             inflation_adjustment=inflation_adjustment,
                             *args, **kwargs)


class WithdrawalStrategy(Strategy):
    """ Determines an annual gross withdrawal.

    This class is callable. Its call signature has this form:
    `obj(benefits, net_income, gross_income, principal,
    inflation_adjustment, retirement_year, this_year)`.

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
        rate (Decimal, Money): A [user-supplied] withdrawal rate.
            Has different meanings for different strategies; may be a
            percentage (e.g. Decimal('0.03') means 3%) or a currency
            value (e.g. Decimal('3000') for a $3000 withdrawal).
        min_living_standard (Money): Withdrawals will not go below the
            level needed to maintain this (real-valued) living standard.
        timing (str, Decimal): Withdrawals are modelled as a lump sum
            which takes place at this time. If you're using a
            TransactionStrategy to determine per-account withdrawals,
            it's recommended that it use the same timing.
            This is expressed according to the `when` convention
            described in `ledger.Account`.
        inflation_adjusted (bool): If True, `rate` is interpreted as a
            real (i.e. inflation-adjusted) currency value, unless the
            current strategy interprets it as a percentage.
            If True (and if used by the current strategy), inflation_adjustment
            is a required arg when calling an instance of this class.
            Optional. Defaults to True.
        benefit_adjusted (bool): If True, withdrawals are reduced to
            account for expected benefits.

    Args:
        benefits (Money): Other income for the year.
            If `benefits_adjusted` is True, withdrawals will be reduced
            accordingly to maintain the target living standard.
        net_income (dict): {year: Money} pairs. Provides the family's
            total net income for each year.
        gross_income (dict): {year: Money} pairs. Provides the family's
            total gross income for each year.
        principal (dict): {year: Money} pairs. Provides the total
            principal saves for each year.
        inflation_adjustment (dict): {year: Decimal} pairs. The
            inflation adjustment for each year. If `inflation_adjusted`
            is True, this will be used to inflation-adjust any
            non-percentage-based strategy.
        retirement_year (int): The year in which the family retired.
            Used as a reference date to set withdrawals for some
            strategies.
        this_year (int): The current year. Used for to adjust for
            inflation if `inflation_adjusted` is True.

    Returns:
        A Money object corresponding to the gross withdrawal amount
        for the family for the year.

    Raises:
        ValueError: A required value was not provided for the given
            strategy.
    """

    def __init__(self, strategy=None, rate=None, min_living_standard=None,
                 timing=None, benefit_adjusted=None, inflation_adjusted=None,
                 settings=Settings):
        """ Constructor for ContributionStrategy. """
        # Use the subclass-specific default strategy if none provided
        if strategy is None:
            strategy = settings.withdrawal_strategy
        super().__init__(strategy, settings)

        # Use default values from settings if none are provided
        if isinstance(rate, Money):  # `Money` doesn't cast to Decimal
            self.rate = rate
        else:
            self.rate = Decimal(rate) if rate is not None \
                else Decimal(settings.withdrawal_rate)
        self.min_living_standard = Money(min_living_standard) \
            if min_living_standard is not None \
            else Money(settings.withdrawal_min_living_standard)
        self.timing = timing if timing is not None \
            else settings.transaction_out_timing
        self.benefit_adjusted = bool(benefit_adjusted) \
            if benefit_adjusted is not None \
            else bool(settings.withdrawal_benefit_adjusted)
        self.inflation_adjusted = bool(inflation_adjusted) \
            if inflation_adjusted is not None \
            else bool(settings.withdrawal_inflation_adjusted)

        if not isinstance(self.timing, (Decimal, str)):
            raise TypeError('WithdrawalStrategy: timing must be Decimal ' +
                            'or str type.')
        elif isinstance(self.timing, str) and not (self.timing == 'start' or
                                                   self.timing == 'end'):
            raise ValueError('WithdrawalStrategy: timing must be \'start\' ' +
                             'or \'end\' if of type str')

    # Begin defining subclass-specific strategies
    @strategy('Constant withdrawal')
    def _strategy_constant_withdrawal(self, inflation_adjustment=None,
                                      this_year=None, *args, **kwargs):
        """ Withdraw a constant amount each year. """
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(this_year, 'this year', int)
            self._param_check(inflation_adjustment, 'inflation adjustment',
                              dict)
            inflation_adjustment = inflation_adjustment[this_year]
        return Money(self.rate * inflation_adjustment)

    @strategy('Percentage of principal')
    def _strategy_principal_percent(self, principal, retirement_year,
                                    inflation_adjustment=None, this_year=None,
                                    *args, **kwargs):
        """ Withdraw a percentage of principal (as of retirement). """
        # Check mandatory params
        self._param_check(principal, 'principal', dict)
        self._param_check(retirement_year, 'retirement year', int)
        if self.inflation_adjusted:
            self._param_check(this_year, 'this year', int)
            self._param_check(inflation_adjustment, 'inflation adjustment',
                              dict)
            inflation_adjustment = (inflation_adjustment[this_year] /
                                    inflation_adjustment[retirement_year])
        else:
            inflation_adjustment = 1
        return self.rate * principal[retirement_year] * inflation_adjustment

    @strategy('Percentage of net income')
    def _strategy_net_percent(self, net_income, retirement_year,
                              inflation_adjustment=None, this_year=None,
                              *args, **kwargs):
        """ Withdraw a percentage of max. net income (as of retirement). """
        self._param_check(net_income, 'net income', dict)
        self._param_check(retirement_year, 'retirement year', int)
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(this_year, 'this year', int)
            self._param_check(inflation_adjustment, 'inflation adjustment',
                              dict)
            inflation_adjustment = (inflation_adjustment[this_year] /
                                    inflation_adjustment[retirement_year])
        return self.rate * net_income[retirement_year] * inflation_adjustment

    @strategy('Percentage of gross income')
    def _strategy_gross_percent(self, gross_income, retirement_year,
                                inflation_adjustment=None, this_year=None,
                                *args, **kwargs):
        """ Contribute a percentage of gross income. """
        self._param_check(gross_income, 'gross income', dict)
        self._param_check(retirement_year, 'retirement year', int)
        # If not inflation-adjusted, ignore the discount rate
        if not self.inflation_adjusted:
            inflation_adjustment = 1
        # If inflation-adjusted, confirm that inflation_adjustment was provided
        else:
            self._param_check(this_year, 'this year', int)
            self._param_check(inflation_adjustment, 'inflation adjustment',
                              dict)
            inflation_adjustment = (inflation_adjustment[this_year] /
                                    inflation_adjustment[retirement_year])
        return self.rate * gross_income[retirement_year] * inflation_adjustment

    # TODO: Add another strategy that tweaks the withdrawal rate
    # periodically (e.g. every 10 years) based on actual portfolio
    # performance? (This sort of thing is why this class was redesigned
    # to take dicts as inputs instead of a handful of scalar values.)

    def min_withdrawal(self, inflation_adjustment=None, this_year=None):
        """ The minimum withdrawal required to meet min_living_standard. """
        # TODO: Make this more sophisticated (e.g. account for taxes so
        # that the min. withdrawal yieds a post-tax amount of
        # self.min_living_standard)

        # No need to inflation-adjust a $0 living standard
        if self.min_living_standard > Money(0):
            self._param_check(this_year, 'this year', int)
            self._param_check(inflation_adjustment, 'inflation adjustment',
                              dict)
            return self.min_living_standard * inflation_adjustment[this_year]
        else:
            return Money(0)

    def __call__(self, benefits=Money(0), net_income=None, gross_income=None,
                 principal=None, inflation_adjustment=None,
                 retirement_year=None, this_year=None, *args, **kwargs):
        """ Returns the gross withdrawal for the year. """
        # This is what the strategy recommends, before benefit adjustment.
        strategy_result = super().__call__(
            net_income=net_income,
            gross_income=gross_income,
            principal=principal,
            inflation_adjustment=inflation_adjustment,
            retirement_year=retirement_year,
            this_year=this_year,
            *args, **kwargs)
        # Separate this out for readability:
        min_withdrawal = self.min_withdrawal(inflation_adjustment, this_year)
        # Determine how much to reduce the withdrawal due to benefits:
        benefit_adjustment = Money(benefits if self.benefit_adjusted else 0)
        # We want to deduct benefits from the withdrawal amount, but
        # we don't want to return a negative value.
        return max(max(min_withdrawal, strategy_result) - benefit_adjustment,
                   Money(0))


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
    def __init__(self, strategy, weights, timing, settings=Settings):
        """ Constructor for TransactionStrategy. """
        # We use different defaults for inflows and outflows, so
        # rely on subclasses to provide defaults.
        super().__init__(strategy, settings)

        self.weights = weights
        self.timing = timing

        self._param_check(self.weights, 'weights', dict)
        for key, val in self.weights.items():
            self._param_check(key, 'account type (key)', str)
            # TODO: Check that val is Decimal-convertible instead of
            # a rigid type check?
            self._param_check(val, 'account weight (value)',
                              (Decimal, float, int))
        # NOTE: We leave it to calling code to interpret str-valued
        # timing. (We could convert to `When` here - consider it.)
        self._param_check(self.timing, 'timing', (Decimal, str))

    @strategy('Ordered')
    def _strategy_ordered(self, total, accounts, *args, **kwargs):
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

    @strategy('Weighted')
    def _strategy_weighted(self, total, accounts, *args, **kwargs):
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
        if len(override_accounts) == 0:
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
        if len(override_accounts) == 0:
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


# TODO: Delete the two subclasses of TransactionStrategy and leave it
# to client code to init with settings values.


class TransactionInStrategy(TransactionStrategy):
    ''' A TransactionStrategy that uses contribution defaults. '''
    def __init__(self, strategy=None, weights=None, timing=None,
                 settings=Settings):
        """ Constructor for TransactionStrategy. """
        if strategy is None:
            strategy = settings.transaction_in_strategy
        if weights is None:
            weights = settings.transaction_in_weights
        if timing is None:
            timing = settings.transaction_in_timing
        super().__init__(strategy, weights, timing, settings)


class TransactionOutStrategy(TransactionStrategy):
    """ A TransactionStrategy that uses withdrawal defaults. """
    def __init__(self, strategy=None, weights=None, timing=None,
                 settings=Settings):
        """ Constructor for TransactionStrategy. """
        if strategy is None:
            strategy = settings.transaction_out_strategy
        if weights is None:
            weights = settings.transaction_out_weights
        if timing is None:
            timing = settings.transaction_out_timing
        super().__init__(strategy, weights, timing, settings)


AssetAllocation = namedtuple('AssetAllocation', 'equity fixed_income')


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
        An Allocation object describing the asset allocation. Each
        element of the Allocation tuple is of type Decimal and expresses
        a percentage (e.g. Decimal('0.03') means 3%). They sum to 100%.
    """
    def __init__(self, strategy=None, min_equity=None, max_equity=None,
                 target=None, standard_retirement_age=None,
                 risk_transition_period=None, adjust_for_retirement_plan=None,
                 settings=Settings):
        """ Constructor for AllocationStrategy. """
        # Use the subclass-specific default strategy if none provided
        if strategy is None:
            strategy = settings.allocation_strategy
        super().__init__(strategy, settings)

        # Pick the correct default setting depending on the strategy:
        if self.strategy == (
          AllocationStrategy._strategy_n_minus_age.strategy_key):
            target_default = settings.allocation_constant_strategy_target
        elif self.strategy == (
          AllocationStrategy._strategy_transition_to_constant.strategy_key):
            target_default = settings.allocation_transition_strategy_target
        else:  # Just in case
            target_default = 0

        # Default to Settings values where no input was provided.
        self.min_equity = Decimal(
            min_equity if min_equity is not None
            else settings.allocation_min_equity)
        self.max_equity = Decimal(
            max_equity if max_equity is not None
            else settings.allocation_max_equity)
        self.standard_retirement_age = int(
            standard_retirement_age if standard_retirement_age is not None
            else settings.allocation_standard_retirement_age)
        self.target = Decimal(target if target is not None else target_default)
        self.risk_transition_period = int(
            risk_transition_period if risk_transition_period is not None
            else settings.allocation_risk_transition_period)
        self.adjust_for_retirement_plan = bool(
            adjust_for_retirement_plan
            if adjust_for_retirement_plan is not None
            else settings.allocation_adjust_for_retirement_plan)

        # All of the above are type-converted; no need to check types!

        if self.max_equity < self.min_equity:
            raise ValueError('AllocationStrategy: min_equity must not be ' +
                             'greater than max_equity.')

    @strategy('n-age')
    def _strategy_n_minus_age(self, age, retirement_age=None,
                              *args, **kwargs):
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
        # Fixed income is simply whatever isn't in equities
        return AssetAllocation(equity=target, fixed_income=1-target)

    @strategy('Transition to constant')
    def _strategy_transition_to_constant(self, age, retirement_age=None,
                                         *args, **kwargs):
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
            return AssetAllocation(equity=self.max_equity,
                                   fixed_income=1-self.max_equity)
        # If we've hit retirement, keep equity allocation constant at
        # our target
        elif age >= retirement_age:
            min_equity = max(self.min_equity, self.target)
            return AssetAllocation(equity=min_equity,
                                   fixed_income=1-min_equity)
        # Otherwise, smoothly move from max_equity to target over
        # the risk_transition_period
        else:
            target = self.target + \
                (self.max_equity - self.target) * \
                (retirement_age - age) / self.risk_transition_period
            return AssetAllocation(equity=target, fixed_income=1-target)

    def __call__(self, age, retirement_age=None, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        # TODO: Add list (dict?) arguments with historical data (e.g.
        # withdrawals and principal) to allow for behaviour-aware
        # rebalancing.
        # TODO: Move min_equity and max_equity logic here to simplify
        # the logic of each strategy.
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

    def __init__(self, strategy=None, timing=None, settings=Settings):
        """ Constructor for DebtPaymentStrategy. """

        # Pull values from Settings
        if strategy is None:
            strategy = settings.debt_payment_strategy
        if timing is None:
            timing = settings.debt_payment_timing

        super().__init__(strategy, settings)

        self.timing = timing

        # NOTE: We leave it to calling code to interpret str-valued
        # timing. (We could convert to `When` here - consider it.)
        self._param_check(self.timing, 'timing', (Decimal, str))

    @strategy('Snowball')
    def _strategy_snowball(self, available, debts, *args, **kwargs):
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

        # Iterate over debts from smallest balance to largest:
        for debt in sorted(debts, key=lambda x: abs(x.balance), reverse=False):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                pass

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

    @strategy('Avalanche')
    def _strategy_avalanche(self, available, debts, *args, **kwargs):
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

        # Iterate over debts from largest rate to smallest:
        for debt in sorted(debts, key=lambda x: x.rate, reverse=True):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                pass

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
    def __call__(self, available, debts, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(available, debts, *args, **kwargs)
