""" Provides classes for determining where and when transactions occur.

These include the generic `TransactionStrategy` (which handles both
contributions and withdrawals to all types of accounts) and
`DebtPaymentStrategy` (which handles inflows to Debt accounts
specifically).
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

            * "Snowball"
            * "Avalanche"

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
