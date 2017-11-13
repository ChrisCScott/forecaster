""" This module provides a Tax class and subclasses.

These classes are callable with the form `tax(taxable_income, year)`
"""

from constants import Constants
import collections
from decimal import Decimal
from ledger import *


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


# NOTE: Consider making this a ledger-like object that stores values
# year-over-year. These values might include:
    # taxable_income (sum of sources' taxable income),
    # tax_withheld (sum of sources' withholdings, *plus* additional
    #   mandatory tax instalment payments for when withholdings at source
    #   fall below the CRA's thresholds)
    # tax_credits (sum of sources' tax credits, plus any additional credits
    #   arising from the overall context)
    # tax_deductions (sum of sources' tax deductions, plus any additional
    #   deductions arising from the overall context)
    # tax_refund_or_owing (total amount paid to persons [refund] or payable
    #   to CRA [owing]; refunds are positive and owing is negative)
# One of the challenges with this approach is that tax objects may be
# invoked several times in a given year. It may be better to leave it
# to Forecast to track that information. Or perhaps just store the last-
# generated return value of a Tax call.
# NOTE: Federal and provincial deductions and credits are separate;
# you can't just combine them by summation. Consider whether to use two
# separate dicts for tax_credits and tax_deductions, or to use a tuple
# (such as FedProvTuple).


