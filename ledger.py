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
from moneyed import Money
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


Transaction = namedtuple("Transaction", "value time")
""" Define a container for transactions.

    Args:
        value (Money): The value of the transaction. Positive values
            are inflows and negative values are outflows.
        time (float, Decimal): The point in the period at which the
            transaction occurred, in the range [0,1].
"""


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
        `account1.balance == 100` evaluates to True
        `account2.balance == 105` evaluates to True

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

    def __init__(self, balance, apr=0, transactions={}, nper='C',
                 settings=None):
        """ Constructor for `Account`. """
        # This class provides some secondary attributes that are
        # evaluated lazily and cached until a primary attribute is
        # changed, at which time the cache is invalidated and we
        # force recalculation when that value is next called.
        # Cached attributes are those not provided directly to __init__:
        #   returns
        #   max_outflow
        #   next_balance
        #   acb
        #   taxable_income
        self._cache = {}

        # Now set the primary (non-lazy) attributes:
        self.balance = balance
        self.apr = apr
        self.nper = self._conv_nper(compounding)
        self.settings = settings if settings is not None else Settings
        self.transactions = transactions

    def cached_property(property):
        """ A decorator for cached properties. """
        def wrapper(self, *args):
            # If the property is not in the cache, call it and add it.
            if property.__name__ not in self._cache:
                self._cache[property.__name__] = property(self, *args)
            return self._cache[property.__name__]
        return wrapper

    def invalidate_cache(self):
        """ Invalidates the cache for all cached attributes. """
        self._cache = {}

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
        self._invalidate_cache()

    @property
    def apr(self) -> Decimal:
        """ The rate (interest rate, rate of return, etc.) as an apr.

        This determines the growth/losses in the account balance. """
        return self._apr

    @rate.setter
    def apr(self, apr) -> None:
        """ Sets the apr.

        The apr must be convertible to Decimal """
        self._apr = Decimal(apr)
        # Also update rate
        self._rate = self.apr_to_rate(self._apr, self._nper)

        # This is a primary attribute, so invalidate the cache.
        self._invalidate_cache()

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

    @staticmethod
    def apr_to_rate(apr, nper=None) -> Decimal:
        """ The annual rate of return pre-compounding.

        Args:
            apr (Decimal): Annual percentage rate (i.e. a measure of the
                rate post-compounding).
            nper (int): The number of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        nper = self._conv_nper(nper)
        if nper is None:  # Continuous
            # Solve P(1+apr)=Pe^rt for r, given t=1:
            # r = log(1+apr)/t = log(1+apr)
            return math.log(1+apr)
        else:  # Periodic
            # Solve P(1+apr)=P(1+r/n)^nt for r, given t=1
            # r = n [(1 + apr)^-nt - 1] = n [(1 + apr)^-n - 1]
            return nper * (math.pow(1+apr, -nper)-1)

    @staticmethod
    def rate_to_apr(rate, nper=None) -> Decimal:
        """ The post-compounding annual percentage rate of return.

        Args:
            rate (Decimal): Rate of return (pre-compounding).
            nper (int): The nuber of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        nper = self._conv_nper(nper)
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
        self._invalidate_cache()

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
            return {  # Fancy python-style switch statement
                'C': None,
                'D': 365,
                'W': 52,
                'BW': 26,
                'SM': 24,
                'M': 12,
                'BM': 6,
                'Q': 4,
                'SA': 2,
                'A': 1}[nper]
        else:  # Attempt to cast to int
            return int(freq)

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
            for when, value in transactions:
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
        self._invalidate_cache()

    def _add_transaction(self, value, when) -> None:
        """ Adds a transaction to the time series of transactions.

        This is a helper function. It doesn't clear the cache or do
        anything else to clean up the object - that's up to the caller.
        If you're calling this, you probably need to call the
        `_invalidate_cache()` method on this object before calling
        any other secondary/cached properties.

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

    @staticmethod
    def _when_conv(when) -> Decimal:
        """ Converts various types of `when` inputs to Decimal.

        Args:
            `when` (float, Decimal, str): Describes the timing of
                the transaction.
                Must be in the range [0,1] or in ('start', 'end').
                The definition of this range is counterintuitive:
                0 corresponds to 'end' and 1 corresponds to 'start'.
                (This is how `numpy` defines its `when` argument
                for financial methods.)

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

    @staticmethod
    def growth(val, rate, start, end, nper) -> Money:
        """ Growth of `val` over period `[start,end]` given `rate`. """
        # TODO: Complete docstring
        # TODO: Implement compounding-aware growth function

        pass

    @cached_property
    def returns(self) -> Money:
        """ Total growth/losses in the account, after transactions. """
        balance = self.balance
        growth = 0
        for when, value in self:
            growth = balance

    def next_balance(self) -> Money:
        """ The balance after applying inflows/outflows/rate.

        Inflows and outflows are included in the gains/losses
        calculation based on the corresponding `*_inclusion` attribute
        (which is interpreted as a percentage and should be in [0,1]).

        Returns:
            The new balance as a `Money` object.
        """
        # Cache the result for future calls.
        # TODO: Update the below calculation to use the new transactions
        # dict with `when` timings.
        if 'next_balance' in self._cache and self._cache['next_balance']:
            self._next_balance = self._balance * (1 + rate) + \
                inflow * (rate * inflow_inclusion + 1) - \
                outflow * (rate * outflow_inclusion + 1)
            self._cache['next_balance'] = True
        return self._next_balance

    def next_year(self):
        """ Applies inflows/outflows/rate/etc. to the balance.

        Returns a new account object which has only its balance set.

        Returns:
            An object of the same type as the Account (i.e. if this
            method is called by an instance of a subclass, the method
            returns an instance of that subclass.)
        """
        return type(self)(self.next_balance())

    def max_outflow(self) -> Money:
        """ The maximum outflow for the given year.

        This is based on the balance/inflows/inclusions. Thus, if there
        are inflows and they are partially included in the rate (and/or
        if withdrawals are included in rate) then the total amount that
        can be withdrawn is affected.
        """
        # This is the same equation as is used in change_in_value, but
        # solved for result = 0.
        return (self._balance * (1 + rate) +
                inflow * (rate * inflow_inclusion + 1)) / \
            (rate * outflow_inclusion + 1)

    def balance_at_time(self, time) -> Money:
        """ The balance at time `time`, accounting for flows/growth.

        Args:
            time (float, Decimal): a value in [0,1], where 1 is the
                end of the period and 0 is the start.
        Returns:
            The balance as of the input time, as a Money object.
        """
        # TODO: Consider whether we even need this. It's only used in
        # TaxableAccount, and it seems like a lot of code duplication
        # would be necessary. It also implements some (likely
        # inaccurate) assumptions.
        balance = self.balance
        period_start = 0

        # Apply each transaction to the balance in sequence.
        for transaction in transactions:
            balance *= 1 + self.rate_for_period(period_start, transaction.time)
            balance += transaction.value

        # Apply the rate of return for the last portion of the period.
        # (Note that, if the last transaction is at the end of the
        # period, this will have no effect on the balance.)
        balance *= 1 + self.rate_for_period(period_start, 1)

    def _invalidate_cache(self):
        """ Invalidates the cache for all cached attributes. """
        for key in self._cache:
            self._cache[key] = False


