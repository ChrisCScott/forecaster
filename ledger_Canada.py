""" A module for Canada-specific ledger subclasses. """

from decimal import Decimal
from utility import *
from ledger import Person, Account, recorded_property, recorded_property_cached
from settings_Canada import SettingsCanada
from constants import Constants


class RegisteredAccount(Account):
    """ A registered retirement account (Canada).

    This account isn't intended to use by client code. There are just
    so many commonalities between RRSPs and TFSAs that it made sense
    to combine them here.

    Args:
        inflation_adjust: A method with the following form:
            `inflation_adjust(val, this_year, target_year)`.
            Returns a Money object (assuming Money-typed `val` input).
            Finds a nominal value in `target_year` with the same real
            value as `val`, a nominal value in `this_year`. Optional.
            If not provided, all values are assumed to be in real terms,
            so no inflation adjustment is performed.
        contribution_room (Money): The amount of contribution room
            available in the first year. Optional.
        contributor (Person): The contributor to the RRSP. Optional.
            If not provided, the contributor is assumed to be the same
            as the annuitant (i.e. the owner.)
    """
    def __init__(self, owner, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=SettingsCanada,
                 contribution_room=None, contributor=None,
                 inflation_adjust=None):
        """ Initializes a RegisteredAccount object. """
        super().__init__(
            owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, initial_year=initial_year, settings=settings)

        # If no contributor was provided, assume it's the owner.
        if contributor is None:
            self.contributor = self.owner
        else:
            self.contributor = contributor

        self.inflation_adjust = build_inflation_adjust(inflation_adjust)

        # Set up a _contribution_token that's the same for all instances
        # of a subclass but differs between subclasses.
        self._contribution_token = type(self).__name__

        # Prepare this account for having its contribution room tracked
        self.contributor.register_shared_contribution_account(self)
        # Contribution room is stored with the contributor and shared
        # between accounts. Accordingly, only set contribution room if
        # it's explicitly provided, to avoid overwriting previously-
        # determined contribution room data with a default value.
        if contribution_room is not None:
            self.contribution_room = contribution_room

    @property
    def contributor(self):
        """ The contributor to the account. """
        return self._contributor

    @contributor.setter
    def contributor(self, val):
        """ Sets the contributor to the account. """
        if not isinstance(val, Person):
            raise TypeError(
                'RegisteredAccount: person must be of type Person.'
            )
        else:
            self._contributor = val

    @property
    def contribution_group(self):
        """ The accounts that share contribution room with this one. """
        return self.contributor.contribution_group(self)

    @property
    def contribution_room(self):
        """ Contribution room available for the current year. """
        return self.contributor.contribution_room(self)[self.this_year]

    @contribution_room.setter
    def contribution_room(self, val):
        """ Updates contribution room for RRSPs """
        self.contributor.contribution_room(self)[self.this_year] = Money(val)

    @property
    def contribution_room_history(self):
        """ A dict of {year: contribution_room} pairs. """
        return self.contributor.contribution_room(self)

    def next_year(self, *args, **kwargs):
        """ Confirms that the year is within the range of our data. """
        # NOTE: Invoking super().next_year will increment self.this_year
        super().next_year(*args, **kwargs)

        # Ensure that the contributor has advanced to this year.
        while self.contributor.this_year < self.this_year:
            self.contributor.next_year()

        # Determine contribution room for the next year:
        self.contribution_room = self.next_contribution_room(
            year=self.this_year - 1, *args, **kwargs
        )

    def next_contribution_room(self, year=None, *args, **kwargs):
        raise NotImplementedError(
            'RegisteredAccount: next_contribution_room is not implemented. ' +
            'Use RRSP or TFSA instead.'
        )

    def max_inflow(self, when='end'):
        """ Limits outflows based on available contribution room. """
        return self.contribution_room_history[self.this_year]


