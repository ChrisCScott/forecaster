""" A module providing Canada-specific tax treatment. """

from forecaster.tax import Tax, TaxMulti
from forecaster.utility.precision import HighPrecisionOptional
from forecaster.canada.accounts import RRSP
from forecaster.canada.constants import ConstantsCanada
from forecaster.utility import extend_inflation_adjusted


class TaxCanadaJurisdiction(Tax):
    """ Federal or provincial tax treatment (Canada). """

    def __init__(
            self, inflation_adjustments, jurisdiction='Federal',
            *, high_precision=None, constants=None, **kwargs):
        # We need to get the relevant constants to call super.__init__:
        if constants is None:
            self.constants = ConstantsCanada(high_precision=high_precision)
        else:
            self.constants = constants
        # All the work here is done by the superclass, we just need to
        # tell it what brackets/credits/deductions/timing to apply:
        super().__init__(
            tax_brackets=self.constants.TAX_BRACKETS[jurisdiction],
            personal_deduction=self.constants.TAX_PERSONAL_DEDUCTION[
                jurisdiction
            ],
            credit_rate=self.constants.TAX_CREDIT_RATE[jurisdiction],
            inflation_adjust=inflation_adjustments,
            refund_timing=self.constants.TAX_REFUND_TIMING,
            payment_timing=self.constants.TAX_PAYMENT_TIMING,
            **kwargs)

        self.jurisdiction = jurisdiction

    def credit(self, person, year, deduction=None):
        """ Finds tax credit available for each taxpayer.

        Args:
            person (Person): A person with some number of accounts
                (or other tax sources).
            year (int): The year in which money is expressed (used for
                inflation adjustment)
            deductions (Money): The deductions for which the person
                is eligible.

        Returns:
            Money: The tax credit available in this jurisdiction for
                the person.
        """
        # Get basic credits (i.e. those tied to accounts) from the
        # superclass method:
        _credits = super().credit(person, year, deduction)

        # Apply the pension income tax credit for each person:
        _credits += self._pension_income_credit(person, year)

        # Apply the spousal tax credit if the person is married:
        if person.spouse is not None:
            _credits += self._spousal_tax_credit(person, year)

        return _credits

    def _pension_income_credit(self, person, year):
        """ Determines the pension income credit claimable by `person`.

        Args:
            person (Person): The person who will claim the pension
                income credit (if any)
            year (int): The year in which the pension income credit is
                claimable.

        Returns:
            Money: The amount of the credit claimable by person in year.
        """
        pension_income = abs(sum(
            account.outflows() for account in person.accounts
            if isinstance(account, RRSP)))
            # NOTE: Other qualified pension income sources can be
            # added here
        # Each jurisdiction has a maximum claimable amount for the
        # pension credit, so determine that (inflation-adjusted
        # amount) here:
        deduction_max = extend_inflation_adjusted(
            self.constants.TAX_PENSION_CREDIT[self.jurisdiction],
            self.inflation_adjust,
            year)
        return min(pension_income, deduction_max)

    def _spousal_tax_credit(self, person, year):
        """ Determines the spousal tax credit amount claimable.

        This method assigns the credit to the higher-earning
        partner. Multiple people can be passed and the credit
        will be determined for each individually.

        Where both partners have the same income, the credit is
        assigned to one partner in an implementation-dependent
        way (e.g. based on a hash).

        Args:
            person (Person): One member of a couple (or a single
                person, in which case the credit will be $0).
            year (int): The year in which the spousal tax credit is
                claimable.

        Returns:
            Money: The amount of the credit claimable by the person
                in `year`.
        """
        # Unmarried folks don't get the credit:
        if person.spouse is None:
            return 0 # Money value

        # Determine the maximum claimable amount:
        max_spousal_amount = extend_inflation_adjusted(
            self.constants.TAX_SPOUSAL_AMOUNT[self.jurisdiction],
            self.inflation_adjust,
            year)

        # We need to know the spouse's net income to assess the credit:
        # TODO: Pass in deductions for both spouses as args?
        # This would help to avoid calling self.deductions many times.
        spouse = person.spouse
        spouse_net_income = (
            spouse.taxable_income - self.deduction(spouse, year))

        # Figure out whether to assign the credit to this person or
        # their spouse based on who has more income:

        # If this is the lower-earner, use their spouse instead:
        person_net_income = (
            person.taxable_income - self.deduction(person, year))
        if person_net_income < spouse_net_income:
            return 0 # Money value
        # If their incomes are the same, use memory location to
        # decide in a deterministic way:
        if person_net_income == spouse_net_income:
            if id(person) < id(spouse):
                return 0 # Money value

        # The credit is determined by reducing the spousal amount
        # by the spouse's (net) income, but in any event it's not
        # negative.
        credit = max(
            max_spousal_amount - spouse_net_income,
            0) # Money value

        return credit