class SavingsAccount(Account):
    """ A savings account. Contains assets and describes their growth.

    Subclasses implement registered accounts (RRSPs, TFSAs) and more
    complex non-registered (i.e. taxable) investment accounts.

    Attributes:
        balance (Money): The account balance at a point in time
        rate (Decimal): The rate of gains/losses, as a percentage of
            the balance, over the following year.
        contribution (Money): The amount of money contributed to the
            account over the following year.
        withdrawal (Money): The amount of money withdrawn from the
            account over the following year.
        contribution_inclusion (Decimal): The percentage of the
            contribution to be included in gains/losses calculation.
        withdrawal_inclusion (Decimal): The percentage of the withdrawal
            to be included in gains/losses calculation.
    """

    # TODO: Expand SavingsAccount to handle:
    # 1) Time series transaction data (with conversions where scalar
    # data is provided by the caller).
    # 2) multiple asset classes with different types of income (e.g.
    # interest, dividends, capital gains, or combinations thereof).
    # Perhaps implement an Asset class (with subclasses for each
    # type of asset, e.g. stocks/bonds?) and track acb independently?
    # 3) rebalancing of asset classes

    # Define aliases for `SavingsAccount` properties.
    @property
    def contribution(self):
        return self.inflow

    @contribution.setter
    def contribution(self, val):
        self.inflow = val

    @property
    def withdrawal(self):
        return self.outflow

    @withdrawal.setter
    def withdrawal(self, val):
        self.outflow = val

    @property
    def contribution_inclusion(self):
        return self.inflow_inclusion

    @contribution_inclusion.setter
    def contribution_inclusion(self, val):
        self.inflow_inclusion = val

    @property
    def withdrawal_inclusion(self):
        return self.outflow_inclusion

    @withdrawal_inclusion.setter
    def withdrawal_inclusion(self, val):
        self.outflow_inclusion = val

    # Define new methods
    def taxable_income(self, asset_allocation=None) -> Money:
        """ The total taxable income arising from growth of the account.

        Args:
            allocation: An optional parameter that defines the
                relative allocations of different asset classes.
                No effect in `SavingsAccount`, but used by subclasses.

        Returns:
            The taxable income arising from growth of the account as a
                `Money` object.
        """
        # Assume all growth is immediately taxable (e.g. as in a
        # conventional savings account earning interest)
        return self.next_balance()


