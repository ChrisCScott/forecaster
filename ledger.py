""" Defines basic recordkeeping classes, like `Person` and `Account`. """

import inspect
import math
from decimal import Decimal
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from utility import *
from settings import Settings

# TODO: Consider revising all Account-like objects to delete the
# settings argument and make necessary arguments non-defaulted
# (i.e. leave it to Forecaster to interact with Settings).
# Modify next_year() to take an optional arg for each attribute being
# updated, which will allow calling code to pass in an overriding input
# value when appropriate.


class recorded_property(property):
    """ A decorator for properties that record their annual amounts.

    Methods decorated with this decorator (a) are decorated with the
    @property decorator, and (b) sets a recorded_property flag attribute
    on the decorated property.

    `recorded_property`-decorated properties are processed by the Ledger
    metaclass to automatically generate have a <name>_history property,
    and a _<name> dict attribute to the class.

    Example:
        class ExampleLedger(Ledger):
            @recorded_property
            def taxable_income(self):
                return <formula for taxable_income>
    """
    def __init__(self, fget=None, doc=None):
        """ Init recorded_property.

        This wraps the getter received via the @recorded_property
        decoration into a method that returns a value from a dict of
        recorded values if such a value is present for the key
        `self.this_year`. If not, it calls the getter. No setter may be
        provided; this decorator automatically generates one based on
        this dict of recorded values.
        """
        self.__name__ = fget.__name__
        self.history_prop_name = self.__name__ + '_history'
        self.history_dict_name = '_' + self.history_prop_name

        # Getter returns stored value if available, otherwise generates
        # a new value (and does not cache it - we only automatically
        # store a value when next_year() is called)
        def getter(obj):
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year in history_dict:
                return history_dict[obj.this_year]
            else:
                return fget(obj)

        def setter(obj, val):
            history_dict = getattr(obj, self.history_dict_name)
            history_dict[obj.this_year] = val

        super().__init__(fget=getter, fset=setter, fdel=None, doc=doc)

        def history(obj):
            # For non-cached properties, the history dict might
            # not include a property for the current year.
            # NOTE: Consider building a new dict and adding the
            # current year to that (if not already in the dict),
            # so that *_history always contains the current year
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year in history_dict:
                return history_dict
            else:
                history_dict = dict(history_dict)  # copy dict
                history_dict[obj.this_year] = fget(obj)  # add this year
                return history_dict

        history.__name__ = self.history_prop_name

        # Cast history_function to a property with sane docstring.
        self.history_property = property(
            fget=history,
            doc='Record of ' + self.__name__ + ' over all past years.'
        )


class recorded_property_cached(recorded_property):
    """ A recorded property that is cached by Ledger classes. """
    # NOTE: Due to how decorators' pie-notation works, this is much
    # simpler than extending `recorded_property` to take a `cached`
    # argument (since `@recorded_property` (with no args) calls only
    # __init__ and `@recorded_property(cached=True)` calls __init__
    # with the keyword arg `cached` and then `__call__` with the
    # decorated method -- which makes `recorded_property` a much more
    # complicated subclass of `property`.)
    # NOTE: This doesn't address the situation where *_history is called
    # before the corresponding property; LedgerType needs to deal with
    # that scenario.
    def __init__(self, fget=None, doc=None):
        """ Overrides the property getter to cache on first call. """

        # Wrap the getter in a method that will cache the property the
        # first time it's called each year.
        def getter(obj):
            history_dict = getattr(obj, self.history_dict_name)
            val = fget(obj)
            history_dict[obj.this_year] = val
            return val

        # Property needs the original name and docstring:
        getter.__name__ = fget.__name__
        getter.__doc__ = fget.__doc__

        super().__init__(fget=getter, doc=doc)

        # Override history property with different method that adds the
        # current year's value to the cache if it isn't already there:
        def history(obj):
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year not in history_dict:
                history_dict[obj.this_year] = fget(obj)
            return history_dict

        history.__name__ = self.history_prop_name

        # This property was set by super().__init__
        self.history_property = property(
            fget=history,
            doc=self.history_property.__doc__
        )


