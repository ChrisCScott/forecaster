""" This module provides a Tax class and subclasses.

These classes are callable with the form `tax(taxable_income, year)`
"""

import collections
from decimal import Decimal
from forecaster.ledger import Money
from forecaster.person import Person
from forecaster.utility import (
    build_inflation_adjust, nearest_year, extend_inflation_adjusted,
    when_conv)

# NOTE: Consider making this a ledger-like object that stores values
# year-over-year. These values might include:
#   taxable_income (sum of sources' taxable income),
#   tax_withheld (sum of sources' withholdings, *plus* additional
#       mandatory tax instalment payments for when withholdings at
#       source fall below the CRA's thresholds)
#   tax_credit (sum of sources' tax credit, plus any additional
#       credit arising from the overall context)
#   tax_deduction (sum of sources' tax deduction, plus any additional
#           deduction arising from the overall context)
#   tax_refund_or_owing (total refund paid to persons or amount owing to
#       tax authority; refunds are positive and owing is negative)
# One of the challenges with this approach is that tax objects may be
# invoked several times in a given year. It may be better to leave it
# to Forecast to track that information. Or perhaps just store the last-
# generated return value of a Tax call.
# NOTE: Federal and provincial deduction and credit are separate;
# you can't just combine them by summation. Consider whether to use two
# separate dicts for tax_credit and tax_deduction, or to use a tuple
# (such as FedProvTuple).