class RRSP(SavingsAccount):
    """ A Registered Retirement Savings Plan (Canada) """

    def taxable_income(self, asset_allocation=None) -> Money:
        """ The total tax owing on withdrawals from the account.

        Args:
            sources: An optional parameter. Has no effect for RRSPs.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        return self.withdrawal


class TFSA(SavingsAccount):
    """ A Tax-Free Savings Account (Canada) """
    def taxable_income(self, asset_allocation=None) -> Money:
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)


class TaxableAccount(SavingsAccount):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income. """

    def __init__(self, balance, rate=0, inflow=0, outflow=0,
                 inflow_inclusion=0, outflow_inclusion=0, acb=0):
        """ Constructor for `TaxableAccount`

        Args:
            acb: Adjusted cost base of the taxable account. Used to
                determine realized capital gains.
            (See Account for other args) """
        super().__init__(balance, rate, inflow, outflow, inflow_inclusion,
                         outflow_inclusion)
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

    def next_acb(self) -> Money:
        """ Determines acb after contributions/withdrawals.

        Returns:
            The acb after all contributions and withdrawals are made,
                as a Money object.
        """
        # NOTE: See capital_gains() for a similarly-defined method.
        # Any changes here should probably happen there too.

        # See the following link for information on calculating ACB:
        # https://www.adjustedcostbase.ca/blog/how-to-calculate-adjusted-cost-base-acb-and-capital-gains/

        # Set up initial conditions
        balance = self.balance
        period_start = 0
        acb = self._acb

        # Iterate over transactions in order of occurrence
        for transaction in self.transactions():
            # There are different acb formulae for inflows and outflows
            if transaction.value >= 0:  # inflow
                acb += transaction.value
            else:  # outflow
                acb *= (balance + transaction.value) / balance

            # Reflect any growth in the balance since the previous
            # transaction (plus the current transaction, of course)
            balance += transaction.value + balance * \
                self.rate_for_period(period_start, transaction.time)
            period_start = transaction.time

        # No need to incorporate growth following the last transaction
        return acb

    def capital_gains(self) -> Money:
        """ The total capital gain for the period. """
        # NOTE: See next_acb() for a very similarly-defined method.
        # Any changes there should be reflected here, and (mostly) vice-
        # versa.

        # TODO: Cache the result of this calculation (and cause related
        # property setter methods to set a flag requiring recalculation)

        # Set up initial conditions
        balance = self.balance
        period_start = 0
        acb = self._acb
        capital_gains = 0

        # Iterate over transactions in order of occurrence
        for transaction in self.transactions():
            # There are different acb formulae for inflows and outflows
            if transaction.value >= 0:  # inflow
                acb += transaction.value
            else:  # outflow
                capital_gains += transaction.value * (1 - (acb / balance))
                acb *= (balance + transaction.value) / balance

            # Reflect any growth in the balance since the previous
            # transaction (plus the current transaction, of course)
            balance += transaction.value + balance * \
                self.rate_for_period(period_start, transaction.time)
            period_start = transaction.time

        # No need to incorporate growth following the last transaction
        return capital_gains

    def taxable_income(self, asset_allocation=None) -> Money:
        """ The total tax owing based on activity in the account.

        Tax can arise from realizing capital gains, receiving dividends
        (Canadian or foreign), or receiving interest. Optionally,
        `sources` may define the relative weightings of each of these
        sources of income. See the following link for more information:
        http://www.moneysense.ca/invest/asset-ocation-everything-in-its-place/

        Args:
            asset_allocation: # TODO: Define this arg

        Returns:
            Taxable income for the year from this account as a `Money`
                object.
        """

        # TODO: Cache the result of this calculation (and cause related
        # property setter methods to set a flag requiring recalculation)

        # If no asset allocation is provided, assume 100% of the return
        # is capital gains. This is taxed at a 50% rate.
        if asset_allocation is None:
            return self.capital_gains() / 2

        # TODO: Handle asset allocation in such a way that growth in the
        # account can be apportioned between capital gains, dividends,
        # etc.
        return self.capital_gains() / 2


