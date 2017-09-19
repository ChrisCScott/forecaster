""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from numbers import Number
import math
import decimal
from decimal import Decimal
from collections import namedtuple
from collections import Sequence
import moneyed
# TODO: implement cached properties
# from cached_property import cached_property
from moneyed import Money as PyMoney
from settings import Settings


class Person(object):
    """ Represents a person's basic information: age and retirement age.

    Attributes:
        name: A string corresponding to the person's name.
        birth_date: A datetime corresponding to the person's birth date.
            If a non-datetime argument is received, will interpret
            `int` as a birth year; other values will parsed as strings.
        retirement_date: An optional datetime corresponding to the
            person's retirement date.
            If a non-datetime argument is received, will interpret
            `int` as a birth year; other values will parsed as strings
    """

    # TODO: Add life expectancy?
    def __init__(self, name, birth_date, retirement_date=None):
        """ Constructor for `Person`.

        Args:
            name (str): The person's name.
            birth_date: The person's date of birth.
                May be passed as any value that can be cast to str and
                converted to datetime by python-dateutils.parse().
            retirement_date: The person's retirement date.Optional.
                May be passed as any value that can be cast to str and
                converted to datetime by python-dateutils.parse().

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
        age_ = date.year - self.birth_date.year
        if date.replace(self.birth_date.year) < self.birth_date:
            age_ -= 1

        # We allow age to be negative, if that's what the caller wants.
        # if age_ < 0:
            # raise ValueError("Person: date must be after birth_date")

        return age_


class Money(PyMoney):
    """ Extends py-moneyed to support __round__ """
    def __round__(self, ndigits=None):
        """ Rounds to ndigits """
        return Money(round(self.amount, ndigits), self.currency)

    def __eq__(self, other):
        """ Extends == to use Decimal's ==.

        This allows for comparison to 0 (or other Decimal-convertible
        values).
        """
        # NOTE: If the other object is also a Money object, this
        # won't fall back to Decimal, because Decimal doesn't know how
        # to compare itself to Money. This is good, because otherwise
        # we'd be comparing face values of different currencies,
        # yielding incorrect behaviour like JPY1 == USD1.
        return super().__eq__(other) or self.amount == other


# TODO: Either use this class or delete it.
class Asset(Money):
    """ An asset having a value and an adjusted cost base.

    Attributes:
        acb (Money): The adjusted cost base of the asset.
    """

    def __init__(self, amount=Decimal('0.0'),
                 currency=moneyed.DEFAULT_CURRENCY_CODE,
                 acb=None):
        """ Constructor for `Asset` """
        # Let the Money class do its work:
        super().__init__(amount, currency)

        if acb is None:
            self.acb = self.amount
        else:
            self.acb = acb

    def buy(self, amount, transaction_cost=0):
        """ Increase the asset value and update its acb.

        Args:
            amount (Money): The amount of this asset class to purchase.
            transaction_cost (Money): The cost of the buy operation.
                This amount is added to the acb. Optional.
        """
        self.amount += amount
        self.acb += amount + transaction_cost

    def sell(self, amount, transaction_cost=0):
        """ Decrease the asset value and update its acb.

        Args:
            amount (Money): The amount of the asset class to sell.
            transaction_cost (Money): The cost of the sell operation.
                This amount is subtracted from the acb. Optional.
        """
        self.acb -= self.acb * amount / self.amount
        self.amount -= amount


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
        balance (Money): The account balance at a point in time
        apr (float, Decimal): The annual percentage rate, i.e. the rate
            of return after compounding. Optional.
        transactions (Money, list, dict): One or more transactions.
            May be given as a Money object or a list of Money objects.
            In that case, each transaction is modelled as a lump sum
            according to the timing given by `*_timing_default`.
            May be given as (and will be converted to) a dict of
            `{when:value}` pairs, where:
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
        settings (Settings): Defines default values (initial year,
            inflow/outflow transaction timing, etc.). Optional; uses
            global Settings class attributes if None given.
    """

    def __init__(self, balance, apr=0, transactions={}, nper=1,
                 settings=None):
        """ Constructor for `Account`. """
        # This class provides some secondary attributes that are
        # evaluated lazily (e.g. rate). These are not set in __init__
        # and are not provided by the user.
        # TODO: Implement a cached_property decorator and cache these
        # secondary attributes until a primary attribute (i.e. one of
        # the ones received by __init__) is changed. Ensure that the
        # cache is invalidated when a primary attribute is invalidated.

        # Set the primary (non-lazy) attributes:
        self.balance = balance
        # Set nper before apr (because we need nper to convert apr to rate)
        self.nper = self._conv_nper(nper)
        self.apr = apr
        self.settings = settings if settings is not None else Settings
        self.transactions = transactions