class RRSP(RegisteredAccount):
    """ A Registered Retirement Savings Plan (Canada). """

    # Explicitly repeat superclass args for the sake of intellisense.
    def __init__(self, owner, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=SettingsCanada,
                 contribution_room=None, contributor=None,
                 inflation_adjust=None):
        """ Initializes an RRSP object. """
        super().__init__(
            owner, inflation_adjust=inflation_adjust, balance=balance,
            rate=rate, transactions=transactions, nper=nper,
            initial_year=initial_year, settings=settings,
            contribution_room=contribution_room, contributor=contributor)

        # Although `person` might provide a retirement_age, the RRSP
        # won't necessarily be turned into an RRIF at the retirement
        # date (depending on withdrawal strategy).
        # TODO: Allow RRIF_conversion_year to be passed as an argument?
        # We could use the below convert-at-71 logic if None is passed.
        # TODO: Automatically trigger RRIF conversion when an outflow
        # is detected? (Perhaps control this behaviour with an arg?)

        # The law requires that RRSPs be converted to RRIFs by a certain
        # age (currently 71). We can calculate that here:
        self.RRIF_conversion_year = self.initial_year + \
            Constants.RRSPRRIFConversionAge - \
            self.owner.age(self.initial_year)

        # Determine the max contribution room accrual in initial_year:
        self._initial_accrual = extend_inflation_adjusted(
            Constants.RRSPContributionRoomAccrualMax,
            self.inflation_adjust,
            self.initial_year
        )

        # If no contribution room is provided and none is already known,
        # set contribution_room to 0.
        if (
            contribution_room is None and
            self.initial_year not in self.contribution_room_history
        ):
            self.contribution_room = Money(0)

    def convert_to_RRIF(self, year=None):
        """ Converts the RRSP to an RRIF. """
        year = self.this_year if year is None else year
        self.RRIF_conversion_year = year

    @recorded_property
    def taxable_income(self):
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        # Return the sum of all withdrawals from the account.
        return -self.outflows

    @recorded_property
    def tax_withheld(self):
        """ The total tax withheld from the account for the year.

        For RRSPs, this is calculated according to a CRA formula.
        """
        # NOTE: It's possible to attract a lower tax rate by making
        # smaller one-off withdrawals, but in general multiple
        # withdrawals will be treated as a lump sum for the purpose of
        # determining the tax rate, so we pretend it's a lump sum.
        if self.RRIF_conversion_year > self.this_year:
            taxable_income = self.taxable_income
        else:
            # Only withdrawals in excess of the minimum RRIF withdrawal
            # are hit by the withholding tax.
            taxable_income = self.taxable_income - self.min_outflow

        # TODO: inflation-adjust `x` to match the inflation-adjustment
        # year of taxable_income? (this would likely require identifying
        # a year for which `x` is expressed in nominal dollars, probably
        # in Constants; maybe make RRSPWithholdingTaxRate a dict of
        # {year: {amount: rate}}?)
        # TODO: Pass a Tax object for RRSP tax treatment?
        tax_rate = max(
            (Constants.RRSPWithholdingTaxRate[x]
             for x in Constants.RRSPWithholdingTaxRate
             if x < taxable_income.amount),
            default=0)
        return taxable_income * tax_rate

    @recorded_property
    def tax_deduction(self):
        """ The total sum of tax deductions available for the year.

        For RRSPs, this the amount contributed in the year.
        """
        return self.inflows

    def next_contribution_room(self, year=None, *args, **kwargs):
        """ Determines the amount of contribution room for next year.

        Args:
            income (Money): The amount of taxable income for this year
                used to calculate RRSP contribution room.
            year (int): The year in which the income is received.

        Returns:
            The contribution room for the RRSP for the year *after*
            `year`.
        """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        if self.contributor.age(year + 1) > Constants.RRSPRRIFConversionAge:
            # If past the mandatory RRIF conversion age, no
            # contributions are allowed.
            return Money(0)
        else:
            # TODO: Add pension adjustment?

            # Contribution room is determined based on the contributor's
            # gross income for the previous year.
            income = self.contributor.gross_income_history[year]

            # First, determine how much more contribution room will
            # accrue due to this year's income:
            accrual = income * Constants.RRSPContributionRoomAccrualRate
            # Second, compare to the (inflation-adjusted) max accrual:
            max_accrual = extend_inflation_adjusted(
                Constants.RRSPContributionRoomAccrualMax,
                self.inflation_adjust,
                year + 1
            )
            # Don't forget to add in any rollovers:
            rollover = self.contribution_room_history[year] - \
                self.inflows_history[year]
            return min(accrual, Money(max_accrual)) + rollover

    def min_outflow(self, when='end'):
        """ Minimum RRSP withdrawal """
        # Minimum withdrawals are required the year after converting to
        # an RRIF. How it is calculated depends on the person's age.
        if self.RRIF_conversion_year < self.this_year:
            age = self.contributor.age(self.this_year)
            if age in Constants.RRSPRRIFMinWithdrawal:
                return Constants.RRSPRRIFMinWithdrawal[age] * self.balance
            elif age > max(Constants.RRSPRRIFMinWithdrawal):
                return self.balance * \
                    max(Constants.RRSPRRIFMinWithdrawal.values())
            else:
                return self.balance / (90 - age)
        else:
            return Money(0)

    # TODO: Determine whether there are any RRSP tax credits to
    # implement in an overloaded _tax_credit method
    # (e.g. pension tax credit?)


