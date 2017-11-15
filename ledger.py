""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from numbers import Number
import math
from numpy import fv, pv
import decimal
from decimal import Decimal
from collections import namedtuple
from collections import Sequence
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import moneyed
from moneyed import Money as PyMoney
from settings import Settings
from constants import Constants


class Person(object):
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
    # TODO: Add gross_income(), net_income, taxable_income, tax_payable,
    # tax_withheld, etc. as dicts. Perhaps also add next_year() (similar
    # to Account)? This would require that each Forecast build new
    # Person objects, but that might be the most practical way to go.
    # TODO: Move contribution room information from TFSA/RRSP to here?
    # (This will help with coordinating inflows to multiple RRSPs/TFSAs
    # and perhaps will allow for the implementation of Spousal RRSPs).
    # OR: Cause RRSP/TFSA to add their contribution_room attribute to
    # the owning `Person`, not to `self`.
    # TODO: Add estimated_retirement_date(...) method? Use Dr. Pfau's
    # study's results on safe withdrawal rates and require total balance
    # and desired income as input?

    def __init__(self, name, birth_date, retirement_date=None,
                 gross_income=0, spouse=None, tax_treatment=None,
                 initial_year=None, settings=Settings):
        """ Constructor for `Person`.

        TODO: Add Attributes list that includes `accounts` (which is
        not an arg.)

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
        if not isinstance(name, str):
            raise TypeError("Person: name must be a string")
        self.name = name

        # If `birth_date` is not a `datetime`, attempt to parse
        if not isinstance(birth_date, datetime):
            # If the birth date omits a year, use this year. If it omits
            # a month or day, use January and the 1st, respectively
            default_date = datetime(datetime.today().year, 1, 1)
            birth_date = parse(str(birth_date), default=default_date)

        self.birth_date = birth_date

        if retirement_date is not None:
            if not isinstance(retirement_date, datetime):
                # If `retirement_date` is not a `datetime`, attempt to parse.
                # If month/day aren't given, use the corresponding values of
                # birth_date
                default_date = self.birth_date
                retirement_date = parse(str(retirement_date),
                                        default=default_date)

            # `retirement_date` must follow `birth_date`
            if retirement_date < birth_date:
                raise ValueError("Person: retirement_date precedes birth_date")

        self.retirement_date = retirement_date

        if spouse is not None:
            if not isinstance(spouse, Person):
                raise TypeError('Person: spouse must be of type Person')
            # Spousehood is mutual, so mutate both this object and
            # the spouse object to point at each other.
            spouse.spouse = self
        self.spouse = spouse  # Assign to attr `spouse` even if None

        # We need to set the initial_year in order to build dicts
        self.initial_year = int(initial_year if initial_year is not None
                                else settings.initial_year)
        self.this_year = self.initial_year

        # Set up tax treatment before calling tax_withheld()
        self.tax_treatment = tax_treatment

        # Set up gross/net income hidden dicts
        self._gross_income = {}
        self._net_income = {}
        # Let the properties do typecasting/etc.
        self.gross_income = gross_income
        self.net_income = self.gross_income - self.tax_withheld()

        # Build an empty set for accounts to add themselves to.
        self.accounts = set()

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
    def gross_income(self):
        """ The `Person`'s gross income for this year. """
        return self._gross_income[self.this_year]

    @gross_income.setter
    def gross_income(self, val):
        """ Sets gross_income and casts input value to `Money` """
        self._gross_income[self.this_year] = Money(val)

    @property
    def net_income(self):
        """ The `Person`'s gross income for this year. """
        return self._net_income[self.this_year]

    @gross_income.setter
    def net_income(self, val):
        """ Sets net_income and casts input value to `Money` """
        self._net_income[self.this_year] = Money(val)

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

    def next_year(self, raise_rate, tax):
        # TODO (v2): Include temporary loss of income due to parental leave.
        self.this_year += 1
        self.gross_income[self.this_year] = (
            self.gross_income[self.this_year] * (1 + raise_rate))
        self.net_income[self.this_year] = self.gross_income[self.this_year] - \
            self.taxable_income(self.this_year)

    def taxable_income(self, year=None):
        year = self.this_year if year is None else year
        return self._gross_income[year]

    def tax_withheld(self, year=None):
        year = self.this_year if year is None else year
        if self.tax_treatment is not None:
            return self.tax_treatment(self._gross_income[year], year)
        else:
            return Money(0)

    def tax_credit(self, year=None):
        """ The total sum of tax credits available for the year. """
        # TODO: Implement spousal tax credit?
        # NOTE: Probably not - that's not specific to the Person (it
        # depends on the other person's income), so it should go to
        # a Tax subclass for inclusion in a holistic analysis.
        return Money(0)

    def tax_deduction(self, year=None):
        """ The total sum of tax deductions available for the year. """
        return Money(0)

    def __gt__(self, other):
        """ Allows for sorting, max, min, etc. based on gross income. """
        return self.gross_income > other.gross_income