class LedgerType(type):
    """ A metaclass for Ledger classes.

    This metaclass inspects the class for any
    @recorded_property-decorated methods and generates a corresponding
    *_history method and _* dict attribute.
    """
    def __init__(cls, *args, **kwargs):
        # First, build the class normally.
        super().__init__(*args, **kwargs)

        # Prepare to store all recorded properties for the class.
        cls._recorded_properties = set()
        cls._recorded_properties_cached = set()

        # Then identify all recorded_property attributes:
        for name, prop in inspect.getmembers(
            cls, lambda x: hasattr(x, 'history_property')
        ):
            # Store the identified recorded_property:
            # (This will help Ledger build object-specific dicts for
            # storing the values of each recorded property. We don't
            # want to do this at the class level because dicts are
            # mutable and we don't want to share the dict mutations
            # between objects.)
            cls._recorded_properties.add(prop)
            if isinstance(prop, recorded_property_cached):
                cls._recorded_properties_cached.add(prop)

            # Add the new attribute to the class.
            setattr(cls, prop.history_prop_name, prop.history_property)


class Ledger(object, metaclass=LedgerType):
    """ An object with a next_year() method that tracks the curent year.

    This object provides the basic infrastructure not only for advancing
    through a sequence of years but also for managing any
    `recorded_property`-decorated properties.

    Attributes:
        initial_year (int): The initial year for the object.
        this_year (int): The current year for the object. Incremented
            with each call to next_year()
        next_year(): A method that increments this_year.
    """
    def __init__(self, initial_year=None, settings=Settings):
        """ Inits IncrementableByYear. """
        self.initial_year = int(
            initial_year
            if initial_year is not None
            else settings.initial_year)
        self.this_year = self.initial_year

        # Build a history dict for each recorded_property
        for prop in self._recorded_properties:
            setattr(self, prop.history_dict_name, {})

        # NOTE: We don't call cache_properties here because subclasses
        # may need to do more initing before properties can be called.
        # Leave it to each subclass with cached properties to call
        # cached_properties at the end of its init.

    def next_year(self, *args, **kwargs):
        """ Advances to the next year. """
        # Record all recorded properties in the moment before advancing
        # to the next year:
        for recorded_property in self._recorded_properties:
            history_dict = getattr(self, recorded_property.history_dict_name)
            # Only add a value to the history dict if one has not
            # already been added for this year:
            if self.this_year not in history_dict:
                # NOTE: We could alternatively do this via setattr
                # (which would call the setter function defined by the
                # recorded_property decorator - perhaps preferable?)
                history_dict[self.this_year] = getattr(
                    self, recorded_property.__name__)
        # Advance to the next year after recording properties:
        self.this_year += 1


