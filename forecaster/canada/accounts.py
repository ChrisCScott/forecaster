""" A module for Canada-specific ledger subclasses. """

from forecaster.accounts import Account, ContributionLimitAccount
from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.utility import (
    build_inflation_adjust, extend_inflation_adjusted, nearest_year)
from forecaster.canada import constants


class RegisteredAccount(ContributionLimitAccount):
    """ An abstract base class for RRSPs, TFSAs, etc. """

    # This class is also abstract; it's up to subclasses to implement
    # `next_contribution_room` concretely.
    # pylint: disable=abstract-method

    def __init__(self, *args, inflation_adjust=None, **kwargs):
        """ Inits RegisteredAccount.

        See documentation for `Account` and `ContributionLimitAccount`
        for information on any args not listed below.

        Args:
            inflation_adjust: A method with the following form:
                `inflation_adjust(val, this_year, target_year)`.

                Returns a Decimal object which is the inflation-
                adjustment factor from base_year to target_year.

                Optional. If not provided, all values are assumed to be
                in real terms, so no inflation adjustment is performed.
        """
        super().__init__(*args, **kwargs)
        self.inflation_adjust = build_inflation_adjust(inflation_adjust)


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
        # TODO: Automatically trigger RRIF conversion when an outflow
        # is detected? (Perhaps control this behaviour with an arg?)

        self._rrif_conversion_year = None
        self.rrif_conversion_year = rrif_conversion_year

        # Determine the max contribution room accrual in initial_year:
        self._initial_accrual = extend_inflation_adjusted(
            constants.RRSP_ACCRUAL_MAX,
            self.inflation_adjust,
            self.initial_year
        )

        # If no contribution room is provided and none is already known,
        # set contribution_room to 0.
        if (
            'contribution_room' not in kwargs and
            self.contribution_room is None
        ):
            self.contribution_room = Money(0)

    @property
    def rrif_conversion_year(self):
        """ The year in which the RRSP is converted to an RRIF.

        If not set explicitly, the owner's retirement year or year in
        which conversion is required by law is returned (whichever
        happens first).
        """
        if self._rrif_conversion_year is not None:
            return self._rrif_conversion_year
        else:
            mandatory_conversion_year = (
                self.initial_year
                + constants.RRSP_RRIF_CONVERSION_AGE
                - self.owner.age(self.initial_year)
            )
            return min(
                self.owner.retirement_date.year, mandatory_conversion_year)

    @rrif_conversion_year.setter
    def rrif_conversion_year(self, val):
        """ Sets `rrif_conversion_year`. """
        if val is None:
            self._rrif_conversion_year = None
        else:
            self._rrif_conversion_year = int(val)

    def convert_to_rrif(self, year=None):
        """ Converts the RRSP to an RRIF. """
        year = self.this_year if year is None else year
        self.rrif_conversion_year = year

    @recorded_property
    def taxable_income(self):
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        # Return the sum of all withdrawals from the account.
        # pylint: disable=invalid-unary-operand-type
        # Pylint thinks this doesn't support negation via `-`, but it's
        # wrong - `outflows` returns `Money`, which supports `-`:
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
        if self.rrif_conversion_year > self.this_year:
            taxable_income = self.taxable_income
        else:
            # Only withdrawals in excess of the minimum RRIF withdrawal
            # are hit by the withholding tax.
            taxable_income = self.taxable_income - self.min_outflow

        year = nearest_year(
            constants.RRSP_WITHHOLDING_TAX_RATE,
            self.this_year)
        tax_rates = constants.RRSP_WITHHOLDING_TAX_RATE[year]
        taxable_income_adjusted = (
            taxable_income
            * self.inflation_adjust(year, self.this_year)
        )
        bracket = max((
            bracket for bracket in tax_rates
            if bracket < taxable_income_adjusted.amount),
            default=min(tax_rates.keys())
        )
        tax_rate = tax_rates[bracket]
        return taxable_income * tax_rate

    @recorded_property
    def tax_deduction(self):
        """ The total sum of tax deductions available for the year.

        For RRSPs, this the amount contributed in the year.
        """
        return self.inflows

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
            return Money(0)
        else:
            # TODO: Add pension adjustment?

            # Contribution room is determined based on the contributor's
            # gross income for the previous year.
            income = self.contributor.gross_income_history[self.this_year]

            # First, determine how much more contribution room will
            # accrue due to this year's income:
            accrual = income * constants.RRSP_ACCRUAL_RATE
            # Second, compare to the (inflation-adjusted) max accrual
            # for next year:
            max_accrual = extend_inflation_adjusted(
                constants.RRSP_ACCRUAL_MAX,
                self.inflation_adjust,
                year + 1
            )
            # Don't forget to add in any rollovers:
            rollover = self.contribution_room - self.inflows
            return min(accrual, Money(max_accrual)) + rollover

    def min_outflow(self, when='end'):
        """ Minimum RRSP withdrawal """
        # Minimum withdrawals are required the year after converting to
        # an RRIF. How it is calculated depends on the person's age.
        if self.rrif_conversion_year < self.this_year:
            age = self.contributor.age(self.this_year)
            if age in constants.RRSP_RRIF_WITHDRAWAL_MIN:
                return constants.RRSP_RRIF_WITHDRAWAL_MIN[age] * self.balance
            elif age > max(constants.RRSP_RRIF_WITHDRAWAL_MIN):
                return self.balance * \
                    max(constants.RRSP_RRIF_WITHDRAWAL_MIN.values())
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
                 transactions=None, nper=1, inputs=None, initial_year=None,
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
            owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, inputs=inputs, initial_year=initial_year,
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
            self.initial_year not in self.contribution_room_history
        ):
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