class Money(PyMoney):
    """ Extends py-moneyed to support Decimal-like functions. """
    def __init__(self, amount=Decimal('0.0'), currency=None):
        """ Initializes with application-level default currency.

        Also allows for initializing from another Money object.
        """
        if isinstance(amount, Money):
            super().__init__(amount.amount, amount.currency)
        elif currency is None:
            super().__init__(amount, Settings.currency)
        else:
            super().__init__(amount, currency)

    def __round__(self, ndigits=None):
        """ Rounds to ndigits """
        return Money(round(self.amount, ndigits), self.currency)

    def __hash__(self):
        """ Allows for use in sets and as dict keys. """
        # Equality of Money objects is based on amount and currency.
        return hash(self.amount) + hash(self.currency)

    def __eq__(self, other):
        """ Extends == operator to allow comparison with Decimal.

        This allows for comparison to 0 (or other Decimal-convertible
        values), but not with other Money objects in different
        currencies.
        """
        # NOTE: If the other object is also a Money object, this
        # won't fall back to Decimal, because Decimal doesn't know how
        # to compare itself to Money. This is good, because otherwise
        # we'd be comparing face values of different currencies,
        # yielding incorrect behaviour like JPY1 == USD1.
        return super().__eq__(other) or self.amount == other

    def __lt__(self, other):
        """ Extends < operator to allow comparison with 0 """
        if other == 0:
            return self.amount < 0
        else:
            return super().__lt__(other)

    def __gt__(self, other):
        """ Extends > operator to allow comparison with 0 """
        if other == 0:
            return self.amount > 0
        else:
            return super().__gt__(other)


def when_conv(when):
    """ Converts various types of `when` inputs to Decimal.

    The Decimal value is in [0,1], where 0 is the start of the period
    and 1 is the end.

    NOTE: `numpy` defines its `when` argument such that 'end' = 0 and
    'start' = 1. If you're using that package, consider whether any
    conversions are necessary.

    Args:
        `when` (float, Decimal, str): The timing of the transaction.
            Must be in the range [0,1] or in ('start', 'end').

    Raises:
        decimal.InvalidOperation: `when` must be convertible to
            type Decimal
        ValueError: `when` must be in [0,1]

    Returns:
        A Decimal in [0,1]
    """
    # Attempt to convert strings 'start' and 'end' first
    if isinstance(when, str):
        if when == 'end':
            when = 1
        elif when == 'start':
            when = 0

    # Decimal can take a variety of input types (including str), so
    # rather than throw an error on non-start/end input strings, try
    # to cast to Decimal and throw a decimal.InvalidOperation error.
    when = Decimal(when)

    if when > 1 or when < 0:
        raise ValueError("When: 'when' must be in [0,1]")

    return when


def nearest_year(vals, year):
    """ Finds the nearest (past) year to `year` in `vals`.

    This is a companion method to `inflation_adjust()`. It's meant to be
    used when you want to pull a value out of an incomplete dict without
    inflation-adjusting it (e.g. when you want to grab the most recent
    percentage rate from a dict of `{year: Decimal}` pairs.)

    If `year` is in `vals`, then this method returns `year`.
    If not, then this method tries to find the last year
    before `year` that is in `vals`. If that doesn't work, then this
    method tries to find the first year in `vals` following `year`.

    Returns:
        A year in `vals` is near to `year`, preferring
        the nearest preceding year (if it exists) over the nearest
        following year. Returns `None` if `vals` is empty.
    """
    if vals == {}:
        return None

    # If the year is explicitly represented, no need to inflation-adjust
    if year in vals:
        return year

    # Look for the most recent year prior to `year` that's in vals
    key = max((k for k in vals if k < year), default=year)

    # If that didn't work, look for the closest following year.
    if key == year:
        key = min((k for k in vals if k > year), default=year)

    return key