class TaxSource(Ledger):
    """ An object that can be considered when calculating taxes.

    Provides standard tax-related properties, listed below.

    Actual tax treatment will vary by subclass. Rather than override
    these properties directly, subclasses should override the methods
    _taxable_income, _tax_withheld, _tax_credit, and _tax_deduction
    (note the leading underscore).

    Attributes:
        taxable_income (Money): Taxable income arising from the
            object for the current year.
        tax_withheld (Money): Tax withheld from the object for the
            current year.
        tax_credit (Money): Taxable credits arising from the
            object for the current year.
        tax_deduction (Money): Taxable deductions arising from the
            object for the current year.
        taxable_income_history (Money): Taxable income arising from the
            object for each year thus far.
        tax_withheld_history (Money): Tax withheld from the object for
            each year thus far.
        tax_credit_history (Money): Taxable credits arising from the
            object for each year thus far.
        tax_deduction_history (Money): Taxable deductions arising from
            the object for each year thus far.
    """

    @recorded_property
    def taxable_income(self):
        """ Taxable income for the given year.

        Subclasses should override this method rather than the
        taxable_income and _taxable_income_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_withheld(self):
        """ Tax withheld for the given year.

        Subclasses should override this method rather than the
        tax_withheld and _tax_withheld_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_credit(self):
        """ Tax credit for the given year.

        Subclasses should override this method rather than the
        tax_credit and _tax_credit_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_deduction(self):
        """ Tax deduction for the given year.

        Subclasses should override this method rather than the
        tax_deduction and _tax_deduction_history properties.
        """
        return Money(0)


class Person(TaxSource):
    """ Represents a person's basic information: age and retirement age.

    Attributes:
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
        raise_rate (Decimal): The person's raise in gross income this
            year relative to last year.
        raise_rate_history (dict[int, Decimal]): Raises for all years
            on record.
        spouse (Person): The person's spouse. This linkage is
            one-to-one; the spouse's `spouse` attribute points back to
            this Person.
        tax_treatment (Tax): The tax treatment of the person. A callable
            object; see documentation for `Tax` for more information.
    """

    # TODO: Add life expectancy?
    # TODO: Add estimated_retirement_date(...) method? Perhaps add an
    # arg for a generator function that takes certain arguments (total
    # investable savings, target withdrawal, and [optionally] year?) and
    # returns an estimated year of retirement?
    #   NOTE: This would allow client code to implement Dr. Pfau's
    #   study's results on safe withdrawal rates, or perhaps to take
    #   into account the person's risk-tolerance.
    # TODO: Subclass Person into CanadianResident, override _tax_credit
    # to provide the spousal tax credit, and replace the `tax_treatment`
    # arg with a `province` (str) arg?

    def __init__(self, name, birth_date, retirement_date=None,
                 gross_income=0, raise_rate=None, spouse=None,
                 tax_treatment=None, allocation_strategy=None,
                 initial_year=None, settings=Settings):
        """ Constructor for `Person`.

        Attributes:
            accounts (set): All accounts naming this Person as an owner.

        Args:
            name (str): The person's name.
            birth_date (datetime): The person's date of birth.
                May be passed as any value that can be cast to str and
                converted to datetime by python-dateutils.parse().
            retirement_date (datetime): The person's retirement date.
                May be passed as any value that can be cast to str and
                converted to datetime by python-dateutils.parse().
                Optional.
            gross_income (Money): The person's gross income in
                `initial_year`.
            raise_rate (dict[int, Decimal], callable): The person's
                raise for each year, as a callable object with the
                signature `raise_rate(year)` or a dict of
                `{year: raise}` pairs. The raise is a Decimal
                interpreted as a percentage (e.g. `Decimal('0.03')`
                indicates a 3% raise).
            spouse (Person): The person's spouse. Optional.
                In ordinary use, the first person of the couple is
                constructed with `spouse=None`, and the second person is
                constructed with `spouse=person1`. Both persons will
                automatically have their spouse attribute updated to
                point at each other.
            tax_treatment (Tax): The person's tax treatment. Optional.
                This can be any callable object that accepts the form
                `tax_treatment(taxable_income, year)` and returns a
                Money object (which corresponds to total taxes payable
                on `taxable_income`).
            allocation_strategy (AllocationStrategy): The person's
                asset allocation strategy for accounts they own. This
                can be used by accounts to determine their raise_rate.
            initial_year (int): The first year for which account data is
                recorded.
            settings (Settings): Defines default values (initial year,
                inflow/outflow transaction timing, etc.). Optional; uses
                global Settings class attributes if None given.

        Returns:
            An instance of class `Person`

        Raises:
            ValueError: birth_date or retirement_date are not parseable
                as dates.
            ValueError: retirement_date precedes birth_date
            OverflowError: birth_date or retirement_date are too large
        """
        super().__init__(initial_year, settings)

        # For attributes wrapped by ordinary properties, create hidden
        # attributes and assign to them using the properties:
        self._name = None
        self._birth_date = None
        self._retirement_date = None
        self._raise_rate_function = None
        self._spouse = None
        self._allocation_strategy = None
        self._tax_treatment = None
        self._contribution_room = {}
        self._contribution_groups = {}
        self.name = name if name is not None else settings.person1_name
        self.birth_date = birth_date if birth_date is not None \
            else settings.person1_birth_date
        self.retirement_date = retirement_date if retirement_date is not None \
            else settings.person1_retirement_date
        self.raise_rate_function = raise_rate if raise_rate is not None \
            else settings.person1_raise_rate
        self.spouse = spouse
        self.allocation_strategy = allocation_strategy
        # Set up tax treatment before calling tax_withheld()
        self.tax_treatment = tax_treatment

        # Now provide initial-year values for recorded properties:
        # NOTE: Be sure to do type-checking here.
        self.gross_income = Money(gross_income)
        self.net_income = self.gross_income - self.tax_withheld

        # Finally, build an empty set for accounts to add themselves to.
        self.accounts = set()

    @property
    def name(self) -> str:
        """ The name of the Person. """
        return self._name

    @name.setter
    def name(self, val) -> None:
        """ Sets the Person's name. """
        self._name = str(val)

    @property
    def birth_date(self) -> datetime:
        """ The birth date of the Person. """
        return self._birth_date

    @birth_date.setter
    def birth_date(self, val) -> None:
        """ Sets the birth date of the Person. """
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
    def retirement_date(self) -> datetime:
        """ The retirement date of the Person. """
        return self._retirement_date

    @retirement_date.setter
    def retirement_date(self, val) -> None:
        """ Sets both retirement_date and retirement_age. """
        if val is None:
            self._retirement_date = None
            self._retirement_age = None
            # NOTE: Delete this error when floating retirement dates
            # are implemented
            raise NotImplementedError(
                'Person: retirement_date must not be None. ' +
                'Floating retirement dates are not yet implemented.'
            )
            return

        # If input is not a `datetime`, attempt to parse. If some values
        # (e.g. month/day) aren't given, use values from birth_date
        if not isinstance(val, datetime):
            default_date = self.birth_date
            val = parse(str(val), default=default_date)

        # `retirement_date` must follow `birth_date`
        if val < self.birth_date:
            raise ValueError("Person: retirement_date precedes birth_date")

        self._retirement_date = val
        self._retirement_age = self.age(val)

    @property
    def retirement_age(self) -> int:
        """ The age of the Person at retirement """
        return relativedelta(self.retirement_date, self.birth_date).years

    @retirement_age.setter
    def retirement_age(self, val) -> None:
        """ Sets retirement_age. """
        # This method only sets values via the retirement_age property.
        # That property's methods set both _retirement_age and
        # _retirement_date, and performs associated checks.
        if val is None:
            self.retirement_date = None
        else:
            # Set retirement_date.
            # Note that relativedelta will scold you if the input is not
            # losslessly convertible to an int
            self.retirement_date = self.birth_date + relativedelta(years=val)

    @property
    def raise_rate_function(self):
        """ """
        return self._raise_rate_function

    @raise_rate_function.setter
    def raise_rate_function(self, val) -> None:
        """ """
        # Is raise_rate isn't callable, convert it to a suitable method:
        if not callable(val):  # Make callable if dict or scalar
            if isinstance(val, dict):
                # assume dict of {year: raise} pairs
                def func(year): return val[year]
            else:
                # If we can cast this to Decimal, return a constant rate
                val = Decimal(val)

                def func(year): return val
            self._raise_rate_function = func
        else:
            # If the input is callable, use it without modification.
            self._raise_rate_function = val

    @property
    def spouse(self) -> 'Person':
        """ The Person's spouse. """
        return self._spouse

    @spouse.setter
    def spouse(self, val) -> None:
        """ Sets the Person's spouse. """
        # If this Person already has a spouse, unlink them:
        if hasattr(self, 'spouse') and self.spouse is not None:
            self.spouse._spouse = None  # Use _spouse to avoid recursion

        # If we're adding a new spouse, make sure that it links back:
        if val is not None:
            if not isinstance(val, Person):  # Spouse must be a Person
                raise TypeError('Person: spouse must be of type Person')
            val._spouse = self  # Use _spouse to avoid recursion

        # Update the spouse attr whether or not the new value is None
        self._spouse = val

    @property
    def tax_treatment(self):
        """ The tax treatment of the Person. """
        return self._tax_treatment

    @tax_treatment.setter
    def tax_treatment(self, val) -> None:
        """ Sets the Person's tax treatment. """
        # Due to import dependencies, we can't type-check against
        # Tax here; leave it to calling code to fail if it provides
        # an object of the wrong type.
        self._tax_treatment = val

    @property
    def allocation_strategy(self):
        """ The asset allocation strategy of the Person. """
        return self._allocation_strategy

    @allocation_strategy.setter
    def allocation_strategy(self, val) -> None:
        """ Sets the Person's asset allocation strategy. """
        # Due to import dependencies, we can't type-check against
        # Strategy here; leave it to calling code to fail if it provides
        # an object of the wrong type.
        self._allocation_strategy = val

    @recorded_property_cached
    def gross_income(self):
        """ The `Person`'s gross income for this year. """
        # No income if retired, otherwise apply the raise rate to last
        # year's income:
        if (
            self.retirement_date is not None and
            self.retirement_date.year < self.this_year
        ):
            return Money(0)
        else:
            return self._gross_income_history[self.this_year - 1] * \
                (1 + self.raise_rate)

    @recorded_property_cached
    def net_income(self):
        """ The `Person`'s gross income for this year. """
        gross_income = self.gross_income
        return gross_income - self.tax_withheld

    @recorded_property_cached
    def raise_rate(self):
        """ The `Person`'s raise for the current year. """
        return self._raise_rate_function(self.this_year)

    def contribution_room(self, account):
        """ The contribution room for the given account.

        The account must provide a `_contribution_token` attribute.

        Returns:
            A dict of {year: contribution_room} pairs for the account if
            it has been registered, or None if it is not registered.
        """
        if account._contribution_token in self._contribution_room:
            return self._contribution_room[account._contribution_token]
        else:
            return None

    def register_shared_contribution_account(self, account):
        """ Prepares a Person to store contribution room for an account.

        This method starts tracking contribution room for the account if
        it isn't already and also keeps track of which accounts have
        shared contribution room.
        """
        # Start tracking contribution room for this account if we aren't
        # already.
        if account._contribution_token not in self._contribution_room:
            self._contribution_room[account._contribution_token] = {}
        # Identify all accounts that share contribution room with this
        # one
        contribution_group = {
            x for x in self._contribution_groups
            if hasattr(x, '_contribution_token') and
            x._contribution_token == account._contribution_token}
        # Store the contribution group for later recall. This also
        # includes updating the stored contribution groups of other
        # accounts in the group.
        for account in contribution_group:
            self._contribution_groups[account] = contribution_group

    def age(self, date) -> int:
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
            The age of the `Person` as an `int`.

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

    @recorded_property
    def taxable_income(self):
        return self.gross_income

    @recorded_property
    def tax_withheld(self):
        if self.tax_treatment is not None:
            return self.tax_treatment(self.gross_income, self.this_year)
        else:
            return Money(0)

    def __gt__(self, other):
        """ Allows for sorting, max, min, etc. based on gross income. """
        return self.gross_income > other.gross_income


