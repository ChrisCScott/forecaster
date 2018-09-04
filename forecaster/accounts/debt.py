""" A module providing the Debt class. """

from decimal import Decimal
from forecaster.accounts.base import Account
from forecaster.person import Person
from forecaster.ledger import Money

class Debt(Account):
    """ A debt with a balance and an interest rate.

    If there is an outstanding balance, the balance value will be a
    *negative* value, in line with typical accounting principles.

    Args:
        minimum_payment (Money): The minimum annual payment on the debt.
            Optional.
        reduction_rate (Decimal): The amount of any payment to be drawn
            from savings instead of living expenses. Expressed as the
            percentage that's drawn from savings (e.g. 75% drawn from
            savings would be `Decimal('0.75')`). Optional.
        accelerated_payment (Money): The maximum value which may be
            paid in a year (above `minimum_payment`) to pay off the
            balance earlier. Optional.

            Debts may be accelerated by as much as possible by setting
            this argument to `Money('Infinity')`, or non-accelerated
            by setting this argument to `Money(0)`.
    """

    def __init__(
        self, owner,
        balance=0, rate=0, nper=1,
        inputs=None, initial_year=None, minimum_payment=Money(0),
        reduction_rate=1, accelerated_payment=Money('Infinity'), **kwargs
    ):
        """ Constructor for `Debt`. """

        # The superclass has a lot of arguments, so we're sort of stuck
        # with having a lot of arguments here (unless we hide them via
        # *args and **kwargs, but that's against the style guide for
        # this project).
        # pylint: disable=too-many-arguments

        super().__init__(
            owner, balance=balance, rate=rate, nper=nper,
            inputs=inputs, initial_year=initial_year, **kwargs)
        self.minimum_payment = Money(minimum_payment)
        self.reduction_rate = Decimal(reduction_rate)
        self.accelerated_payment = Money(accelerated_payment)

        # Debt must have a negative balance
        if self.balance > 0:
            self.balance = -self.balance

    def min_inflow(self, when='end'):
        """ The minimum payment on the debt. """
        return min(
            -self.balance_at_time(when),
            max(
                self.minimum_payment - self.inflows,
                Money(0))
        )

    def max_inflow(self, when='end'):
        """ The payment at time `when` that would reduce balance to 0.

        This is in addition to any existing payments in the account,
        so if an inflow is added `max_inflow` will be reduced.

        Example::

                debt = Debt(-100)
                debt.maximum_payment('start') == Money(100)  # True
                debt.add_transaction(100, 'start')
                debt.maximum_payment('start') == 0  # True

        """
        return min(
            -self.balance_at_time(when),
            max(
                self.minimum_payment
                + self.accelerated_payment
                - self.inflows,
                Money(0))
        )