# TODO: When caching is implemented, provide a method to invalidate the
# cache for *all* secondary attributes.
#    def _invalidate_cache(self):
#        """ Invalidates the cache for all cached attributes. """
#        for attribute in dir(self):
#            if attribute in self.__dict__ and \
#               isinstance(self.__dict__[attribute], cached_property):
#                del self.__dict__[attribute]

    @property
    def balance(self) -> Money:
        """ The balance of the `Account` object. """
        return self._balance

    @balance.setter
    def balance(self, balance) -> None:
        """ Sets the current balance """
        if isinstance(balance, Money):
            self._balance = balance
        else:
            self._balance = Money(balance)

        # This is a primary attribute, so invalidate the cache.
        # self._invalidate_cache()

    @property
    def apr(self) -> Decimal:
        """ The rate (interest rate, rate of return, etc.) as an apr.

        This determines the growth/losses in the account balance. """
        return self._apr

    @apr.setter
    def apr(self, apr) -> None:
        """ Sets the apr.

        The apr must be convertible to Decimal """
        self._apr = Decimal(apr)
        # Also update rate
        self._rate = Decimal(self.apr_to_rate(self._apr, self._nper))

        # This is a primary attribute, so invalidate the cache.
        # self._invalidate_cache()

    @property
    def rate(self) -> Decimal:
        """ The pre-compounding annual rate """
        return self._rate

    @rate.setter
    def rate(self, rate) -> None:
        """ Sets the rate. """
        self._rate = Decimal(rate)
        # Also update apr. This also invalidates the cache.
        self._apr = self.rate_to_apr(self._rate, self._nper)

    @classmethod
    def apr_to_rate(cls, apr, nper=None) -> Decimal:
        """ The annual rate of return pre-compounding.

        Args:
            apr (Decimal): Annual percentage rate (i.e. a measure of the
                rate post-compounding).
            nper (int): The number of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        nper = cls._conv_nper(nper)
        if nper is None:  # Continuous
            # Solve P(1+apr)=Pe^rt for r, given t=1:
            # r = log(1+apr)/t = log(1+apr)
            return math.log(1+apr)
        else:  # Periodic
            # Solve P(1+apr)=P(1+r/n)^nt for r, given t=1
            # r = n [(1 + apr)^-nt - 1] = n [(1 + apr)^-n - 1]
            return nper * (math.pow(1+apr, nper ** -1) - 1)

    @classmethod
    def rate_to_apr(cls, rate, nper=None) -> Decimal:
        """ The post-compounding annual percentage rate of return.

        Args:
            rate (Decimal): Rate of return (pre-compounding).
            nper (int): The nuber of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        nper = cls._conv_nper(nper)
        if nper is None:  # Continuous
            # Solve P(1+apr)=Pe^rt for apr, given t=1:
            # apr = e^rt - 1 = e^r - 1
            return math.exp(rate) - 1
        else:  # Periodic
            # Solve P(1+apr)=P(1+r/n)^nt for apr, given t=1
            # apr = (1 + r / n)^nt - 1 = (1 + r / n)^n - 1
            return math.pow(1 + rate/nper, nper) - 1

    @property
    def nper(self) -> int:
        """ Number of compounding periods.

        Returns:
            An int if there is a discrete number of compounding periods,
                or None if compounding is continuous.
        """
        return self._nper

    @nper.setter
    def nper(self, nper) -> None:
        """ Sets nper. """
        self._nper = self._conv_nper(nper)

        # This is a primary attribute, so invalidate the cache.
        # self._invalidate_cache()
        # NOTE: _rate is a bit different from other properties, because
        # even though it's not cached we store it internally without
        # forcing recalculation. So force recalculation here.
        if '_apr' in self.__dict__:
            self._rate = self.apr_to_rate(self._apr, self._nper)

    @staticmethod
    def _conv_nper(nper) -> int:
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
            mapping = {  # Fancy python-style switch statement
                'C': None,
                'D': 365,
                'W': 52,
                'BW': 26,
                'SM': 24,
                'M': 12,
                'BM': 6,
                'Q': 4,
                'SA': 2,
                'A': 1}
            if nper not in mapping.keys():
                raise ValueError('Account: str nper must have a known value')
            return mapping[nper]
        else:  # Attempt to cast to int
            if not nper == int(nper):
                raise TypeError(
                    'Account: nper is not losslessly convertible to int')
            if nper <= 0:
                raise ValueError('Account: nper must be greater than 0')
            return int(nper)

    @property
    def transactions(self) -> None:
        """ A dict of {when:value} pairs. """
        return self._transactions

    @transactions.setter
    def transactions(self, transactions) -> dict:
        """ Sets transactions and does associated type-checking. """
        # These are long, nested calls, so let's shorten them
        in_t = self.settings.StrategyDefaults.contribution_timing
        out_t = self.settings.StrategyDefaults.withdrawal_timing

        # We have some typechecking to do, so we'll start with an
        # empty dict and add the elements one at a time.
        self._transactions = {}

        # Simplest case: It's already a dict!
        # Add elements one-at-a-time so that we can do conversions.
        if isinstance(transactions, dict):
            for when, value in transactions.items():
                self._add_transaction(value, when)

        # If it's a list, fill in the key values based on defaults
        elif isinstance(transactions, Sequence):
            # Add each transaction to the dict
            for value in transactions:
                if value >= 0:  # Positive transactions are inflows
                    self._add_transaction(value, in_t)
                else:  # Negative transactions are outflows
                    self._add_transaction(value, out_t)

        # If it's not a list or dict, interpret as a single transaction.
        else:
            if value >= 0:
                self._add_transaction(value, in_t)
            else:
                self._add_transaction(value, out_t)

        # This is a primary attribute, so invalidate the cache.
        # self._invalidate_cache()

    def _add_transaction(self, value, when) -> None:
        """ Adds a transaction to the time series of transactions.

        This is a helper function. It doesn't clear the cache or do
        anything else to clean up the object - that's up to the caller.
        If you're calling this, you probably need to call the
        `_invalidate_cache()` method on this object before calling
        any other secondary/cached properties.

        In general, if you're calling from external code, you should be
        calling `add_transaction` (notice the lack of preceding
        underscore), which has some nice defaults and does some cleanup
        for you.

        Args:
            value (Money): The value of the transaction.
            when (float, str): The timing of the transaction. (See
                class definition for more on this parameter.)

        Raises:
            decimal.InvalidOperation: Transactions must be convertible
                to type Money and `when` must be convertible to type
                Decimal
            ValueError: `when` must be in [0,1]
        """
        # Convert `when` to a Decimal value.
        # Even if already a Decimal, this checks `when` for value/type
        when = self._when_conv(when)

        # Try to cast non-Money objects to type Money
        if not isinstance(value, Money):
            value = Money(value)

        # If there's already a transaction at this time, then add them
        # together; simultaneous transactions are modelled as one sum.
        # NOTE: An earlier implementation allowed for separately
        # representing simultaneous transactions by making each value
        # in the dict a list of Money objects. This added some
        # complexity and overhead without any clear benefit, but the
        # original implementation is commented out below just in case.
        if when in self._transactions:  # Add to existing value
            self._transactions[when] += value
            # self._transactions[when].append(value)
        else:  # Create new when/value pair.
            self._transactions[when] = value
            # self._transactions[when] = list(value)

    def add_transaction(self, value, when='end') -> None:
        """ Adds a transaction to the account.

        This is a public-facing method that does some input processing
        and clean-up. Client code should generally call this method
        instead of `_add_transaction` (note the underscore!)

        Args:
            value (Money): The value of the transaction. Positive values
                are inflows and negative values are outflows.
            when (float, Decimal, str): The timing of the transaction.
                Must be in the range [0,1] or in {'start', 'end'}.
                0 corresponds to 'end' and 1 corresponds to 'start'.
                (It's a bit counterintuitive, but this is how `numpy`
                defines its `when` argument for financial methods.)
                Defaults to 'end'.
        """
        # No need to call _when_conv; _add_transaction does that.

        self._add_transaction(value, when)
        # _add_transaction relies on client code for invalidating the
        # cache, so do that here.
        # self._invalidate_cache()

    @staticmethod
    def _when_conv(when) -> Decimal:
        """ Converts various types of `when` inputs to Decimal.

        Args:
            `when` (float, Decimal, str): The timing of the transaction.
                Must be in the range [0,1] or in ('start', 'end').
                The definition of this range is counterintuitive:
                0 corresponds to 'end' and 1 corresponds to 'start'.
                (This is how `numpy` defines its `when` argument
                for financial methods.)

        Returns:
            A Decimal value in [0,1].

        Raises:
            decimal.InvalidOperation: `when` must be convertible to
                type Decimal
            ValueError: `when` must be in [0,1]
        """
        # Attempt to convert a string input first
        if isinstance(when, str):
            # Throws a KeyError if the str isn't 'end' or 'start'
            return {'end': 0, 'start': 1}[when]

        # Otherwise, convert to Decimal (this works with Decimal input)
        when = Decimal(when)
        # Ensure the new value is in the range [0,1]
        if when > 1 or when < 0:
            raise ValueError("Money: 'when' must be in [0,1]")
        return when

    def __iter__(self):
        """ Iterates over {when:value} transaction pairs. """
        return self._transactions.items()

    def accumulation_function(self, t, partial_credit=False) -> Decimal:
        """ The accumulation function, A(t), from interest theory.

        `t` is conventionally defined in such a way that 0 is the start
        of the compounding sequence. This method works just fine that
        way: accumulation_function(t) returns the same result as the
        conventionally-defined A(t) in finance theory.

        It's worth noting that this method _also_ works to determine the
        accumulation from the time an inflow or outflow occurs until
        the end of the period (i.e. the end of the year).
        This is because the time period [0,1] is symmetric; the
        accumulation from [0,t] is the same as the accumulation from
        [1-t, 1]. Thus, for a transaction which occurs at time `when`,
        `accumulation_function(when)` will yield the growth multiplier
        for the transaction.

        Example:
            For an account with 5% apr and a transaction that occurs
            at time `when = 1` (i.e. the start of the period):
                `account.accumulation_function(when)`
            returns `1.05`.

        Args:
            t (float, Decimal): Defines the period [0,t] over which the
                accumulation will be calculated.
            partial_credit (Boolean): If True, any partial compounding
                periods in [0,t] will be included in the accumulation
                on a pro-rated basis.
                This isn't a feature of interest theory formulae, but
                it is something that some banks offer. Use with caution.

        Returns:
            The accumulation A(t), as a Decimal.
        """
        acc = 1

        # Convert t to Decimal
        t = Decimal(t)

        # Use the exponential formula for continuous compounding: e^rt
        if self.nper is None:
            acc = math.exp(self.rate * t)
        # Otherwise use the discrete formula: (1+r/n)^nt
        else:
            acc = (1 + self.rate / self.nper) ** (self.nper * t)

        # Optionally add in growth for any partial compounding periods.
        # The percentage of the partial period that was completed is the
        # decimal portion of `t * nper` (equivalently `t % freq`, where
        # `freq = 1 / nper`).
        # Multiply that by the per-period rate (rate / nper) to obtain
        # the pro-rated growth during the partial period.
        if partial_credit:
            acc *= 1 + (self.rate / self.nper) * ((t * self.nper) % 1)

        return acc

    def future_value(self, value, when, partial_value=False) -> Money:
        """ The nominal value of a transaction at the end of the year.

        Takes into account the compounding frequency and also the effect
        of mid-period transactions.

        Args:
            value (Money): The value of the transaction.
            when (float, Decimal): The timing of the transaction, which
                is a value in [0,1]. See `_when_conv` for more on this
                convention.
            partial_credit (Boolean): If True, any partial compounding
                periods in [0,t] will be included in the accumulation
                on a pro-rated basis.
                This isn't a feature of interest theory formulae, but
                it is something that some banks offer. Use with caution.

        Returns:
            A value of a transaction, including any gains (or losses)
            earned (for inflows) or avoided (for outflows) from the time
            a transaction was entered until the end of the accounting
            period (i.e. until the end of the year).
            Includes the value of the transaction itself.
        """
        # Future value (fv) is `fv = pv*A(t)`, where `pv` is the present
        # value and `A(t)` is the accumulation function at time t.
        # We're playing a bit of a trick here, since we don't want the
        # accumulation over the period [0,t] (which is what A(t) is
        # defined over), we want the accumulation over the period
        # [1-t, 1] (at least, based on how `A(t)` is usually defined).
        # However, `when` is defined in a backwards sort of way where 0
        # is the end and 1 is the start, so `when` effectively gives you
        # `1-t`. Since the interest rate in [0,1] is constant and the
        # compounding periods in [0,1] are symmetric, using `when` gives
        # us exactly what we want!
        return value * self.accumulation_function(when, partial_value)

    def present_value(self, value, when, partial_value=False) -> Money:
        """ Initial value required to achieve a given end-of-year value.

        Takes into account the compounding frequency and also the effect
        of mid-period transactions.

        Args:
            value (Money): The present value of the transaction,
                measured at t='end' (i.e. at the end of the year)
            when (float, Decimal): The timing of the transaction, which
                is a value in [0,1]. See `_when_conv` for more on this
                convention.
            partial_credit (Boolean): If True, any partial compounding
                periods in [0,t] will be included in the accumulation
                on a pro-rated basis.
                This isn't a feature of interest theory formulae, but
                it is something that some banks offer. Use with caution.

        Returns:
            The sum of initial capital required at time t to achieve a
            future (nominal) balance of `value`, including any gains (or
            losses) earned (for inflows) or avoided (for outflows) from
            time `t` until the end of the accounting period (i.e. until
            end of the year).
        """
        # Present value (pv) is `pv = fv/A(t)`, where `fv` is the future
        # value and `A(t)` is the accumulation function at time t.
        # See `future_value` for comments on some tricks being played
        # with `accumulation_function` and `when` here.
        return value / self.accumulation_function(when, partial_value)

