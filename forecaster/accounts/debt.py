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
            the amount determined by `savings_rate`. If payments for
            a given year are less than this value, they are 100%
            excluded from `savings_rate`. (The total payment amount
            is not increased to match this value.) Optional.
        savings_rate (Decimal): The amount of any payment (in excess
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
        default_timing (Timing, dict[float, float]): The timings of
            payments and the weight of each payment timing. Optional.
    """

    def __init__(
            self, owner,
            balance=0, rate=0, nper=1,
            inputs=None, initial_year=None, minimum_payment=Money(0),
            living_expense=Money(0), savings_rate=1,
            accelerated_payment=Money('Infinity'),
            default_timing=None,
            **kwargs):
        """ Constructor for `Debt`. """

        # The superclass has a lot of arguments, so we're sort of stuck
        # with having a lot of arguments here (unless we hide them via
        # *args and **kwargs, but that's against the style guide for
        # this project).
        # pylint: disable=too-many-arguments

        # Declare hidden variables for properties:
        self._minimum_payment = None
        self._living_expense = None
        self._savings_rate = None
        self._accelerated_payment = None

        # Apply generic Account logic:
        super().__init__(
            owner, balance=balance, rate=rate, nper=nper,
            inputs=inputs, initial_year=initial_year,
            default_timing=default_timing, **kwargs)

        # Set up (and type-convert) Debt-specific inputs:
        self.minimum_payment = minimum_payment
        self.living_expense = living_expense
        self.savings_rate = savings_rate
        self.accelerated_payment = accelerated_payment

        # Debt must have a negative balance
        if self.balance > 0:
            self.balance = -self.balance

    @property
    def minimum_payment(self):
        """ The minimum payment required each year. """
        return self._minimum_payment

    @minimum_payment.setter
    def minimum_payment(self, val):
        self._minimum_payment = Money(val)

    @property
    def living_expense(self):
        """ Amount to repay each year, drawn from living expenses. """
        return self._living_expense

    @living_expense.setter
    def living_expense(self, val):
        self._living_expense = Money(val)

    @property
    def savings_rate(self):
        """ The percentage of repayments drawn from savings.

        This applies only to repayment amounts in excess of the
        amount defined by `living_expenses`.
        """
        return self._savings_rate

    @savings_rate.setter
    def savings_rate(self, val):
        self._savings_rate = Decimal(val)

    @property
    def accelerated_payment(self):
        """ The maximum amount to repay above the minimum payment. """
        return self._accelerated_payment

    @accelerated_payment.setter
    def accelerated_payment(self, val):
        self._accelerated_payment = Money(val)

    @property
    def min_inflow(self):
        """ The minimum annual payment on the debt. """
        return self.minimum_payment

    @property
    def max_inflow(self):
        """ The maximum annual payment on the debt. """
        return self.minimum_payment + self.accelerated_payment

    @property
    def max_outflow(self):
        """ The maximum annual withdrawals from the debt account. """
        return Money(0)

    def max_inflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The maximum amounts that can be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a `Debt`, this will return the amounts that return the
        account to a zero balance.

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            balance_limit (Money): This balance, if provided, will not
                be exceeded at year-end. Optional.
            transaction_limit (Money): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum amount that can be
                contributed at that time.
        """
        if balance_limit is None:
            # Only pay off debts until they reach $0 balance.
            # (Superclass assumes we want to contribute indefinitely.)
            balance_limit = Money(0)
        return super().max_inflows(
            timing=timing,
            balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def min_inflows(
            self, timing=None, balance_limit=None, transaction_limit=None):
        """ The minimum amounts that must be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a `Debt`, this will return the minimum payments (or the
        amounts that return the account to a zero balance, if less).

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            balance_limit (Money): This balance, if provided, will not
                be exceeded at year-end. Optional.
            transaction_limit (Money): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum amount that can be
                contributed at that time.
        """
        if balance_limit is None:
            # Only pay off debts until they reach $0 balance.
            # (Superclass assumes we want to contribute indefinitely.)
            balance_limit = Money(0)
        return super().min_inflows(
            timing=timing,
            balance_limit=balance_limit,
            transaction_limit=transaction_limit)

    def max_payment(
            self, savings_available=Money(0),
            living_expenses_available=Money('Infinity'),
            other_payments=Money(0),
            timing=None):
        """ Calculates the maximum payment amount for the year.

        Unlike `max_inflow` or `max_inflows`, this method bases its
        calculation on the amount of money available for repayment,
        split up into pools of savings, living expenses (which each may
        have limits on their use), and other payments.

        Args:
            savings_available (Money): The amount available from
                savings to repay this debt this year. Optional.
            living_expenses_available (Money): The amount available
                from living expenses to repay this debt this year.
                Optional.
            other_payments (Money): An amount of money that is
                planned for payment to this debt but which has
                not yet been recorded as an inflow. Optional.
            timing (Timing): The times at which the payments
                are to occur, along with weights for each payment.

        Returns:
            Money: The maximum payment amount that can be made to
                this account this year given the amounts available
                for repayment.
        """
        # Convert types of inputs if they aren't as expected.
        if not isinstance(savings_available, Money):
            savings_available = Money(savings_available)
        if not isinstance(living_expenses_available, Money):
            living_expenses_available = Money(living_expenses_available)
        if not isinstance(other_payments, Money):
            other_payments = Money(other_payments)

        # Set aside the base amount payable directly from living
        # expenses (i.e. before drawing down any savings)
        base_living_expense = max(
            self.living_expense - (self.inflows + other_payments),
            Money(0))
        # Apply the base living amount right up-front:
        payment = min(
            base_living_expense,
            living_expenses_available)
        living_expenses_available -= payment

        # Deal with the special cases where we withdraw 0% from
        # either savings or living expenses (to avoid DIV0 error).
        # We do the same for both savings and living expenses
        # because these impose separate limits.
        if self.savings_rate == 0:
            max_savings = Money('Infinity')
        else:
            max_savings = savings_available / self.savings_rate
        # (This could be indented, but it's much more readable
        # this way. We can incur an extra comparison if it means
        # we're being more Pythonic.)
        if self.savings_rate == 1:
            max_living = Money('Infinity')
        else:
            max_living = (
                living_expenses_available / (1 - self.savings_rate))

        # Available savings and living expenses will result in two
        # different max payments; use the lesser of the two.
        payment += min(max_savings, max_living)

        # The payment shouldn't exceed the maximum inflow:
        max_inflow = sum(self.max_inflows(timing).values())
        max_inflow -= other_payments
        payment = min(max_inflow, payment)
        return payment

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
            (amount - living_expense) * self.savings_rate
        )

        # Payments should always be non-negative:
        return max(Money(0), payment_from_savings)