class Tax(object):
    """ Determines taxes payable on taxable income.

    When called with a Money-type first argument (i.e. as
    `tax(taxable_income, year)`), this object returns the amount of tax
    payable on taxable income without any source-specific deductions or
    credits. This should correspond to how employment withholding taxes
    are calculated, so `gross_income - tax(gross_income, year)`
    will return a person's net income.

    For a more sophisticated assessment of credits/etc., provide an
    iterable of sources as the first argument. Each source must provide
    the following methods:
        taxable_income(self [, year])
        tax_withheld(self [, year])
        tax_credit(self [, year])
        tax_deduction(self [, year])

    Thus, calling `tax({person, account1, ... accountn}, year)` will
    return the total tax liability for the year, after applying any
    credits/etc. and including `person`'s employment income and any
    account earnings.

    Attributes:
        tax_brackets (dict): A dict of `{year: brackets}` pairs, where
            `brackets` is a dict of `{bracket: rate}` pairs. `bracket`
            must be convertible to Money and `rate` must be convertible
            to Decimal. `rate` will be interpreted as a percentage (e.g.
            Decimal('0.03') is interpreted as 3%)
        inflation_adjustments (dict): A dict of `{year: Decimal}` pairs,
            where the Decimal value is the adjustment for the year.
        personal_deduction (dict): A dict of `{year: deduction}` pairs,
            where `deduction` is convertible to Money.
            The personal deduction for a given year is deducted from
            income when determining income tax in that year.
        credit_rate (dict): A dict of `{year: rate}` pairs, where `rate`
            is convertible to Decimal.
            The credit rate is used to determine how much each tax
            credit reduced total tax liability.
        accum (dict): A dict of `{year: {bracket: accum}}` pairs, where
            each `bracket` corresponds to a key in `tax_brackets` and
            `accum` is the sum of tax payable on the income falling into
            all lower brackets. For example, if there are $10, $100, and
            $1000 tax brackets, then `accum[year][$1000]` is equal to
            `tax_brackets[year][$10] * $10 + tax_brackets[year][$100] *
            $100`.

    Args:
        taxable_income (Money, iterable): Taxable income for the year,
            either as a single scalar Money object or as an iterable
            (list, set, etc.) of sources of taxable income (i.e.
            Person/Account objects).
        year (int): The taxation year. This determines which tax rules
            and inflation-adjusted brackets are used.
        other_deductions (Money): Any other deductions which can be
            applied and which aren't evident from the income sources
            themselves. These will generally be itemized deductions.
            It's a good idea to be familiar with the Tax implementation
            you're working with before passing any of these, otherwise
            you risk double-counting.
            Optional.
        other_credits (Money): Any other tax credits which can be
            applied and which aren't evident from the income sources
            themselves. These will generally be boutique tax credits.
            Optional.
    """
    def __init__(self, tax_brackets, inflation_adjustments,
                 personal_deduction={}, credit_rate={}):
        # TODO: Consider whether this should receive persons/accounts as
        # args, or whether this should be passed as an arg to persons/accounts
            # NOTE: I think I favour receiving accounts/etc. here, since
            # tax logic will require looking at account types and applying tax
            # rules holistically in view of other accounts/etc.
            # NOTE: (The exception here is `Person`, which will be passed a
            # tax object for convenience)
            # NOTE: This is likely to be significantly more efficient
            # than the current implementation, which re-sorts accounts
            # and identifies taxpayers with each invocation.
        # TODO: Add an initial_year arg. If it's provided, interpret any
        # scalar args (or, for tax_brackets, non-year-indexed dict) as
        # {initial_year: arg} dicts (i.e. single-value dicts). This will
        # make building a Tax object much less confusing.

        # Enforce {int: {Money: Decimal}} types for tax_brackets and
        # generate an entry in `accum` for each new bracket:
        self._accum = {}
        self._tax_brackets = {}
        for year in tax_brackets:
            self.add_brackets(tax_brackets[year], year)

        # Enforce {int: Decimal} types for inflation_adjustments:
        self._inflation_adjustments = {
            int(year): Decimal(inflation_adjustments[year])
            for year in inflation_adjustments
        }

        if personal_deduction != {}:
            # Enforce {int: Money} types for personal_deduction:
            self._personal_deduction = {
                int(year): Money(personal_deduction[year])
                for year in personal_deduction
            }
        else:
            # If this arg wasn't passed, assume there's no deduction
            self._personal_deduction = {min(self._tax_brackets): Money(0)}

        if credit_rate != {}:
            # Enforce {int: Decimal} types for credit_rate:
            self._credit_rate = {
                int(year): Decimal(credit_rate[year])
                for year in credit_rate
            }
        else:
            # If this argument wasn't passed, default to behaviour where
            # all tax credits are fully refundable (i.e. credits reduce
            # tax liability at a 100% rate)
            self._credit_rate = {min(self._tax_brackets): Decimal(1)}

    def tax_brackets(self, year, bracket=None):
        """ Retrieve tax brackets for year. """
        # NOTE: We cache the inflation-adjusted tax brackets here,
        # but this will cause problems if you want to reuse the
        # Tax object for other Scenarios. If we keep this behaviour,
        # then Tax objects should be treated as mutable/disposable.
        # TODO: Confirm that this is desired behaviour once the
        # application is in a state where we can run efficiency metrics.
        if year not in self._tax_brackets:
            # Get the inflation-adjusted tax brackets for this year:
            brackets = inflation_adjust(self._tax_brackets,
                                        self._inflation_adjustments,
                                        year)
            self.add_brackets(brackets, year)
        if bracket is None:
            return self._tax_brackets[year]
        else:
            return self._tax_brackets[year][bracket]

    def accum(self, year, bracket=None):
        """ The accumulated tax payable for a given tax bracket. """
        # If we don't have this accum, we'll need to generate it.
        # add_brackets() does this for us.
        if year not in self._accum:
            # Get the inflation-adjusted tax brackets for this year:
            brackets = inflation_adjust(self._tax_brackets,
                                        self._inflation_adjustments,
                                        year)
            self.add_brackets(brackets, year)
        if bracket is None:
            return self._accum[year]
        else:
            return self._accum[year][bracket]

    def inflation_adjustments(self, year):
        # This one is easy - there's no extrapolating to do, just use
        # the values that you've been given.
        return self.inflation_adjustments[year]

    def personal_deduction(self, year):
        """ The inflation-adjusted personal deduction. """
        return inflation_adjust(self._personal_deduction,
                                self._inflation_adjustments,
                                year)

    def credit_rate(self, year):
        """ The credit rate for the given year. """
        return nearest_val(self._credit_rate, year)

    def marginal_bracket(self, taxable_income, year):
        """ The top tax bracket that taxable_income falls into. """
        brackets = self.tax_brackets(year)
        return max(
            (bracket for bracket in brackets
             if bracket < taxable_income),
            default=min(brackets)
        )

    def marginal_rate(self, taxable_income, year):
        """ The marginal rate for the given income. """
        brackets = self.tax_brackets(year)
        return brackets[self.marginal_bracket(taxable_income, year)]

    def add_brackets(self, brackets, year):
        """ Adds a year of tax brackets to attribute self.tax_brackets.

        Also generates an `accum` dict based on the tax brackets.
        """
        year = int(year)
        # Enforce types for the new brackets (We'll reuse this short
        # name later when building the accum dict for convenience)
        brackets = {
            Money(key): Decimal(brackets[key])
            for key in brackets
        }
        self._tax_brackets[year] = brackets

        self.add_accum(brackets, year)

    def add_accum(self, brackets, year):
        """ Generates an accum dict for the given brackets and year. """
        # For each bracket, the new accumulation is whatever the accum
        # is for the next-lowest bracket (which itself is the
        # accumulation of all lower brackets' tax owing), plus the
        # marginal rate of that bracket applied to the full taxable
        # income within its range.
        prev = min(brackets)  # We need to look at 2 brackets at a time
        self._accum[year] = {prev: Money(0)}  # Accum for lowest bracket
        iterator = sorted(brackets.keys())  # Look at brackets in order
        iterator.remove(prev)  # Lowest bracket is already accounted for.
        for bracket in iterator:
            self._accum[year][bracket] = \
                (bracket - prev) * brackets[prev] + self._accum[year][prev]
            prev = bracket  # Keep track of next-lowest bracket

    def tax_money(self, taxable_income, year,
                  other_deductions=Money(0), other_credits=Money(0)):
        """ Returns taxes owing without source-specific deductions/etc. """
        # TODO: Flesh out docstring.

        # Some calling methods might pass None, so deal with the here:
        if other_deductions is None:
            other_deductions = Money(0)
        if other_credits is None:
            other_credits = Money(0)

        # Apply the personal deduction and any other deductions before
        # determining brackets.
        taxable_income = max(
            Money(taxable_income) - (self.personal_deduction(year) +
                                     other_deductions),
            Money(0))
        # Get the inflation-adjusted tax brackets for this year:
        brackets = self.tax_brackets(year)
        bracket = self.marginal_bracket(taxable_income, year)
        # By using accum, we only have to think about the effect of
        # the marginal rate on any income over the bracket threshold
        marginal_rate = brackets[bracket]
        accum = self.accum(year, bracket)
        # NOTE: The following assumes that tax credits are nonrefundable
        return max(
            accum + (taxable_income - bracket) * marginal_rate -
            other_credits * self.credit_rate(year),
            Money(0))

    def tax_person(self, person, year,
                   other_deductions=Money(0), other_credits=Money(0)):
        """ """
        # TODO: Flesh out docstring.

        # Some calling methods might pass None, so deal with the here:
        if other_deductions is None:
            other_deductions = Money(0)
        if other_credits is None:
            other_credits = Money(0)
        # Accumulate the relevant tax information for the person:
        taxable_income = person.taxable_income(year) + \
            sum((x.taxable_income(year) for x in person.accounts))
        tax_credits = person.tax_credit(year) + \
            sum((x.tax_credit(year) for x in person.accounts))
        tax_deductions = person.tax_deduction(year) + \
            sum((x.tax_deduction(year) for x in person.accounts))
        # Apply deductions to income, find taxes payable based on that,
        # and then apply tax credits.
        return self.tax_money(
            taxable_income - (tax_deductions + other_deductions), year
        ) - (tax_credits + other_credits) * self.credit_rate(year)

    def tax_people(self, people, year, other_deductions={},
                   other_credits={}):
        """ Applies available deductions/etc. based on income sources. """
        # TODO: Flesh out docstring.
        tax_owed = Money(0)
        for person in people:
            # Check to see whether other_deductions and other_credits
            # are indexable based on `person`, since deductions and
            # credits are person-specific (i.e. there's no generic
            # way to apply, say, a `Money(100)` deduction to 2 people -
            # do we apply it to both? To just one? If the latter, which
            # one? Is it split between them somehow?)
            if person in other_deductions:
                deductions = other_deductions[person]
            else:
                deductions = Money(0)

            if person in other_credits:
                credits = other_credits[person]
            else:
                credits = Money(0)

            # Iteratively determine tax owing for each person.
            tax_owed += self.tax_person(person, year, deductions, credits)
        return tax_owed

    # TODO: Implement tax_people and tax_person (this will involve
    # making tax_people a simple loop and tax_person hold much of
    # the logic of the former tax_on_sources (now tax_people).
    # NOTE: This allows places with household taxpayers (like the US)
    # to simply override tax_people to check for spouses. We'll do that
    # in Canada as well to apply spousal tax credits and the like.
    def __call__(self, taxpayers, year,
                 other_deductions=None, other_credits=None):
        """ Makes `Tax` objects callable. """
        year = int(year)
        # The different tax_* methods have different defaults for
        # optional arguments, so build a kwargs dict:
        kwargs = {}
        if other_deductions is not None:
            kwargs['other_deductions'] = other_deductions
        if other_credits is not None:
            kwargs['other_credits'] = other_credits

        # If taxpayers are non-scalar, interpret it as a group of people
        if isinstance(taxpayers, collections.Iterable):
            return self.tax_people(taxpayers, year, **kwargs)
        # If it's just one taxpayer, 
        elif isinstance(taxpayers, Person):
            return self.tax_person(taxpayers, year, **kwargs)
        # Otherwise, this is the easy case: interpret taxable_income as
        # Money (or Money-convertible)
        else:
            return self.tax_money(taxpayers, year, **kwargs)