class Account(TaxSource):
    """ An account storing a `Money` balance.

    Has a `balance` indicating the balance of the account at the start
    of the period (generally a year). Optionally, a rate of growth,
    `rate`, expressed as an apr (annual percentage rate) can be given.
    For example, a 5% apr could be passed as `rate=0.05`.

    May optionally also recieve one or more transactions defining a time
    series of inflows and outflows from the account. These transactions
    do not modify the `balance` directly; rather, they are applied
    to the balance, with any growth, when `next_year()` is called.
    A new `Account` object with an updated balance is generated; the
    calling object's balance does not change.

    Examples:
        `account1 = Account(100, 0.05)`
        `account2 = account1.next_year()`
        `account1.balance == 100  # True`
        `account2.balance == 105  # True`

    Attributes:
        balance (Money): The opening account balance for this year.
        balance_history (dict): A dict of {year: balance} pairs covering
            all years in the range `initial_year: this year`
        rate (Decimal): The rate of return (or interest) for this year,
            before compounding.
        rate_history (dict): A dict of {year: rate} pairs covering
            all years in the range `initial_year: this year`
        transactions (dict): The transactions to/from the account for
            this year. A dict of `{when: value}` pairs, where:
                `when` (float, Decimal, str): Describes the timing of
                    the transaction in the year. In the range [0, 1].
                `value` (Money): The inflows and outflows at time `when`.
                    Positive for inflows and negative for outflows.
                    Each element must be a Money object (or convertible
                    to one).
        transactions_history (dict): A dict of {year: transactions}
            pairs covering all years in the range
            `initial_year: this year`
        returns (Money): The returns (losses) of the account for the
            year.
        returns_history (dict): A dict of {year: returns} pairs covering
            all years in the range `initial_year: this year`
        nper (int, str): The compounding frequency. May be given as
            a number of periods (an int) or via a code (a str). Codes
            include:
                C: Continuous (default)
                D: Daily
                W: Weekly
                BW: Biweekly (every two weeks)
                SM: Semi-monthly (twice a month)
                M: Monthly
                BM: Bimonthly (every two months)
                Q: Quarterly (every 3 months)
                SA: Semi-annually (twice a year)
                A: Annually
            Note that `nper` is not a list; it's assumed that the
            compounding frequency (unlike the rate)
        initial_year (int): The first year for which account data is
            recorded.
        settings (Settings): Defines default values (initial year,
            inflow/outflow transaction timing, etc.). Optional; uses
            global Settings class attributes if None given.
    """
    def __init__(self,
                 owner,
                 balance=0,
                 rate=None,
                 transactions={},
                 nper=1,
                 initial_year=None,
                 default_inflow_timing=None,
                 default_outflow_timing=None,
                 settings=Settings):
        """ Constructor for `Account`.

        This constructor receives only values for the first year.

        Args:
            owner (Person): The owner of the account. Optional.
            balance (Money): The balance for the first year
            rate (float, Decimal): The rate for the first year.
            transactions (dict): The transactions for the first year,
                as {Decimal: Money} pairs, where Decimal denotes timing
                of the transaction and is in [0,1] as described in the
                `When` class and Money denotes the values of the
                transaction (positive to inflow, negative for outflow).
            nper (int): The number of compounding periods per year.
            initial_year (int): The first year (e.g. 2000)
            default_inflow_timing (Decimal): The default timing used for
                inflow transactions (when a timing is not explicitly
                provided).
            default_outflow_timing (Decimal): The default timing used
                for outflow transactions (when a timing is not
                explicitly provided).
            settings (Settings): Provides default values.
        """
        super().__init__(initial_year, settings)

        # Set hidden attributes to support properties that need them to
        # be set in advance:
        self._owner = None
        self._transactions = {}
        self._rate_function = None

        # Set the various property values based on inputs:
        self.owner = owner
        self.balance = Money(balance)
        # If rate is not provided, infer from owner's asset allocation:
        self.rate_function = rate if rate is not None else \
            self.rate_from_asset_allocation
        self.nper = self._conv_nper(nper)
        self._inflow_timing = when_conv(
            default_inflow_timing
            if default_inflow_timing is not None
            else settings.transaction_in_timing)
        self._outflow_timing = when_conv(
            default_outflow_timing
            if default_outflow_timing is not None
            else settings.transaction_out_timing)
        # NOTE: returns is calculated lazily

        # Add each transaction manually to populate the transactions
        # dict; this will do the necessary type-checking and conversions
        # on each element:
        for when, value in transactions.items():
            self.add_transaction(value, when)

    # String codes describing compounding periods (keys) and ints
    # describing the number of such periods in a year (values):
    _nper_mapping = {
        'C': None,
        'D': 365,
        'W': 52,
        'BW': 26,
        'SM': 24,
        'M': 12,
        'BM': 6,
        'Q': 4,
        'SA': 2,
        'A': 1
        }

    @property
    def owner(self) -> Person:
        """ The account's owner. """
        return self._owner

    @owner.setter
    def owner(self, val) -> None:
        """ Sets the account's owner. """
        # Type-check the input
        if not isinstance(val, Person):
            raise TypeError('Account: owner must be of type Person.')
        val.accounts.add(self)  # Track this account via owner.
        self._owner = val

    @recorded_property_cached
    def balance(self):
        """ The balance of the account for the current year (Money).

        This is the balance after applying all transactions and any
        growth/losses from the rate.
        """
        # First, grow last year's initial balance based on the rate:
        balance = self.value_at_time(
            self._balance_history[self.this_year - 1], 'start', 'end')

        # Then, grow each transactions and add it to the year-end total.
        # NOTE: This accounts for both inflows and outflows; outflows
        # and their growth are negative and will reduce the balance.
        transactions_history = self._transactions_history
        for when, value in transactions_history[self.this_year - 1].items():
            balance += self.value_at_time(value, when, 'end')

        return balance

    @property
    def rate_function(self):
        """ A function that generates a rate for a given year.

        The function is callable with one (potentially optional)
        argument: year.
        """
        return self._rate_function

    @rate_function.setter
    def rate_function(self, val):
        """ Sets the rate function """
        # If input isn't callable, convert it to a suitable method:
        if not callable(val):
            if isinstance(val, dict):
                # assume dict of {year: rate} pairs
                def func(year): return val[year]
            else:
                # If we can cast this to Decimal, return a constant rate
                val = Decimal(val)

                def func(year): return val
            self._rate_function = func
        else:
            # If the input is callable, use it without modification.
            self._rate_function = val

    @recorded_property_cached
    def rate(self):
        """ The rate of the account for the current year (Decimal). """
        return self.rate_function(self.this_year)

    @recorded_property
    def transactions(self):
        """ The transactions in and out of the account this year (dict). """
        return self._transactions

    @recorded_property
    def returns(self):
        """ Returns (losses) on the balance and transactions this year. """
        # Find returns on the initial balance.
        # This doesn't include any transactions or their growth.
        returns = (
            self.balance *
            (self.accumulation_function(1, self.rate, self.nper) - 1)
        )

        # Add in the returns on each transaction.
        # (Withdrawals will generate returns with the opposite sign of
        # the returns on the initial balance and prior inflows, thereby
        # cancelling out a portion of those returns.)
        for when in self._transactions:
            returns += (
                self._transactions[when] *
                (self.accumulation_function(
                    1 - when, self.rate, self.nper
                    ) - 1)
            )

        return returns

    @classmethod
    def _conv_nper(cls, nper):
        """ Number of periods in a year given a compounding frequency.

        Args:
            nper (str, int): A code (str) indicating a compounding
                frequency (e.g. 'W', 'M'), an int, or None

        Returns:
            An int indicating the number of compounding periods in a
                year or None if compounding is continuous.
        """
        # nper can be None, so return gracefully.
        if nper is None:
            return None

        # Try to parse a string based on known compounding frequencies
        if isinstance(nper, str):
            if nper not in cls._nper_mapping:
                raise ValueError('Account: str nper must have a known value')
            return cls._nper_mapping[nper]
        else:  # Attempt to cast to int
            if not nper == int(nper):
                raise TypeError(
                    'Account: nper is not losslessly convertible to int')
            if nper <= 0:
                raise ValueError('Account: nper must be greater than 0')
            return int(nper)

    def contribution_group(self):
        """ The accounts that share contribution room with this one.

        Returns:
            A set of accounts that should be considered together when
            allocating contributions between them. Includes this account
        """
        return {self}

    def add_transaction(self, value, when='end'):
        """ Adds a transaction to the account.

        Args:
            value (Money): The value of the transaction. Positive values
                are inflows and negative values are outflows.
            when (float, Decimal, str): The timing of the transaction.
                Must be in the range [0,1] or in {'start', 'end'}.
                0 corresponds to 'end' and 1 corresponds to 'start'.
                (It's a bit counterintuitive, but this is how `numpy`
                defines its `when` argument for financial methods.)
                Defaults to 'end'.

        Raises:
            decimal.InvalidOperation: Transactions must be convertible
                to type Money and `when` must be convertible to type
                Decimal
            ValueError: `when` must be in [0,1]
        """
        # Convert `when` to a Decimal value.
        # Even if already a Decimal, this checks `when` for value/type
        if when is None:
            when = self._inflow_timing if value >= 0 else self._outflow_timing
        else:
            when = when_conv(when)

        # Try to cast non-Money objects to type Money
        if not isinstance(value, Money):
            value = Money(value)

        # If there's already a transaction at this time, then add them
        # together; simultaneous transactions are modelled as one sum.
        if when in self.transactions:  # Add to existing value
            self.transactions[when] += value
        else:  # Create new when/value pair.
            self.transactions[when] = value

    # TODO: Add add_inflow and add_outflow methods? These could ignore
    # sign (or, for add_inflow, raise an error with negative sign) and
    # add an inflow (+) or outflow (-) with the magnitude of the input
    # arg and the appropriate sign.

    @recorded_property
    def inflows(self):
        """ The sum of all inflows to the account. """
        return Money(sum(
            val for val in self._transactions.values() if val.amount > 0)
        )

    @recorded_property
    def outflows(self):
        """ The sum of all outflows from the account. """
        return Money(sum(
            val for val in self._transactions.values() if val.amount < 0)
        )

    def __len__(self):
        """ The number of years of transaction data in the account. """
        return self.this_year - self.initial_year + 1

    def rate_from_asset_allocation(self, year=None):
        """ The rate of return for a portfolio with a given composition.

        This determines the portfolio composition based on the owner's
        asset allocation strategy, and their age and (estimated)
        retirement age.

        Args:
            year (int): The year for which a rate is desired. Optional;
                defaults to the current year.
        """
        year = year if year is not None else self.this_year
        return self.owner.allocation_strategy.rate_of_return(
            year=year,
            age=self.owner.age(year),
            retirement_age=self.owner.retirement_age)

    @staticmethod
    def accumulation_function(t, rate, nper=1):
        """ The accumulation function, A(t), from interest theory.

        A(t) provides the growth (or discount) factor over the period
        [0, t]. If `t` is negative, this method returns the inverse
        (i.e. A(t)^-1).

        This method's output is not well-defined where t does not align
        with the start/end of a compounding period. (It will produce
        sensible output, but it might not correspond to how your bank
        calculates interest).

        Args:
            t (float, Decimal): Defines the period [0,t] over which the
                accumulation will be calculated.
            rate (float, Decimal): The rate of return (or interest).
            nper (int): The number of compounding periods per year.

        Returns:
            The accumulation A(t), as a Decimal.
        """
        # Convert t and rate to Decimal
        t = Decimal(t)
        rate = Decimal(rate)

        # Use the exponential formula for continuous compounding: e^rt
        if nper is None:
            # math.exp(rate * t) throws a warning, since there's an
            # implicit float-Decimal multiplication.
            acc = Decimal(math.e) ** (rate * t)
        # Otherwise use the discrete formula: (1+r/n)^nt
        else:
            acc = (1 + rate / nper) ** (nper * t)

        return acc

    def value_at_time(self, value, now='start', time='end'):
        """ Returns the present (or future) value.

        Args:
            value (Money): The (nominal) value to be converted.
            now (Decimal): The time associated with the nominal value.
            time (Decimal): The time to which the nominal value is to
                be converted.

        Returns:
            A Money object representing the present value
            (if now > time) or the future value (if now < time) of
            `value`.
        """
        return value * self.accumulation_function(
            when_conv(time) - when_conv(now), self.rate, self.nper
        )

    def balance_at_time(self, time):
        """ Returns the balance at a point in time.

        Args:
            when (Decimal, str): The timing of the transaction.
        """
        # We need to convert `time` to enable the comparison in the dict
        # comprehension in the for loop below.
        time = when_conv(time)

        # Find the future value (at t=time) of the initial balance.
        # This doesn't include any transactions of their growth.
        balance = self.value_at_time(self.balance, 'start', time)

        # Add in the future value of each transaction (except that that
        # happen after `time`).
        for when in {w for w in self._transactions.keys() if w <= time}:
            balance += self.value_at_time(
                self._transactions[when], when, time
            )

        return balance

    def next_year(self, *args, **kwargs):
        """ Adds another year to the account.

        This method will call the next_year method for the owner if they
        haven't been advanced to the next year.
        """
        # Ensure that the owner has been brought up to this year
        while self.owner.this_year < self.this_year:
            self.owner.next_year()

        # Now increment year via superclass:
        super().next_year(*args, **kwargs)

        # Clear out transactions for the new year:
        self._transactions = {}

    def max_outflow(self, when='end'):
        """ An outflow which would reduce the end-of-year balance to 0.

        NOTE: This does not guarantee that the account balance will not
        be negative at a time between `when` and `end`.

        Args:
            when (When): The timing of the transaction.

        Returns:
            A value which, if withdrawn at time `when`, would make the
            account balance 0 at the end of the year, after all
            transactions are accounted for.
        """
        # If the balance is positive, the max outflow is simply the
        # current balance (but negative). If the balance is negative,
        # then there's no further outflows to be made.
        return min(-self.balance_at_time(when), Money(0))

    def max_inflow(self, when='end'):
        """ The maximum amount that can be contributed to the account. """
        # For non-registered accounts, there is no maximum
        return Money('Infinity')

    def min_outflow(self, when='end'):
        """ The minimum amount to be withdrawn from the account. """
        # For non-registered accounts, there is no minimum
        return Money('0')

    def min_inflow(self, when='end'):
        """ The minimum amount to be contributed to the account. """
        # For non-registered accounts, there is no minimum
        return Money('0')

    @recorded_property
    def taxable_income(self):
        """ Treats all returns as taxable. """
        return max(self.returns, Money(0))