def inflation_adjust(vals, inflation_adjustments, year):
    """ Fills in partial time-series with inflation-adjusted values.

    This method is targeted at inflation-adjusting input data (e.g.
    as found in the Constants module), which tends to be incomplete
    and can represent non-sequential years. New years are often entered
    when something changes (i.e. when values change in real terms), so
    this method prefers to infer inflation-adjusted values based on the
    most recent *past* years when possible (since future years might
    not be comparable).

    If `year` is in `vals`, then this method returns the value in `vals`
    without further inflation-adjusted (as that value is already in
    nominal terms).

    If `year` is not in `vals`, then this method attempts to interpolate
    an inflation-adjusted value. It will first attempt to forward-adjust
    by looking for the last year which is represented in `vals` and
    `inflation_adjustment` but before `year` and inflation-adjusting
    from there.

    If that doesn't work, it will backwards-adjust by looking for the
    first year in `vals` and `inflation_adjustment` following `year` and
    adjust from there.

    Args:
        vals (dict): A dict of `{year: val}` pairs, where `val` is a
            scalar, list, or dict. This dict may be incomplete, in the
            sense that some years may not be represented.
            If `val` is non-scalar, an object of the same type is
            returned with each of its values inflation-adjusted.
        inflation_adjustment (dict): A dict of `{year: Decimal}` pairs,
            where the Decimal is a scaling factor that adjusts for
            inflation (e.g. {2017: 1.25} for a 25% inflationary increase
            over the base year in 2017).
        year (int): The year for which an adjusted value is to be
            generated.

    Raises:
        ValueError: No year is in both `vals` and
            `inflation_adjustment`.
    """
    # If the year is explicitly represented, no need to inflation-adjust
    if year in vals:
        return vals[year]

    # If year isn't represented, we'll need to inflation-adjust values,
    # which means we need an inflation adjustment for year.
    if year not in inflation_adjustments:
        raise ValueError('inflation_adjust: year not in inflation_adjustment')

    # Look for the most recent year prior to `year` that's in both dicts
    key = max(
        (k for k in vals if k < year and k in inflation_adjustments),
        default=year
    )

    # If that didn't work, look for the closest following year.
    if key == year:
        key = min(
            (k for k in vals if k > year and k in inflation_adjustments),
            default=year
        )

    # If one of the above searches worked, return an inflation-adjusted
    # value (or dict/list of values, depending on what the values of
    # `vals` are)
    if key != year:
        val = vals[key]
        adj = inflation_adjustments[year] / inflation_adjustments[key]
        if isinstance(val, dict):
            return {k: val[k] * adj for k in val}
        elif isinstance(val, list):
            return [v * adj for v in val]
        else:
            return val * adj
    # If none of the above searches for a year worked, raise an error.
    else:
        raise ValueError('inflation_adjust: No year is in both vals and ' +
                         'inflation_adjustment')


# TODO: Add `owner` attribute at the `Account` level?
# (This could make tax determinations easier)
# Also change `person` attribute of RRSP to `contributor`, default to
# `owner` if none provided?


