""" Provides a Canadian tax-free savings account. """

from forecaster.canada.accounts.registered_account import RegisteredAccount
from forecaster.ledger import Money, recorded_property
from forecaster.utility import (
    build_inflation_adjust, extend_inflation_adjusted)
from forecaster.canada import constants

class TFSA(RegisteredAccount):
    """ A Tax-Free Savings Account (Canada). """

    def __init__(self, owner, balance=0, rate=0,
                 nper=1, inputs=None, initial_year=None,
                 default_timing=None,
                 contribution_room=None, contributor=None,
                 inflation_adjust=None, **kwargs):
        """ Initializes a TFSA object.

        Args:
            inflation_adjust: A method with the following form:
                `inflation_adjust(val, this_year, target_year)`.

                Returns a Decimal object which is the inflation-
                adjustment factor from base_year to target_year.

                Optional. If not provided, all values are assumed to be
                in real terms, so no inflation adjustment is performed.
        """
        # This method does have a lot of arguments, but they're mostly
        # inherited from a superclass. We're stuck with them here.
        # pylint: disable=too-many-arguments

        super().__init__(
            owner, balance=balance, rate=rate,
            nper=nper, inputs=inputs, initial_year=initial_year,
            default_timing=default_timing,
            contribution_room=contribution_room, contributor=contributor,
            **kwargs)

        self.inflation_adjust = build_inflation_adjust(inflation_adjust)

        # This is our baseline for estimating contribution room
        # (By law, inflation-adjustments are relative to 2009, the
        # first year that TFSAs were available, and rounded to the
        # nearest $500)
        self._base_accrual_year = min(constants.TFSA_ANNUAL_ACCRUAL.keys())
        self._base_accrual = round(extend_inflation_adjusted(
            constants.TFSA_ANNUAL_ACCRUAL,
            self.inflation_adjust,
            self._base_accrual_year
        ) / constants.TFSA_ACCRUAL_ROUNDING_FACTOR) * \
            constants.TFSA_ACCRUAL_ROUNDING_FACTOR

        # If contribution_room is not provided (and it's already known
        # based on other TFSA accounts), infer it based on age.
        if (
                contribution_room is None and
                self.initial_year not in self.contribution_room_history):
            # We might already have set contribution room for years
            # before this initial_year, in which case we should start
            # extrapolate from the following year onwards:
            if self.contribution_room_history:
                start_year = max(
                    year for year in self.contribution_room_history
                    if year < self.initial_year
                ) + 1
                contribution_room = self.contribution_room_history[
                    start_year - 1
                ]
            else:
                # If there's no known contribution room, simply sum up
                # all of the default accruals from the first year the
                # owner was eligible:
                start_year = max(
                    self.initial_year -
                    self.contributor.age(self.initial_year) +
                    constants.TFSA_ELIGIBILITY_AGE,
                    min(constants.TFSA_ANNUAL_ACCRUAL.keys())
                )
                contribution_room = 0
            # Accumulate contribution room over applicable years
            self.contribution_room = contribution_room + sum(
                self._contribution_room_accrual(year)
                for year in range(start_year, self.initial_year + 1)
            )

    def _contribution_room_accrual(self, year):
        """ The amount of contribution room accrued in a given year.

        This excludes any rollovers - it's just the statutory accrual.
        """
        # No accrual if the owner is too young to qualify:
        if self.owner.age(year + 1) < constants.TFSA_ELIGIBILITY_AGE:
            return Money(0)

        # If we already have an accrual rate set for this year, use that
        if year in constants.TFSA_ANNUAL_ACCRUAL:
            return Money(constants.TFSA_ANNUAL_ACCRUAL[year])
        # Otherwise, infer the accrual rate by inflation-adjusting the
        # base rate and rounding.
        else:
            return Money(
                round(
                    self._base_accrual * self.inflation_adjust(
                        self._base_accrual_year, year) /
                    constants.TFSA_ACCRUAL_ROUNDING_FACTOR) *
                constants.TFSA_ACCRUAL_ROUNDING_FACTOR
            )

    def next_contribution_room(self):
        """ The amount of contribution room for next year. """
        year = self.this_year

        # If the contribution room for next year is already known, use
        # that:
        if year + 1 in self.contribution_room_history:
            return self.contribution_room_history[year + 1]

        contribution_room = self._contribution_room_accrual(year + 1)
        # On top of this year's accrual, roll over unused contribution
        # room, plus any withdrawals (less contributions) from last year
        if year in self.contribution_room_history:
            rollover = self.contribution_room_history[year] - (
                # pylint: disable=no-member
                # Pylint gets confused by attributes added by metaclass.
                # recorded_property members always have a corresponding
                # *_history member:
                self.outflows_history[year] + self.inflows_history[year]
            )
        else:
            rollover = 0
        return contribution_room + rollover

    @recorded_property
    def taxable_income(self):
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)
