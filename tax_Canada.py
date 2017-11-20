""" A module providing Canada-specific tax treatment. """

from constants import Constants
import collections
from decimal import Decimal
from tax import Tax
from ledger import Person, Account
from ledger_Canada import *
from utility import *


class SumOfDicts(dict):
    """ A dict that lazily sums the values of two or more dicts """
    def __init__(self, *args):
        # Accepts any number of input dicts (or dict-like objects)
        self.dicts = args

    def __missing__(self, key):
        # Attempt to return (and store) the sum of key values across all
        # dicts in the SumOfDicts
        return self.setdefault(key, sum((d[key] for d in self.dicts)))

    def __contains__(self, key):
        # Override the `in` operator to use the underlying dicts so that
        # iteration/etc. will automatically look through to those
        return all(key in d for d in self.dicts)

# NOTE: Eventually, we'll probably implement a separate class for each
# province and delete this tuple. For now, though, the program logic is
# simple enough that we can deal with all of this in one class
# (CanadianResidentTax)
# TODO (v2): Revise CanadianResidentTax to allow for different people to
# be taxed at different provincial rates. (Build provincial tax
# treatment objects dynamically based on input Persons?)
FedProvTuple = collections.namedtuple('FedProvTuple', 'federal provincial')


class CanadianJurisdictionTax(Tax):
    """ Federal or provincial tax treatment (Canada). """

    def __init__(self, inflation_adjustments, jurisdiction='Federal'):
        super().__init__(Constants.TaxBrackets[jurisdiction],
                         inflation_adjustments,
                         Constants.TaxBasicPersonalDeduction[jurisdiction],
                         Constants.TaxCreditRate[jurisdiction])


class CanadianResidentTax(object):
    """ Federal and provincial tax treatment for a Canadian resident.

    Attributes:
        inflation_adjustments (dict): A dict of `{year: Decimal}` pairs.
        province (str): The province in which income tax is paid.
    """

    def __init__(self, inflation_adjustments, province='BC'):
        self.federal_tax = CanadianResidentTax(inflation_adjustments)
        self.provincial_tax = CanadianResidentTax(
            inflation_adjustments, province)

    def _merge_brackets(self, brackets1, brackets2, bracket=None):
        """ """
        brackets = set(brackets1).union(brackets2)
        bracket = {
            bracket: brackets1[max(b for b in brackets1 if b <= bracket)] +
            brackets2[max(b for b in brackets2 if b <= bracket)]
        }
        if bracket is None:
            return brackets
        else:
            return brackets[bracket]

    def tax_brackets(self, year, bracket=None):
        """ Retrieve tax brackets for year. """
        # Synthesize brackets from federal/provincial taxes
        # NOTE: Avoid invoking the `_tax_brackets` dict directly,
        # since they're extended on the fly by `tax_brackets()`
        return self._merge_brackets(
            self.federal_tax.tax_brackets(year),
            self.provincial_tax.tax_brackets(year),
            bracket
        )

    def accum(self, year, bracket=None):
        """ The accumulated tax payable for a given tax bracket. """
        return self._merge_brackets(
            self.federal_tax.accum(year),
            self.provincial_tax.accum(year),
            bracket
        )

    def inflation_adjustments(self, year):
        # This is identical between federal and provincial taxes.
        return self.federal_tax.inflation_adjustments(year)

    def personal_deduction(self, year):
        """ The inflation-adjusted personal deduction. """
        return self.federal_tax.personal_deduction(year) + \
            self.provincial_tax.personal_deduction(year)

    def credit_rate(self, year):
        """ The credit rate for the given year. """
        return self.federal_tax.credit_rate(year) + \
            self.provincial_tax.credit_rate(year)

    def marginal_bracket(self, taxable_income, year):
        """ The top tax bracket that taxable_income falls into. """
        return max(self.federal_tax.marginal_bracket(year),
                   self.provincial_tax.marginal_bracket(year))

    def marginal_rate(self, taxable_income, year):
        """ The marginal rate for the given income. """
        return self.federal_tax.marginal_rate(taxable_income, year) + \
            self.provincial_tax.marginal_rate(taxable_income, year)

    def tax_deductions(self, people, year):
        """ Finds tax deductions available for each taxpayer.

        Args:
            sources (dict): A dict of `{taxpayer: sources}` pairs, where
                `taxpayer` is of type `Person` and `sources` is a set of
                income sources (accounts and people).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            A dict of `{taxpayer: (fed_deduction, prov_deduction)}`
            pairs, where `*_deduction` is of type Money.
            These are bundled into a FedProvTuple for convenience.
        """
        # TODO: Implement tax deductions.
        return FedProvTuple(Money(0), Money(0))

    def tax_credits(self, sources, year):
        """ Finds tax credits available for each taxpayer.

        Args:
            sources (dict): A dict of `{taxpayer: sources}` pairs, where
                `taxpayer` is of type `Person` and `sources` is a set of
                income sources (accounts and people).
            year (int): The year in which money is expressed (used for
                inflation adjustment)

        Returns:
            A dict of `{taxpayer: (fed_credit, prov_credit)}` pairs,
            where `*_deduction` is of type Money.
            These are bundled into a FedProvTuple for convenience.
        """
        # TODO: Implement tax credit logic.
        return FedProvTuple(Money(0), Money(0))

    def __call__(self, income, year,
                 other_federal_deductions=0, other_federal_credits=0,
                 other_provincial_deductions=0, other_provincial_credits=0):
        # In the easiest case, we don't have any account information;
        # just pass the information on to federal/provincial Tax objects
        if isinstance(income, Money):
            return (
                self.federal_tax(
                    income, year,
                    other_federal_deductions, other_federal_credits) +
                self.provincial_tax(
                    income, year,
                    other_provincial_deductions, other_provincial_credits)
            )
        # If income sources are provided, divide those up into a
        # separate call for each taxpayer.
        # First, divide up accounts by taxpayer.
        deductions = self.tax_deductions(sources, year)
        credits = self.tax_credits(sources, year)

        return (
            self.federal_tax(
                income, year,
                other_federal_deductions + deductions.federal,
                other_federal_credits + credits.federal) +
            self.provincial_tax(
                income, year,
                other_provincial_deductions + deductions.provincial,
                other_provincial_credits + credits.provincial)
            )
