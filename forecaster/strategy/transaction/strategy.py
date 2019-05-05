""" Provides Strategy-type wrappers for TransactionTraversal. """

from forecaster.accounts.debt import Debt
from forecaster.strategy.base import Strategy, strategy_method
from forecaster.strategy.debt_payment import PRIORITY_METHODS, AVALANCHE_KEY
from forecaster.strategy.transaction.base import TransactionTraversal

class TransactionStrategy(Strategy):
    """ Determines transactions to/from a group of accounts.

    This is simply a convenient wrapper for `TransactionTraversal`. It
    generates a suitable `priority` tree based on the selected strategy
    and then traverses the tree to generate transactions for the
    accounts.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.

            Acceptable keys include:

            * "TODO"
            * "TODO"
        debt_strategy (str): A key in `DebtPayment.strategies`.
            Strategies will prioritize debts according to this strategy.
            See `DebtPaymentStrategy` for more information.
        high_interest_threshold (Decimal): Debt accounts with this rate
            of interest or greater will be considered high-interest
            and those with lower interest rates will be considered
            low-interest. Some strategies use this division to determine
            which debts to prioritize ahead of investments.

            Optional. If not provided, all debts are considered
            high-interest.

    Args:
        available (dict[float, Money]): The amounts to be
            contributed to (or withdrawn from, if negative) the
            accounts, as a mapping of {timing: value} pairs.

    Returns:
        dict[Account, dict[Decimal, Money]]: A mapping of accounts to
        transactions.
    """

    # NOTE: Consider the question of how to deal with more complex
    # priority structures, e.g. where you might want to contribute first
    # to an RRSP and spousal RRSP with the same contributor (a
    # higher-earner) before contributing to another RRSP and spousal
    # RRSP with another contributor (a lower-earner).
    # That goes deeper into country-specific tax planning. Should these
    # country-specific scenarios be carved off into country-specific
    # submodules? Is there a generic way to implement this class so that
    # it allows for accounts of the same type to be divided up according
    # to come criterion while still allowing it to be useful?
    # In short: can we abandon type-based approaches entirely?

    def __init__(
            self, strategy, weights,
            debt_strategy=None, high_interest_threshold=None):
        """ Init TransactionStrategy. """
        super().__init__(strategy)

        # Store args:
        self.weights = weights
        if debt_strategy is None:
            # Default to "Avalanche" (which has superior performance to
            # Snowball, though is admittedly less popular.)
            debt_strategy = AVALANCHE_KEY
        self.debt_strategy = debt_strategy
        self.high_interest_threshold = high_interest_threshold

    @strategy_method('Ordered')
    def strategy_ordered(
            self, accounts, *args, type_specific_weights=None, **kwargs):
        """ TODO """
        # pylint: disable=unused-argument
        # We provide *args and **kwargs in case a subclass wants to
        # extend the signature for strategy methods.

        # Sort types according to the weight in `weights` and then
        # swap in priority trees for each account type (either as
        # provided in type_specific weights or according to a default
        # scheme).
        remaining_accounts = set(accounts)
        ordered_accounts = list()
        for account_type in sorted(self.weights, self.weights.get):
            # Get all accounts of this type (which haven't already been
            # assigned):
            group = {
                account for account in remaining_accounts
                # TODO: This test needs to get refined.
                # What are the keys of self.weights? Probably strs.
                # Should this be `str(type(account)) == account_type`?
                # Or should it be `isinstance(account, account_Type)`?
                # Does isinstance accomplish what we want here, or
                # should there be strict type-checking? E.g. What
                # happens to an RRSP if "RRSP" and "Account" are both
                # in `weights`? What if "Account" and
                # "LinkedLimitAccount" are both in `weights`, but _not_
                # "RRSP" - should it be lumped in with accounts of the
                # closest type?
                if str(type(account)) == account_type}
            # If there aren't any, move along:
            if not group:
                continue
            # If some type-specific treatment has been passed in for
            # this type, use that:
            if account_type in type_specific_weights:
                # If the treatment is `None`, skip this type:
                if type_specific_weights[account_type] is None:
                    continue
                # Otherwise, simply use whatever priority tree is given:
                else:
                    ordered_accounts.append(type_specific_weights[account_type])
            else:
                # If we don't have type-specific treatment, assume all
                # accounts of this type are equal-weighted:
                ordered_accounts.append({account: 1 for account in group})
        return ordered_accounts

    @strategy_method('Weighted')
    def strategy_weighted(
            self, accounts, *args, type_specific_weights=None, **kwargs):
        """ TODO """
        # pylint: disable=unused-argument
        # We provide *args and **kwargs in case a subclass wants to
        # extend the signature for strategy methods.

        # TODO: Build and return a priority tree
        pass

    def divide_debts(self, accounts):
        """ TODO """
        # Get all debts with balances owing:
        debts = {
            account for account in accounts
            if isinstance(account, Debt) and account.balance < 0}
        # If we're distinguishing high-interest from low-interest debts,
        # separate them out here:
        if self.high_interest_threshold is not None:
            low_interest_debts = {
                debt for debt in debts
                if debt.rate < self.high_interest_threshold}
            high_interest_debts = {
                debt for debt in debts if debt not in low_interest_debts}
        # Otherwise, consider all debts to be low-interest:
        else:
            low_interest_debts = debts
            high_interest_debts = set()
        return low_interest_debts, high_interest_debts

    def debt_priority(self, debts):
        """ TODO """
        # Convert the sets of debts into priority trees
        # (or assign None if there are no debts of a given type)
        if debts is not None and debts:
            # Get the method that turns a set of debts into an ordered
            # list (or other priority tree):
            priority_method = PRIORITY_METHODS[self.debt_strategy]
            priority = priority_method(debts)
        else:
            priority = None
        return priority

    def __call__(self, available, accounts, *args, **kwargs):
        """ Returns a dict of account: transaction pairs. """
        # Debts get special treatment, so separate them out here:
        low_interest_debts, high_interest_debts = self.divide_debts(accounts)
        regular_accounts = set(accounts) - high_interest_debts

        # Get priority trees for each debt. These will be inserted into
        # the final priority tree differently (in-place replacement for
        # low-interest, prepending for high-interest.)
        low_interest_priority = self.debt_priority(low_interest_debts)
        high_interest_priority = self.debt_priority(high_interest_debts)

        # Ensure that low-interest weights are properly ordered, rather
        # than assigned some default order based on their common typing.
        type_specific_weights = {Debt: low_interest_priority}

        # Get the basic priority tree based on this strategy:
        priority = super().__call__(
            regular_accounts, *args,
            type_specific_weights=type_specific_weights, **kwargs)

        # Prioritize high-interest debts repayment, if provided:
        if high_interest_priority is not None and high_interest_priority:
            # Prepend the high-interest debts, so that they are repaid
            # before any discretionary money is allocated to other
            # accounts (i.e. money other than minimums):
            priority = [high_interest_priority, priority]

        # Traverse the tree and return the results:
        traverse = TransactionTraversal(priority=priority)
        return traverse(available)
