""" A module providing a Person class. """

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from forecaster.ledger import (
    TaxSource, recorded_property, recorded_property_cached)
from forecaster.utility import Timing


class Person(TaxSource):
    """ Represents a person's basic information: age and retirement age.

    Arguments:
        name (str): The person's name. No specific form is required;
            this is only used for display, not any computations.
        birth_date (datetime, str, int): The person's birth date.
            May be passed as an int (interpreted as the birth year) or
            as a datetime-convertible value (e.g. a string in a
            suitable format)
        retirement_date (datetime, str, int): The person's retirement
            date. Optional.
            May be passed as an int (interpreted as the birth year) or
            as a datetime-convertible value (e.g. a string in a
            suitable format)
        gross_income (Money): Annual gross income for the initial year.
        raise_rate (float, Callable): The person's raise in gross
            income for each year relative to the previous year.
        payment_timing (Timing, dict[float, float]): The timings of
            payments mapped to the weight of each payment. Optional.
        spouse (Person): The person's spouse. This linkage is
            one-to-one; the spouse's `spouse` attribute points back to
            this Person.
        tax_treatment (Tax): The tax treatment of the person. A callable
            object; see documentation for `Tax` for more information.
        inputs (dict[str, dict[int, Any]]): `{attr: {year: val}}`
            pairs, where `attr` is any one of `Person`'s recorded
            propertes, namely:

            * taxable_income
            * tax_withheld
            * tax_credit
            * tax_deduction
            * gross_income
            * net_income
            * raise_rate

    Attributes:
        accounts (set): All accounts naming this Person as an owner.
        name (str): The person's name. No specific form is required;
            this is only used for display, not any computations.
        birth_date (datetime): The person's birth date.
            May be passed as an int (interpreted as the birth year) or
            as a datetime-convertible value (e.g. a string in a
            suitable format)
        retirement_date (datetime): The person's retirement date.
            Optional.
            May be passed as an int (interpreted as the birth year) or
            as a datetime-convertible value (e.g. a string in a
            suitable format)
        gross_income (Money): Annual gross income for the current year.
        gross_income_history (dict[int, Money]): Gross income for all
            years on record.
        net_income (Money): Annual net income for the current year.
        net_income_history (dict[int, Money]): Net income for all
            years on record.
        raise_rate_callable (callable): A function for determining the
            Person's raise rate for a given year. A callable object with
            the form `raise_rate_function(year) -> float`.
        raise_rate (float): The person's raise in gross income this
            year relative to last year.
        raise_rate_history (dict[int, float]): Raises for all years
            on record.
        payment_timing (Timing, dict[float, float]): The timings of
            payments and the weight of each payment timing. Optional.
        spouse (Person): The person's spouse. This linkage is
            one-to-one; the spouse's `spouse` attribute points back to
            this Person.
        tax_treatment (Tax): The tax treatment of the person. A callable
            object; see documentation for `Tax` for more information.

    Raises:
        TypeError: birth_date or retirement_date are not parseable
            as datetimes due to an unexpected type.
        ValueError: birth_date or retirement_date are not parseable
            as datetimes due to an unexpected value.
        ValueError: retirement_date precedes birth_date
        OverflowError: birth_date or retirement_date are too large.
    """

    # This class has a lot of members in large part because every
    # recorded_property turns into three members (prop, history_prop,
    # and _history_prop). It has 8 primary members (initial_year,
    # name, birth_date, retirement_date, gross_income, net_income,
    # raise_rate, spouse, and tax_treatment), and it seems proper that
    # all of these members live together rather than being refactored
    # into several sub-objects.
    # pylint: disable=too-many-instance-attributes,too-many-arguments

    # TODO: Add life expectancy? #14
    # TODO: Add estimated_retirement_date(...) method? #15
    # Perhaps add an arg for a generator function that takes certain
    # arguments (total investable savings, target withdrawal, and
    # [optionally] year?) and returns an estimated year of retirement?
    #   NOTE: This would allow client code to implement Dr. Pfau's
    #   study's results on safe withdrawal rates, or perhaps to take
    #   into account the person's risk-tolerance.
    # TODO: Subclass Person into CanadianResident?
    # We could override `_tax_credit` to provide the spousal tax credit
    # and replace the `tax_treatment` arg with a `province` (str) arg.

    def __init__(
            self, initial_year, name, birth_date, retirement_date=None,
            gross_income=None, raise_rate=None, spouse=None, tax_treatment=None,
            payment_timing=None, inputs=None, **kwargs):
        """ Initializes a `Person` object. """
        super().__init__(initial_year=initial_year, inputs=inputs, **kwargs)

        # For numerical optional inputs, ensure an appropriately-typed
        # default value is used:
        if gross_income is None:
            gross_income = self.precision_convert(0)
        if raise_rate is None:
            raise_rate = self.precision_convert(0)

        # For simple, non-property-wrapped attributes, assign directly:
        self.name = name
        if payment_timing is None:
            # Timing is technically mutable, so init it here rather than
            # using "Timing()" as a default value.
            self.payment_timing = Timing(high_precision=self.high_precision)
        else:
            self.payment_timing = Timing(
                payment_timing, high_precision=self.high_precision)

        # For attributes wrapped by ordinary properties, create hidden
        # attributes and assign to them using the properties:
        self._birth_date = None
        self._retirement_date = None
        self._raise_rate_callable = None
        self._spouse = None
        self._tax_treatment = None
        self._contribution_room = {}
        self._contribution_groups = {}
        self.birth_date = birth_date
        self.retirement_date = retirement_date
        self.raise_rate_callable = raise_rate
        self.spouse = spouse
        self.tax_treatment = tax_treatment

        # Now provide initial-year values for recorded properties:
        self.gross_income = gross_income # Money value
        # NOTE: Be sure to set up tax_treatment before calling tax_withheld
        self.net_income = self.gross_income - self.tax_withheld

        # Finally, build an empty set for accounts to add themselves to
        # and a `data` dict for accounts to write unstructed data to.
        self.accounts = set()
        self.data = {}

    @property
    def birth_date(self):
        """ The birth date of the Person. """
        return self._birth_date

    @birth_date.setter
    def birth_date(self, val):
        """ Sets the birth date of the Person.

        Raises:
            TypeError: `val` could not be parsed as a datetime due to
                an unexpected type.
            ValueError: `val` could not be parsed as a datetime due to
                an unexpected value.
        """
        # If `birth_date` is not a `datetime`, attempt to parse
        if not isinstance(val, datetime):
            # Parsing will fail if it can't generate a year, month, and
            # day. Use January 1 of this year as the default. If the
            # input is a valid date but lacks a year, month, or day,
            # then those will be filled in as needed.
            default_date = datetime(datetime.today().year, 1, 1)
            val = parse(str(val), default=default_date)
        self._birth_date = val

    @property
    def retirement_date(self):
        """ The retirement date of the Person. """
        return self._retirement_date

    @retirement_date.setter
    def retirement_date(self, val):
        """ Sets both retirement_date and retirement_age.

        Raises:
            ValueError: retirement_date precedes birth_date or could
                not be parsed as a datetime due to an unexpected value.
            TypeError: retirement_date could not be parsed as a datetime
                due to an unexpected type.
            NotImplementedError: retirement_date must not be None.
                Floating retirement dates are not yet implemented.
        """
        if val is None:
            self._retirement_date = None
            # NOTE: Delete this error when floating retirement dates
            # are implemented
            raise NotImplementedError(
                'Person: retirement_date must not be None. ' +
                'Floating retirement dates are not yet implemented.'
            )

        # If input is not a `datetime`, attempt to parse. If some values
        # (e.g. month/day) aren't given, use values from birth_date
        if not isinstance(val, datetime):
            default_date = self.birth_date
            val = parse(str(val), default=default_date)

        # `retirement_date` must follow `birth_date`
        if val < self.birth_date:
            raise ValueError("Person: retirement_date precedes birth_date")

        self._retirement_date = val

    @property
    def retirement_age(self):
        """ The age of the Person at retirement """
        return relativedelta(self.retirement_date, self.birth_date).years

    @retirement_age.setter
    def retirement_age(self, val):
        """ Sets retirement_age. """
        # This method sets values via the retirement_date property.
        if val is None:
            self.retirement_date = None
        else:
            # Set retirement_date.
            # Note that relativedelta will scold you if the input is not
            # losslessly convertible to an int
            self.retirement_date = self.birth_date + relativedelta(years=val)

    @property
    def raise_rate_callable(self):
        """ A callable object that generates a raise rate for the year.

        Returns:
            callable: A function with signature
            `raise_rate(year) -> float`.
        """
        return self._raise_rate_callable

    @raise_rate_callable.setter
    def raise_rate_callable(self, val):
        """ Sets raise_rate_function. """
        # Treat setting the method to None as reverting to the default
        # rate parameter, which is Money(0).
        if val is None:
            self.raise_rate_callable = 0
        # Is raise_rate isn't callable, convert it to a suitable method:
        if not callable(val):  # Make callable if dict or scalar
            if isinstance(val, dict):
                # assume dict of {year: raise} pairs
                def func(year):
                    """ Wraps dict in a function """
                    return val[year]
            else:
                # Return a constant rate
                # First, convert to high-precision if appropriate:
                val = self.precision_convert(val)
                def func(_=None):
                    """ Wraps value in a function with an optional arg. """
                    return val
            self._raise_rate_callable = func
        else:
            # If the input is callable, use it without modification.
            self._raise_rate_callable = val

    @property
    def spouse(self):
        """ The Person's spouse. """
        return self._spouse

    @spouse.setter
    def spouse(self, val):
        """ Sets the Person's spouse. """
        # If this Person already has a spouse, unlink them:
        if hasattr(self, 'spouse') and self.spouse is not None:
            # Assign to _spouse to avoid recursing on this method.
            # pylint: disable=protected-access
            # spouse is a Person, so this isn't accessing a protected
            # member of a client class.
            self.spouse._spouse = None

        # If we're adding a new spouse, make sure that it links back:
        if val is not None:
            if not isinstance(val, Person):  # Spouse must be a Person
                raise TypeError('Person: spouse must be of type Person')
            # Assign to _spouse to avoid recursing on this method.
            # pylint: disable=protected-access
            # spouse is a Person, so this isn't accessing a protected
            # member of a client class.
            val._spouse = self  # Use _spouse to avoid recursion

        # Update the spouse attr whether or not the new value is None
        self._spouse = val

    @property
    def tax_treatment(self):
        """ The tax treatment of the Person. """
        return self._tax_treatment

    @tax_treatment.setter
    def tax_treatment(self, val):
        """ Sets the Person's tax treatment. """
        if val is None:
            self._tax_treatment = None
        elif callable(val):
            self._tax_treatment = val
        else:
            raise TypeError('Person: tax_treatment must be callable or None.')

    # pylint: disable=method-hidden
    # Pylint gets confused by attributes added by metaclass.
    # This method isn't hidden in __init__; it's assigned to (by a
    # setter defined via metaclass)
    @recorded_property_cached
    def gross_income(self):
        """ The `Person`'s gross income for this year. """
        # No income if retired, otherwise apply the raise rate to last
        # year's income:
        if (
                self.retirement_date is not None and
                self.retirement_date.year < self.this_year):
            return self.precision_convert(0) # Money value
        else:
            return (
                # Pylint gets confused by attributes added by metaclass.
                # pylint: disable=no-member
                self._gross_income_history[self.this_year - 1] *
                (1 + self.raise_rate)
            )

    # pylint: disable=method-hidden
    # Pylint gets confused by attributes added by metaclass.
    # This method isn't hidden in __init__; it's assigned to (by a
    # setter defined via metaclass)
    @recorded_property_cached
    def net_income(self):
        """ The `Person`'s gross income for this year. """
        gross_income = self.gross_income
        return gross_income - self.tax_withheld

    @recorded_property_cached
    def raise_rate(self):
        """ The `Person`'s raise for the current year. """
        return self._raise_rate_callable(self.this_year)

    def age(self, date):
        """ The age of the `Person` as of `date`.

        `date` may be a `datetime` object or a numeric value indicating
        a year (e.g. 2001). In the latter case, the age on the person's
        birthday (in that year) is returned.

        Args:
            date: The date at which to determine the person's age.
                May be passed as a datetime or any other value that can
                be cast to str and converted to datetime by
                python-dateutils.parse().

        Returns:
            int: The age of the `Person`.

        Raises:
            ValueError: `date` is not parseable as a datetime.
            ValueError: `date` is earlier than `birth_date`.
            OverflowError: `date` is too large.
        """

        # If `date` is not `datetime`, attempt to parse
        if not isinstance(date, datetime):
            date = parse(str(date), default=self.birth_date)

        # Remember to check whether the month/day are earlier in `date`
        age = date.year - self.birth_date.year
        if date.replace(self.birth_date.year) < self.birth_date:
            age -= 1

        # We allow age to be negative, if that's what the caller wants.
        # if age_ < 0:
            # raise ValueError("Person: date must be after birth_date")

        return age

    # NOTE: Test overloading of recorded property by subclass

    @recorded_property_cached
    def tax_deduction(self):
        """ The `Person`'s tax deductions for the year. """
        return sum(
            (account.tax_deduction for account in self.accounts))

    @recorded_property_cached
    def tax_credit(self):
        """ The `Person`'s tax credits for the year. """
        return sum(
            (account.tax_credit for account in self.accounts))

    @recorded_property
    def taxable_income(self):
        return self.gross_income + sum(
            (account.taxable_income for account in self.accounts)
        )

    @recorded_property
    def tax_withheld(self):
        if self.tax_treatment is not None:
            # pylint: disable=not-callable
            # We test that tax_treatment is callable in its setter.
            return self.tax_treatment(self.gross_income, self.this_year)
        else:
            return 0 # Money value

    def __gt__(self, other):
        """ Allows for sorting, max, min, etc. based on gross income. """
        return self.gross_income > other.gross_income
