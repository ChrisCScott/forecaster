""" A module providing the Debt class. """

from forecaster.accounts.base import Account
from forecaster.money import Money

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
            # Inherited args:
            self, owner, balance=0, rate=0, nper=1,
            inputs=None, initial_year=None,
            # New args:
            minimum_payment=Money(0), accelerated_payment=Money('Infinity'),
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
        self._accelerated_payment = None

        # Apply generic Account logic:
        super().__init__(
            owner, balance=balance, rate=rate, nper=nper,
            inputs=inputs, initial_year=initial_year,
            default_timing=default_timing, **kwargs)

        # Set up (and type-convert) Debt-specific inputs:
        self.minimum_payment = minimum_payment
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
    def accelerated_payment(self):
        """ The maximum amount to repay above the minimum payment. """
        return self._accelerated_payment

    @accelerated_payment.setter
    def accelerated_payment(self, val):
        self._accelerated_payment = Money(val)

    @property
    def min_inflow_limit(self):
        """ The minimum annual payment on the debt. """
        # Must make at least the minimum payment
        return self.minimum_payment

    @property
    def max_inflow_limit(self):
        """ The maximum annual payment on the debt. """
        # Largest payment exceeds minimum only by `accelerated_payment`
        return self.minimum_payment + self.accelerated_payment

    @property
    def max_outflow_limit(self):
        """ The maximum annual withdrawals from the debt account. """
        # No outflows permitted
        return Money(0)

    # No need to override min_outflow_limit - still $0.

    def max_inflow(self, when="end"):
        """ The maximum amount that can be contributed at `when`. """
        # Max you can contribute is the lesser of: the limit and the
        # remaining balance.
        return min(
            # Repay the whole balance (or none if positive)
            max(-self.balance_at_time(when), Money(0)),
            # But no more than the maximum outflow:
            self.max_inflow_limit)

    def max_inflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The maximum amounts that can be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a `Debt`, this will return the amounts that return the
        account to a zero balance.

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (Money): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.
            balance_limit (Money): This balance, if provided, will not
                be exceeded at year-end. Optional.

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
            transaction_limit=transaction_limit,
            balance_limit=balance_limit,
            transactions=transactions,
            **kwargs)

    def min_inflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The minimum amounts that must be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a `Debt`, this will return the minimum payments (or the
        amounts that return the account to a zero balance, if less).

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (Money): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.
            balance_limit (Money): This balance, if provided, will not
                be exceeded at year-end. Optional.

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
            transaction_limit=transaction_limit,
            balance_limit=balance_limit,
            transactions=transactions,
            **kwargs)