class Account(object):
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
        # Type-check the owner
        if not isinstance(owner, Person):
            raise TypeError('Account: owner must be of type Person.')
        owner.accounts.add(self)  # Track this account via owner.
        self.owner = owner

        # Set the scalar values first, 'cause they're easy!
        self.initial_year = int(initial_year if initial_year is not None
                                else settings.initial_year)
        self.this_year = self.initial_year
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
    def rate(self):
        """ The rate of the account for the current year (Decimal). """
        return self._rate[self.this_year]

    @rate.setter
    def rate(self, val):
        """ Sets the rate of the account for the current year. """
        self._rate[self.this_year] = Decimal(val)

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

    # TODO: Add add_inflow and add_outflow methods?
    # TODO: Cache results (in _inflows and _outflows dicts) and cause
    # add_transactions to invalidate the cache, similar to
    # TaxableAccount._get_capital_gain

    def inflows(self, year=None):
        """ The sum of all inflows to the account. """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # Convert to Money at the end because the sum might return 0
        # (an int) if there are no transactions
        return Money(sum([val for val in self._transactions[year].values()
                          if val.amount > 0]))

    def outflows(self, year=None):
        """ The sum of all outflows from the account. """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # Convert to Money at the end because the sum might return 0
        # (an int) if there are no transactions
        return Money(sum([val for val in self._transactions[year].values()
                          if val.amount < 0]))

    def __len__(self):
        """ The number of years of transaction data in the account. """
        return self.this_year - self.initial_year + 1

    # TODO: Remove accumulation_function, future_value, & present_value
    # and replace with numpy.fv and numpy.pv?

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

    def future_value(self, value, when, year=None):
        """ The nominal value of a transaction at the end of the year.

        Args:
            value (Money): The value of the transaction.
            when (When): The timing of the transaction.
            year (int): The year in which to determine the future value.

        Returns:
            The future value of the transaction as a Money object.
        """
        return self.value_at_time(value, when, 'end', year)

    def present_value(self, value, when, year=None):
        """ Initial value required to achieve a given end-of-year value.

        Args:
            value (Money): The present value of the transaction,
                measured at t='end' (i.e. at the end of the year)
            when (When): The timing of the transaction.
            year (int): The year in which to determine the present value

        Returns:
            The sum of initial capital required at time t to achieve a
            future (nominal) balance of `value`, including any gains (or
            losses) earned (for inflows) or avoided (for outflows) from
            time `t` until the end of the accounting period (i.e. until
            end of the year).
        """
        return self.value_at_time(value, when, 'start', year)

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
        balance = self.future_value(self._balance[year], 'start', year)

        # Then, add in the future value of each transaction. Note that
        # this accounts for both inflows and outflows; the future value
        # of an outflow will negate the future value of any inflows that
        # are removed. Order doesn't matter.
        for when, value in self._transactions[year].items():
            balance += self.future_value(value, when, year)

        return balance

    def next_year(self, *args, **kwargs):
        """ Adds another year to the account.

        Sets the next year's balance and rate, but does not set any
        transactions.
        """
        self.this_year += 1
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

    def taxable_income(self, year=None):
        """ The taxable income arising from the account in a year. """
        return Money(0)

    def tax_withheld(self, year=None):
        """ The total sum of witholding taxes incurred in the year. """
        return Money(0)

    def tax_credit(self, year=None):
        """ The total sum of tax credits available for the year. """
        return Money(0)

    def tax_deduction(self, year=None):
        """ The total sum of tax deductions available for the year. """
        return Money(0)