#    @cached_property
    @property
    def next_balance(self) -> Money:
        """ The balance after applying inflows/outflows/rate.

        Inflows and outflows are included in the gains/losses
        calculation based on the corresponding `*_inclusion` attribute
        (which is interpreted as a percentage and should be in [0,1]).

        Returns:
            The new balance as a `Money` object.
        """
        # First, find the future value of the initial balance assuming
        # there are no transactions.
        balance = self.future_value(self.balance, 1)

        # Then, add in the future value of each transaction. Note that
        # this accounts for both inflows and outflows; the future value
        # of an outflow will negate the future value of any inflows that
        # are removed. Order doesn't matter.
        for when, value in self.transactions.items():
            balance += self.future_value(value, when)

        return balance

    def balance_at_time(self, time):
        """ Returns the balance at a point in time.

        Args:
            time (float, Decimal, str): The timing of the transaction,
                which is a value in [0,1]. See `_when_conv` for more on
                this convention.
        """
        # Parse the time input
        time = when_conv(time)

        # Find the future value of the initial balance assuming there
        # are no transactions.
        balance = self.future_value(self.balance, 1 - time)

        # Add in the future value of each transaction up to and
        # including `time`.
        for when in [w for w in self.transactions.keys() if w >= time]:
            # HACK: This is working around the fact that `present_value`
            # and `future_value` each only take one time value, rather
            # than a start time and an end time. Consider reimplementing
            # `future_value` to take two time values.

            # Determine the value at the end of the year
            end_value = self.future_value(self.transactions[value], when)
            # Figure out the balance at time `time` attributable to that
            # final balance.
            balance += self.present_value(self.transactions[value], time)

        return balance

    def next_year(self):
        """ Applies inflows/outflows/rate/etc. to the balance.

        Returns a new account object which has only its balance set.

        Returns:
            An object of the same type as the Account (i.e. if this
            method is called by an instance of a subclass, the method
            returns an instance of that subclass.)
        """
        return type(self)(self.next_balance)

    def max_outflow(self, when) -> Money:
        """ An outflow which would reduce the end-of-year balance to 0.

        Returns a value which, if withdrawn at time `when`, would result
        in the account balance being 0 at the end of the year, after all
        other transactions are accounted for.

        NOTE: This does not guarantee that the account balance will not
        be negative at a time between `when` and `'end'`.

        Equivalently, this is the future value of the account, net of
        all existing transactions, at present time `when`.

        Args:
            when (float, Decimal, str): The timing of the transaction,
                which is a value in [0,1]. See `_when_conv` for more on
                this convention.
        """
        # Parse `when`
        when = self._when_conv(when)

        # We want the future balance, reduced by the growth.
        # And, since this is an outflow, the result should be negative.
        return -self.next_balance / self.accumulation_function(when)


