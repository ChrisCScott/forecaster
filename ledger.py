""" Defines basic recordkeeping classes, like `Person` and `Account`. """

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
#   NOTE: This may require building dicts for tax* methods, otherwise
#   we won't be able to recall any overridden tax data. See below notes.
# TODO: Store taxable_income, tax_payable, tax_withheld, etc. as
# dicts? (Or perhaps provide a generator method.)
#   NOTE: Alternatively, add *_history() methods that return a dict,
#   which avoids having to expose implementation details (e.g. it
#   means that client code won't need to access _net_income, etc.,
#   since they can access net_income_history())
#   NOTE: We should do this for Accounts as well, for all
#   underscore-prefixed dicts and tax* methods.


class IncrementableByYear(object):
    """ An object with a next_year() method that tracks the curent year.

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

    def next_year(self, *args, **kwargs):
        """ Advances to the next year. """
        self.this_year += 1


class TaxSource(IncrementableByYear):
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

    def __init__(self, initial_year=None, settings=Settings):
        """ Inits TaxSource. """
        super().__init__(initial_year, settings)

        self.__taxable_income = {}
        self.__tax_withheld = {}
        self.__tax_credit = {}
        self.__tax_deduction = {}

    @property
    def taxable_income(self):
        """ Taxable income for the current year. """
        # Taxable income can change depending on account activity, so
        # recalculate it each time and store it in the internal dict.
        self.__taxable_income[self.this_year] = \
            self._taxable_income(self.this_year)
        return self.__taxable_income[self.this_year]

    @property
    def taxable_income_history(self):
        """ Taxable income for all years on record. """
        # Taxable income for the current year can change depending on
        # account activity, so recalculate it before returning the dict.
        self.__taxable_income[self.this_year] = self.taxable_income
        return self.__taxable_income

    def _taxable_income(self, year):
        """ Taxable income for the given year.

        Subclasses should override this method rather than the
        taxable_income and _taxable_income_history properties.
        """
        return Money(0)

    @property
    def tax_withheld(self):
        """ Tax withheld for the current year. """
        # Tax withheld can change depending on account activity, so
        # recalculate it each time and store it in the internal dict.
        self.__tax_withheld[self.this_year] = \
            self._tax_withheld(self.this_year)
        return self.__tax_withheld[self.this_year]

    @property
    def tax_withheld_history(self):
        """ Tax withheld for all years on record. """
        # Tax withheld for the current year can change depending on
        # account activity, so recalculate it before returning the dict.
        self.__tax_withheld[self.this_year] = self.tax_withheld
        return self.__tax_withheld

    def _tax_withheld(self, year):
        """ Tax withheld for the given year.

        Subclasses should override this method rather than the
        tax_withheld and _tax_withheld_history properties.
        """
        return Money(0)

    @property
    def tax_credit(self):
        """ Tax credit for the current year. """
        # Tax credit can change depending on account activity, so
        # recalculate it each time and store it in the internal dict.
        self.__tax_credit[self.this_year] = \
            self._tax_credit(self.this_year)
        return self.__tax_credit[self.this_year]

    @property
    def tax_credit_history(self):
        """ Tax credit for all years on record. """
        # Tax credit for the current year can change depending on
        # account activity, so recalculate it before returning the dict.
        self.__tax_credit[self.this_year] = self.tax_credit
        return self.__tax_credit

    def _tax_credit(self, year):
        """ Tax credit for the given year.

        Subclasses should override this method rather than the
        tax_credit and _tax_credit_history properties.
        """
        return Money(0)

    @property
    def tax_deduction(self):
        """ Tax deduction for the current year. """
        # Tax deduction can change depending on account activity, so
        # recalculate it each time and store it in the internal dict.
        self.__tax_deduction[self.this_year] = \
            self._tax_deduction(self.this_year)
        return self.__tax_deduction[self.this_year]

    @property
    def tax_deduction_history(self):
        """ Tax deduction for all years on record. """
        # Tax deduction for the current year can change depending on
        # account activity, so recalculate it before returning the dict.
        self.__tax_deduction[self.this_year] = self.tax_deduction
        return self.__tax_deduction

    def _tax_deduction(self, year):
        """ Tax deduction for the given year.

        Subclasses should override this method rather than the
        tax_deduction and _tax_deduction_history properties.
        """
        return Money(0)

    def next_year(self, *args, **kwargs):
        """ Advances to the next year. """
        # Since this moment is when the current year gets set in stone,
        # recalculate and store the current tax* values before
        # incrementing the year:
        self.__taxable_income[self.this_year] = self.taxable_income
        self.__tax_withheld[self.this_year] = self.tax_withheld
        self.__tax_credit[self.this_year] = self.tax_credit
        self.__tax_deduction[self.this_year] = self.tax_deduction
        super().next_year(*args, **kwargs)


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
        gross_income (dict): Annual gross income for several
    """

    # TODO: Add life expectancy?
    # TODO: Move contribution room information from TFSA/RRSP to
    # Person. This will allow for the use of multiple TFSA/RRSP accounts
    # with shared contribution rooms.
    #   NOTE: It is likely that each RRSP/TFSA will hold the logic re:
    #   contribution room, but it may be useful to have a generic
    #   mechanism in Person - e.g. a dict of {token: contribution_room}
    #   pairs, plus a generic method for registering accounts. The
    #   accounts themselves could provide the token - a unique hash if
    #   the account has a unique contribution room or a static str if
    #   its contribution room is shared (e.g. all RRSP objects could
    #   use the token 'RRSP' - RegisteredAccount can implement this via
    #   `str(type(self))`). Each account should expose a method for
    #   getting a set of itself and all of the other accounts that it
    #   shares a contribution room with, which should be easy - just
    #   return `self.owner.contribution_room[self._token]`
    #   (n.b. use `self.contributor` for RRSPs).
    #   Client code can then ensure that it isn't double-contributing by
    #   spreading contributions over all accounts that share
    #   contribution room (and can find such accounts easily, without
    #   ever touching tokens themselves)
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
                 gross_income=0, raise_rate={}, spouse=None,
                 tax_treatment=None, initial_year=None, settings=Settings):
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
            raise_rate (dict): A dict of `{year: raise}` pairs, where
                `raise` is a Decimal interpreted as a percentage (e.g.
                `Decimal('0.03')` indicates a 3% raise).
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

        # First assign attributes that aren't wrapped by properties:
        if not isinstance(name, str):
            raise TypeError("Person: name must be a string")
        self.name = name

        # Build an empty set for accounts to add themselves to.
        self.accounts = set()

        # Set up tax treatment before calling tax_withheld()
        # TODO: Make this a mandatory argument?
        self.tax_treatment = tax_treatment

        # For attributes wrapped by properties, create hidden attributes
        # and assign to them using the properties:
        self._birth_date = None
        self._retirement_date = None
        self._retirement_age = None
        self._spouse = None
        self._gross_income = {}
        self._net_income = {}
        self._raise_rate = {
            int(k): Decimal(raise_rate[k]) for k in raise_rate
        }
        self._contribution_room = {}
        self._contribution_groups = {}
        self.birth_date = birth_date
        self.retirement_date = retirement_date
        self.spouse = spouse
        self.gross_income = gross_income
        self.net_income = self.gross_income - self.tax_withheld

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
        return self._retirement_age

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
    def gross_income(self):
        """ The `Person`'s gross income for this year. """
        return self._gross_income[self.this_year]

    @gross_income.setter
    def gross_income(self, val):
        """ Sets gross_income and casts input value to `Money` """
        self._gross_income[self.this_year] = Money(val)

    @property
    def gross_income_history(self):
        """ The `Person`'s gross income for all years on record. """
        return self._gross_income

    @property
    def net_income(self):
        """ The `Person`'s gross income for this year. """
        return self._net_income[self.this_year]

    @net_income.setter
    def net_income(self, val):
        """ Sets net_income and casts input value to `Money` """
        self._net_income[self.this_year] = Money(val)

    @property
    def net_income_history(self):
        """ The `Person`'s net income for all years on record. """
        return self._net_income

    @property
    def raise_rate(self):
        """ The `Person`'s raise for the current year. """
        return self._raise_rate[self.this_year]

    @raise_rate.setter
    def raise_rate(self, val):
        """ Sets the `Person`'s raise for the current year. """
        self._raise_rate[self.this_year] = Decimal(val)

    @property
    def raise_rate_history(self):
        """ The `Person`'s raise for all years. """
        return self._raise_rate

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

    def next_year(self):
        # TODO (v2): Include temporary loss of income due to parental leave.
        # TODO (v1): Test for retirement
        super().next_year()
        self.gross_income = (
            self._gross_income[self.this_year - 1] * (1 + self.raise_rate))
        self.net_income = \
            self.gross_income - self.tax_withheld

    def _taxable_income(self, year=None):
        year = self.this_year if year is None else year
        return self._gross_income[year]

    def _tax_withheld(self, year=None):
        year = self.this_year if year is None else year
        if self.tax_treatment is not None:
            return self.tax_treatment(self._gross_income[year], year)
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
        balance (dict): The opening account balance for each year.
            Each element is a Money object.
        rate (dict): The rate of return (or interest) per year, before
            compounding.
            Each element is float-like (e.g. float, Decimal).
        transactions (dict): The transactions to/from the account for
            each year. Each element is a dict of `{when: value}` pairs,
            where:
                `when` (float, Decimal, str): Describes the timing of
                    the transaction.
                    Must be in the range [0,1] or in ('start', 'end').
                    The definition of this range is counterintuitive:
                    0 corresponds to 'end' and 1 corresponds to 'start'.
                    (This is how `numpy` defines its `when` argument
                    for financial methods.)
                `value` (Money): The inflows and outflows at time `when`.
                    Positive for inflows and negative for outflows.
                    Each element must be a Money object (or convertible
                    to one).
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
    def __init__(self, owner, balance=0, rate=0, transactions={},
                 nper=1, initial_year=None, settings=Settings):
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
            settings (Settings): Provides default values.
        """
        super().__init__(initial_year, settings)

        # Type-check the owner
        if not isinstance(owner, Person):
            raise TypeError('Account: owner must be of type Person.')
        owner.accounts.add(self)  # Track this account via owner.
        self.owner = owner

        # Set the scalar values first, 'cause they're easy!
        self.nper = self._conv_nper(nper)

        # Initialize dict values
        self._balance = {}
        self._rate = {}
        self._transactions = {}

        # Type-checking and such is handled by property setters.
        self.balance = balance
        self.rate = rate
        self.transactions = transactions

        # We don't save the settings object, but we do need to save
        # defaults for certain methods. These are not used when methods
        # are called with explicit `when` arguments.
        self._inflow_timing = when_conv(settings.transaction_in_timing)
        self._outflow_timing = when_conv(settings.transaction_out_timing)

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
    def balance(self):
        """ The balance of the account for the current year (Money). """
        return self._balance[self.this_year]

    @balance.setter
    def balance(self, val):
        """ Sets the balance of the account for the current year. """
        self._balance[self.this_year] = Money(val)

    @property
    def balance_history(self):
        """ All year-opening balances of the account. """
        return self._balance

    @property
    def rate(self):
        """ The rate of the account for the current year (Decimal). """
        return self._rate[self.this_year]

    @rate.setter
    def rate(self, val):
        """ Sets the rate of the account for the current year. """
        self._rate[self.this_year] = Decimal(val)

    @property
    def rate_history(self):
        """ All annual rates of the account. """
        return self._rate

    @property
    def transactions(self):
        """ The transactions in and out of the account this year (dict). """
        return self._transactions[self.this_year]

    @transactions.setter
    def transactions(self, val):
        """ Sets transactions in and out of the account for this year. """
        self._transactions[self.this_year] = {
            when_conv(x): Money(val[x]) for x in val
        }

    @property
    def transactions_history(self):
        """ All transactions in and out of the account. """
        return self._transactions

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

    def inflows(self, year=None):
        """ The sum of all inflows to the account. """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # Convert to Money at the end because the sum might return 0
        # (an int) if there are no transactions
        if year in self._transactions:
            return Money(sum([val for val in self._transactions[year].values()
                              if val.amount > 0]))
        else:
            return Money(0)

    def outflows(self, year=None):
        """ The sum of all outflows from the account. """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # Convert to Money at the end because the sum might return 0
        # (an int) if there are no transactions
        if year in self._transactions:
            return Money(sum([val for val in self._transactions[year].values()
                              if val.amount < 0]))
        else:
            return Money(0)

    def __len__(self):
        """ The number of years of transaction data in the account. """
        return self.this_year - self.initial_year + 1

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

    def value_at_time(self, value, now='start', time='end', year=None):
        """ Returns the present (or future) value.

        Args:
            value (Money): The (nominal) value to be converted.
            now (Decimal): The time associated with the nominal value.
            time (Decimal): The time to which the nominal value is to
                be converted.
            year (int): The year in which to determine the future value.

        Returns:
            A Money object representing the present value
            (if now > time) or the future value (if now < time) of
            `value`.
        """
        if year is None:
            year = self.this_year

        return value * self.accumulation_function(
            when_conv(time) - when_conv(now), self._rate[year], self.nper
        )

    def balance_at_time(self, time, year=None):
        """ Returns the balance at a point in time.

        Args:
            when (Decimal, str): The timing of the transaction.
        """
        if year is None:
            year = self.this_year

        # We need to convert `time` to enable the comparison in the dict
        # comprehension in the for loop below.
        time = when_conv(time)

        # Find the future value (at t=time) of the initial balance.
        # This doesn't include any transactions of their growth.
        balance = self.value_at_time(self._balance[year], 'start', time, year)

        # Add in the future value of each transaction (except that that
        # happen after `time`).
        for when in [w for w in self._transactions[year].keys() if w <= time]:
            balance += self.value_at_time(
                self._transactions[year][when], when, time, year
            )

        return balance

    def next_balance(self, year=None):
        """ The balance at the start of the next year.

        This is the balance after applying all transactions and any
        growth/losses from the rate.

        Returns:
            The new balance as a `Money` object.
        """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # First, find the future value of the initial balance assuming
        # there are no transactions.
        balance = self.value_at_time(self._balance[year], 'start', 'end', year)

        # Then, add in the future value of each transaction. Note that
        # this accounts for both inflows and outflows; the future value
        # of an outflow will negate the future value of any inflows that
        # are removed. Order doesn't matter.
        for when, value in self._transactions[year].items():
            balance += self.value_at_time(value, when, 'end', year)

        return balance

    def next_year(self, *args, **kwargs):
        """ Adds another year to the account.

        Sets the next year's balance and rate, but does not set any
        transactions.
        """
        super().next_year(*args, **kwargs)

        # Ensure that the owner has been brought up to this year
        while self.owner.this_year < self.this_year:
            self.owner.next_year()

        self.balance = self.next_balance(self.this_year - 1)
        self.rate = self._rate[self.this_year - 1]
        self.transactions = {}

    def max_outflow(self, when='end', year=None):
        """ An outflow which would reduce the end-of-year balance to 0.

        Returns a value which, if withdrawn at time `when`, would result
        in the account balance being 0 at the end of the year, after all
        other transactions are accounted for.

        NOTE: This does not guarantee that the account balance will not
        be negative at a time between `when` and `end`.

        Equivalently, this is the future value of the account, net of
        all existing transactions, at present time `when`.

        Args:
            when (When): The timing of the transaction.
        """
        # If the balance is positive, the max outflow is simply the
        # current balance (but negative). If the balance is negative,
        # then there's no further outflows to be made.
        return min(-self.balance_at_time(when, year), Money(0))

    def max_inflow(self, when='end', year=None):
        """ The maximum amount that can be contributed to the account.

        For non-registered accounts, there is no maximum, so this method
        returns Money('Infinity')
        """
        return Money('Infinity')

    def min_outflow(self, when='end', year=None):
        """ The minimum amount to be withdrawn from the account.

        For non-registered accounts, there is no minimum, so this method
        returns Money('0')
        """
        return Money('0')

    def min_inflow(self, when='end', year=None):
        """ The minimum amount to be contributed to the account.

        For non-registered accounts, there is no minimum, so this method
        returns Money('0')
        """
        return Money('0')