# TODO: Implement SpousalRRSP? (It may be that RRSP provides all of the
# logic necessary, but consider that we need a way to know who receives
# the deduction - this can be done by type-checking an account in the
# Tax class, or perhaps we should add a method
# [tax_deduction_eligibility?] that identifies one or more people who
# may claim the deduction).
# NOTE: This can get complicated quickly. It's probably best to
# implement a test in the Tax object rather than go for totally generic
# code at this point.


class TFSA(RegisteredAccount):
    """ A Tax-Free Savings Account (Canada). """

    def __init__(self, owner, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=SettingsCanada, contribution_room=None,
                 contributor=None, inflation_adjust=None):
        """ Initializes a TFSA object. """
        super().__init__(
            owner, inflation_adjust=inflation_adjust, balance=balance,
            rate=rate, transactions=transactions, nper=nper,
            initial_year=initial_year, settings=settings,
            contribution_room=contribution_room, contributor=contributor)

        # This is our baseline for estimating contribution room
        # (By law, inflation-adjustments are relative to 2009, the
        # first year that TFSAs were available, and rounded to the
        # nearest $500)
        self._base_accrual_year = min(Constants.TFSAAnnualAccrual.keys())
        self._base_accrual = round(extend_inflation_adjusted(
            Constants.TFSAAnnualAccrual,
            self.inflation_adjust,
            self._base_accrual_year
        ) / Constants.TFSAInflationRoundingFactor) * \
            Constants.TFSAInflationRoundingFactor

        # If contribution_room is not provided (and it's already known
        # based on other TFSA accounts), infer it based on age.
        if (
            contribution_room is None and
            self.initial_year not in self.contribution_room_history
        ):
            # We might already have set contribution room for years
            # before this initial_year, in which case we should start
            # extrapolate from the following year onwards:
            if len(self.contribution_room_history) > 0:
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
                    Constants.TFSAAccrualEligibilityAge,
                    min(Constants.TFSAAnnualAccrual.keys())
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
        if self.owner.age(year + 1) < Constants.TFSAAccrualEligibilityAge:
            return Money(0)

        # If we already have an accrual rate set for this year, use that
        if year in Constants.TFSAAnnualAccrual:
            return Money(Constants.TFSAAnnualAccrual[year])
        # Otherwise, infer the accrual rate by inflation-adjusting the
        # base rate and rounding.
        else:
            return Money(
                round(
                    self._base_accrual * self.inflation_adjust(
                        self._base_accrual_year, year) /
                    Constants.TFSAInflationRoundingFactor) *
                Constants.TFSAInflationRoundingFactor
            )

    def next_contribution_room(self, year=None):
        """ The amount of contribution room for next year. """
        # Return most recent year by default
        if year is None:
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
                self.outflows_history[year] + self.inflows_history[year]
            )
        else:
            rollover = 0
        return contribution_room + rollover

    @recorded_property
    def taxable_income(self, year=None):
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)


