""" Provices Registered Retirement Savings Accounts for Canadians. """

from forecaster.canada.accounts.registered_account import RegisteredAccount
from forecaster.ledger import recorded_property
from forecaster.utility import extend_inflation_adjusted, nearest_year
from forecaster.canada import constants

class RRSP(RegisteredAccount):
    """ A Registered Retirement Savings Plan (Canada). """

    def __init__(self, *args, rrif_conversion_year=None, **kwargs):
        """ Initializes an RRSP object.

        This class also implements RRIFs (which RRSPs are converted into
        either at a user-defined time or by operation of law). A new
        object is not created when the RRSP converts to an RRIF; rather,
        the object's behaviour changes to limit inflows, require
        minimum withdrawals, and reduce withholding taxes.

        See documentation for `RegisteredAccount` for information on
        args not listed below.

        Args:
            rrif_conversion_year (int): The year in which the `RRSP`
                object's behaviour switches from RRSP rules to RRIF
                rules.
        """
        super().__init__(*args, **kwargs)

        # Although `person` might provide a retirement_age, the RRSP
        # won't necessarily be turned into an RRIF at the retirement
        # date (depending on withdrawal strategy).
        # TODO: Allow RRIF_conversion_year to be passed as an argument?
        # We could use the below convert-at-71 logic if None is passed.
        # TODO: Automatically trigger RRIF conversion after outflow?
        # (Perhaps control this behaviour with an arg?)

        self._rrif_conversion_year = None
        self.rrif_conversion_year = rrif_conversion_year

        # Convert RRSP_ACCRUAL_MAX values if operating in high-precision
        # mode.
        # TODO: Perform this conversion in the `constants` class?
        # Otherwise, we'll need to perform this conversion in
        # `next_contribution_room`, which will get expensive
        # (and kludgy)
        if self.high_precision is not None:
            rrsp_accrual_max = {
                # pylint: disable=not-callable
                # Non-None `high_precision` is expected to be callable
                year: self.high_precision(val)
                for (year, val) in constants.RRSP_ACCRUAL_MAX.items()}
                # pylint: enable=not-callable
        else:
            rrsp_accrual_max = constants.RRSP_ACCRUAL_MAX

        # Determine the max contribution room accrual in initial_year:
        self._initial_accrual = extend_inflation_adjusted(
            rrsp_accrual_max,
            self.inflation_adjust,
            self.initial_year
        )

        # If no contribution room was provided, set it to $0.
        if self.contribution_room is None:
            self.contribution_room = self.precision_convert(0) # Money value

    def _rrif_max_conversion_year(self):
        """ The latest year in which the RRSP can convert to an RRIF. """
        return (
            self.initial_year
            + constants.RRSP_RRIF_CONVERSION_AGE
            - self.owner.age(self.initial_year)
        )

    @property
    def rrif_conversion_year(self):
        """ The year in which the RRSP is converted to an RRIF.

        If not set explicitly, the year in which conversion is required
        by law is returned (whichever happens first).
        """
        if self._rrif_conversion_year is not None:
            return self._rrif_conversion_year
        else:
            return self._rrif_max_conversion_year()

    @rrif_conversion_year.setter
    def rrif_conversion_year(self, val):
        """ Sets `rrif_conversion_year`.

        Arg:
            val (int): The year in which to convert the RRSP to an
                RRIF. May be None, in which case the RRIF conversion
                year will be determined based on default logic.

        Raises:
            ValueError: Can't cast `val` to `int`
            ValueError: Attempt to convert RRSP to RRIF after mandatory
                conversion year.
        """
        if val is None:
            self._rrif_conversion_year = None
        else:
            # Convert to int if necessary.
            # This can raise ValueError if `val` isn't convertible.
            if not isinstance(val, int):
                val = int(val)
            if val > self._rrif_max_conversion_year():
                raise ValueError( #@IgnoreException
                    'Attempt to convert RRSP to RRIF after mandatory '
                    + 'conversion year. Latest valid year is '
                    + str(self._rrif_max_conversion_year())
                )
            # We don't worry about conversion years that are too early;
            # even if they predate the owner's birth, it ends up just
            # being treated as an immediate conversion.
            self._rrif_conversion_year = int(val)

    def convert_to_rrif(self, year=None):
        """ Converts the RRSP to an RRIF. """
        year = self.this_year if year is None else int(year)
        self.rrif_conversion_year = year

    @recorded_property
    def taxable_income(self):
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals from the account
        """
        # Return the sum of all withdrawals from the account.
        # pylint: disable=invalid-unary-operand-type
        # Pylint thinks this doesn't support negation via `-`, but it's
        # wrong - `outflows` returns `float`, which supports `-`:
        return -self.outflows()

    @recorded_property
    def tax_withheld(self):
        """ The total tax withheld from the account for the year.

        For RRSPs, this is calculated according to a CRA formula.
        """
        # NOTE: It's possible to attract a lower tax rate by making
        # smaller one-off withdrawals, but in general multiple
        # withdrawals will be treated as a lump sum for the purpose of
        # determining the tax rate, so we pretend it's a lump sum.
        if self.rrif_conversion_year > self.this_year:
            taxable_income = self.taxable_income
        else:
            # Only withdrawals in excess of the minimum RRIF withdrawal
            # are hit by the withholding tax.
            taxable_income = self.taxable_income - self.min_outflow_limit

        year = nearest_year(
            constants.RRSP_WITHHOLDING_TAX_RATE,
            self.this_year)
        # We convert this inline below (when assigning `tax_rate`):
        tax_rates = constants.RRSP_WITHHOLDING_TAX_RATE[year]
        taxable_income_adjusted = (
            taxable_income
            * self.inflation_adjust(year, self.this_year)
        )
        bracket = max(
            (
                bracket for bracket in tax_rates
                if bracket < taxable_income_adjusted),
            default=min(tax_rates.keys()))
        tax_rate = self.precision_convert(tax_rates[bracket])
        return taxable_income * tax_rate

    @recorded_property
    def tax_deduction(self):
        """ The total sum of tax deductions available for the year.

        For RRSPs, this the amount contributed in the year.
        """
        return self.inflows()

    def next_contribution_room(self):
        """ Determines the amount of contribution room for next year.

        Args:
            income (Money): The amount of taxable income for this year
                used to calculate RRSP contribution room.
            year (int): The year in which the income is received.

        Returns:
            The contribution room for the RRSP for the year *after*
            `year`.
        """
        year = self.this_year

        if self.contributor.age(year + 1) > constants.RRSP_RRIF_CONVERSION_AGE:
            # If past the mandatory RRIF conversion age, no
            # contributions are allowed.
            return self.precision_convert(0) # Money value
        else:
            # TODO: Add pension adjustment?

            # Contribution room is determined based on the contributor's
            # gross income for the previous year.
            income = self.contributor.gross_income_history[self.this_year]

            # First, determine how much more contribution room will
            # accrue due to this year's income:
            accrual = income * self.precision_convert(
                constants.RRSP_ACCRUAL_RATE)
            accrual_max = {
                year: self.precision_convert(val)
                for (year, val) in constants.RRSP_ACCRUAL_MAX.items()}
            # Second, compare to the (inflation-adjusted) max accrual
            # for next year:
            max_accrual = extend_inflation_adjusted(
                accrual_max,
                self.inflation_adjust,
                year + 1)
            # Don't forget to add in any rollovers:
            rollover = self.contribution_room - self.inflows()
            return min(
                accrual,
                max_accrual # Money value
                ) + rollover

    @property
    def min_outflow_limit(self):
        """ Minimum annual RRSP/RRIF withdrawal """
        # Return the larger (in terms of magnitude - recall outflows
        # are negative!) of: the minimum required age-based distribution
        # and any shared minimum (e.g. home-buyers' amounts):
        return min(-self.minimum_distribution(), super().min_outflow_limit)

    def minimum_distribution(self):
        """ A min. amount required by law to be withdrawn based on age. """
        # Convert relevant constants:
        if self.high_precision is not None:
            rrif_withdrawal_min = {
                # pylint: disable=not-callable
                year: self.high_precision(val)
                # pylint: enable=not-callable
                for (year, val) in constants.RRSP_RRIF_WITHDRAWAL_MIN.items()}
        else:
            rrif_withdrawal_min = constants.RRSP_RRIF_WITHDRAWAL_MIN

        # Minimum withdrawals are required the year after converting to
        # an RRIF. How it is calculated depends on the person's age.
        if self.rrif_conversion_year < self.this_year:
            age = self.contributor.age(self.this_year)
            if age in rrif_withdrawal_min:
                return (
                    self.precision_convert(rrif_withdrawal_min[age])
                    * self.balance)
            elif age > max(rrif_withdrawal_min):
                return self.balance * max(rrif_withdrawal_min.values())
            else:
                return self.balance / (90 - age)
        else:
            return self.precision_convert(0) # Money value

    # TODO: Add RRSP tax credits (e.g. pension tax credit)?
    # Implement this in an overloaded _tax_credit method.


# TODO: Implement SpousalRRSP?
# (It may be that RRSP provides all of the logic necessary, but consider
# that we need a way to know who receives the deduction - this can be
# done by type-checking an account in the TaxCanada class, or perhaps we
# should add a method [tax_deduction_eligibility?] that identifies one
# or more people who may claim the deduction).
# NOTE: This can get complicated quickly. It's probably best to
# implement a test in the Tax object rather than go for totally generic
# code at this point.
