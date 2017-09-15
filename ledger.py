""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from numbers import Number
import math
import decimal
from decimal import Decimal
from collections import namedtuple
from moneyed import Money
from settings import Settings
# swapping custom Money class for py-moneyed's Money class
# from money import Money


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


class Asset(object):
    """ An asset having a value and an adjusted cost base.

    Attributes:
        value (Money): The nominal value of the asset.
        acb (Money): The adjusted cost base of the asset.
    """

    def __init__(self, value, acb=None):
        """ Constructor for `Asset` """
        self.value = value
        if acb is None:
            self.acb = value
        else:
            self.acb = acb

    def buy(self, value, transaction_cost=0):
        """ Increase the asset value and update its acb.

        Args:
            value (Money): The amount of this asset class to purchase.
            transaction_cost (Money): The cost of the buy operation.
                This amount is added to the acb. Optional.
        """
        self.value += value
        self.acb += value + transaction_cost

    def sell(self, value, transaction_cost=0):
        """ Decrease the asset value and update its acb.

        Args:
            value (Money): The amount of the asset class to sell.
            transaction_cost (Money): The cost of the sell operation.
                This amount is subtracted from the acb. Optional.
        """
        self.acb -= self.acb * value / self.value
        self.value -= value


class Account(object):
    """ An account storing a `Money` balance.

    Has a `balance` and, optionally, a rate of growth `rate` expressed
    as an apr (annual percentage rate). For example, a 5% apr could be
    passed as `rate=0.05`.

    May optionally also recieve one or more transactions
    In addition to the balance, `Account` objects have a rate of return
    (`rate`) as well as `inflow` and `outflow` attributes. These
    attributes do not modify the `balance` directly; rather, once the
    attributes have been set, `next_year()` may be called to generate
    a new `Account` object with an updated balance.

    Attributes:
        balance (Money): The account balance at a point in time
        rate (Decimal): The rate of gains/losses, as a percentage of
            the balance, over the following year.
        inflow (Money): The amount of money added to the account
            over the following year.
        outflow (Money): The amount of money removed from the account
            over the following year.
        inflow_inclusion (Decimal): The percentage of the inflow to be
            included in gains/losses calculation.
        outflow_inclusion (Decimal): The percentage of the outflow to be
            included in gains/losses calculation.
    """

    # NOTE: This originally used None as a default value, but we seemed
    # to be interpreting None as 0 a lot in methods of this class and
    # subclasses, and we weren't using None to convey meaningful
    # information (other than that the value hasn't been set, but
    # that doesn't appear to be important for this class).
    def __init__(self, balance, rate=0, inflow=0, outflow=0,
                 inflow_inclusion=0, outflow_inclusion=0):
        """ Constructor for `Account`.

        Inflows and outflows to the account may be modelled
        independently. They may optionally be included in any returns or
        losses (arising from `rate`) based on corresponding
        `*_inclusion` arguments. This allows the `Account` object to
        model different timing strategies for inflows and outflows.
        """
        self.balance = balance
        self.rate = rate
        self.inflow = inflow
        self.outflow = outflow
        self.inflow_inclusion = inflow_inclusion
        self.outflow_inclusion = outflow_inclusion

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

    @property
    def rate(self) -> Decimal:
        """ The rate (interest rate, rate of return, etc.).

        This determines the growth/losses in the account balance. """
        return self._rate

    @rate.setter
    def rate(self, rate) -> None:
        """ Sets the rate.

        The rate must be convertible to Decimal """
        if isinstance(rate, Decimal):
            self._rate = rate
        else:
            self._rate = Decimal(rate)

    @property
    def inflow(self) -> Money:
        """ The inflow to the `Account` object """
        return self._inflow

    @inflow.setter
    def inflow(self, inflow) -> None:
        """ Sets the inflow.

        Inflows must be convertible to type `Money`. """
        if isinstance(inflow, Money):
            self._inflow = inflow
        else:
            self._inflow = Money(inflow)

    @property
    def outflow(self) -> Money:
        """ The outflow from the `Account` object """
        return self._outflow

    @outflow.setter
    def outflow(self, outflow) -> None:
        """ Sets the outflow.

        Outflows must be convertible to type `Money`. """
        if isinstance(outflow, Money):
            self._outflow = outflow
        else:
            self._outflow = Money(outflow)

    @property
    def inflow_inclusion(self) -> Decimal:
        """ The inclusion rate for inflows when applying the rate """
        return self._inflow_inclusion

    @inflow_inclusion.setter
    def inflow_inclusion(self, inflow_inclusion) -> None:
        """ Sets the inclusion rate for inflows.

        Inflows must be numeric and in [0,1] """
        # Cast to Decimal if necessary
        if not isinstance(inflow_inclusion, Decimal):
            inflow_inclusion = Decimal(inflow_inclusion)
        # Ensure the new value is in the range [0,1]
        if not (inflow_inclusion >= 0 and inflow_inclusion <= 1):
            raise ValueError("Money: inflow_inclusion must be in [0,1]")
        self._inflow_inclusion = inflow_inclusion

    @property
    def outflow_inclusion(self) -> Decimal:
        """ The inclusion rate for outflow amounts """
        return self._outflow_inclusion

    @outflow_inclusion.setter
    def outflow_inclusion(self, outflow_inclusion) -> None:
        """ Sets the inclusion rate for outflows.

        Outflows must be convertible to Decimal and in [0,1]. """
        # Cast to Decimal if necessary
        if not isinstance(outflow_inclusion, Decimal):
            outflow_inclusion = Decimal(outflow_inclusion)
        # Ensure the new value is in the range [0,1]
        if not (outflow_inclusion >= 0 and outflow_inclusion <= 1):
            raise ValueError("Money: outflow_inclusion must be in [0,1]")
        self._outflow_inclusion = outflow_inclusion

    def transactions(self):
        """ Iterates over transactions to the account in order.

        Since this class currently doesnt receive a time series of
        in/outflow data, this method implements on some important
        assumptions.

        The key assumption is that all inflows and outflows are made as
        lump sums at time (1-i), where `i` is the inclusion rate. Thus,
        an inclusion rate of `1` means that the flow occurs immediately,
        and an inclusion rate of `0` means that the flow occurs at the
        end of the period.

        Yields:
            An ordered series of Transaction objects.
        """
        # TODO: Redesign the underlying data model to provide more
        # robust transaction data.
        if self.inflow_inclusion >= self.outflow_inclusion:
            yield Transaction(self.inflow, 1 - self.inflow_inclusion)
            yield Transaction(self.outflow, 1 - self.outflow_inclusion)
        else:
            yield Transaction(self.outflow, 1 - self.outflow_inclusion)
            yield Transaction(self.inflow, 1 - self.inflow_inclusion)

    def next_balance(self) -> Money:
        """ The balance after applying inflows/outflows/rate.

        Inflows and outflows are included in the gains/losses
        calculation based on the corresponding `*_inclusion` attribute
        (which is interpreted as a percentage and should be in [0,1]).

        Returns:
            The new balance as a `Money` object.
        """
        return self._balance * (1 + rate) + \
            inflow * (rate * inflow_inclusion + 1) - \
            outflow * (rate * outflow_inclusion + 1)

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
