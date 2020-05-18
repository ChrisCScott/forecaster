""" Provides a Canadian tax-free savings account. """

from forecaster.canada.accounts.registered_account import RegisteredAccount
from forecaster.ledger import recorded_property
from forecaster.money import Money
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
            inflation_adjust=inflation_adjust,
            **kwargs)

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

        # If contribution_room is not provided, infer it based on age.
        if self.contribution_room is None:
            self.contribution_room = self._infer_initial_contribution_rm()
        # NOTE: We don't need an `else` branch; `contribution_room` will
        # be set via superclass init if it is provided.

    def _infer_initial_contribution_rm(self):
        """ Infers initial contribution room for a new TFSA. """
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass,
        # including `contribution_room_history`. It's called a lot here.

        # First thing's first: If there's already a value for this year
        # in contribution_room_history, use that.
        # NOTE: `this_year` is guaranteed to be in the dict returned
        # by `contribution_room_history`, since it's added in by the
        # property if it isn't already in the dict.
        # Check the underlying dict to avoid this.
        if self.this_year in self._contribution_room_history:
            return self._contribution_room_history[self.this_year]

        # We might already have set contribution room for years
        # before this initial_year (e.g. due to `input`), in which
        # case we should extrapolate from that year onwards:
        # (See above note re: `_contribution_room_history`)
        if self._contribution_room_history:
            # Get the last year for which there is data and the
            # contribution room recorded for that year:
            last_year = max(
                year for year in self._contribution_room_history
                if year < self.initial_year)
            contribution_room = self._contribution_room_history[last_year]
            # We'll add up accruals starting the year after that:
            start_year = last_year + 1
        else:
            # Otherwise, simply sum up all of the default accruals
            # from the first year the owner was eligible:
            start_year = max(
                self.initial_year -
                self.contributor.age(self.initial_year) +
                constants.TFSA_ELIGIBILITY_AGE,
                min(constants.TFSA_ANNUAL_ACCRUAL.keys()))
            # The owner accumulated no room prior to eligibility:
            contribution_room = 0
        # Accumulate contribution room over applicable years
        return contribution_room + sum(
            self._contribution_room_accrual(year)
            for year in range(start_year, self.initial_year + 1))

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
        contribution_room = self._contribution_room_accrual(self.this_year + 1)
        # On top of this year's accrual, roll over unused contribution
        # room, plus any withdrawals (less contributions) from last year
        rollover = self.contribution_room - (self.outflows() + self.inflows())
        return contribution_room + rollover

    @recorded_property
    def taxable_income(self):
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)
