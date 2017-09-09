""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from datetime import datetime
from dateutil.parser import parse
from numbers import Number
from decimal import Decimal
from moneyed import Money
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
            OverflowError: birth_date or retirement_date are too large
        """
        if not isinstance(name, str):
            raise TypeError("Person: name must be a string")
        self.name = name

        # If `birth_date` is not a `datetime`, attempt to parse
        if not isinstance(birth_date, datetime):
            birth_date = parse(str(birth_date))
        self.birth_date = birth_date

        # If `retirement_date` is not a `datetime`, attempt to parse.
        # If month/day aren't given, use the corresponding values of
        # birth_date
        if not isinstance(retirement_date, datetime):
            retirement_date = parse(str(retirement_date), self.birth_date)
        self.retirement_date = retirement_date

    def age(self, date) -> int:
        """ The age of the `Person` as of `date`.

        `date` may be a `datetime` object or a numeric value indicating
        a year (e.g. 2001). In the latter case, the age at the *end* of
        `year` is returned.

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
            date = parse(str(date),
                         datetime(self.birth_date.year()-1, 12, 12))

        age_ = date.year() - self.birth_date.year

        # `age` cannot be negative
        # NOTE: Should we return None instead of raising an error?
        if age_ < 0:
            raise ValueError("Person: date must be no earlier than birth_date")
        return age_

    def retirement_age(self) -> datetime:
        """ The age at which the `Person` will retire.

        Returns:
            The age at which the `Person` will retire as a `datetime`.
            `None` if the person's retirement date is unknown. """
        if self.retirement_date is None:
            return None
        else:
            age = self.retirement_date.year - self.birth_date.year
            if self.birth_date.replace(self.retirement_date.year) < \
               self.retirement_date:
                age += 1
            return age