class SavingsAccount(Account):
    """ A savings account. Contains assets and describes their growth.

    Subclasses implement registered accounts (RRSPs, TFSAs) and more
    complex non-registered (i.e. taxable) investment accounts.

    Attributes:
        contributions (Money): The sum of all contributions to the
            account.
        withdrawals (Money): The sum of all withdrawals from the
            account.
        taxable_income (Money): The taxable income for the year arising
            from activity in the account.
    """

    # TODO: Expand SavingsAccount to handle:
    # 1) multiple asset classes with different types of income (e.g.
    # interest, dividends, capital gains, or combinations thereof).
    # Perhaps implement an Asset class (with subclasses for each
    # type of asset, e.g. stocks/bonds?) and track acb independently?
    # 2) rebalancing of asset classes

    # Define aliases for `SavingsAccount` properties.
    def contribute(self, value, when=None) -> None:
        """ Adds a contribution transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        If `when` is not provided, the application-level default timing
        for contributions is used.
        """
        if value < 0:
            raise ValueError('SavingsAccount: Contributions must be positive.')

        # Use an application-level default for `when` if none provided.
        if when is None:
            when = Settings.StrategyDefaults.contribution_timing

        self.add_transaction(value, when)

#    @cached_property
    @property
    def contributions(self) -> Money:
        """ Returns the sum of all contributions to the account. """
        return sum([val for val in self.transactions.values() if val > 0])

    def withdraw(self, value, when=None) -> None:
        """ Adds a withdrawal transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        If `when` is not provided, the application-level default timing
        for withdrawals is used.
        """
        if value < 0:
            raise ValueError('SavingsAccount: Withdrawals must be positive.')

        # Use an application-level default for `when` if none provided.
        if when is None:
            when = Settings.StrategyDefaults.withdrawal_timing

        self.add_transaction(value, when)