FedProvTuple = collections.namedtuple('FedProvTuple', 'federal provincial')


class CanadianResidentTax(object):
    """ Federal and provincial tax treatment for a Canadian resident.

    Attributes:
        inflation_adjustments (dict): A dict of `{year: Decimal}` pairs.
        province (str): The province in which income tax is paid.
    """

    def __init__(self, inflation_adjustments, province='BC'):
        self.federal_tax = Tax(
            Constants.TaxFederalBrackets,
            inflation_adjustments,
            Constants.TaxFederalBasicPersonalDeduction,
            Constants.TaxFederalCreditRate)
        self.provincial_tax = Tax(
            Constants.TaxProvincialBrackets[province],
            inflation_adjustments,
            Constants.TaxProvincialBasicPersonalDeduction[province],
            Constants.TaxProvincialCreditRate[province])

    def __call_both(taxable_income, year, other_federal_deductions,
                    other_federal_credits, other_provincial_deductions,
                    other_provincial_credits):
        """ Convenience method for calling federal and provincial tax. """
        return (
            self.federal_tax(
                taxable_income, year,
                other_federal_deductions, other_federal_credits) +
            self.provincial_tax(
                taxable_income, year,
                other_provincial_deductions, other_provincial_credits)
        )

    def tax_deductions(self, sources, year):
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

    def sources_by_taxpayer(self, sources):
        """ """
        # First, identify taxpayers:
        taxpayers = {
            a.owner for a in sources if isinstance(a, Account)
        }.update({p for p in sources if isinstance(p, Person)}) - {None}

        # If no taxpayers are named, lump all sources together with one
        # unnamed (i.e. None) taxpayer:
        if taxpayers == {}:
            return {None: sources}

        # Set up a dict to populate.
        sources_by_taxpayer = {}
        # If we have accounts that don't have an owner, assume the
        # worst - that is, assume that they are taxable in the hands of
        # the highest-earning person. Select them as the default owner.
        default_owner = max(taxpayers - {None})

        # Populate the dict taxpayer-by-taxpayer.
        for taxpayer in taxpayers:
            sources_by_taxpayer[taxpayer] = {
                a for a in sources
                if isinstance(a, Account) and a.owner == taxpayer}
            # If this is the default owner, add in any accounts without
            # an explicit owner.
            if taxpayer == default_owner:
                sources_by_taxpayer.update({
                    a for a in sources
                    if isinstance(a, Account) and a.owner is None}
                )

        return sources_by_taxpayer

    def __call__(self, taxable_income, year, other_federal_deductions=0,
                 other_federal_credits=0, other_provincial_deductions=0,
                 other_provincial_credits=0):
        # In the easiest case, we don't have any account information;
        # just pass the information on to federal/provincial Tax objects
        if isinstance(taxable_income, Money):
            return self.__call_both(
                taxable_income, year, other_federal_deductions,
                other_federal_credits, other_provincial_deductions,
                other_provincial_credits)
        # If income sources are provided, divide those up into a
        # separate call for each taxpayer.
        # First, divide up accounts by taxpayer.
        sources = self.sources_by_taxpayer(taxable_income)
        deductions = self.tax_deductions(sources, year)
        credits = self.tax_deductions(sources, year)

        # Now accumulate taxes owed by each of the taxpayers:
        taxes_owing = 0
        for taxpayer in sources:
            # Add each taxpayer's federal and provincial tax to the
            # total taxes owing for all taxpayers.
            taxes_owing += self.__call_both(
                sources[taxpayer], year,
                other_federal_deductions + deductions.federal,
                other_federal_credits + credits.federal,
                other_provincial_deductions + deductions.provincial,
                other_provincial_credits + credits.provincial)
        # TODO: Implement Canada-specific specific tax deductions and
        # credits, like the pension tax credit, spousal tax credits,
        # spousal RRSP deductions, etc.
        return taxes_owing