class Debt(Account):
    """ A debt with a balance and an interest rate.

    If there is an outstanding balance, the balance value will be a
    *negative* value, in line with typical accounting principles.

    Args:
        minimum_payment (Money): The minimum annual payment on the debt.
            Optional.
        reduction_rate (Money, Decimal, float, int): If provided, some
            (or all) of the debt payments are drawn from savings instead
            of living expenses. If Money, this is the amount drawn from
            savings. If a number in [0,1], this is the percentage of the
            payment that's drawn from savings. Optional.
        accelerate_payment (bool): If True, payments above the minimum
            may be made to pay off the balance earlier. Optional.
    """

    # TODO: Add a max_accelerate arg (or perhaps change
    # accelerate_payment to Money type and test for >0?) to set a cap on
    # how much to accelerate payments by.

    def __init__(self, owner, balance=0, rate=0, transactions={},
                 nper=1, initial_year=None, settings=Settings,
                 minimum_payment=Money(0), reduction_rate=1,
                 accelerate_payment=False):
        """ Constructor for `Debt`. """
        super().__init__(
            owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, initial_year=initial_year, settings=settings)
        self.minimum_payment = Money(minimum_payment)
        self.reduction_rate = Decimal(reduction_rate) \
            if reduction_rate is not None \
            else Settings.DebtReductionRate
        self.accelerate_payment = bool(accelerate_payment) \
            if accelerate_payment is not None \
            else Settings.DebtAcceleratePayment

        # Debt must have a negative balance
        if self.balance > 0:
            self.balance = -self.balance

    def min_inflow(self, when='end'):
        """ The minimum payment on the debt. """
        return min(-self.balance_at_time(when), self.minimum_payment)

    def max_inflow(self, when='end'):
        """ The payment at time `when` that would reduce balance to 0.

        This is in addition to any existing payments in the account.

        Example:
            debt = Debt(-100)
            debt.maximum_payment('start') == Money(100)  # True
            debt.add_transaction(100, 'start')
            debt.maximum_payment('start') == 0  # True
        """
        return -self.balance_at_time(when)