#    @cached_property
    @property
    def withdrawals(self) -> Money:
        """ Returns the sum of all withdrawals from the account. """
        return sum([val for val in self.transactions.values() if val < 0])

    # Define new methods
#    @cached_property
    @property
    def taxable_income(self) -> Money:
        """ The total taxable income arising from growth of the account.

        Returns:
            The taxable income arising from growth of the account as a
                `Money` object.
        """
        # TODO: Define an asset_allocation property and determine the
        # taxable income based on that allocation. Be sure to define
        # a setter on that allocation parameter which invalidates the
        # cache!

        # Assume all growth is immediately taxable (e.g. as in a
        # conventional savings account earning interest)
        return self.next_balance - self.balance

#    @cached_property
    @property
    def tax_withheld(self) -> Money:
        """ The total sum of witholding taxes incurred in the year.

        Returns:
            The tax withheld on account activity (e.g. on withdrawals,
            certain forms of income, etc.)
        """
        # Standard savings account doesn't have any witholding taxes.
        return 0

#    @cached_property
    @property
    def tax_credit(self) -> Money:
        """ The total sum of tax credits available for the year.

        Returns:
            The tax credits arising from account activity (e.g. for
            certain witholding taxes and forms of income)
        """
        # Standard savings account doesn't have any tax credits.
        return 0


