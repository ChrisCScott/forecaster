""" A module providing Canada-specific tax treatment. """

from constants_Canada import ConstantsCanada
import collections
from decimal import Decimal
from tax import Tax
from ledger import Person, Account
from ledger_Canada import *
from utility import *


class TaxCanadaJurisdiction(Tax):
    """ Federal or provincial tax treatment (Canada). """

    def __init__(self, inflation_adjustments, jurisdiction='Federal'):
        super().__init__(
            tax_brackets=ConstantsCanada.TaxBrackets[jurisdiction],
            personal_deduction=ConstantsCanada.TaxBasicPersonalDeduction[
                jurisdiction
            ],
            credit_rate=ConstantsCanada.TaxCreditRate[jurisdiction],
            inflation_adjust=inflation_adjustments)

        self.jurisdiction = jurisdiction

    def tax_deductions(self, people, year):
        """ Finds tax deductions available for each taxpayer.

        Args:
            people (set[Person]): A dict of `{taxpayer: sources}` pairs, where
                `taxpayer` is of type `Person` and `sources` is a set of
                income sources (accounts and people).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            A dict of `{taxpayer: (fed_deduction, prov_deduction)}`
            pairs, where `*_deduction` is of type Money.
            These are bundled into a FedProvTuple for convenience.
        """
        deductions = {person: Money(0) for person in people}
        # NOTE: Presenty, no deductions are modelled. We could extend
        # this in a future update to include, e.g. the family tax cut
        # or the childcare deduction.
        return deductions

    def tax_credits(self, people, year):
        """ Finds tax credits available for each taxpayer.

        Args:
            people (set[Person]): One or more `Person` objects, each
                having some number of accounts (or other tax sources).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            dict[Person, Money]: The tax credits available in this
            jurisdiction for each person.
        """
        credits = {person: Money(0) for person in people}
        for person in people:
            # Apply the pension income tax credit for each person:
            credits[person] += self._pension_income_credit(person, year)
        return credits

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
            ConstantsCanada.TaxPensionCredit[self.jurisdiction],
            self.inflation_adjust,
            year
        ))
        pension_income = min(pension_income, deduction_max)
        return pension_income * self.credit_rate(year)

    def __call__(self, income, year,
                 other_deductions=None, other_credits=None):
        """ Determines taxes owing on one or more income sources.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            other_deductions (Money, dict[Person, Money]):
                Deductions to be applied against the jurisdiction's
                taxes. See documentation for `Tax` for more.
            other_credits (Money, dict[Person, Money]):
                Credits to be applied against the jurisdiction's taxes.
                See documentation for `Tax` for more.

        Returns:
            Money: The total amount of tax owing for the year.
        """
        # Process deductions and credits, which take different forms
        # depending on the form of `income`:
        # For Money `income`, there's no method to call to determine
        # deductions/credits; either apply what was passed, or set to $0
        if isinstance(income, Money):
            deductions = other_deductions if other_deductions is not None \
                else Money(0)
            credits = other_credits if other_credits is not None \
                else Money(0)
        # If there's just one person, we expect other_* to be Money
        # objects, not dicts, so handle them appropriately:
        elif isinstance(income, Person):
            # NOTE: These methods require iterable `income` args:
            deductions = self.tax_deductions({income}, year)[income]
            credits = self.tax_credits({income}, year)[income]
            if other_deductions is not None:
                deductions += other_deductions
            if other_credits is not None:
                credits += other_credits
        # If there are multiple people passed, expect a form of
        # dict[Person, Money] for other_* params:
        else:
            deductions = self.tax_deductions(income, year)
            credits = self.tax_credits(income, year)
            if other_deductions is not None:
                for person in deductions:
                    if person in other_deductions:
                        deductions[person] += other_deductions[person]
            if other_credits is not None:
                for person in deductions:
                    if person in other_credits:
                        credits[person] += other_credits[person]

        # Determine taxes owing in the usual way, applying the
        # jurisdiction-specific credits and deductions:
        return super().__call__(income, year, deductions, credits)


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
        return max(self.federal_tax.marginal_bracket(year),
                   self.provincial_tax.marginal_bracket(year))

    def marginal_rate(self, taxable_income, year):
        """ The marginal rate for the given income. """
        return self.federal_tax.marginal_rate(taxable_income, year) + \
            self.provincial_tax.marginal_rate(taxable_income, year)

    def __call__(self, income, year,
                 other_federal_deductions=None,
                 other_federal_credits=None,
                 other_provincial_deductions=None,
                 other_provincial_credits=None):
        """ Determines Canadian taxes owing on given income sources.

        This includes provincial and federal taxes.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            other_federal_deductions (Money, dict[Person, Money]):
                Deductions to be applied against federal taxes.
                See documentation for `Tax` for more.
            other_federal_credits (Money, dict[Person, Money]):
                Credits to be applied against federal taxes.
                See documentation for `Tax` for more.
            other_provincial_deductions (Money, dict[Person, Money]):
                Deductions to be applied against provincial taxes.
                See documentation for `Tax` for more.
            other_provincial_credits (Money, dict[Person, Money]):
                Credits to be applied against provincial taxes.
                See documentation for `Tax` for more.

        Returns:
            Money: The total amount of tax owing for the year.
        """
        # Total tax is simply the sum of federal and prov. taxes.
        return (
            self.federal_tax(
                income, year,
                other_federal_deductions, other_federal_credits) +
            self.provincial_tax(
                income, year,
                other_provincial_deductions, other_provincial_credits)
            )
