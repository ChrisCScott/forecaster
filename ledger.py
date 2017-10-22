""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from numbers import Number
import math
import decimal
from decimal import Decimal
from collections import namedtuple
from collections import Sequence
import moneyed
from moneyed import Money as PyMoney
from settings import Settings


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
        balance (dict): The opening account balance for each year.
            Each element is a Money object.
        rate (dict): The rate of return (or interest) per year, before
            compounding.
            Each element is float-like (e.g. float, Decimal).
        apr (dict): The annual percentage rate per year, i.e. the rate
            of return after compounding.
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
        settings (Settings): Defines default values (initial year,
            inflow/outflow transaction timing, etc.). Optional; uses
            global Settings class attributes if None given.
    """
    # TODO: Convert all attributes into dicts (essentially, turn
    # `Account` into a dict of `Account`). The same core logic will
    # apply to most methods, although indexing will be required.

    # TODO: Modify next_year to add to the dicts. (add a _this_year
    # attribute to make accessing the last elements convenient).

    # TODO: Consider removing most properties and replacing them with
    # methods. (Most setters are just there for type-checking anyways).
    # The methods can operate on the values of the current year, and
    # previous years' values can be treated as immutable.

    # NOTE: Consider using lists instead - this would be more efficient
    # and might map better to the logic of this method (which doesn't
    # care about indexing but does want to maintain an ordered list that
    # we append to), but it may be less convenient for client code that
    # generally prefers to access attributes via a `year` key.

    def __init__(self, balance=0, rate=0, transactions={},
                 nper=1, apr=False, initial_year=None, settings=Settings):
        """ Constructor for `Account`.

        This constructor receives only values for the first year.

        Args:
            initial_year (int): The first year (e.g. 2000)
            balance (Money): The balance for the first year
            rate (float, Decimal): The rate for the first year.
            transactions (dict): The transactions for the first year,
                as {timing: amount} pairs, where `timing` is defined
                according to the `when` convention described in the
                description of the Account class.
            nper (int): The number of compounding periods per year.
            apr (bool): If True, rate is interpreted as an annual
                percentage rate and will be converted to a
                pre-compounding figure.
            settings (Settings): Provides default values.
        """
        # TODO: Implement a cached_property decorator and cache these
        # secondary attributes until a primary attribute (i.e. one of
        # the ones received by __init__) is changed. Ensure that the
        # cache is invalidated when a primary attribute is invalidated.

        # TODO: Type-check inputs.
        self.initial_year = initial_year if initial_year is not None \
            else settings.initial_year
        self.last_year = self.initial_year
        self.balance = {self.initial_year: balance}
        self.nper = self._conv_nper(nper)
        if apr:
            rate = self.apr_to_rate(rate, self.nper)
        self.rate = {self.initial_year: rate}
        self.transactions = {self.initial_year: transactions}

        # Copy relevant values from the settings object
        self._inflow_timing = self._when_conv(settings.transaction_in_timing)
        self._outflow_timing = self._when_conv(settings.transaction_out_timing)

    @staticmethod
    def apr_to_rate(apr, nper=None):
        """ The annual rate of return pre-compounding.

        Args:
            apr (Decimal): Annual percentage rate (i.e. a measure of the
                rate post-compounding).
            nper (int): The number of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        if nper is None:  # Continuous
            # Solve P(1+apr)=Pe^rt for r, given t=1:
            # r = log(1+apr)/t = log(1+apr)
            return math.log(1+apr)
        else:  # Periodic
            nper = Account._conv_nper(nper)
            # Solve P(1+apr)=P(1+r/n)^nt for r, given t=1
            # r = n [(1 + apr)^-nt - 1] = n [(1 + apr)^-n - 1]
            return nper * (math.pow(1+apr, nper ** -1) - 1)

    def apr(self, year=None):
        """ The post-compounding annual percentage rate of return.

        Args:
            rate (Decimal): Rate of return (pre-compounding).
            nper (int): The nuber of compounding periods. Optional.
                If not given, compounding is continuous.
        """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        if self.nper is None:  # Continuous
            # Solve P(1+apr)=Pe^rt for apr, given t=1:
            # apr = e^rt - 1 = e^r - 1
            return math.exp(self.rate[year]) - 1
        else:  # Periodic
            # Solve P(1+apr)=P(1+r/n)^nt for apr, given t=1
            # apr = (1 + r / n)^nt - 1 = (1 + r / n)^n - 1
            return math.pow(1 + self.rate[year]/self.nper, self.nper) - 1

    @staticmethod
    def _conv_nper(nper):
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

    def add_transaction(self, value, when='end', year=None):
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

        Raises:
            decimal.InvalidOperation: Transactions must be convertible
                to type Money and `when` must be convertible to type
                Decimal
            ValueError: `when` must be in [0,1]
        """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        # Convert `when` to a Decimal value.
        # Even if already a Decimal, this checks `when` for value/type
        if when is None:
            when = self._inflow_timing if value >= 0 else self._outflow_timing
        else:
            when = self._when_conv(when)

        # Try to cast non-Money objects to type Money
        if not isinstance(value, Money):
            value = Money(value)

        # If there's already a transaction at this time, then add them
        # together; simultaneous transactions are modelled as one sum.
        if when in self.transactions[year]:  # Add to existing value
            self.transactions[year][when] += value
        else:  # Create new when/value pair.
            self.transactions[year][when] = value

    def inflows(self, year=None):
        """ The sum of all inflows to the account. """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        return sum([val for val in self.transactions[year].values()
                   if val.amount > 0])

    def outflows(self, year=None):
        """ The sum of all outflows from the account. """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        return sum([val for val in self.transactions[year].values()
                   if val.amount < 0])

    @staticmethod
    def _when_conv(when):
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
        """ Iterates over balance entries """
        for key in sorted(self.balance.keys()):
            yield self.balance[key]

    def __len__(self):
        """ The number of years of transaction data in the account. """
        return self.last_year - self.initial_year + 1

    @staticmethod
    def accumulation_function(self, t, rate, nper=1):
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

        This method's output is not well-defined where t does not align
        with the start/end of a compounding period. (It will produce
        sensible output, but it might not correspond to how your bank
        calculates interest)

        Example:
            For an account with 5% apr and a transaction that occurs
            at time `when = 1` (i.e. the start of the period):
                `account.accumulation_function(when)`
            returns `1.05`.

        Args:
            t (float, Decimal): Defines the period [0,t] over which the
                accumulation will be calculated.
            rate (float, Decimal): The rate of return (or interest).
            nper (int): The number of compounding periods per year.

        Returns:
            The accumulation A(t), as a Decimal.
        """
        acc = 1

        # Convert t to Decimal
        t = Decimal(t)

        # Use the exponential formula for continuous compounding: e^rt
        if nper is None:
            acc = math.exp(rate * t)
        # Otherwise use the discrete formula: (1+r/n)^nt
        else:
            acc = (1 + rate / nper) ** (nper * t)

        return acc

    def future_value(self, value, when, year=None):
        """ The nominal value of a transaction at the end of the year.

        Takes into account the compounding frequency and also the effect
        of mid-period transactions.

        Args:
            value (Money): The value of the transaction.
            when (float, Decimal): The timing of the transaction, which
                is a value in [0,1]. See `_when_conv` for more on this
                convention.
            year (int): The year in which to determine the future value.

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

        # Return most recent year by default
        if year is None:
            year = self.last_year
        return value * Decimal(self.accumulation_function(when,
                                                          self.rate[year],
                                                          self.nper))

    def present_value(self, value, when, year=None):
        """ Initial value required to achieve a given end-of-year value.

        Takes into account the compounding frequency and also the effect
        of mid-period transactions.

        Args:
            value (Money): The present value of the transaction,
                measured at t='end' (i.e. at the end of the year)
            when (float, Decimal): The timing of the transaction, which
                is a value in [0,1]. See `_when_conv` for more on this
                convention.
            year (int): The year in which to determine the present value

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

        # Return most recent year by default
        if year is None:
            year = self.last_year
        return value / Decimal(self.accumulation_function(when,
                                                          self.rate[year],
                                                          self.nper))

    def next_balance(self, year=None):
        """ The balance at the start of the next year.

        This is the balance after applying all transactions and any
        growth/losses from the rate.

        Returns:
            The new balance as a `Money` object.
        """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        # First, find the future value of the initial balance assuming
        # there are no transactions.
        balance = self.future_value(self.balance[year], 1, year)

        # Then, add in the future value of each transaction. Note that
        # this accounts for both inflows and outflows; the future value
        # of an outflow will negate the future value of any inflows that
        # are removed. Order doesn't matter.
        for when, value in self.transactions[year].items():
            balance += self.future_value(value, when, year)

        return balance

    def balance_at_time(self, time, year=None):
        """ Returns the balance at a point in time.

        Args:
            time (float, Decimal, str): The timing of the transaction,
                which is a value in [0,1]. See `_when_conv` for more on
                this convention.
        """
        if year is None:
            year = self.last_year

        # Parse the time input
        time = when_conv(time)

        # Find the future value of the initial balance assuming there
        # are no transactions.
        balance = self.future_value(self.balance[year], 1 - time, year)

        # Add in the future value of each transaction up to and
        # including `time`.
        for when in [w for w in self.transactions[year].keys() if w >= time]:
            # HACK: This is working around the fact that `present_value`
            # and `future_value` each only take one time value, rather
            # than a start time and an end time. Consider reimplementing
            # `future_value` to take two time values.

            # Determine the value at the end of the year
            end_value = self.future_value(self.transactions[year][when], when)
            # Figure out the balance at time `time` attributable to that
            # final balance.
            balance += self.present_value(self.transactions[year][when], time)

        return balance

    def next_year(self):
        """ Adds another year to the account.

        Sets the next year's balance and rate, but does not set any
        transactions.
        """
        self.last_year += 1
        self.balance[self.last_year] = self.next_balance()
        self.rate[self.last_year] = self.rate[self.last_year - 1]
        self.transactions[self.last_year] = {}

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
            when (float, Decimal, str): The timing of the transaction,
                which is a value in [0,1]. See `_when_conv` for more on
                this convention.
        """
        # Return most recent year by default
        if year is None:
            year = self.last_year

        # Parse `when`
        when = self._when_conv(when)

        # We want the future balance, reduced by the growth.
        # And, since this is an outflow, the result should be negative.
        return -self.next_balance(year) / \
            self.accumulation_function(when, self.rate[year], self.nper)

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
    # TODO: Remove aliases?

    # Define aliases for `SavingsAccount` properties.
    def contribute(self, value, when=None, year=None):
        """ Adds a contribution transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        Values must be non-negative.
        """
        # TODO: Remove `year` attribute, so that only last year is
        # treated as mutable?
        if value < 0:
            raise ValueError('SavingsAccount: Contributions must be positive.')

        self.add_transaction(value, when, year)

    def contributions(self, year=None):
        """ The sum of all contributions to the account. """
        return self.inflows(year)

    def withdraw(self, value, when=None, year=None):
        """ Adds a withdrawal transaction to the account.

        This is a convenience method that wraps Account.add_transaction.
        If `when` is not provided, the application-level default timing
        for withdrawals is used.
        """
        # TODO: Remove `year` attribute, so that only last year is
        # treated as mutable?
        if value < 0:
            raise ValueError('SavingsAccount: Withdrawals must be positive.')

        self.add_transaction(value, when, year)

    def withdrawals(self, year=None):
        """ The sum of all withdrawals from the account. """
        return self.outflows(year)

    # Define new methods
    def taxable_income(self, year=None):
        """ The total taxable income arising from growth of the account.

        Returns:
            The taxable income arising from growth of the account as a
                `Money` object.
        """
        # TODO: Define an asset_allocation property and determine the
        # taxable income based on that allocation.

        # Assume all growth is immediately taxable (e.g. as in a
        # conventional savings account earning interest)
        if year is not None and year < self._this_year:
            return self.balance[year + 1] - self.balance[year]
        else:
            return self.next_balance(year) - self.balance[year]

    def tax_withheld(self, year=None):
        """ The total sum of witholding taxes incurred in the year.

        Returns:
            The tax withheld on account activity (e.g. on withdrawals,
            certain forms of income, etc.)
        """
        # Standard savings account doesn't have any witholding taxes.
        return Money(0)

    def tax_credit(self):
        """ The total sum of tax credits available for the year.

        Returns:
            The tax credits arising from account activity (e.g. for
            certain witholding taxes and forms of income)
        """
        # Standard savings account doesn't have any tax credits.
        return Money(0)


class RRSP(SavingsAccount):
    """ A Registered Retirement Savings Plan (Canada) """

    def taxable_income(self, year=None):
        """ The total tax owing on withdrawals from the account.

        Returns:
            The taxable income owing on withdrawals the account as a
                `Money` object.
        """
        # Return the sum of all withdrawals from the account.
        return self.withdrawals(year)

    def tax_withheld(self, year=None):
        """ The total tax withheld from the account for the year.

        For RRSPs, this is calculated according to a CRA formula.
        """
        # TODO: Figure out where tax methods should live. (e.g.
        # tax_withheld will vary by year as the rate schedule changes;
        # should this logic live in the Tax class entirely? Should this
        # method receive a `rate` dict of {amount, rate} pairs?
        # HACK: The usual rate (for withdrawals over $5000) is 30%, but
        # lower rates apply to smaller, one-off withdrawals.
        return self.taxable_income(year) * Decimal(0.3)

    # TODO: Determine whether there are any RRSP tax credits to
    # implement in an overloaded tax_credit method.
    # TODO: Overload min_withdrawal, max_withdrawal, etc. (This will
    # require adding an attribute to manage contribution limits. Do this
    # in the parent class?)


class TFSA(SavingsAccount):
    """ A Tax-Free Savings Account (Canada) """

    def taxable_income(self, year=None):
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)


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

    def __init__(self, acb=0, *args, **kwargs):
        """ Constructor for `TaxableAccount`. """
        super().__init__(*args, **kwargs)
        acb = acb if acb is not None else self.balance
        self.acb = {self.initial_year: acb}

    # TODO: Memoize this method.
    def _acb_and_capital_gain(self, year=None):
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
        if year is None:
            year = self._this_year
        acb = self.acb[year]
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

    def next_acb(self, year=None):
        """ Determines acb after contributions/withdrawals.

        Returns:
            The acb after all contributions and withdrawals are made,
                as a Money object.
        """
        return self._acb_and_capital_gain(year)[0]

    def capital_gain(self, year=None):
        """ The total capital gain for the period.

        Returns:
            The capital gains from all withdrawals made during the year,
                as a Money object.
        """
        return self._acb_and_capital_gain(year)[1]

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
        year = self._this_year if year is None else year

        return self.capital_gain(year) / 2

        # TODO: Track asset allocation and apportion growth in the
        # account between capital gains, dividends, etc.

    # TODO: Implement tax_withheld and tax_credit.
    # tax_withheld: foreign withholding taxes.
    # tax_credit: Canadian dividend credit


class Debt(Account):
    """ A debt with a balance and an interest rate.

    If there is an outstanding balance, the balance value will be a
    *negative* value, in line with typical accounting principles.

    Attributes:
        reduction_rate (Money, Decimal, float, int): If provided, some
            (or all) of the debt payments are drawn from savings instead
            of living expenses. If Money, this is the amount drawn from
            savings. If a number in [0,1], this is the percentage of the
            payment that's drawn from savings. Optional.
        minimum_payment (Money): The minimum annual payment on the debt.
            Optional.
        maximum_payment(when) (Money): The amount of a payment at time
            `when` that would reduce the debt balance to 0.
        accelerate_payment (bool): If True, payments above the minimum
            may be made to pay off the balance earlier. Optional.
        balance (Money): The balance of the debt.
        withdrawals (Money): The amount withdrawn. This increases the
            (negative-valued) balance.
        payments (Money): The amount paid. This decreases the
            (negative-valued) balance.
    """

    def __init__(self, reduction_rate=1, minimum_payment=Money(0),
                 accelerate_payment=False, *args, **kwargs):
        """ Constructor for `Debt`. """
        super().__init__(*args, **kwargs)
        self.reduction_rate = Decimal(reduction_rate)
        self.minimum_payment = Money(minimum_payment)
        self.accelerate_payment = bool(accelerate_payment)

    def pay(self, value, when=None, year=None):
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
        # TODO: Remove `year` attribute, so that only last year is
        # treated as mutable?
        # TODO: Use different default for `when`? (check add_transaction)
        self.add_transaction(abs(value), when, year)

    def payments(self, year=None):
        """ The sum of all payments to the account. """
        return self.inflows(year)

    def withdraw(self, value, when=None, year=None):
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
        # TODO: Remove `year` attribute, so that only last year is
        # treated as mutable?
        # TODO: Use different default for `when`? (check add_transaction)
        self.add_transaction(-abs(value), when, year)

    def withdrawals(self, year):
        """ The sum of all withdrawals from the account. """
        return self.outflows(year)

    def maximum_payment(self, when, year=None):
        """ The payment at time `when` that would reduce balance to 0.

        This is in addition to any existing payments in the account.

        Example:
            debt = Debt(-100)
            debt.maximum_payment('start') == Money(100)  # True
            debt.add_transaction(100, 'start')
            debt.maximum_payment('start') == 0  # True
        """
        # TODO: Test this method.
        return self.max_outflow(when, year)


class OtherProperty(SavingsAccount):
    """ An asset other than a bank account or similar financial vehicle.

    Unlike other SavingsAccount subclasses, the user can select whether
    growth in the account is taxable. This allows for tax-preferred
    assets like mortgages to be conveniently represented.

    Attributes:
        taxable (bool): Whether or not growth of the account is taxable.
    """
    def __init__(self, taxable=False, *args, **kwargs):
        """ Constructor for OtherProperty. """
        super().__init__(*args, **kwargs)
        self.taxable = bool(taxable)

    def taxable_income(self, year=None):
        """ The taxable income generated by the account for the year. """
        if self.taxable:
            return super().taxable_income(year)
        else:
            return 0