class RRSP(SavingsAccount):
    """ A Registered Retirement Savings Plan (Canada) """

#    @cached_property
    @property
    def taxable_income(self) -> Money:
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        # Return the sum of all withdrawals from the account.
        return self.withdrawals

#    @cached_property
    @property
    def tax_withheld(self) -> Money:
        """ The total tax withheld from the account for the year.

        For RRSPs, this is calculated according to a CRA formula.
        """
        # TODO: Figure out where tax methods should live. (e.g.
        # tax_withheld will vary by year as the rate schedule changes;
        # should this logic live in the Tax class entirely? Should this
        # method receive a `rate` dict of {amount, rate} pairs?
        # HACK: The usual rate (for withdrawals over $5000) is 30%, but
        # lower rates apply to smaller, one-off withdrawals.
        return self.taxable_income * Decimal(0.3)

    # TODO: Determine whether there are any RRSP tax credits to
    # implement in an overloaded tax_credit method.


class TFSA(SavingsAccount):
    """ A Tax-Free Savings Account (Canada) """

#    @cached_property
    @property
    def taxable_income(self) -> Money:
        """ Returns $0 (TFSAs are not taxable.) """
        return 0


class TaxableAccount(SavingsAccount):
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
    # TODO: Reimplement TaxableAccount based on Asset objects
    # (subclassed from Money), which independently track acb and possess
    # an asset class (or perhaps `distribution` dict defining the
    # relative proportions of sources of taxable income?)
    # Perhaps also implement a tax_credit and/or tax_deduction method
    # (e.g. to account for Canadian dividends)

    def __init__(self, balance, apr=0, transactions={}, nper=1,
                 settings=None, acb=0):
        """ Constructor for `TaxableAccount`. """
        super().__init__(balance, apr, transactions, nper, settings)
        self.acb = acb if acb is not None else self.balance

    @property
    def acb(self) -> Money:
        """ Adjusted cost base. """
        return self._acb

    @acb.setter
    def acb(self, val) -> None:
        """ Sets acb. """
        if isinstance(val, Money):
            self._acb = val
        else:
            self._acb = Money(val)
        # If acb is changed, we'll need to recalculate taxable_income,
        # which is cached. Thus, invalidate the cache when acb is set.
        # self._invalidate_cache()