class Account(object):
    """ An account storing a `Money` balance.

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

    def __init__(self, balance, rate=None, inflow=None, outflow=None,
                 inflow_inclusion=None, outflow_inclusion=None):
        """ Constructor for `Account`.

        Receives `balance` and stores it as type `Money`. Optionally
        receives a `rate` of return/loss/interest/etc (of numeric type).
        For example, a 5% interest rate could be passed as `rate=0.05`.

        Inflows and outflows to the account may be modelled
        independently. They may optionally be included in any returns or
        losses (arising from `rate`) based on corresponding
        `*_inclusion` arguments. This allows the `Account` object to
        model different timing strategies for inflows and outflows.
        """
        self._balance = balance
        self._rate = rate
        self._inflow = inflow
        self._outflow = outflow
        self._inflow_inclusion = inflow_inclusion
        self._outflow_inclusion = outflow_inclusion

    @property
    def balance(self) -> Money:
        """ The balance of the `Account` object. """
        return self._balance

    @balance.setter
    def set_balance(self, balance) -> None:
        """ Sets the current balance """
        self._balance = Money(balance)

    @property
    def rate(self) -> Decimal:
        """ The rate (interest rate, rate of return, etc.).

        This determines the growth/losses in the account balance. """
        return self._rate

    @rate.setter
    def set_rate(self, rate) -> None:
        """ Sets the rate.

        The rate must be numeric (e.g. Decimal, float, int) """
        if not isinstance(rate, Number):
            raise TypeError("Money: rate must be numeric")
        self._rate = rate

    @property
    def inflow(self) -> Money:
        """ The inflow to the `Account` object """
        return self._inflow

    @inflow.setter
    def set_inflow(self, inflow) -> None:
        """ Sets the inflow.

        Inflows must be convertible to type `Money`. """
        self._inflow = Money(inflow)

    @property
    def outflow(self) -> Money:
        """ The outflow from the `Account` object """
        return self._outflow

    @outflow.setter
    def set_outflow(self, outflow) -> None:
        """ Sets the outflow.

        Outflows must be convertible to type `Money`. """
        self._outflow = Money(outflow)

    @property
    def inflow_inclusion(self) -> Decimal:
        """ The inclusion rate for inflows when applying the rate """
        return self._inflow_inclusion

    @inflow_inclusion.setter
    def set_inflow_inclusion(self, inflow_inclusion) -> None:
        """ Sets the inclusion rate for inflows.

        Inflows must be numeric and in [0,1] """
        if not isinstance(inflow_inclusion, Number) and \
           inflow_inclusion is not None:
            raise TypeError("Money: inflow_inclusion must be numeric")
        if not (inflow_inclusion >= 0 and inflow_inclusion <= 1):
            raise ValueError("Money: inflow_inclusion must be in [0,1]")
        self._inflow_inclusion = inflow_inclusion

    @property
    def outflow_inclusion(self) -> Decimal:
        """ The inclusion rate for outflow amounts """
        return self._outflow_inclusion

    @outflow_inclusion.setter
    def set_outflow_inclusion(self, outflow_inclusion) -> None:
        """ Sets the inclusion rate for outflows.

        Outflows must be numeric and in [0,1]. """
        if not isinstance(outflow_inclusion, Number) and \
           outflow_inclusion is not None:
            raise TypeError("Money: outflow_inclusion must be numeric")
        if not (outflow_inclusion >= 0 and outflow_inclusion <= 1):
            raise ValueError("Money: outflow_inclusion must be in [0,1]")
        self._outflow_inclusion = outflow_inclusion

    def change_in_balance(self) -> Money:
        """ The balance after applying inflows/outflows/rate.

        Inflows and outflows are included in the gains/losses
        calculation based on the corresponding `*_inclusion` attribute
        (which is interpreted as a percentage and should be in [0,1]).

        Returns:
            The new balance as a `Money` object.
        """
        balance = self._balance * (1 + self._rate)

        if self._inflow is not None:
            balance += self._inflow
            if self._inflow_inclusion is not None:
                balance += self._inflow * self._rate * self._inflow_inclusion

        if self._outflow is not None:
            balance -= self._outflow.nominal_value
            if self._outflow_inclusion is not None:
                balance -= self._outflow * self._rate * self._outflow_inclusion

        return balance

    def next_year(self):
        """ Applies inflows/outflows/rate/etc. to the balance.

        Returns a new account object which has only its balance set.

        Returns:
            An object of the same type as the Account (i.e. if this
            method is called by an instance of a subclass, the method
            returns an instance of that subclass.)
        """
        return type(self)(self.change_in_balance())


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

    # TODO: Expand SavingsAccount to handle multiple asset classes with
    # different types of gains/distributions (e.g. interest, dividends),
    # perhaps by implementing an Asset class (with subclasses for each
    # type of asset, e.g. stocks/bonds?) which tracks acb independently.
    # Perhaps support rebalancing as well?

    # Define aliases for `SavingsAccount` methods.
    contribution = property(Account.inflow, Account.set_inflow, None,
                            "A contribution to the `Account` object.")

    withdrawal = property(Account.outflow, Account.set_outflow, None,
                          "A withdrawal from the `Account` object.")

    contribution_inclusion = property(Account.inflow_inclusion,
                                      Account.set_inflow_inclusion,
                                      None,
                                      "Sets inclusion rate for contributions.")

    withdrawal_inclusion = property(Account.outflow_inclusion,
                                    Account.set_outflow_inclusion, None,
                                    "Sets the inclusion rate for withdrawals.")

    # Define new methods
    def taxable_income(self, stock_allocation=None) -> Money:
        """ The total taxable income arising from growth of the account.

        Args:
            allocation: An optional parameter that defines the
                relative allocations of different asset classes.
                No effect in `SavingsAccount`, but used by subclasses.

        Returns:
            The taxable income arising from growth of the account as a
                `Money` object.
        """
        return self.change_in_balance()


class RRSP(SavingsAccount):
    """ A Registered Retirement Savings Plan (Canada) """

    def taxable_income(self, sources=None) -> Money:
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
    def taxable_income(self, sources=None) -> Money:
        """ Returns $0 (TFSAs are not taxable.) """
        return Money(0)


class TaxableAccount(SavingsAccount):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income. """

    def __init__(self, balance, rate=None, inflow=None, outflow=None,
                 inflow_inclusion=None, outflow_inclusion=None, acb=None):
        """ Constructor for `TaxableAccount`

        Args:
            acb: Adjusted cost base of the taxable account. Used to
                determine realized capital gains.
            (See Account for other args) """
        super.__init__(self, balance, rate, inflow, outflow, inflow_inclusion,
                       outflow_inclusion)
        self.acb = acb if adb is not None else self.balance

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
        net_flows = self.contribution - self.withdrawal
        # Add net flows and their growth to balance
        balance = self.balance + net_flows + \
            (self.contribution * self.contribution_inclusion) - \
            (self.withdrawal * self.withdrawal_inclusion)
        # Add net flows (but not their growth) to ACB
        acb = self.acb + net_flows
        # Any withdrawals will realize capital gains
        return self.withdrawal * (acb / balance)


class Debt(Account):
    """ A debt with a balance and an interest rate. """

    # Define aliases for `Debt` methods.
    withdrawal = property(Account.inflow, Account.set_inflow, None,
                          "A withdrawal from the `Debt` object.")

    payment = property(Account.outflow, Account.set_outflow, None,
                       "A payment to the `Debt` object.")

    withdrawal_inclusion = property(Account.inflow_inclusion,
                                    Account.set_inflow_inclusion,
                                    None,
                                    "Sets inclusion rate for contributions.")

    payment_inclusion = property(Account.outflow_inclusion,
                                 Account.set_outflow_inclusion, None,
                                 "Sets the inclusion rate for withdrawals.")


class OtherProperty(Account):
    """ An asset other than a bank account or similar financial vehicle."""
    pass
