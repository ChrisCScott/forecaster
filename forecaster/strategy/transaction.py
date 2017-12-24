""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.

`DebtPaymentStrategy` is a related `Debt`-specific class.
"""

from decimal import Decimal
from forecaster.ledger import Money
from forecaster.strategy.base import Strategy, strategy_method


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

            * "Ordered"
            * "Weighted"

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
        weighted_accounts (dict[Union[Account, AccountGroup], Decimal]):
            Accounts to contribute to/withdraw from mapped to weights.

    Returns:
        dict[Union[Account, AccountGroup], Money] pairs. The keys are
        a subset of the input `accounts` keys and the values are the
        corresponding transaction amount for that account.
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

    @strategy_method('Ordered')
    def strategy_ordered(self, total, weighted_accounts, *args, **kwargs):
        """ Contributes/withdraws in order of account priority.

        The account with the lowest-valued priority is contributed to
        (or withdrawn from) first. Thus, if three accounts have weights
        1, 2, and 3, then account with weight 1 will go first, followed
        by 2, then 3.

        Args:
            total (Money): The sum of transactions (positive, for
                contributions, or negative, for withdrawals) across
                all accounts.
            weighted_accounts (dict[Union[Account, AccountGroup],
                Decimal]): Accounts to contribute to (or withdraw from)
                mapped to weights.

        Returns:
            dict[Union[Account, AccountGroup], Money] pairs. The keys
            are a subset of the input `accounts` keys and the values are
            the corresponding transaction amount for that account.
        """
        # We provide *args and **kwargs to maintain a consistent
        # interface between strategy methods.
        # pylint: disable=unused-argument
        # Mixing @property (or its subclass @strategy_method) with
        # @staticmethod is not recommended.
        # pylint: disable=no-self-use

        # Build a sorted list based on the account_set: weight pairings:
        accounts_ordered = sorted(weighted_accounts, key=weighted_accounts.get)

        transactions = {}

        # Now fill up (or drain) the accounts in order of priority
        # until we hit the total.
        for account in accounts_ordered:
            if total >= 0:
                transaction = min(total, account.max_inflow())
            else:
                transaction = max(total, account.max_outflow())
            transactions[account] = transaction
            total -= transaction

        return transactions

    @strategy_method('Weighted')
    def strategy_weighted(self, total, weighted_accounts, *args, **kwargs):
        """ Assigns transactions proportionately to accounts' weights.

        Args:
            total (Money): The sum of transactions (positive, for
                contributions, or negative, for withdrawals) across
                all accounts.
            weighted_accounts (dict[Union[Account, AccountGroup],
                Decimal]): Accounts to contribute to (or withdraw from)
                mapped to weights.

        Returns:
            dict[Union[Account, AccountGroup], Money] pairs. The keys
            are a subset of the input `accounts` keys and the values are
            the corresponding transaction amount for that account.
        """
        # We provide *args and **kwargs to maintain a consistent
        # interface between strategy methods.
        # pylint: disable=unused-argument
        # Mixing @property (or its subclass @strategy_method) with
        # @staticmethod is not recommended.
        # pylint: disable=no-self-use

        # Due to recursion, there's no guarantee that weights will sum
        # to 1, so we'll need to normalize weights.
        normalization = sum(weighted_accounts.values())

        transactions = {}

        # Determine contributions/withdrawals for each account set based
        # on its associated weight:
        for account, weight in weighted_accounts.items():
            transaction = total * weight / normalization
            transactions[account] = transaction

        return transactions

    def _recurse_min(
        self, total, accounts, transactions, *args, **kwargs
    ):
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
        remaining_accounts = {
            account for account in accounts
            if account not in override_accounts}

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
        remaining_transactions = self.__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # It's not necessary to return `transactions` because we mutate
        # it above, but it's also not harmful, so why not?
        return transactions

    def _recurse_max(
        self, total, accounts, transactions, *args, **kwargs
    ):
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
        remaining_accounts = accounts.difference(override_accounts)

        # Determine the amount to be allocated to the non-maxed accounts:
        remaining_total = total - sum(override_accounts.values())

        # Reassign money to non-maxed accounts according to the selected
        # strategy.
        remaining_transactions = self.__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # It's not necessary to return `transactions` because we mutate
        # it above, but it's also not harmful, so why not?
        return transactions

    def group_accounts(self, accounts):
        """ Maps a set of accounts to a dict of `{set: weight}` pairs.

        Each set contains one or more accounts which are processed
        together (essentially as if they were one account).

        Args:
            accounts (set[Account]): The `Account` objects to be
                collected into weighted groups.

        Returns:
            dict[set[Account]: Decimal]: A mapping of groups of
                `Account` objects to their weights.
        """
        # We only want to build non-empty sets, so filter out weights
        # that none of the input accounts match.
        accounts_by_type = {
            type(account).__name__: set() for account in accounts
            if type(account).__name__ in self.weights
        }
        for account in accounts:
            accounts_by_type[type(account).__name__].add(account)
        grouped_accounts = {}
        for name, group in accounts_by_type.items():
            if len(group) == 1:
                account = next(iter(group))
            else:
                account = AccountGroup(group)
            grouped_accounts[account] = self.weights[name]
        return grouped_accounts

    def ungroup_transactions(self, transactions):
        """ Transforms AccountGroup keys to multiple Account keys.

        The input `transactions` dict may also have non-AccountGroup
        keys; these are included in the return dict without
        modification.

        Args:
            transactions (dict[Union[Account, AccountGroup], Money])
        """
        # Collect all AccountGroups (as opposed to ordinary Accounts):
        groups = {
            account for account in transactions
            if isinstance(account, AccountGroup)
        }
        ungrouped_transactions = {
            account: transactions[account] for account in transactions
            if account not in groups
        }
        # Flow down the group-level transaction into transactions for
        # each constituent account (this basically "flattens" the
        # transactions dict by removing the AccountGroup layer):
        for group in groups:
            ungrouped_transactions.update(
                self.transactions_for_group(
                    transactions[group], group.accounts))
        return ungrouped_transactions

    def transactions_for_group(self, total, group):
        """ Determines transactions for each account in a group.

        Accounts in `group` are treated as a group of accounts
        that share a weighting. Transactions for each account are
        determined proportionately to their maximum inflow/outflow.

        Note that this method guarantees that `total` will always be
        assigned, even if the accounts in `group` don't have
        sufficient max inflow/outflow space.

        Args:
            total (Money): The total amount to be divided up between
                accounts in the group.
            group (iterable): An `AccountGroup`, `set`, or other object
                that iterates over a group of accounts.

        Returns:
            dict[Account, Money]: A mapping of transaction amounts to
                `Account` objects.
        """
        # First, identify accounts with finite limits (and create a
        # mapping of accounts to applicable inflow or outflow limit for
        # convenience):
        finite_accounts = {}
        infinite_accounts = set()
        for account in group:
            limit = (
                account.max_inflow() if total >= 0 else
                account.max_outflow(self.timing)
            )
            if Money('-Infinity') < limit < Money('Infinity'):
                finite_accounts[account] = limit
            else:
                infinite_accounts.add(account)
        total_finite_limit = sum(finite_accounts.values(), Money(0))
        # Allocate to the finite accounts first. If we can't fill them
        # all, add proportionately to each account's limit:
        if abs(total) < abs(total_finite_limit):
            transactions = {
                account: total * (
                    finite_accounts[account] / total_finite_limit)
                for account in finite_accounts
            }
        # If we can fill each finite account, fill them and then
        # allocate the remainder equally between all infinite accounts
        # (or, if there are no infinite accounts, allocate it equally
        # between finite accounts, even though it puts them over-limit):
        else:
            transactions = finite_accounts  # fill finite accounts
            remaining_total = total - total_finite_limit
            # Allocate remainder to infinite accounts:
            if infinite_accounts:
                for account in infinite_accounts:
                    transactions[account] = (
                        remaining_total / len(infinite_accounts))
            # If there are no infinite accounts, use finite accounts:
            if not infinite_accounts:
                for account in finite_accounts:
                    transactions[account] += (
                        remaining_total / len(finite_accounts))
        return transactions

    def __call__(self, total, accounts, *args, **kwargs):
        """ Returns a dict of accounts mapped to transactions. """
        # Get an initial proposal for the transactions based on the
        # selected strategy:
        account_groups = self.group_accounts(accounts)
        grouped_transactions = super().__call__(
            total=total, weighted_accounts=account_groups, *args, **kwargs)
        transactions = self.ungroup_transactions(grouped_transactions)

        # Recursively ensure that minimum in/outflows are respected:
        transactions = self._recurse_min(
            total, accounts, transactions, *args, **kwargs)
        # Recursively ensure that maximum in/outflows are respected:
        transactions = self._recurse_max(
            total, accounts, transactions, *args, **kwargs)
        return transactions


class AccountGroup(object):
    """ Wraps one or more accounts and mimics the `Account` interface.

    This is a utility class for `TransactionStrategy`. `Accounts` that
    share a weighting can be grouped into an `AccountGroup` by a high-
    level function (e.g. `__call__`) and then seamlessly treated as a
    single account by lower-level functions (e.g. `strategy_\\*`).

    Not every `Account` method and property is provided here. For
    example, `rate` and `transactions` are not provided, as all of the
    methods of this class are simply sums of the attributes of the
    contained accounts (and sum doesn't apply sensibly to those
    attributes).
    """
    def __init__(self, *args):
        """ Inits `AccountGroup` with one or more accounts. """
        self.accounts = frozenset(*args)

    @property
    def balance(self):
        """ The sum of account balances. """
        return sum(account.balance for account in self.accounts)

    def min_outflow(self, *args, **kwargs):
        """ The sum of account `min_outflow`. """
        return sum(
            account.min_outflow(*args, **kwargs) for account in self.accounts)

    def min_inflow(self, *args, **kwargs):
        """ The sum of account `min_inflow`. """
        return sum(
            account.min_inflow(*args, **kwargs) for account in self.accounts)

    def max_outflow(self, *args, **kwargs):
        """ The sum of account `max_outflow`. """
        return sum(
            account.max_outflow(*args, **kwargs) for account in self.accounts)

    def max_inflow(self, *args, **kwargs):
        """ The sum of account `max_inflow`. """
        return sum(
            account.max_inflow(*args, **kwargs) for account in self.accounts)

    def __iter__(self):
        """ Iterates over accounts in the group. """
        for account in self.accounts:
            yield account
