""" A module providing Canada-specific tax treatment. """

from forecaster.ledger import Money
from forecaster.tax import Tax
from forecaster.canada.accounts import RRSP
from forecaster.canada import constants
from forecaster.utility import extend_inflation_adjusted


class TaxCanadaJurisdiction(Tax):
    """ Federal or provincial tax treatment (Canada). """

    def __init__(
            self, inflation_adjustments, jurisdiction='Federal',
            payment_timing='start'):
        super().__init__(
            tax_brackets=constants.TAX_BRACKETS[jurisdiction],
            personal_deduction=constants.TAX_PERSONAL_DEDUCTION[
                jurisdiction
            ],
            credit_rate=constants.TAX_CREDIT_RATE[jurisdiction],
            inflation_adjust=inflation_adjustments,
            payment_timing=payment_timing)

        self.jurisdiction = jurisdiction

    def credits(self, person, year, deductions=None):
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
        _credits = super().credits(person, year, deductions)

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
            if isinstance(account, RRSP)
            # NOTE: Other qualified pension income sources can be
            # added here
        ))
        # Each jurisdiction has a maximum claimable amount for the
        # pension credit, so determine that (inflation-adjusted
        # amount) here:
        deduction_max = Money(extend_inflation_adjusted(
            constants.TAX_PENSION_CREDIT[self.jurisdiction],
            self.inflation_adjust,
            year
        ))
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
            return Money(0)

        # Determine the maximum claimable amount:
        max_spousal_amount = Money(
            extend_inflation_adjusted(
                constants.TAX_SPOUSAL_AMOUNT[self.jurisdiction],
                self.inflation_adjust,
                year
            )
        )

        # We need to know the spouse's net income to assess the credit:
        # TODO: Pass in deductions for both spouses as args?
        # This would help to avoid calling self.deductions many times.
        spouse = person.spouse
        spouse_net_income = (
            spouse.taxable_income - self.deductions(spouse, year)
        )

        # Figure out whether to assign the credit to this person or
        # their spouse based on who has more income:

        # If this is the lower-earner, use their spouse instead:
        person_net_income = (
            person.taxable_income - self.deductions(person, year)
        )
        if person_net_income < spouse_net_income:
            return Money(0)
        # If their incomes are the same, use memory location to
        # decide in a deterministic way:
        if person_net_income == spouse_net_income:
            if id(person) < id(spouse):
                return Money(0)

        # The credit is determined by reducing the spousal amount
        # by the spouse's (net) income, but in any event it's not
        # negative.
        credit = max(
            max_spousal_amount - spouse_net_income,
            Money(0)
        )

        return credit


class TaxCanada(object):
    """ Federal and provincial tax treatment for a Canadian resident.

    Attributes:
        inflation_adjust: A method with the following form:
            `inflation_adjust(target_year, base_year) -> Decimal`.
            See documentation for `Tax` for more information.
        province (str): The province in which income tax is paid.
    """

    def __init__(
            self, inflation_adjust, province='BC', payment_timing='start'):
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
            inflation_adjust, payment_timing=payment_timing)
        self.provincial_tax = TaxCanadaJurisdiction(
            inflation_adjust, province, payment_timing=payment_timing)
        self.province = province

    @property
    def payment_timing(self):
        """ Timing for refunds and payments. """
        return self.federal_tax.payment_timing

    @payment_timing.setter
    def payment_timing(self, val):
        """ Sets `payment_timing`. """
        self.federal_tax.payment_timing = val

    # Marginal rate information is helpful for client code, so implement
    # it here based on fed. and prov. tax brackets:

    def marginal_bracket(self, taxable_income, year):
        """ The top tax bracket that taxable_income falls into. """
        return max(
            self.federal_tax.marginal_bracket(taxable_income, year),
            self.provincial_tax.marginal_bracket(taxable_income, year)
        )

    def marginal_rate(self, taxable_income, year):
        """ The marginal rate for the given income. """
        return self.federal_tax.marginal_rate(taxable_income, year) + \
            self.provincial_tax.marginal_rate(taxable_income, year)

    def __call__(
            self, income, year,
            other_federal_deduction=None, other_federal_credit=None,
            other_provincial_deduction=None, other_provincial_credit=None):
        """ Determines Canadian taxes owing on given income sources.

        This includes provincial and federal taxes.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            other_federal_deduction (Money, dict[Person, Money]):
                Deductions to be applied against federal taxes.
                See documentation for `Tax` for more.
            other_federal_credit (Money, dict[Person, Money]):
                Credits to be applied against federal taxes.
                See documentation for `Tax` for more.
            other_provincial_deduction (Money, dict[Person, Money]):
                Deductions to be applied against provincial taxes.
                See documentation for `Tax` for more.
            other_provincial_credit (Money, dict[Person, Money]):
                Credits to be applied against provincial taxes.
                See documentation for `Tax` for more.

        Returns:
            Money: The total amount of tax owing for the year.
        """
        # This method has a lot of (optional) arguments, but this is
        # much cleaner than bundling federal and provincial amounts into
        # a collection to be passed in. (We tried it; it was ugly.)
        # pylint: disable=too-many-arguments

        # Total tax is simply the sum of federal and prov. taxes.
        return (
            self.federal_tax(
                income, year,
                other_federal_deduction, other_federal_credit) +
            self.provincial_tax(
                income, year,
                other_provincial_deduction, other_provincial_credit)
        )