class RegisteredAccount(Account):
    """ A registered retirement account (Canada).

    This account isn't intended to use by client code. There are just
    so many commonalities between RRSPs and TFSAs that it made sense
    to combine them here.

    Args:
        inflation_adjustments (dict): {year, Decimal} pairs. Each
            Decimal defines a cumulative inflation adjustment relative
            to a baseline year.
        contribution_room (Money): The amount of contribution room
            available in the first year. Optional.
        contributor (Person): The contributor to the RRSP. Optional.
            If not provided, the contributor is assumed to be the same
            as the annuitant (i.e. the owner.)
    """
    def __init__(self, owner, inflation_adjustments, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=Settings, contribution_room=None, contributor=None):
        """ Initializes a RegisteredAccount object. """
        super().__init__(
            owner, balance, rate, transactions, nper, initial_year, settings)

        # If no contributor was provided, assume it's the owner.
        if contributor is None:
            self.contributor = self.owner
        elif not isinstance(contributor, Person):
            raise TypeError(
                'RegisteredAccount: person must be of type Person.'
            )
        else:
            self.contributor = contributor

        # Convert keys and values of inflation_adjustments.
        # NOTE: This creates a copy, which will reduce efficiency.
        # Consider simply retaining a link to a central dict.
        self._inflation_adjustments = {
            int(x): Decimal(inflation_adjustments[x])
            for x in inflation_adjustments
        }

        if self.initial_year not in self._inflation_adjustments:
            raise ValueError(
                'RegisteredAccount: initial_year is outside of the range of ' +
                'dates given by inflation_adjustments'
            )

        # Assign the default here instead of in the call signature
        # to maintain consistency with subclasses.
        if contribution_room is None:
            contribution_room = 0
        # Initialize _contribution_room, then use the setter.
        self._contribution_room = {}
        self.contribution_room = contribution_room

    @property
    def inflation_adjustment(self):
        """ The inflation adjustment for the current year """
        # NOTE: This property is immutable, so there's no setter
        return self._inflation_adjustments[self.this_year]

    @property
    def contribution_room(self):
        """ The contribution room for the current year. """
        return self._contribution_room[self.this_year]

    @contribution_room.setter
    def contribution_room(self, val):
        """ Sets contribution room for the current year. """
        self._contribution_room[self.this_year] = Money(val)

    def next_year(self, *args, **kwargs):
        """ Confirms that the year is within the range of our data. """
        # NOTE: Invoking super().next_year will increment self.this_year
        super().next_year(*args, **kwargs)

        if self.this_year not in self._inflation_adjustments:
            raise ValueError('RegisteredAccount: next_year is outside range ' +
                             'of inflation_adjustments.')

        # Determine contribution room for the next year:
        self.contribution_room = self.next_contribution_room(
            year=self.this_year - 1, *args, **kwargs
        )

    def next_contribution_room(self, year=None, *args, **kwargs):
        raise NotImplementedError(
            'RegisteredAccount: next_contribution_room is not implemented. ' +
            'Use RRSP or TFSA instead.'
        )

    def max_inflow(self, when='end', year=None):
        """ Limits outflows based on available contribution room. """
        if year is None:
            year = self.this_year
        return Money(self._contribution_room[year])


