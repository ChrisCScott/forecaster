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

    @strategy_method('Ordered')
    def strategy_ordered(self, total, account_sets, *args, **kwargs):
        """ Contributes/withdraws in order of account priority.

        The account with the lowest-valued priority is contributed to
        (or withdrawn from) first. Thus, if three accounts have weights
        1, 2, and 3, then account with weight 1 will go first, followed
        by 2, then 3.

        Args:
            total (Money): The total amount to be contributed/withdrawn.
            account_sets (dict[set[Account], Decimal]): `{set: weight}`
                pairs, where each set has one or more `Account` objects.
                `Account` objects in the same set are handled as a
                group, as if they were one `Account`.

        Returns:
            dict[Account, Money]: A mapping of transaction amounts to
                `Account` objects.
        """
        # We provide *args and **kwargs to maintain a consistent
        # interface between strategy methods.
        # pylint: disable=unused-argument

        # Build a sorted list based on the account_set: weight pairings:
        account_sets_ordered = sorted(account_sets, key=account_sets.get)

        transactions = {}

        # Now fill up (or drain) the accounts in order of priority
        # until we hit the total.
        for account_set in account_sets_ordered:
            if total >= 0:
                set_total = min(total, sum(
                    (account.max_inflow() for account in account_set),
                    Money(0))
                )
            else:
                set_total = max(total, sum(
                    (
                        account.max_outflow(self.timing)
                        for account in account_set
                    ), Money(0))
                )
            transactions_for_set = self.transactions_for_set(
                set_total, account_set)
            transactions.update(transactions_for_set)
            total -= sum(transactions_for_set.values())

        return transactions

    @strategy_method('Weighted')
    def strategy_weighted(self, total, account_sets, *args, **kwargs):
        """ Contributes to/withdraws from all accounts based on weights. """
        # We provide *args and **kwargs to maintain a consistent
        # interface between strategy methods.
        # pylint: disable=unused-argument

        # Due to recursion, there's no guarantee that weights will sum
        # to 1, so we'll need to normalize weights.
        normalization = sum(account_sets.values())

        transactions = {}

        # Determine contributions/withdrawals for each account set based
        # on its associated weight:
        for account_set, weight in account_sets.items():
            transactions_for_set = self.transactions_for_set(
                total * weight / normalization, account_set)
            transactions.update(transactions_for_set)

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
        remaining_account_sets = (
            self.map_accounts_to_weighted_sets(remaining_accounts))
        remaining_transactions = super().__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            account_sets=remaining_account_sets,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # Now recurse to ensure that non of the non-maxed accounts have
        # exceeded their max after applying the strategy.
        return self._recurse_min(
            remaining_total, remaining_accounts, transactions,
            *args, **kwargs)

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
        remaining_accounts = {
            account for account in accounts
            if account not in override_accounts}

        # Determine the amount to be allocated to the non-maxed accounts:
        remaining_total = total - sum(override_accounts.values())

        # Reassign money to non-maxed accounts according to the selected
        # strategy.
        remaining_account_sets = (
            self.map_accounts_to_weighted_sets(remaining_accounts))
        remaining_transactions = super().__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            account_sets=remaining_account_sets,
            *args, **kwargs)

        transactions.update(remaining_transactions)

        # Now recurse to ensure that non of the non-maxed accounts have
        # exceeded their max after applying the strategy.
        return self._recurse_max(
            remaining_total, remaining_accounts, transactions,
            *args, **kwargs)

    def map_accounts_to_weighted_sets(self, accounts):
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
        account_types = {
            type(account).__name__ for account in accounts
            if type(account).__name__ in self.weights
        }
        # We're using a set as a key, but sets aren't hashable.
        # frozenset is hashable, so use that instead.
        return {
            frozenset(
                account for account in accounts
                if type(account).__name__ == key
            ):
            self.weights[key] for key in account_types
        }

    def transactions_for_set(self, total, account_set):
        """ Determines transactions for each account in a group.

        Accounts in `account_set` are treated as a group of accounts
        that share a weighting. Transactions for each account are
        determined proportionately to their maximum inflow/outflow.

        Note that this method guarantees that `total` will always be
        assigned, even if the accounts in `account_set` don't have
        sufficient max inflow/outflow space.

        Returns:
            dict[Account, Money]: A mapping of transaction amounts to
                `Account` objects.
        """
        # First, deal with accounts with finite limits:
        finite_accounts = {}
        infinite_accounts = set()
        for account in account_set:
            limit = (
                account.max_inflow() if total >= 0 else
                account.max_outflow(self.timing)
            )
            if Money('-Infinity') < limit < Money('Infinity'):
                finite_accounts[account] = limit
            else:
                infinite_accounts.add(account)
        total_finite_limit = sum(finite_accounts.values(), Money(0))
        # Allocate as much as we can to the finite accounts; if we can't
        # fill them all, add proportionately to each account's limit:
        if abs(total) < abs(total_finite_limit):
            transactions = {
                account: total * (
                    finite_accounts[account] / total_finite_limit)
                for account in finite_accounts
            }
        # If we can fill each finite account, allocate the remainder
        # equally between all infinite accounts.
        else:
            transactions = finite_accounts
            remaining_total = total - total_finite_limit
            for account in infinite_accounts:
                transactions[account] = (
                    remaining_total / len(infinite_accounts))
            # If there aren't any accounts with infinite room, dump the
            # remainder equally into each of the those accounts:
            if not infinite_accounts:
                for account in finite_accounts:
                    transactions[account] += (
                        remaining_total / len(finite_accounts))
        return transactions

    def __call__(self, total, accounts, *args, **kwargs):
        """ Returns a dict of accounts mapped to transactions. """
        # Get an initial proposal for the transactions based on the
        # selected strategy:
        account_sets = self.map_accounts_to_weighted_sets(accounts)
        transactions = super().__call__(
            total=total, account_sets=account_sets, *args, **kwargs)
        # Recursively ensure that minimum in/outflows are respected:
        transactions = self._recurse_min(
            total, accounts, transactions, *args, **kwargs)
        # Recursively ensure that maximum in/outflows are respected:
        transactions = self._recurse_max(
            total, accounts, transactions, *args, **kwargs)
        return transactions
