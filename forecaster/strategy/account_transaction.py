""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.

`DebtPaymentStrategy` is a related `Debt`-specific class.
"""

import collections
from decimal import Decimal
from forecaster.ledger import Money
from forecaster.strategy.base import Strategy, strategy_method


def contribution_group(account):
    """ Returns a set of accounts with shared contribution room. """
    if hasattr(account, "max_inflow_link"):
        return account.max_inflow_link.group
    else:
        return {account}

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

    Attributes:
        accounts (set[Account]): The member accounts of the
            `AccountGroup`.
        contribution_groups (set[set[Account]]): The members of the
            `AccountGroup` reorganized into disjoint sets of
            contribution groups. Each contribution group shares common
            `max_inflow` property values.
    """
    def __init__(self, *args):
        """ Inits `AccountGroup` with one or more accounts. """
        self.accounts = frozenset(*args)
        self.contribution_groups = frozenset(
            frozenset(
                contribution_group(account).intersection(self.accounts))
            for account in self)

    @property
    def balance(self):
        """ The sum of account balances. """
        return sum(account.balance for account in self)

    @property
    def min_outflow(self):
        """ The sum of account `min_outflow`. """
        return sum(
            account.min_outflow for account in self)

    @property
    def min_inflow(self):
        """ The sum of account `min_inflow`. """
        return sum(
            account.min_inflow for account in self)

    @property
    def max_outflow(self):
        """ The sum of account `max_outflow`. """
        return sum(
            account.max_outflow for account in self)

    @property
    def max_inflow(self):
        """ The sum of account `max_inflow`.

        This method respects contribution groups, and will not double-
        count the contribution room of multiple accounts in the same
        contribution group.
        """
        # For each group, pull an element out at random (since they
        # should all share the same max_inflow)
        return sum(
            next(iter(group)).max_inflow
            for group in self.contribution_groups)

    def min_inflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The combined minimum inflows for all accounts in the group. """
        return self._transaction_limit(
            method_name="min_inflows", is_max=False,
            timing=timing, balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def max_inflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The combined maximum inflows for all accounts in the group.

        This method respects contribution groups, and will not double-
        count the contribution room of multiple accounts in the same
        contribution group.
        """
        accounts = set()
        # To be contribution group-aware, pull out one account for
        # each contribution group:
        for group in self.contribution_groups:
            accounts.add(next(iter(group)))
        return self._transaction_limit(
            method_name="max_inflows", is_max=False,
            accounts=accounts,
            timing=timing, balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def min_outflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The combined minimum outflows for all accounts in the group. """
        return self._transaction_limit(
            method_name="min_outflows", is_max=False,
            timing=timing, balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def max_outflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The combined maximum outflows for all accounts in the group. """
        return self._transaction_limit(
            method_name="max_outflows", is_max=True,
            timing=timing, balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def _transaction_limit(
            self, method_name, is_max, accounts=None,
            timing=None, balance_limit=None, transaction_limit=None):
        """ The combined max/min in/outflows for all accounts.

        Args:
            method_name (str): The name of an attribute of each account
                which is callable with the signature
                `method(timing, balance_limit), transaction_limit)`
                and returns a `dict[Decimal, Money]`
            is_max (Boolean): True if we're finding max in/outflows,
                otherwise we find min in/outflows.
            accounts (set): The accounts to iterate over. Optional.
                Defaults to all accounts in the group.
            timing (Timing): Same arg as in `max_inflows`
            balance_limit (Money): Same arg as in `max_inflows`
            transaction_limit (Money): Same arg as in `max_inflows`
        """
        if accounts is None:
            accounts = self.accounts
        # Get the min/max transactions for each account and store the
        # sum of those (across all accounts) in `transactions`:
        transactions = collections.defaultdict(lambda: Money(0))
        for account in accounts:
            limit_method = getattr(account, method_name)
            account_transactions = limit_method(
                timing=timing, balance_limit=balance_limit,
                # NOTE: It's useful to specify `transaction_limit` here,
                # even though we scale down later, because accounts can
                # provide an infinite limit which would be harder to
                # scale.
                transaction_limit=transaction_limit)
            for when, value in account_transactions.items():
                transactions[when] += value
        # Ensure that `transaction_limit` is respected; scale down the
        # transactions if necessary.
        if transaction_limit is not None:
            total_transactions = abs(sum(transactions.values()))
            transaction_limit_abs = abs(transaction_limit)
            if (
                    is_max and total_transactions > transaction_limit_abs or
                    not is_max and total_transactions < transaction_limit_abs
            ):
                scaling_factor = transaction_limit_abs / total_transactions
                transactions = {
                    when: value * scaling_factor
                    for when, value in transactions.items()}
        # TODO: Do the same for `balance_limit`.
        # NOTE: If we scale each transaction equally, we can assume that
        # change in balance varies linearly as we scale transactions.
        # One obstacle: Since transactions aren't recorded against each
        # account, it's hard to tell what balance each account will
        # reach under these transactions. We may need to add a
        # `balance_after_transactions` that ingests a transactions dict.
        return transactions

    def get_type(self):
        """ Gets the type of a random contained `Account`. """
        return type(next(iter(self)))

    def __iter__(self):
        """ Iterates over accounts in the group. """
        for account in self.accounts:
            yield account


class AccountTransactionStrategy(Strategy):
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
    def __init__(self, strategy, weights):
        """ Constructor for TransactionStrategy. """
        super().__init__(strategy)

        self.weights = weights

        self._param_check(self.weights, 'weights', dict)
        for key, val in self.weights.items():
            self._param_check(key, 'account type (key)', str)
            # TODO: Check that val is Decimal-convertible instead of
            # a rigid type check?
            self._param_check(
                val, 'account weight (value)', (Decimal, float, int))

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
            dict[Union[Account, AccountGroup], dict[Decimal, Money]]
            pairs. The keys are a subset of the input `accounts` keys
            and the values are the corresponding transactions for that
            account (as `when: value` pairs).
        """
        # We provide *args and **kwargs to maintain a consistent
        # interface between strategy methods.
        # pylint: disable=unused-argument

        # Build a sorted list based on the account_set: weight pairings:
        accounts_ordered = sorted(weighted_accounts, key=weighted_accounts.get)

        transactions = {}

        # Now fill up (or drain) the accounts in order of priority
        # until we hit the total.
        for account in accounts_ordered:
            if total > 0:
                # Add as much inflow as we can, up to the amount we have
                # left available.
                transactions[account] = account.max_inflows(
                    transaction_limit=total)
            elif total < 0:
                # Add as much outflow as we can, up to the amount we
                # have left to withdraw:
                transactions[account] = account.max_outflows(
                    transaction_limit=total)
            else:
                # If we have no money left to withdraw/contribute, then
                # we're done! Return now to avoid unnecessary iterations
                # NOTE: Not all accounts are necessarily used as keys!
                return transactions
            total -= sum(transactions[account].values())

        return transactions

    @strategy_method('Weighted')
    def strategy_weighted(self, total, weighted_accounts, *_, **__):
        """ Assigns transactions proportionately to accounts' weights.

        Args:
            total (Money): The sum of transactions (positive, for
                contributions, or negative, for withdrawals) across
                all accounts.
            weighted_accounts (dict[Union[Account, AccountGroup],
                Decimal]): Accounts to contribute to (or withdraw from)
                mapped to weights.

        Returns:
            dict[Union[Account, AccountGroup], dict[Decimal, Money]]
            pairs. The keys are a subset of the input `accounts` keys
            and the values are the corresponding transactions for that
            account (as `when: value` pairs).
        """
        # Due to recursion, there's no guarantee that weights will sum
        # to 1, so we'll need to normalize weights.
        normalization = sum(weighted_accounts.values())

        transactions = {}
        limited_accounts = {}

        # Determine contributions/withdrawals for each account set based
        # on its associated weight:
        for account, weight in weighted_accounts.items():
            # Determine the amount to be allocated to this account:
            value = total * weight / normalization
            # In a perfect world we could simply assign weighted
            # portions of `value` for keys in `account.default_timing`,
            # but AccountGroup doesn't have a `default_timing` attribute
            # so we'll use `max_inflows`/`max_outflows` as appropriate.
            if total > 0:
                transactions[account] = account.max_inflows(
                    transaction_limit=value)
            elif total < 0:
                transactions[account] = account.max_outflows(
                    transaction_limit=value)

            # Using `max_inflows` or `max_outflows` creates a problem:
            # We might assign less than `total` if it exceeds an
            # account's max! Determine whether this has happened for
            # any accounts...
            amount_added = sum(transactions[account].values())
            if value != amount_added:
                limited_accounts[account] = amount_added

        # ... and if it has, recurse on the remaining accounts.
        if limited_accounts:
            non_limited_accounts = set(weighted_accounts.keys()).difference(
                limited_accounts.keys())
            weighted_accounts = {
                account: weighted_accounts[account]
                for account in non_limited_accounts}
            total -= sum(limited_accounts.values())
            recurse_transactions = self.strategy_weighted(
                total=total, weighted_accounts=weighted_accounts)
            # Overwrite any non-limited accounts with the results of the
            # recursion. Limited accounts remain as-is.
            transactions.update(recurse_transactions)


        return transactions

    def _recurse_limit(
            self, total, accounts, transactions, method_name, is_min,
            *args, **kwargs
        ):
        """ Recursively assigns min/max inflows/outflows to accounts. """
        # Check to see whether any accounts have transactions that don't
        # meet the min/max limit provided by `method_name`.
        min_transactions = {}  # Find this for every account
        override_transactions = {}  # Only for accts. where min not met
        for account in accounts:
            # Grab the appropriate bound method for this account:
            limit_method = getattr(account, method_name)
            # Use the timing in `transactions` if available:
            if account in transactions:
                min_transactions[account] = limit_method(
                    timing=transactions[account])
                # If min aren't met by `transactions`, we'll want to
                # override them. Record that here:
                total_limit = abs(sum(min_transactions[account].values()))
                total_trans = abs(sum(transactions[account].values()))
                if (
                        (is_min and total_limit > total_trans)
                        or (not is_min and total_limit < total_trans)
                    ):
                    override_transactions[account] = min_transactions[account]

        # If there are no accounts that need to be tweaked, we're done.
        if not override_transactions:
            return transactions

        # If we found some such accounts, set their transaction amounts
        # manually and recurse onto the remaining accounts.

        # Identify all accounts that haven't been manually set yet:
        remaining_accounts = {
            account for account in accounts
            if account not in override_transactions}

        # Determine the amount remaining to be allocated:
        remaining_total = total - sum(
            sum(override_transactions[account].values())
            for account in override_transactions)

        # For minimum transactions only:
        # If there's no `remaining_total` left (or if it's overshot
        # total and thus has a different sign) then there's no room left
        # to recurse on the strategy. Simply allocate the minimum
        # inflow/outflow for each remaining account and terminate:
        # NOTE: Consider whether this behaviour should be deactivatable.
        # It's not necessarily desirable to allocate more than `total`,
        # even if required by the chosen minimum transactions.
        if (is_min and (remaining_total == 0 or total / remaining_total < 0)):
            for account in remaining_accounts:
                limit_method = getattr(account, method_name)
                override_transactions[account] = limit_method()
            return override_transactions

        # Otherwise, if there's still money to be allocated,
        # recurse onto the remaining accounts:
        remaining_transactions = self.__call__(
            total=remaining_total,
            accounts=remaining_accounts,
            *args, **kwargs)

        override_transactions.update(remaining_transactions)
        return override_transactions


    def _recurse_min(
            self, total, accounts, transactions, *args, **kwargs):
        """ Recursively assigns minimum inflows/outflows to accounts. """
        if total >= 0:
            method_name = "min_inflows"
        else:
            method_name = "min_outflows"
        return self._recurse_limit(
            total, accounts, transactions,
            method_name=method_name, is_min=True,
            *args, **kwargs)

    def _recurse_max(
            self, total, accounts, transactions, *args, **kwargs):
        """ Recursively assigns minimum inflows/outflows to accounts. """
        if total >= 0:
            method_name = "max_inflows"
        else:
            method_name = "max_outflows"
        return self._recurse_limit(
            total, accounts, transactions,
            method_name=method_name, is_min=False,
            *args, **kwargs)

    def _group_by_contribution_group(self, accounts):
        """ Groups together accounts belonging to a contribution group.

        Args:
            accounts (set[Account]): The `Account` objects to be
                combined into zero or more AccountGroups.

        Returns:
            set[Union[Account, AccountGroup]]: A version of `accounts`
                where any accounts belonging to the same contribution
                group are combined into a single `AccountGroup` object.

                Accounts not sharing a contribution group
        """
        contribution_groups = set()
        ungrouped_accounts = set()
        # We want to bundle contribution groups into AccountGroup
        # objects, but we want to limit those groups to accounts
        # included in `accounts`.
        for account in accounts:
            group = frozenset(contribution_group(account))
            if len(group) > 1:
                # If the account is linked to other accounts, record its
                # group (to be agglomerated into an AccountGroup later):
                contribution_groups.add(group)
            else:
                # Otherwise just store the account on its own:
                ungrouped_accounts.add(account)
        # The final set includes both contribution groups (bundled into
        # account-like `AccountGroup` objects) and unmodified `Account`
        # objects.
        grouped_accounts = {
            AccountGroup(group) for group in contribution_groups
        }.union(ungrouped_accounts)
        return grouped_accounts

    def _group_by_type(self, accounts):
        """ Groups accounts by type into AccountGroups.

        Each AccountGroup contains one or more accounts which have the
        same type. Input accounts may themselves be AccountGroup
        objects.

        Args:
            accounts (set[Union[Account, AccountGroup]]): The `Account`
                objects to be collected into weighted groups.

        Returns:
            set[Union[Account, AccountGroup]]: The input `accounts` set,
                modified so that accounts with the same type are grouped
                into `AccountGroup` objects.
        """
        accounts_by_type = collections.defaultdict(set)
        for account in accounts:
            name = self._get_weights_key(account)
            if name in self.weights:
                accounts_by_type[name].add(account)

        grouped_accounts = set()
        for name, group in accounts_by_type.items():
            if len(group) == 1:
                # Leave accounts with unique type ungrouped:
                account = next(iter(group))
            else:
                # Group any set of 2 or more accounts:
                account = AccountGroup(group)
            grouped_accounts.add(account)
        return grouped_accounts

    def _group_accounts(self, accounts, total):
        """ Groups accounts into AccountGroups.

        Each AccountGroup contains one or more accounts which are
        processed together (essentially as if they were one account).

        Args:
            accounts (set[Account]): The `Account` objects to be
                collected into groups.

        Returns:
            set[Union[Account, AccountGroup]]: The input `accounts` set,
                modified so that (some) accounts are grouped into
                `AccountGroup` objects.
        """
        # Don't wrap any accounts that are already grouped:
        grouped_accounts = {
            account for account in accounts
            if isinstance(account, AccountGroup)
        }
        accounts = accounts.difference(grouped_accounts)

        # Only group by contribution group if we're actually
        # contributing:
        if total > 0:
            accounts = self._group_by_contribution_group(accounts)
        # Always group by type:
        accounts = self._group_by_type(accounts)

        return accounts.union(grouped_accounts)

    def _weight_accounts(self, accounts):
        """ Maps accounts to a dict of `{account: weight}` pairs.

        Args:
            accounts (set[Union[Account, AccountGroup]]): The `Account`
                (and/or `AccountGroup`) objects to be mapped to weights.

        Returns:
            dict[set[Union[Account, AccountGroup]]: Decimal]: A mapping
                of groups of `Account` objects to their weights.
        """
        weighted_accounts = {}
        for account in accounts:
            name = self._get_weights_key(account)
            weighted_accounts[account] = self.weights[name]

        return weighted_accounts

    def _ungroup_transactions(self, transactions):
        """ Transforms AccountGroup keys to multiple Account keys.

        The input `transactions` dict may also have non-AccountGroup
        keys; these are included in the return dict without
        modification.

        `AccountGroup` objects may be nested (that is, an `AccountGroup`
        object may contain another `AccountGroup` object). This method
        recursively flattens such hierarchies, so the output is
        guaranteed not to contain any `AccountGroup` objects as keys.

        Args:
            transactions (dict[Account], Money])
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
        # each constituent account. We recurse onto the results, which
        # effectively "flattens" the transactions dict by removing any
        # further AccountGroup layers:
        for group in groups:
            transactions_for_group = self._transactions_for_accounts(
                transactions[group], group.accounts)
            # Recurse onto any nested AccountGroup objects:
            flattened_transactions = self._ungroup_transactions(
                transactions_for_group)
            ungrouped_transactions.update(flattened_transactions)
        return ungrouped_transactions

    def _transactions_for_accounts(self, transactions, group):
        """ Determines transactions for each account in a group.

        Accounts in `group` are treated as a group of accounts
        that share a weighting. Transactions for each account are
        determined proportionately to their maximum inflow/outflow.

        Note that this method guarantees that `total` will always be
        assigned, even if the accounts in `group` don't have
        sufficient max inflow/outflow space.

        Args:
            transactions (Money): The transactions allocated to the
                group, to be divided up between accounts in the group.
            group (iterable): An `AccountGroup`, `set`, or other object
                that iterates over a group of accounts.

        Returns:
            dict[Account, Money]: A mapping of transaction amounts to
                `Account` objects.
        """
        # First, identify accounts with finite limits (and create a
        # mapping of accounts to applicable inflow or outflow limit for
        # convenience):
        finite_accounts_trans = {}
        finite_accounts_total = {}
        infinite_accounts = set()
        total = sum(transactions.values())
        for account in group:
            # Identify max inflows or outflows, as appropriate:
            if total >= 0:
                limit = account.max_inflows(timing=transactions)
            else:
                limit = account.max_outflows(timing=transactions)
            # If the account has a finite limit, store its maximum
            # in/outflows for later reference.
            total_limit = sum(limit.values())
            if Money('-Infinity') < total_limit < Money('Infinity'):
                finite_accounts_trans[account] = limit
                finite_accounts_total[account] = total_limit
            else:
                infinite_accounts.add(account)

        # For N accounts, try to allocate 1/N to each infinite account
        # and divide the remainder between finite accounts
        # proportionately to their limits.
        # Try to contribute to finite accounts first:
        total_finite_limit = sum(finite_accounts_total.values(), Money(0))
        finite_total = total * (len(finite_accounts_trans) / len(group))
        # First, if we can't fill them all, add proportionately to each
        # account's limit:
        if abs(total) < abs(total_finite_limit):
            _transactions = {}
            for account in finite_accounts_trans:
                # Determine what proportion of the total transactions should
                # go to each account based on the relative sizes of their
                # limits:
                weight = (
                    (finite_accounts_total[account] / total_finite_limit)
                    * (finite_total / total))
                # Now scale each transaction for each account based on
                # its weight:
                _transactions[account] = {
                    when: value * weight
                    for when, value in transactions.items()}
        # If we _can_ fill each finite account, fill them and then
        # allocate the remainder equally between all infinite accounts
        # (or, if there are no infinite accounts, allocate it equally
        # between finite accounts, even though it puts them over-limit):
        else:
            _transactions = finite_accounts_trans  # fill finite accounts
            remaining_total = total - total_finite_limit
            num_transactions = len(transactions)
            # Allocate remainder to infinite accounts:
            if infinite_accounts:
                num_infinite = len(infinite_accounts)
                for account in infinite_accounts:
                    _transactions[account] = {
                        when: remaining_total
                              / (num_infinite * num_transactions)
                        for when in transactions}
            # If there are no infinite accounts, divide evenly between
            # the finite accounts:
            # TODO: Should we over-contribute to finite accounts?
            # I doubt there is ever a reason to assign more than the max
            if not infinite_accounts:
                num_finite = len(finite_accounts_trans)
                for account in finite_accounts_trans:
                    for when in _transactions[account]:
                        _transactions[account][when] += (
                            remaining_total / (num_finite * num_transactions))
        return _transactions

    def _get_weights_key(self, account):
        """ Retrieves the `weights` key that `account` corresponds to.

        The key for an `AccountGroup` is determined based on its
        member accounts.

        Args:
            account (Union[Account, AccountGroup]): An `Account`-like
                object.

        Returns:
            str: A key that may be found in `weights`. The key is not
                guaranteed to actually be in the `weights` dict of this
                particular `TransactionStrategy`, but if a weight is
                given for this kind of account then this would be its
                key.
        """
        return self._get_representative_type(account).__name__

    def _get_representative_type(self, account):
        """ The representative type of `account`.

        The representative type of an `Account` is simply the
        `Account`'s type.

        The representative type for an `AccountGroup` is determined
        based on the types of its member accounts. This is determined
        recursively in the event that any members are also
        `AccountGroup` objects.

        Args:
            account (Union[Account, AccountGroup]): An `Account`-like
                object.

        Returns:
            type: The representative type of `account`.

        Raises:
            ValueError: Accounts in an AccountGroup must share a common
                superclass.
        """
        if isinstance(account, AccountGroup):
            account_types = {
                self._get_representative_type(member) for member in account
            }
            if len(account_types) == 1:
                return account_types.pop()
            else:
                # If the members aren't all of the same type, return the
                # greatest common class:
                classes = [
                    type(account_type).mro() for account_type in account_types]
                for account_type in classes[0]:
                    if all(account_type in mro for mro in classes):
                        return account_type
                # If we can't identify a greatest common class, raise an
                # error.
                raise ValueError(
                    'TransactionStrategy: Accounts in an AccountGroup must ' +
                    'share a common superclass.')
        else:
            return type(account)

    def __call__(self, total, accounts, *args, **kwargs):
        """ Returns a dict of accounts mapped to transactions. """
        # First, wrap the groups into AccountGroup objects (where
        # appropriate):
        account_groups = self._group_accounts(accounts, total)
        # Then map accounts to their weights:
        weighted_accounts = self._weight_accounts(account_groups)
        # Now map the accounts (or groups thereof) to transactions:
        transactions = super().__call__(
            total=total, weighted_accounts=weighted_accounts, *args, **kwargs)

        # That only gives us an initial proposal; we need to ensure that
        # any restrictions on inflows/outflows are being respected.
        # Recursively ensure that minimum in/outflows are respected:
        transactions = self._recurse_min(
            total, account_groups, transactions, *args, **kwargs)
        # Recursively ensure that maximum in/outflows are respected:
        transactions = self._recurse_max(
            total, account_groups, transactions, *args, **kwargs)

        # Once we've found transactions that satisfy all constraints,
        # flatten the results to {account: transaction} pairs by
        # eliminating any groups and flowing down transactions to the
        # accounts they contain:
        transactions = self._ungroup_transactions(transactions)
        return transactions
