""" Defines basic recordkeeping classes, like `Person` and `Account`. """

from datetime import datetime
from python-dateutil import parse
from numbers import Number
from py-moneyed import moneyed
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
        """
        if not isinstance(name, str):
            raise TypeError("Person: name must be a string")
        self.name = name

        self.birth_date = parse(str(birth_date))

        self.retirement_age = parse(str(retirement_date), self.birth_date)

    def age(self, date) -> int:
        """ Returns the age of the `Person` as of `date`.

        `date` may be a `datetime` object or a numeric value indicating
        a year (e.g. 2001). In the latter case, the age at the *end* of
        `year` is returned.

        Args:
            date (datetime): The date at which the person's age is to
                be determined.
        """
        if isinstance(date, Number):
            age_ = date - self.birth_date.year
        else:
            if not isinstance(date, datetime):
                raise TypeError("Person: date must be a datetime")
            age_ = date.year - self.birth_date.year

        if age_ < 0:
            raise ValueError("Person: date must be no earlier than birth_date")
        return age_

    def retirement_age(self) -> datetime:
        """ Returns the age at which the `Person` will retire.

        Returns None if the person's age is unknown. """
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
        """ The balance of the `Account` object """
        return self._balance

    @balance.setter
    def set_balance(self, balance) -> None:
        """ Sets the current balance """
        self._balance = Money(balance)

    @property
    def rate(self) -> Decimal:
        """ The rate (interest rate, rate of return, etc.) of the account """
        return self._rate

    @rate.setter
    def set_rate(self, rate) -> None:
        """ Sets the rate """
        if not isinstance(rate, Number):
            raise TypeError("Money: rate must be numeric")
        self._rate = rate

    @property
    def inflow(self) -> Money:
        """ The inflow to the `Account` object """
        return self._inflow

    @inflow.setter
    def set_inflow(self, inflow) -> None:
        """ Sets the inflow, which must be convertible to type `Money` """
        self._inflow = Money(inflow)

    @property
    def outflow(self) -> Money:
        """ The outflow to the `Account` object """
        return self._outflow

    @outflow.setter
    def set_outflow(self, outflow) -> None:
        """ Sets the outflow, which must be convertible to type `Money` """
        self._outflow = Money(outflow)

    @property
    def inflow_inclusion(self) -> Decimal:
        """ The inclusion rate for inflow amounts when applying the rate """
        return self._inflow_inclusion

    @inflow_inclusion.setter
    def set_inflow_inclusion(self, inflow_inclusion) -> None:
        """ Sets the inclusion rate for inflows, which must be numeric and in [0,1] """
        if not isinstance(inflow_inclusion, Number) and not inflow_inclusion is None:
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
        """ Sets the inclusion rate for outflows, which must be numeric and in [0,1] """
        if not isinstance(outflow_inclusion, Number) and \
           outflow_inclusion is not None:
            raise TypeError("Money: outflow_inclusion must be numeric")
        if not (outflow_inclusion >= 0 and outflow_inclusion <= 1):
            raise ValueError("Money: outflow_inclusion must be in [0,1]")
        self._outflow_inclusion = outflow_inclusion

    def next_year(self) -> Account:
        """ Returns an `Account` object where any contribution,
        withdrawal, and rate have been applied to the balance. Only
        `inclusion_rate`% of `contribution` are affected by `rate`.
        The returned object has only its balance set. """

        balance = self._balance.nominal_value * (1 + self._rate)

        if self._inflow is not None:
            balance += self._inflow.nominal_value
            if self._inflow_inclusion is not None:
                balance += self._inflow.nominal_value() * self._rate * self._inflow_inclusion

        if self._outflow is not None:
            balance -= self._outflow.nominal_value
            if self._outflow_inclusion is not None:
                balance -= self._outflow.nominal_value() * self._rate * self._outflow_inclusion

        return type(self)(balance)


class SavingsAccount(Account):
    """ A savings account. Supports contributions and withdrawals.
    
    Provides a `taxable_income` method """

    # Define aliases for `Savings Account` methods.
    contribution = property(Account.inflow, Account.set_inflow, None,
                            "A contribution to the `Account` object.")

    withdrawal = property(Account.outflow, Account.set_outflow, None,
                          "A withdrawal from the `Account` object.")
    
    contribution_inclusion = property(Account.inflow_inclusion,
                                      Account.set_inflow_inclusion,
                                      None,
                                      "Sets inclusion rate for contributions.")
    
    withdrawal_inclusion = property(Account.outflow_inclusion, Account.set_outflow_inclusion, None,
        "Sets the inclusion rate for withdrawals, which must be numeric and in [0,1].")

    # TODO: add a `taxable_income` method


class RRSP(SavingsAccount):
    # TODO: implement class
    pass


class TFSA(SavingsAccount):
    # TODO: implement class
    pass


class TaxableAccount(SavingsAccount):
    # TODO: implement class
    pass


class Debt(Account):
    # TODO: implement class
    pass


class OtherProperty(Account):
    # TODO: implement class
    pass