#    @cached_property
    @property
    def _acb_and_capital_gain(self) -> (Money, Money):
        """ Determines both acb and capital gains. For internal use.

        These can be implemented as separate functions. However, they
        use the same underlying logic, but their results can't be
        inferred from each other. (i.e. you can't determine capital
        gains just from the acb at the start and end of the year).

        Returns:
            A (acb, capital_gains) tuple.
        """
        # See this link for information on calculating ACB/cap. gains:
        # https://www.adjustedcostbase.ca/blog/how-to-calculate-adjusted-cost-base-acb-and-capital-gains/

        # Set up initial conditions
        acb = self._acb
        capital_gain = 0

        # Iterate over transactions in order of occurrence
        for when in sorted(self.transactions.keys()):
            value = self.transactions[when]
            # There are different acb formulae for inflows and outflows
            if value >= 0:  # inflow
                acb += value
            else:  # outflow
                # Capital gains are calculated based on the acb and
                # balance before the transaction occurred.
                balance = self.balance_at_time(when) - value
                capital_gain += -value * (1 - (acb / balance))
                acb *= 1 - (-value / balance)

        return (acb, capital_gain)

#    @cached_property
    @property
    def next_acb(self) -> Money:
        """ Determines acb after contributions/withdrawals.

        Returns:
            The acb after all contributions and withdrawals are made,
                as a Money object.
        """
        return self._acb_and_capital_gain()[0]

