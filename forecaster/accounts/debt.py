""" A module providing the Debt class. """

from decimal import Decimal
from forecaster.accounts.base import Account
from forecaster.ledger import Money

class Debt(Account):
    """ A debt with a balance and an interest rate.

    If there is an outstanding balance, the balance value will be a
    *negative* value, in line with typical accounting principles.

    Args:
        minimum_payment (Money): The minimum annual payment on the debt.
            Optional.
        living_expense (Money): The amount paid annually out of living
            expenses. This portion of payments is excluded from
            the amount determined by `reduction_rate`. If payments for
            a given year are less than this value, they are 100%
            excluded from `reduction_rate`. (The total payment amount
            is not increased to match this value.) Optional.
        reduction_rate (Decimal): The amount of any payment (in excess
            of `living_expense`) to be drawn from savings instead of
            living expenses. Expressed as the percentage that's drawn
            from savings (e.g. 75% drawn from savings would be
            `Decimal('0.75')`). Optional.
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
        living_expense=Money(0), reduction_rate=1,
        accelerated_payment=Money('Infinity'),
        **kwargs
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
        self.living_expense = Money(living_expense)
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

    def payment(
        self, savings_available=Money(0),
        living_expenses_available=Money('Infinity'),
        other_payments=Money(0),
        when='end'
    ):
        """ Calculates the maximum payment amount for the year.
        
        Args:
            savings_available (Money): The amount available from
                savings to repay this debt this year. Optional.
            living_expenses (Money): The amount available from
                living expenses to repay this debt this year.
                Optional.
            other_payments (Money): An amount of money that is
                planned for payment to this debt but which has
                not yet been recorded as an inflow. Optional.
            when (str, Decimal): The date at which the payment
                is to occur.

        Returns:
            Money: The maximum payment amount that can be made to
                this account this year given the amounts available
                for repayment.
        """
        # Set aside the base amount payable directly from living
        # expenses (i.e. before drawing down any savings)
        base_living_expense = max(
            self.living_expense - (self.inflows + other_payments),
            Money(0)
        )
        # Apply the base living amount right up-front:
        payment = min(
            base_living_expense,
            living_expenses_available
        )
        living_expenses_available -= payment

        # Deal with the special cases where we withdraw 0% from
        # either savings or living expenses (to avoid DIV0 error).
        # We do the same for both savings and living expenses
        # because these impose separate limits.
        if self.reduction_rate == 0:
            max_savings = Money('Infinity')
        else:
            max_savings = savings_available / self.reduction_rate
        # (This could be indented, but it's much more readable
        # this way. We can incur an extra comparison if it means
        # we're being more Pythonic.)
        if self.reduction_rate == 1:
            max_living = Money('Infinity')
        else:
            max_living = (
                living_expenses_available / (1 - self.reduction_rate))

        # Available savings and living expenses will result in two
        # different max payments; use the lesser of the two.
        payment += min(max_savings, max_living)

        # The payment shouldn't exceed the maximum inflow:
        return min(
            self.max_inflow(when) - other_payments,
            payment
        )

    def payment_from_savings(self, amount=None, base=Money(0)):
        """ The amount of annual payments made from savings.

        NOTE: This method is not useful if called on a single
        transation (if there are multiple inflows for the year)
        because the `living_expense` amount applies on an annual
        basis against all transactions, not each transaction
        individually. Be careful!

        Args:
            amount (Money): The amount paid against this debt in the
                year.
                Optional. If not provided, uses current inflows for
                the year.
            base (Money): Amounts already paid against this debt in
                the year (and which have thus reduced the living
                expenses portion available to be claimed.)
                Optional.
        
        Returns:
            Money: The amount paid from savings for the year.
        """
        if amount is None:
            amount = self.inflows
        # Determine how much of this payment is eligible to be
        # wholly included in living expenses (after accounting
        # for past payments, i.e. `base`)
        living_expense = max(self.living_expense - base, Money(0))
        payment_from_savings = (
            (amount - living_expense) * self.reduction_rate
        )

        # Payments should always be non-negative:
        return max(Money(0), payment_from_savings)
