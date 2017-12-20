""" A module providing Canada-specific tax treatment. """

from forecaster.ledger import Money
from forecaster.person import Person
from forecaster.tax import Tax
from forecaster.canada.accounts import RRSP
from forecaster.canada import constants
from forecaster.utility import extend_inflation_adjusted


class TaxCanadaJurisdiction(Tax):
    """ Federal or provincial tax treatment (Canada). """

    def __init__(self, inflation_adjustments, jurisdiction='Federal'):
        super().__init__(
            tax_brackets=constants.TAX_BRACKETS[jurisdiction],
            personal_deduction=constants.TAX_PERSONAL_DEDUCTION[
                jurisdiction
            ],
            credit_rate=constants.TAX_CREDIT_RATE[jurisdiction],
            inflation_adjust=inflation_adjustments)

        self.jurisdiction = jurisdiction

    def tax_deduction(self, people, year):
        """ Finds tax deduction available for each taxpayer.

        Args:
            people (set[Person]): One or more `Person` objects, each
                having some number of accounts (or other tax sources).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            dict[Person, Money]: The tax deduction available in this
            jurisdiction for each person.
        """
        # NOTE: Presenty, no deduction are modelled. We could extend
        # this in a future update to include, e.g. the family tax cut
        # or the childcare deduction.
        # Since we want to preserve this call signature for subclassing or
        # future expansions, let's disable Pylint's complaints:
        # pylint: disable=unused-argument,no-self-use
        deduction = {person: Money(0) for person in people}
        return deduction

    def tax_credit(self, people, year):
        """ Finds tax credit available for each taxpayer.

        Args:
            people (set[Person]): One or more `Person` objects, each
                having some number of accounts (or other tax sources).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            dict[Person, Money]: The tax credit available in this
            jurisdiction for each person.
        """
        credit = {person: Money(0) for person in people}
        for person in people:
            # Apply the pension income tax credit for each person:
            credit[person] += self._pension_income_credit(person, year)
        return credit

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
        pension_income = sum(
            account.outflows for account in person.accounts
            if isinstance(account, RRSP)
            # NOTE: Other qualified pension income sources can be
            # added here
        )
        # Each jurisdiction has a maximum claimable amount for the
        # pension credit, so determine that (inflation-adjusted
        # amount) here:
        deduction_max = Money(extend_inflation_adjusted(
            constants.TAX_PENSION_CREDIT[self.jurisdiction],
            self.inflation_adjust,
            year
        ))
        pension_income = min(pension_income, deduction_max)
        return pension_income * self.credit_rate(year)

    def __call__(self, income, year,
                 other_deduction=None, other_credit=None):
        """ Determines taxes owing on one or more income sources.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            other_deduction (Money, dict[Person, Money]):
                Deductions to be applied against the jurisdiction's
                taxes.

                See documentation for `Tax` for more.
            other_credit (Money, dict[Person, Money]):
                Credits to be applied against the jurisdiction's taxes.

                See documentation for `Tax` for more.

        Returns:
            Money: The total amount of tax owing for the year.
        """
        # Process deduction and credit, which take different forms
        # depending on the form of `income`:
        # For Money `income`, there's no method to call to determine
        # deduction/credit; either apply what was passed, or set to $0
        if isinstance(income, Money):
            deduction = other_deduction if other_deduction is not None \
                else Money(0)
            credit = other_credit if other_credit is not None \
                else Money(0)
        # If there's just one person, we expect other_* to be Money
        # objects, not dicts, so handle them appropriately:
        elif isinstance(income, Person):
            # NOTE: These methods require iterable `income` args:
            deduction = self.tax_deduction({income}, year)[income]
            credit = self.tax_credit({income}, year)[income]
            if other_deduction is not None:
                deduction += other_deduction
            if other_credit is not None:
                credit += other_credit
        # If there are multiple people passed, expect a form of
        # dict[Person, Money] for other_* params:
        else:
            deduction = self.tax_deduction(income, year)
            credit = self.tax_credit(income, year)
            if other_deduction is not None:
                for person in deduction:
                    if person in other_deduction:
                        deduction[person] += other_deduction[person]
            if other_credit is not None:
                for person in deduction:
                    if person in other_credit:
                        credit[person] += other_credit[person]

        # Determine taxes owing in the usual way, applying the
        # jurisdiction-specific credit and deduction:
        return super().__call__(income, year, deduction, credit)


class TaxCanada(object):
    """ Federal and provincial tax treatment for a Canadian resident.

    Attributes:
        inflation_adjust: A method with the following form:
            `inflation_adjust(target_year, base_year) -> Decimal`.
            See documentation for `Tax` for more information.
        province (str): The province in which income tax is paid.
    """

    def __init__(self, inflation_adjust, province='BC'):
        """ Initializes TaxCanada.

        Args:
            inflation_adjust: A method with the following form:
                `inflation_adjust(target_year, base_year) -> Decimal`.

                Can be passed as dict or Decimal-convertible scalar,
                which will be converted to a callable object.

                See documentation for `Tax` for more information.
            province (str): The province in which income tax is paid.
        """
        self.federal_tax = TaxCanadaJurisdiction(inflation_adjust)
        self.provincial_tax = TaxCanadaJurisdiction(
            inflation_adjust, province)
        self.province = province

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
        other_provincial_deduction=None, other_provincial_credit=None
    ):
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