class Debt(Account):
    """ A debt with a balance and an interest rate.

    Attributes:
        balance (Money): The balance of the debt. If there is an
            outstanding balance, this value will be *positive*, not
            negative.
        withdrawal (Money): The amount withdrawn. This increases the
            balance.
        payment (Money): The amount paid. This decreases the balance.
        withdrawal_inclusion (float): The *_inclusion for withdrawals.
        payment_inclusion (float): The *_inclusion for payments.
    """

    # Define aliases for `Account` properties.
    @property
    def withdrawal(self):
        return self.inflow

    @withdrawal.setter
    def withdrawal(self, val):
        self.inflow = val

    @property
    def payment(self):
        return self.outflow

    @payment.setter
    def payment(self, val):
        self.outflow = val

    @property
    def withdrawal_inclusion(self):
        return self.inflow_inclusion

    @withdrawal_inclusion.setter
    def withdrawal_inclusion(self, val):
        self.inflow_inclusion = val

    @property
    def payment_inclusion(self):
        return self.outflow_inclusion

    @payment_inclusion.setter
    def payment_inclusion(self, val):
        self.outflow_inclusion = val


class OtherProperty(Account):
    """ An asset other than a bank account or similar financial vehicle.

    Unlike other SavingsAccount classes, the user can select whether or
    not growth in the account is taxable. This allows for tax-preferred
    assets like mortgages to be conveniently represented.

    Attributes:
        taxable (bool): Whether or not growth of the account is taxable.
    """
    def __init__(self, balance, rate=0, inflow=0, outflow=0,
                 inflow_inclusion=0, outflow_inclusion=0, taxable=False):
        """ Constructor for OtherProperty. """
        super().__init__(balance, rate, inflow, outflow, inflow_inclusion,
                         outflow_inclusion)
        self.taxable = taxable

    def taxable_income(self) -> Money:
        """ The taxable income generated by the account for the year. """
        if self.taxable:
            return super().taxable_income()
        else:
            return 0