class RRSP(RegisteredAccount):
    """ A Registered Retirement Savings Plan (Canada). """

    # Explicitly repeat superclass args for the sake of intellisense.
    def __init__(self, owner, inflation_adjustments, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=Settings, contribution_room=None, contributor=None):
        """ Initializes an RRSP object. """
        super().__init__(
            owner, inflation_adjustments, balance, rate, transactions, nper,
            initial_year, settings, contribution_room, contributor)

        # Although `person` might provide a retirement_age, the RRSP
        # won't necessarily be turned into an RRIF at the retirement
        # date (depending on withdrawal strategy).
        # TODO: Allow RRIF_conversion_year to be passed as an argument?
        # We could use the below convert-at-71 logic if None is passed.
        # TODO: Automatically trigger RRIF conversion when an outflow
        # is detected? (Perhaps control this behaviour with an arg?)

        # The law requires that RRSPs be converted to RRIFs by a certain
        # age (currently 71). We can calculate that here:
        self.RRIF_conversion_year = self.initial_year + \
            Constants.RRSPRRIFConversionAge - \
            self.owner.age(self.initial_year)

        # Determine the max contribution room accrual in initial_year:
        self._initial_accrual = inflation_adjust(
            Constants.RRSPContributionRoomAccrualMax,
            self._inflation_adjustments,
            self.initial_year
        )

    def convert_to_RRIF(self, year=None):
        """ Converts the RRSP to an RRIF. """
        year = self.this_year if year is None else year
        self.RRIF_conversion_year = year

    def taxable_income(self, year=None):
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        # Return the sum of all withdrawals from the account.
        return -self.outflows(year)

    def tax_withheld(self, year=None):
        """ The total tax withheld from the account for the year.

        For RRSPs, this is calculated according to a CRA formula.
        """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        # NOTE: It's possible to attract a lower tax rate by making
        # smaller one-off withdrawals, but in general multiple
        # withdrawals will be treated as a lump sum for the purpose of
        # determining the tax rate, so we pretend it's a lump sum.
        if self.RRIF_conversion_year > year:
            taxable_income = self.taxable_income(year)
        else:
            # Only withdrawals in excess of the minimum RRIF withdrawal
            # are hit by the withholding tax.
            taxable_income = self.taxable_income(year) - self.min_outflow(year)

        # TODO: inflation-adjust `x` to match the inflation-adjustment
        # year of taxable_income? (this would likely require identifying
        # a year for which `x` is expressed in nominal dollars, probably
        # in Constants; maybe make RRSPWithholdingTaxRate a dict of
        # {year: {amount: rate}}?)
        tax_rate = max([Constants.RRSPWithholdingTaxRate[x]
                        for x in Constants.RRSPWithholdingTaxRate
                        if x < taxable_income.amount], default=0)
        return taxable_income * tax_rate

    def tax_deduction(self, year=None):
        """ The total sum of tax deductions available for the year.

        For RRSPs, this the amount contributed in the year.
        """
        return self.inflows(year)

    def next_contribution_room(self, income, year=None, *args, **kwargs):
        """ Determines the amount of contribution room for next year.

        Args:
            income (Money): The amount of taxable income for this year
                used to calculate RRSP contribution room.
            year (int): The year in which the income is received.

        Returns:
            The contribution room for the RRSP for the year *after*
            `year`.
        """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        if self.contributor.age(year + 1) > Constants.RRSPRRIFConversionAge:
            # If past the mandatory RRIF conversion age, no
            # contributions are allowed.
            return Money(0)
        else:
            # TODO: Add pension adjustment?

            # TODO: Move this logic to __init__, where we can determine
            # baseline accrual maximum as of initial_year. Then, in
            # each subsequent year, we can adjust relative to that.

            # Convert income to Money type
            income = Money(income)

            # First, determine how much more contribution room will
            # accrue due to this year's income:
            accrual = income * Constants.RRSPContributionRoomAccrualRate
            # Second, compare to the (inflation-adjusted) max accrual:
            max_accrual = inflation_adjust(
                Constants.RRSPContributionRoomAccrualMax,
                self._inflation_adjustments,
                year + 1
            )
            # Don't forget to add in any rollovers:
            rollover = self._contribution_room[year] - self.inflows(year)
            return min(accrual, Money(max_accrual)) + rollover

    def min_outflow(self, when='end', year=None):
        """ Minimum RRSP withdrawal """
        if year is None:
            year = self.this_year
        # Minimum withdrawals are required the year after converting to
        # an RRIF. How it is calculated depends on the person's age.
        if self.RRIF_conversion_year < self.this_year:
            age = self.contributor.age(year)
            if age in Constants.RRSPRRIFMinWithdrawal:
                return Constants.RRSPRRIFMinWithdrawal[age] * \
                    self._balance[year]
            elif age > max(Constants.RRSPRRIFMinWithdrawal):
                return self._balance[year] * \
                    max(Constants.RRSPRRIFMinWithdrawal.values())
            else:
                return self._balance[year] / (90 - age)
        else:
            return Money(0)

    # TODO: Determine whether there are any RRSP tax credits to
    # implement in an overloaded tax_credit method
    # (e.g. pension tax credit?)


# TODO: Implement SpousalRRSP?


class TFSA(RegisteredAccount):
    """ A Tax-Free Savings Account (Canada). """

    def __init__(self, owner, inflation_adjustments, balance=0, rate=0,
                 transactions={}, nper=1, initial_year=None,
                 settings=Settings, contribution_room=None, contributor=None):
        """ Initializes a TFSA object. """
        super().__init__(
            owner, inflation_adjustments, balance, rate, transactions, nper,
            initial_year, settings, contribution_room, contributor)

        # This is our baseline for estimating contribution room
        # (By law, inflation-adjustments are relative to 2009, the
        # first year that TFSAs were available, and rounded to the
        # nearest $500)
        self._base_accrual_year = min(Constants.TFSAAnnualAccrual.keys())
        self._base_accrual = round(inflation_adjust(
            Constants.TFSAAnnualAccrual,
            self._inflation_adjustments,
            self._base_accrual_year
        ) / Constants.TFSAInflationRoundingFactor) * \
            Constants.TFSAInflationRoundingFactor

        # If contribution_room is not provided, infer it based on age.
        if contribution_room is None:
            # Determine the accumulated contribution room from the year
            # that the person first became eligible up to initial_year.

            # The start age will be the later of (a) The year the person
            # turned 18 (the eligibility age) and (b) the year that the
            # TFSA program began (i.e. the first year of TFSA accrual):
            start_year = max(
                self.initial_year - self.contributor.age(self.initial_year) +
                Constants.TFSAAccrualEligibilityAge,
                min(Constants.TFSAAnnualAccrual.keys())
            )
            # Accumulate contribution room over applicable years
            # (NOTE: next_contribution_room returns the room for the
            # *following* year, hence the `start_year - 1` start)
            self.contribution_room = sum([
                self.next_contribution_room(year)
                for year in range(start_year - 1, self.initial_year)
            ])

    def next_contribution_room(self, year=None):
        """ The amount of contribution room for next year """
        # Return most recent year by default
        if year is None:
            year = self.this_year

        contribution_room = 0
        # If we already have an accrual rate set for this year, use that
        if year + 1 in Constants.TFSAAnnualAccrual:
            contribution_room += Money(Constants.TFSAAnnualAccrual[year + 1])
        # Otherwise, infer the accrual rate by inflation-adjusting the
        # base rate and rounding.
        else:
            contribution_room += Money(
                round(self._base_accrual *
                      (self._inflation_adjustments[year + 1] /
                       self._inflation_adjustments[self._base_accrual_year]
                       ) /
                      Constants.TFSAInflationRoundingFactor) *
                Constants.TFSAInflationRoundingFactor
            )
        # On top of this year's accrual, roll over unused contribution
        # room, plus any withdrawals (less contributions) from last year
        if year in self._contribution_room:
            rollover = self._contribution_room[year] - (
                self.outflows(year) + self.inflows(year)
            )
        else:
            rollover = 0
        return contribution_room + rollover

    def taxable_income(self, year=None):
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)


