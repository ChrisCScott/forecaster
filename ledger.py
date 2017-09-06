""" Defines basic recordkeeping classes, such as `Money`, `Person`, and `Account` """

from datetime import datetime
from numbers import Number
from money import Money


class Person(object):
    """ Represents a person's basic information: age and retirement age.

    Attributes:
        name: A string corresponding to the person's name.
        birth_date: A datetime corresponding to the person's date of birth.
        retirement_date: An optional datetime corresponding to the person's retirement date.
    """

    # TODO: Add life expectancy?
    def __init__(self, name, birth_date, retirement_date=None):
        """ Constructor for `Person`.

        Args:
            name (string): The person's name.
            birth_date (datetime): The person's date of birth.
            retirement_date (datetime): The person's retirement date. Optional.
                May be passed as a non-datetime numeric value indicating the retirement year.
        """
        if not isinstance(name, str):
            raise TypeError("Person: name must be a string")
        self.name = name

        if not isinstance(birth_date, datetime):
            raise TypeError("Person: birth_date must be a datetime")
        self.birth_date = birth_date

        if retirement_date is None:
            self.retirement_date = None
        elif isinstance(retirement_date, Number):
            self.retirement_date = datetime(birth_date.year + int(retirement_date),
                                            birth_date.month,
                                            birth_date.day)
        else:
            if not isinstance(retirement_date, datetime):
                raise TypeError("Person: retirement_date must be a datetime")
            self.retirement_date = retirement_date

    def age(self, date):
        """ Returns the age of the `Person` as of `date`.

        `date` may be a `datetime` object or a numeric value indicating a year (e.g. 2001).
        In the latter case, the age at the *end* of `year` is returned.

        Args:
            date (datetime):
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

    def retirement_age(self):
        """ If `retirement_date` is known, return the age of the `Person` at retirement """
        if self.retirement_date is None:
            return None
        else:
            age = self.retirement_date.year - self.birth_date.year
            if self.birth_date.replace(self.retirement_date.year) < self.retirement_date:
                age += 1
            return age


class Account:
    ''' An account having a balance, an interest rate, and contributions and/or withdrawals.
    Call `next_year()` to generate a new `Account` object with an updated balance.
    All `Money` elements of the new object will have their `year` incremented. '''

    def __init__(self, balance, rate=None, inflow=None, outflow=None,
                 inflow_inclusion=None, outflow_inclusion=None):
        ''' Constructor for `Account`. Receives `balance` and stores it as type `Money`.
        Optionally receives a `rate` of return/loss/interest/etc. (of a numeric type).
        For example, a 5% interest rate could be passed as `rate=0.05`.

        Inflows and outflows to the account may be modelled independently. They may optionally
        be included in the returns/losses (arising from `rate`) based on corresponding
        `*_inclusion` arguments. This allows the `Account` object to model different timing
        strategies for inflows and outflows. '''
        self._balance = balance
        self._rate = rate
        self._inflow = inflow
        self._outflow = outflow
        self._inflow_inclusion = inflow_inclusion
        self._outflow_inclusion = outflow_inclusion

    @property
    def balance(self):
        ''' The balance of the `Account` object '''
        return self._balance

    @balance.setter
    def set_balance(self, balance):
        ''' Sets the current balance, which must be convertible to type `Money` '''
        self._balance = Money(balance)

    @property
    def rate(self):
        ''' The rate (interest rate, rate of return, etc.) of the `Account` object '''
        return self._rate

    @rate.setter
    def set_rate(self, rate):
        ''' Sets the rate, which must be numeric '''
        if not isinstance(rate, Number):
            raise TypeError("Money: rate must be numeric")
        self._rate = rate

    @property
    def inflow(self):
        ''' The inflow to the `Account` object '''
        return self._inflow

    @inflow.setter
    def set_inflow(self, inflow):
        ''' Sets the inflow, which must be convertible to type `Money` '''
        self._inflow = Money(inflow)

    @property
    def outflow(self):
        ''' The outflow to the `Account` object '''
        return self._outflow

    @outflow.setter
    def set_outflow(self, outflow):
        ''' Sets the outflow, which must be convertible to type `Money` '''
        self._outflow = Money(outflow)

    @property
    def inflow_inclusion(self):
        ''' The inclusion rate for inflow amounts when applying the rate '''
        return self._inflow_inclusion

    @inflow_inclusion.setter
    def set_inflow_inclusion(self, inflow_inclusion):
        ''' Sets the inclusion rate for inflows, which must be numeric and in [0,1] '''
        if not isinstance(inflow_inclusion, Number) and not inflow_inclusion is None:
            raise TypeError("Money: inflow_inclusion must be numeric")
        if not (inflow_inclusion >= 0 and inflow_inclusion <= 1):
            raise ValueError("Money: inflow_inclusion must be in [0,1]")
        self._inflow_inclusion = inflow_inclusion

    @property
    def outflow_inclusion(self):
        ''' The inclusion rate for outflow amounts '''
        return self._outflow_inclusion

    @outflow_inclusion.setter
    def set_outflow_inclusion(self, outflow_inclusion):
        ''' Sets the inclusion rate for outflows, which must be numeric and in [0,1] '''
        if not isinstance(outflow_inclusion, Number) and not outflow_inclusion is None:
            raise TypeError("Money: outflow_inclusion must be numeric")
        if not (outflow_inclusion >= 0 and outflow_inclusion <= 1):
            raise ValueError("Money: outflow_inclusion must be in [0,1]")
        self._outflow_inclusion = outflow_inclusion

    def next_year(self):
        ''' Returns an `Account` object where any contribution, withdrawal, and rate have been
        applied to the balance. Only `inclusion_rate`% of `contribution` are affected by `rate`.
        The returned object has only its balance set. '''

        balance = self._balance.nominal_value * (1 + self._rate)

        if not self._inflow is None:
            balance += self._inflow.nominal_value
            if not self._inflow_inclusion is None:
                balance += self._inflow.nominal_value() * self._rate * self._inflow_inclusion

        if not self._outflow is None:
            balance -= self._outflow.nominal_value
            if not self._outflow_inclusion is None:
                balance -= self._outflow.nominal_value() * self._rate * self._outflow_inclusion

        return type(self)(balance)


class SavingsAccount(Account):
    ''' A savings account. Supports contributions and withdrawals. Provides a `taxable_income()`
    method; subclasses override this to model specific tax treatment for different account types '''

    def contribution(self):
        ''' Returns the contribution to the savings account. This is an alias of `Account.inflow()` '''
        return self.inflow()

    def set_contribution(self, contribution):
        ''' Sets the contribution. `contribution` must be of type `Money`. This is an alias of `Account.inflow()` '''
        self.set_inflow(contribution)

    def withdrawal(self):
        ''' Returns the withdrawal from the savings account. This is an alias of `Account.inflow()` '''
        return self.outflow()

    def set_withdrawal(self, withdrawal):
        ''' Sets the withdrawal. `withdrawal` must be of type `Money`. This is an alias of `Account.inflow()` '''
        self.set_outflow(withdrawal)

        # TODO: add more alias methods (i.e. `*_inclusion`-related methods) and `taxable_income` method


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