class TaxableAccount(Account):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income from
    capital assets. That involves tracking the adjusted cost base (acb)
    of the assets.

    See Account for other attributes not listed below.

    Attributes:
        acb (Money): The adjusted cost base of the assets in the account
            at the start of the year.
        capital_gain (Money): The total capital gains for the year.
            This is evaluated lazily, so it may return different values
            if you add or remove transactions.
    """
    # TODO (v2): Reimplement TaxableAccount based on Asset objects
    # (subclassed from Money), which independently track acb and possess
    # an asset class (or perhaps `distribution` dict defining the
    # relative proportions of sources of taxable income?)
    # Perhaps also implement a tax_credit and/or tax_deduction method
    # (e.g. to account for Canadian dividends)
    # TODO: Define a proportion of growth attributable to capital gains?
    # Potentially subclass this method into a CapitalAsset class where
    # all growth is capital gains - this would allow for modelling
    # non-principle-residence real estate holdings.
    # (But we might want to also model rental income as well...)

    def __init__(
        self, owner, balance=0, rate=0, transactions=None,
        nper=1, inputs=None, initial_year=None, acb=None, **kwargs
    ):
        """ Constructor for `TaxableAccount`.

        See documentation for `Account` for information on args not
        listed below.

        Args:
            acb (Money): The adjusted cost base of the assets in the
                account at the start of `initial_year`.
        """
        # This method does have a lot of arguments, but they're mostly
        # inherited from a superclass. We're stuck with them here.
        # pylint: disable=too-many-arguments

        super().__init__(
            owner=owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, inputs=inputs, initial_year=initial_year, **kwargs)

        # If acb wasn't provided, assume there have been no capital
        # gains or losses, so acb = balance.
        self.acb = Money(acb if acb is not None else self.balance)

    # pylint: disable=method-hidden
    # The `self.acb` assignment in `__init__ doesn't actually overwrite
    # this member; it assigns to it via a setter.
    @recorded_property_cached
    def acb(self):
        """ The adjusted cost base of assets in the account this year. """
        # This is set in advance in the previous year when capital_gains
        # is determined.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # they always have a corresponding *_history member:
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
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # `transactions` returns a dict, so it has a `keys` member:
        for when in sorted(transactions.keys()):
            # pylint: disable=unsubscriptable-object
            # Pylint gets confused by attributes added via metaclass.
            # `transactions` returns a dict, so it is subscriptable:
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
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # All `_*_history` members are dicts added automatically:
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
