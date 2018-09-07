""" Provides a class for determining schedules of debt payments. """

from decimal import Decimal
from forecaster.strategy.base import Strategy, strategy_method


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

    def _assign_available(self, debt, transactions, available):
        """ Proposes a transaction based on savings available.
        
        Args:
            debt (Debt): A debt account.
            transactions (dict[Debt, Money]): Maps debts to
                payments.
                `debt` must be a valid key. Its corresponding
                value may be mutated by this method to reflect
                an increased payment.
            available (Money): The amount available to repay
                debt from savings.

        Returns:
            Money: The amount of savings (`available`) consumed
                by the increased payment proposed by this
                method (via `transactions`).
        """
        # Keep track of how much we were paying before adding
        # a further payment amount:
        initial_payment = transactions[debt] + debt.inflows

        # Determine how much debt we can repay given how much money
        # is available:
        transactions[debt] += debt.payment(
            savings_available=available,
            other_payments=transactions[debt],
            when=self.timing
        )

        # Return the portion of `available` (i.e. savings)
        # consumed by this transaction.
        return debt.payment_from_savings(
            amount=transactions[debt] - initial_payment,
            base=initial_payment
        )

    def _assign_minimums(self, debts, transactions):
        """ Proposes transactions based on minimum payments.
        
        Args:
            debts (set[Debt]): A set of debt accounts.
            transactions (dict[Debt, Money]): Maps debts to
                payments. May be empty. Will be mutated.
            available (Money): The amount available to repay
                debt from savings.

        Returns:
            Money: The amount of savings consumed by the
                payments proposed by this method.
                (Proposed payments are returned via
                `transactions`).
        """
        # Figure out the additional inflows necessary to meet minimum
        # payment obligations:
        payments = {
            debt: debt.min_inflow(when=self.timing)
            for debt in debts
        }

        # Reduce payments by any already-pending payments (if they exist).
        # If they don't exist, add an entry so that the following calls
        # to transaction[debt] don't fail:
        for debt in debts:
            if debt not in transactions:
                transactions[debt] = 0
            else:
                payments[debt] -= transactions[debt]

        # Figure out the amount of savings consumed by the proposed
        # payments:
        savings_used = sum(
            debt.payment_from_savings(
                amount=payments[debt],
                base=transactions[debt] + debt.inflows)
            for debt in debts
        )

        # Mutate transactions to ensure that each debt meets its minimum
        # payment obligation.
        for debt in debts:
            transactions[debt] += payments[debt]

        return savings_used

    # pylint: disable=W0613
    @strategy_method('Snowball')
    def strategy_snowball(self, available, debts, *args, **kwargs):
        """ Pays off the smallest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {}
        # Reduce the available amount accordingly, but don't go negative.
        available -= min(
            self._assign_minimums(debts, transactions),
            available)

        # Increase contributions to debts in order of their balance
        # (smallest first):
        for debt in sorted(
            debts, key=lambda x: abs(x.balance), reverse=False
        ):
            available -= self._assign_available(
                debt, transactions, available)

        return transactions

    @strategy_method('Avalanche')
    def strategy_avalanche(self, available, debts, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {}
        # Reduce the available amount accordingly, but don't go negative.
        available -= min(
            self._assign_minimums(debts, transactions),
            available)

        # Now we increase contributions to debts in order of interest
        # rate (largest rate first):
        for debt in sorted(
            debts, key=lambda x: x.rate, reverse=True
        ):
            available -= self._assign_available(
                debt, transactions, available)

        return transactions

    # Overriding __call__ solely for intellisense purposes.
    # pylint: disable=W0235
    def __call__(self, available, debts, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(available, debts, *args, **kwargs)