class TaxableAccount(Account):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income from
    capital assets. That involves tracking the adjusted cost base (acb)
    of the assets.

    Attributes:
        acb (Money): The adjusted cost base of the assets in the account
            at the start of the year.
        capital_gain
        See Account for other attributes.
    """
    # TODO (v2): Reimplement TaxableAccount based on Asset objects
    # (subclassed from Money), which independently track acb and possess
    # an asset class (or perhaps `distribution` dict defining the
    # relative proportions of sources of taxable income?)
    # Perhaps also implement a tax_credit and/or tax_deduction method
    # (e.g. to account for Canadian dividends)
    # TODO: Define a proportion of growth attributable to capital gains
    # (perhaps via Settings)? Potentially subclass this method into a
    # CapitalAsset class where all growth is capital gains - this would
    # allow for modelling non-principle-residence real estate holdings.
    # (But we might want to also model rental income as well...)

    def __init__(self, owner, balance=0, rate=0, transactions={},
                 nper=1, initial_year=None, settings=Settings, acb=None):
        """ Constructor for `TaxableAccount`. """
        super().__init__(
            owner, balance, rate, transactions, nper, initial_year, settings)

        # If acb wasn't provided, assume there have been no capital
        # gains or losses, so acb = balance.
        acb = acb if acb is not None else self.balance
        # Initialize the _acb dict and set via the property setter.
        self._acb = {}
        self.acb = acb

        # Capital gain, unlike other variables, is determined at the end
        # of the year.
        self._capital_gain = {}

    @property
    def acb(self):
        """ The adjusted cost base of assets in the account this year. """
        return self._acb[self.this_year]

    @acb.setter
    def acb(self, val):
        """ Sets the ACB for the account this year. """
        self._acb[self.this_year] = Money(val)

    def _get_capital_gain(self, year=None):
        """ Helper method. Caches capital gain on first call. """
        if year is None:
            year = self.this_year
        # If capital_gain hasn't yet been calculated, do so now
        # (and also assign acb for next year; we get that for free!)
        if year not in self._capital_gain:
            self._acb[year + 1], self._capital_gain[year] = \
                self._next_acb_and_capital_gain()
        return self._capital_gain[year]

    @property
    def capital_gain(self):
        """ The capital gains (or losses) for this year.

        Note that, unlike other Account attributes, capital_gain is
        given as of the *end* of the year, and is based on transaction
        activity. Therefore, changing any transactions will affect
        capital_gain.
        """
        # If capital_gain hasn't yet been calculated, do so now
        # (and also assign acb for next year; we get that for free!)
        return self._get_capital_gain()

    @capital_gain.setter
    def capital_gain(self, val):
        self._capital_gain[self.this_year] = Money(val)

    def add_transaction(self, value, when='end'):
        super().add_transaction(value, when)
        # Invalidate the figure for capital gains, since transactions
        # will affect it.
        self._capital_gain.pop(self.this_year, None)

    def _next_acb_and_capital_gain(self, year=None):
        """ ACB and capital gains at the end of a given year.

        This method is intended for internal use. Importantly, unlike
        other methods of Account types, this determines values at the
        *end* of a year

        These can be implemented as separate functions. However, they
        are determined in an interrelated way, so it is much more
        efficient to return both from one method.

        Returns:
            A (acb, capital_gains) tuple.
        """
        # See this link for information on calculating ACB/cap. gains:
        # https://www.adjustedcostbase.ca/blog/how-to-calculate-adjusted-cost-base-acb-and-capital-gains/

        # Set up initial conditions
        if year is None:
            year = self.this_year

        if year + 1 in self._acb and year in self._capital_gain:
            return (self._acb[year + 1], self._capital_gain[year])

        # TODO (v2): include a percentage of returns in acb to model
        # reinvestment of non-capital distributions (e.g. interest,
        # dividends)? Perhaps add a % value to Constants to define
        # this behaviour?

        acb = self._acb[year]
        capital_gain = 0

        # Iterate over transactions in order of occurrence
        for when in sorted(self._transactions[year].keys()):
            value = self._transactions[year][when]
            # There are different acb formulae for inflows and outflows
            if value >= 0:  # inflow
                acb += value
            else:  # outflow
                # Capital gains are calculated based on the acb and
                # balance before the transaction occurred.
                balance = self.balance_at_time(when, year) - value
                capital_gain += -value * (1 - (acb / balance))
                acb *= 1 - (-value / balance)

        return (acb, capital_gain)

    def next_year(self, *args, **kwargs):
        """ Updates instance attributes to the next year """
        super().next_year(*args, **kwargs)
        self.acb, self._capital_gain[self.this_year - 1] = \
            self._next_acb_and_capital_gain(self.this_year - 1)

    def taxable_income(self, year=None):
        """ The total tax owing based on activity in the account.

        Tax can arise from realizing capital gains, receiving dividends
        (Canadian or foreign), or receiving interest. Optionally,
        `sources` may define the relative weightings of each of these
        sources of income. See the following link for more information:
        http://www.moneysense.ca/invest/asset-ocation-everything-in-its-place/

        Returns:
            Taxable income for the year from this account as a `Money`
                object.
        """
        year = self.this_year if year is None else year

        # Only 50% of capital gains are included in taxable income
        return self._get_capital_gain(year) / 2

        # TODO: Track asset allocation and apportion growth in the
        # account between capital gains, dividends, etc.

    # TODO: Implement tax_withheld and tax_credit.
    # tax_withheld: foreign withholding taxes.
    # tax_credit: Canadian dividend credit


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

    def __init__(self, owner, balance=0, rate=0, transactions={},
                 nper=1, initial_year=None, settings=Settings,
                 minimum_payment=Money(0), reduction_rate=1,
                 accelerate_payment=False):
        """ Constructor for `Debt`. """
        super().__init__(
            owner, balance, rate, transactions, nper, initial_year, settings)
        self.minimum_payment = Money(minimum_payment)
        self.reduction_rate = Decimal(reduction_rate) \
            if reduction_rate is not None \
            else Settings.DebtReductionRate
        self.accelerate_payment = bool(accelerate_payment) \
            if accelerate_payment is not None \
            else Settings.DebtAcceleratePayment

    def min_inflow(self, when='end', year=None):
        """ The minimum payment on the debt. """
        return min(-self.balance_at_time(when, year), self.minimum_payment)

    def max_inflow(self, when='end', year=None):
        """ The payment at time `when` that would reduce balance to 0.

        This is in addition to any existing payments in the account.

        Example:
            debt = Debt(-100)
            debt.maximum_payment('start') == Money(100)  # True
            debt.add_transaction(100, 'start')
            debt.maximum_payment('start') == 0  # True
        """
        return -self.balance_at_time(when, year)


class PrincipleResidence(Account):
    """ A Canadian principle residence. Gains in value are not taxable. """

    def taxable_income(self, year=None):
        """ The taxable income generated by the account for the year. """
        return Money(0)