class TaxableAccount(Account):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income from
    capital assets. That involves tracking the adjusted cost base (acb)
    of the assets.

    Attributes:
        acb (Money): The adjusted cost base of the assets in the account
            at the start of the year.
        capital_gain
        See Account for other attributes.
    """
    # TODO (v2): Reimplement TaxableAccount based on Asset objects
    # (subclassed from Money), which independently track acb and possess
    # an asset class (or perhaps `distribution` dict defining the
    # relative proportions of sources of taxable income?)
    # Perhaps also implement a tax_credit and/or tax_deduction method
    # (e.g. to account for Canadian dividends)
    # TODO: Define a proportion of growth attributable to capital gains
    # (perhaps via Settings)? Potentially subclass this method into a
    # CapitalAsset class where all growth is capital gains - this would
    # allow for modelling non-principle-residence real estate holdings.
    # (But we might want to also model rental income as well...)

    def __init__(self, owner, balance=0, rate=0, transactions={},
                 nper=1, initial_year=None, settings=SettingsCanada, acb=None):
        """ Constructor for `TaxableAccount`. """
        super().__init__(
            owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, initial_year=initial_year, settings=settings)

        # If acb wasn't provided, assume there have been no capital
        # gains or losses, so acb = balance.
        self.acb = Money(acb if acb is not None else self.balance)

    @recorded_property_cached
    def acb(self):
        """ The adjusted cost base of assets in the account this year. """
        # This is set in advance in the previous year when capital_gains
        # is determined.
        return self._acb_history[self.this_year]

    @recorded_property_cached
    def capital_gain(self):
        """ The capital gains (or losses) for this year.

        Note that, unlike other Account attributes, capital_gain is
        given as of the *end* of the year, and is based on transaction
        activity. Therefore, changing any transactions will affect
        capital_gain.
        """
        acb = self.acb
        capital_gain = 0
        transactions = self.transactions

        # ACB is sensitive to transaction order, so be sure to iterate
        # over transactions from first to last.
        for when in sorted(transactions.keys()):
            value = transactions[when]
            # There are different acb formulae for inflows and outflows
            if value >= 0:  # inflow
                acb += value
            else:  # outflow
                # Capital gains are calculated based on the acb and
                # balance before the transaction occurred.
                balance = self.balance_at_time(when) - value
                capital_gain += -value * (1 - (acb / balance))
                acb *= 1 - (-value / balance)

        # We've generated the ACB for the next year, so store it now.
        self._acb_history[self.this_year + 1] = acb
        return capital_gain

    def add_transaction(self, value, when='end'):
        super().add_transaction(value, when)
        # Invalidate the cache for acb and capital gains, since
        # transactions will affect it.
        self._capital_gain_history.pop(self.this_year, None)
        self._acb_history.pop(self.this_year + 1, None)

    @recorded_property
    def taxable_income(self):
        """ The total tax owing based on activity in the account.

        Tax can arise from realizing capital gains, receiving dividends
        (Canadian or foreign), or receiving interest. Optionally,
        `sources` may define the relative weightings of each of these
        sources of income. See the following link for more information:
        http://www.moneysense.ca/invest/asset-ocation-everything-in-its-place/

        Returns:
            Taxable income for the year from this account as a `Money`
                object.
        """
        # Only 50% of capital gains are included in taxable income
        return self.capital_gain / 2

        # TODO: Track asset allocation and apportion growth in the
        # account between capital gains, dividends, etc.

    # TODO: Implement tax_withheld and tax_credit.
    # tax_withheld: foreign withholding taxes.
    # tax_credit: Canadian dividend credit


class PrincipleResidence(Account):
    """ A Canadian principle residence. Gains in value are not taxable. """

    @recorded_property
    def taxable_income(self):
        """ The taxable income generated by the account for the year. """
        return Money(0)