class TaxCanada(TaxMulti, HighPrecisionOptional):
    """ Federal and provincial tax treatment for a Canadian resident.

    Attributes:
        inflation_adjust: A method with the following form:
            `inflation_adjust(target_year, base_year) -> Decimal`.
            See documentation for `Tax` for more information.
        province (str): The province in which income tax is paid.
    """

    def __init__(
            self, inflation_adjust, province='BC', constants=None, **kwargs):
        """ Initializes TaxCanada.

        Args:
            inflation_adjust: A method with the following form:
                `inflation_adjust(target_year, base_year) -> Decimal`.

                Can be passed as dict or Decimal-convertible scalar,
                which will be converted to a callable object.

                See documentation for `Tax` for more information.
            province (str): The province in which income tax is paid.
            payment_timing (Decimal, str): Timing for tax refunds and
                payments. See `Tax` documentation for more information.
        """
        self.federal_tax = TaxCanadaJurisdiction(
            inflation_adjust, constants=constants, **kwargs)
        self.provincial_tax = TaxCanadaJurisdiction(
            inflation_adjust, province, constants=constants, **kwargs)
        self.province = province

        jurisdictions = (self.federal_tax, self.provincial_tax)
        super().__init__(jurisdictions, **kwargs)

    def __call__(
            self, income, year,
            federal_deduction=None, federal_credit=None,
            provincial_deduction=None, provincial_credit=None, **kwargs):
        """ Determines Canadian taxes owing on given income sources.

        This includes provincial and federal taxes.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            federal_deduction (Money, dict[Person, Money]):
                Deductions to be applied against federal taxes.
                See documentation for `Tax` for more.
            federal_credit (Money, dict[Person, Money]):
                Credits to be applied against federal taxes.
                See documentation for `Tax` for more.
            provincial_deduction (Money, dict[Person, Money]):
                Deductions to be applied against provincial taxes.
                See documentation for `Tax` for more.
            provincial_credit (Money, dict[Person, Money]):
                Credits to be applied against provincial taxes.
                See documentation for `Tax` for more.
            kwargs (dict[str, Any]): Keyword arguments accepted by
                `TaxMulti`, which may be passed instead of (or in
                addition to) the convenience arguments defined by this
                class.

        Returns:
            Money: The total amount of tax owing for the year.
        """
        # pylint: disable=arguments-differ
        # Users can pass in `deductions` and `credits` dicts (as allowed
        # by the superclass), or they can pass in `federal_*` and/or
        # `provincial_*` scalars which we'll wrap up appropriately.
        if "deductions" in kwargs:
            deductions = kwargs["deductions"]
        else:
            deductions = {}
        if "credits_" in kwargs:
            credits_ = kwargs["credits_"]
        else:
            credits_ = {}

        # Override any values in `deductions` and `credis` with
        # subclass-specific kwargs, if provided:
        if federal_deduction is not None:
            deductions[self.federal_tax] = federal_deduction
        if federal_credit is not None:
            credits_[self.federal_tax] = federal_credit
        if provincial_deduction is not None:
            deductions[self.provincial_tax] = provincial_deduction
        if provincial_credit is not None:
            credits_[self.provincial_tax] = provincial_credit

        # Bundle the kwargs up to be passed to the superclass:
        kwargs["deductions"] = deductions
        kwargs["credits_"] = credits_

        return super().__call__(income=income, year=year, **kwargs)