class Tax(object):
    """ Determines taxes payable on taxable income.

    When called with a Money-type first argument (i.e. as
    `tax(taxable_income, year)`), this object returns the amount of tax
    payable on taxable income without any source-specific deduction or
    credit. This should correspond to how employment withholding taxes
    are calculated, so `gross_income - tax(gross_income, year)`
    will return a person's net income.

    For a more sophisticated assessment of credit/etc., provide a
    `Person` object as input (or an iterable of `Person` objects). This
    will assess taxable income, credits, and deductions for the `Person`
    and any `Account` objects they own.

    Thus, calling `tax({person1, person2}, year)` will
    return the total tax liability for the year for both person1 and
    person2, after applying any credit/etc., and including the
    employment income and taxable account activity of each `Person`.

    If spouses are passed in, they are processed together.

    Attributes:
        tax_brackets (dict): A dict of `{year: brackets}` pairs, where
            `brackets` is a dict of `{bracket: rate}` pairs. `bracket`
            must be convertible to Money and `rate` must be convertible
            to Decimal. `rate` will be interpreted as a percentage (e.g.
            Decimal('0.03') is interpreted as 3%)
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
            all lower brackets.

            For example, if there are $10, $100, and $1000 tax brackets,
            then `accum[year][$1000]` is equal to::

                tax_brackets[year][10] * 10 + tax_brackets[year][100] * 100

        inflation_adjust: A method with the following form:
            `inflation_adjust(target_year, base_year)`.

            Returns a Decimal scaling factor. Multiplying this by a
            nominal value in base_year will yield a nominal value in
            target_year with the same real value.

            Optional. If not provided, all values are assumed to be in
            real terms, so no inflation adjustment is performed.

    Args:
        taxable_income (Money, iterable): Taxable income for the year,
            either as a single scalar Money object or as an iterable
            (list, set, etc.) of sources of taxable income (i.e.
            Person/Account objects).
        year (int): The taxation year. This determines which tax rules
            and inflation-adjusted brackets are used.
        deduction (Money): Any other deduction which can be
            applied and which aren't evident from the income sources
            themselves. These will generally be itemized deduction.

            It's a good idea to be familiar with the Tax implementation
            you're working with before passing any of these, otherwise
            you risk double-counting.

            Optional.
        credit (Money): Any other tax credit which can be
            applied and which aren't evident from the income sources
            themselves. These will generally be boutique tax credit.

            Optional.
    """
    def __init__(
        self, tax_brackets, personal_deduction=None, credit_rate=None,
        inflation_adjust=None, payment_timing='start'
    ):
        """ Initializes the Tax object.

        Args:
            tax_brackets (dict[int, dict[Money, Decimal]]):
                `{year: brackets}` pairs, where `brackets` is itself a
                dict of `{bracket: rate}` pairs. Any income above
                `bracket` is taxed at `rate`. (It's thus usually a good
                idea to have at least a {0: rate} element!)
            personal_deduction (dict[int, Money]): `{year: deduction}`
                pairs. This deduction is applied to the income of each
                person when determining tax liability.
            credit_rate (dict[int, Money]): `{year: rate}` pairs.
                This rate is applied to any tax credits the person is
                eligible for when determining tax liability.
            inflation_adjust: A method with the following form:
                `inflation_adjust(val, this_year, target_year)`.
                Returns a Decimal object which is the inflation-
                adjustment factor from base_year to target_year.

                Optional. If not provided, all values are assumed to be
                in real terms, so no inflation adjustment is performed.
            payment_timing (Decimal, str): A `when`-formatted value
                specifying the timing of tax refunds and payments for
                amounts owing. For example, `'start'` indicates that
                refunds are paid on January 1st and that if taxes are
                owing then they are due on January 1st. Optional.
        """
        # NOTE: Consider allowing users to pass in non-year-indexed
        # values (e.g. so that `tax_brackets` can be a dict of
        # {Money: Decimal} pairs instead of {int: {Money: Decimal}}
        # pairs, and `personal_deduction` could be Money instead of
        # {int: Money}).
        # This would likely require adding an initial_year arg.
        # If it's provided, we would interpret any non-year-indexed args
        # as values for the key `initial_year`.

        # Don't set these args to {} in the call signature, or else
        # the mutated dicts will be shared between instances.
        if personal_deduction is None:
            personal_deduction = {}
        if credit_rate is None:
            credit_rate = {}

        # Enforce {int: {Money: Decimal}} types for tax_brackets and
        # generate an entry in `accum` for each new bracket:
        self._accum = {}
        self._tax_brackets = {}
        for year in tax_brackets:
            self.add_brackets(tax_brackets[year], year)

        self.inflation_adjust = build_inflation_adjust(inflation_adjust)

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

        self._payment_timing = None
        self.payment_timing = payment_timing

    def tax_brackets(self, year, bracket=None):
        """ Retrieve tax brackets for year. """
        # NOTE: We cache the inflation-adjusted tax brackets here,
        # but this will cause problems if you want to reuse the
        # Tax object for other Scenarios. If we keep this behaviour,
        # then Tax objects should be treated as mutable/disposable.
        if year not in self._tax_brackets:
            # Get the inflation-adjusted tax brackets for this year:
            base_year = nearest_year(self._tax_brackets, year)
            brackets = {
                key * self.inflation_adjust(year, base_year):
                self._tax_brackets[base_year][key]
                for key in self._tax_brackets[base_year]
            }
            self.add_brackets(brackets, year)
        if bracket is None:
            return self._tax_brackets[year]
        return self._tax_brackets[year][bracket]

    def accum(self, year, bracket=None):
        """ The accumulated tax payable for a given tax bracket. """
        # If we don't have this accum, we'll need to generate it.
        # add_brackets() does this for us.
        if year not in self._accum:
            # Get the inflation-adjusted tax brackets for this year:
            brackets = extend_inflation_adjusted(
                self._tax_brackets, self.inflation_adjust, year)
            self.add_brackets(brackets, year)
        if bracket is None:
            return self._accum[year]
        return self._accum[year][bracket]

    def personal_deduction(self, year):
        """ Personal deduction for `year`. """
        return extend_inflation_adjusted(
            self._personal_deduction, self.inflation_adjust, year)

    def deductions(self, person, year):
        """ The deductions the person is eligible for.

        Args:
            person (Person): The person for whom deductions
                are being assessed.
            year (int): The year for which deductions are being
                assessed.

        Returns:
            Money: The deductions for the person.
                This base class determines the personal deduction
                and other deductions provided by `Person`.
        """
        deductions = self.personal_deduction(year)
        deductions += person.tax_deduction_history[year]
        return deductions

    def credits(self, person, year, deductions=None):
        """ The tax credits each person is eligible for.

        Args:
            person (Person): The person for whom credits
                are being assessed.
            year (int): The year for which credits are being
                assessed.
            deductions (Money): The deductions claimable
                for the person. Optional.

        Returns:
            Money: The credits for the person.
        """
        credits = person.tax_credit_history[year]
        return credits

    def credit_rate(self, year):
        """ The credit rate for the given year. """
        return self._credit_rate[nearest_year(self._credit_rate, year)]

    @property
    def payment_timing(self):
        """ The timing of payments to/from the tax authority. """
        return self._payment_timing

    @payment_timing.setter
    def payment_timing(self, val):
        """ Sets `payment_timing`. """
        self._payment_timing = when_conv(val)

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

    def tax_money(
        self, taxable_income, year, deduction=Money(0), credit=Money(0)
    ):
        """ Returns taxes owing on a given amount of taxable income.

        This method does not apply any deductions or credits other than
        what is passed to it. For example, the personal deduction is
        not applied (unless explicitly passed).

        In general, you should be calling `tax_person` if you want
        to have deductions and credits automatically applied.

        Args:
            taxable_income (Money): The amount of income to be taxed,
                assuming it's taxable in the hands of a single person
                with no other income and no deduction or credit other
                than those provided explicitly to this method.
            year (int): The year for which tax treatment is applied.
            deduction (Money): Any deduction from taxable income to be
                applied before determining total tax liability.
                Optional.
            credit (Money): Any tax credit to be applied against tax
                liability; these are applied at the tax credit rate for
                `year`. Optional.

        Returns:
            Money: Total tax liability arising from `taxable_income` in
                `year`, after applying `deduction` and `credit`.
        """
        # Apply deductions:
        taxable_income -= deduction

        # Get the inflation-adjusted tax brackets for this year:
        brackets = self.tax_brackets(year)
        bracket = self.marginal_bracket(taxable_income, year)

        # `accum` gives us the tax owing on lower brackers, so we only
        # have to think about the effect of the marginal rate on any
        # income over the bracket threshold
        marginal_rate = brackets[bracket]
        accum = self.accum(year, bracket)

        # Assess tax owing on marginal bracket:
        gross_tax = accum + (taxable_income - bracket) * marginal_rate
        # Apply tax credts:
        net_tax = gross_tax - credit * self.credit_rate(year)
        # Assume credits are non-refundable:
        return max(net_tax, Money(0))

    def tax_person(
        self, person, year, deduction=Money(0), credit=Money(0)
    ):
        """ Returns tax treatment for an individual person.

        Args:
            person (Person): A person for whom tax liability will be
                determined.
            year (int): The year for which tax treatment is needed.
            deduction (Money): A deduction to be applied against
                the person's income, on top of whatever other deductions
                they are eligible for, including the personal deduction
                for the year and any specific `tax_deduction` attribute
                values of the person and their accounts.
            credit (Money): A credit to be applied against the
                person's tax liability, on top of whatever other credits
                they are eligible for (provided via the `tax_deduction`
                member of `person` and any of their accounts).

        Returns:
            Money: The tax liability of the person.
        """
        taxable_income = person.taxable_income_history[year]
        deductions = (
            person.tax_deduction_history[year]
            + self.deductions(person, year)
            + deduction
        )
        credits = (
            person.tax_credit_history[year]
            + self.credits(person, year)
            + credit
        )
        return self.tax_money(
            taxable_income,
            year,
            deductions,
            credits
        )

    def tax_people(self, people, year, deduction=None, credit=None):
        """ Total tax liability for a group of people.

        The people do not necessarily need to be spouses or related in
        any way. If a pair of spouses is in `people`, they will be
        passed to `tax_spouses` to be processed together.

        Args:
            people (iterable[Person]): Any number of people.
            year (int): The year for which tax treatment is needed.
            deduction (dict[Person, Money]): A dict of
                `{person: deduction}` pairs. Optional.
            credit (dict[Person, Money]): A dict of `{person: credit}`
                pairs. Optional.

        Returns:
            Money: The total tax liability of the people.
        """
        if deduction is None:
            deduction = {}
        if credit is None:
            credit = {}

        # Base case: If {} is passed, return $0.
        if not people:
            return Money(0)

        # Otherwise, grab someone at random and determine their taxes.
        person = next(iter(people))

        # Treat spouses in a special way; send them to a different
        # method for processing and recurse on the remaining folks.
        # NOTE: This logic (and the logic of Person.spouse) needs to be
        # overridden in subclasses implementing plural marriage.
        if person.spouse is not None and person.spouse in people:
            # Process taxes for the couple and recurse on the remaining
            # people.
            return self.tax_spouses(
                {person, person.spouse}, year, deduction, credit
            ) + self.tax_people(
                people - {person, person.spouse}, year, deduction, credit
            )
        # Otherwise, process this person as a single individual and
        # recurse on the remaining folks:
        else:
            # We don't want to override default values for tax_person,
            # so fill a kwargs dict with only explicitly-passed
            # deduction and credit for this person.
            kwargs = {}
            if person in deduction:
                kwargs['deduction'] = deduction[person]
            if person in credit:
                kwargs['credit'] = credit[person]

            # Determine tax owing for this person and then recurse.
            return self.tax_person(person, year, **kwargs) + \
                self.tax_people(people - {person}, year,
                                deduction, credit)

    def tax_spouses(self, people, year, deduction=None, credit=None):
        """ Tax treatment for a pair of spouses.

        This method doesn't provide any special tax treatment to the
        spouses, but it allows subclasses to override its functionality
        to apply special tax treatments.

        This method is also not restricted to two-element inputs,
        although in countries like Canada (which only recognizes two-
        person marriages for tax purposes) this method should only ever
        receive a two-element `people` input. By allowing for arbitrary-
        size inputs, subclasses can extend this functionality to deal
        with countries where plural marriage is recognized by the tax
        system.

        Args:
            people (iterable): Persons with mutual spousal
                relationships. In countries requiring monogamous
                marriages, this input should have exactly two elements.
            year (int): The year for which tax treatment is needed.
            deduction (dict[Person, Money]): A dict of
                `{person: deduction}` pairs. Optional.
            credit (dict[Person, Money]): A dict of `{person: credit}`
                pairs. Optional.

        Returns:
            Money: The tax liability of the spouses.
        """
        # Avoid using {} as a default value in the call signature:
        if deduction is None:
            deduction = {}
        if credit is None:
            credit = {}

        # Add together the tax treatment for each spouse, without doing
        # anything special (this is essentially the same logic as
        # tax_person, but without the check for spouses or recursion)
        tax = Money(0)
        for person in people:
            kwargs = {}
            if person in deduction:
                kwargs['deduction'] = deduction[person]
            if person in credit:
                kwargs['credit'] = credit[person]
            tax += self.tax_person(person, year, **kwargs)
        return tax

    def __call__(self, income, year,
                 deduction=None, credit=None):
        """ Determines taxes owing on one or more income sources.

        Each `Person` object passed as input may have a number of tax
        sources (e.g. `Account`s, `Benefit`s) associated with them,
        which `Tax` will take into account when calculating taxes.
        They don't need to be passed explicitly.

        Args:
            income (Money, Person, iterable): Taxable income for the
                year, either as a single scalar Money object, a single
                Person object, or as an iterable (list, set, etc.) of
                Person objects.
            year (int): The taxation year. This determines which tax
                rules and inflation-adjusted brackets are used.
            deduction (Money, dict[Person, Money]):
                Any other deduction which can be applied and which
                aren't modelled by the income sources themselves.
                These will generally be itemized deduction.

                If `income` is passed as an iterable, this should also
                be an iterable; otherwise it should be a Money object.

                It's a good idea to be familiar with the `Tax` and
                `Person` implementation you're working with before
                passing any of these, otherwise you risk double-counting
                if both the `Person` and `Tax` objects implement the
                same deduction.

                Optional.
            credit (Money, dict[Person, Money]):
                Any other tax credit which can be applied and which
                aren't modelled by the income sources themselves.

                These are usually boutique tax credits.

                See `deduction` for further comments on being familiar
                with both `Tax` and `Person` implementations when
                passing this.

                Optional.

            Returns:
                Money: The total amount of tax owing for the year.
        """
        year = int(year)
        # The different tax_* methods have different defaults for
        # optional arguments, so build a kwargs dict:
        kwargs = {}
        if deduction is not None:
            kwargs['deduction'] = deduction
        if credit is not None:
            kwargs['credit'] = credit

        # If taxpayers are non-scalar, interpret it as a group of people
        if isinstance(income, collections.abc.Iterable):
            return self.tax_people(income, year, **kwargs)
        # If it's just one taxpayer, use the appropriate method:
        elif isinstance(income, Person):
            return self.tax_person(income, year, **kwargs)
        # Otherwise, this is the easy case: interpret income as
        # Money (or Money-convertible)
        return self.tax_money(income, year, **kwargs)