#    @cached_property
    @property
    def capital_gain(self) -> Money:
        """ The total capital gain for the period.

        Returns:
            The capital gains from all withdrawals made during the year,
                as a Money object.
        """
        return self._acb_and_capital_gain()[1]

#    @cached_property
    @property
    def taxable_income(self) -> Money:
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

        # If no asset allocation is provided, assume 100% of the return
        # is capital gains. This is taxed at a 50% rate.
        if asset_allocation is None:
            return self.capital_gain / 2

        # TODO: Handle asset allocation in such a way that growth in the
        # account can be apportioned between capital gains, dividends,
        # etc.
        return self.capital_gains / 2

    # TODO: Implement tax_withheld and tax_credit.
    # tax_withheld: foreign withholding taxes.
    # tax_credit: Canadian dividend credit


class Debt(Account):
    """ A debt with a balance and an interest rate.

    If there is an outstanding balance, the balance value will be a
    *negative* value, in line with typical accounting principles.

    Attributes:
        balance (Money): The balance of the debt.
        withdrawals (Money): The amount withdrawn. This increases the
            (negative-valued) balance.
        payments (Money): The amount paid. This decreases the
            (negative-valued) balance.
    """

    def pay(self, value, when=0.5) -> None:
        """ Adds a payment transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        If `when` is not provided, the transactions are made in the
        middle of the year (which should yield roughly the same results
        as monthly, mid-month payments).

        For convenience, the sign of `value` is ignored. This will
        result in a positive-valued inflow to the account.

        Args:
            value (Money): A positive value for the payment transaction.
            when (float, Decimal, str): The timing of the payment.
                See _when_conv for conventions on this argument.
        """
        self.add_transaction(abs(value), when)

#    @cached_property
    @property
    def payments(self) -> Money:
        """ Returns the sum of all payments to the account. """
        return sum([val for val in self.transactions.values() if val > 0])

    def withdraw(self, value, when=None) -> None:
        """ Adds a withdrawal transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        If `when` is not provided, the transactions are made in the
        middle of the year (which should yield roughly the same results
        as monthly, mid-month payments).

        For convenience, the sign of `value` is ignored. This will
        result in a negative-valued outflow from the account.

        Args:
            value (Money): A positive value for the withdrawal
                transaction.
            when (float, Decimal, str): The timing of the payment.
                See _when_conv for conventions on this argument.
        """
        self.add_transaction(-abs(value), when)

#    @cached_property
    @property
    def withdrawals(self) -> Money:
        """ Returns the sum of all withdrawals from the account. """
        return abs(sum([val for val in self.transactions.values() if val < 0]))


# TODO: Should this be subclassed from SavingsAccount?
class OtherProperty(Account):
    """ An asset other than a bank account or similar financial vehicle.

    Unlike other SavingsAccount classes, the user can select whether or
    not growth in the account is taxable. This allows for tax-preferred
    assets like mortgages to be conveniently represented.

    Attributes:
        taxable (bool): Whether or not growth of the account is taxable.
    """
    def __init__(self, balance, apr=0, transactions={}, nper=1,
                 settings=None, taxable=False):
        """ Constructor for OtherProperty. """
        super().__init__(balance, apr, transactions, nper, settings)
        self.taxable = taxable

    @property
    def taxable(self) -> bool:
        """ Whether or not the growth of the account is taxable. """
        return self._taxable

    @taxable.setter
    def taxable(self, val) -> None:
        """ Sets taxable property """
        if not isinstance(val, bool):
            raise TypeError('OtherAccount: taxable must be of type bool')

        self._taxable = val
        # self._invalidate_cache()

#    @cached_property
    @property
    def taxable_income(self) -> Money:
        """ The taxable income generated by the account for the year. """
        if self.taxable:
            return super().taxable_income
        else:
            return 0
