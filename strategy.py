""" This module provides the `Strategy` class and subclasses, which
define contribution and withdrawal strategies and associated flags. """

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from ledger import Money


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


class ContributionStrategy(object):
    """ A callable class that determines an annual contribution.

    Attributes:
        strategy (str): A string corresponding to a particular
            contribution strategy. See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function of the form:
                func(TODO) -> Money
            Acceptable keys include: TODO
        rate (Decimal): A user-supplied contribution rate. Has different
            meanings for different strategies; may be a percentage (e.g.
            Decimal('0.03') means 3%) or a currency value (e.g. 3000 for
            a $3000 contribution).
        timing (Decimal, str): The contribution is modelled as a lump
            sum which takes place at this time. Expressed according to
            the `when` convention described in `ledger.Account`.
        inflation_adjusted (bool): If True, `rate` is interpreted as a
            real (i.e. inflation-adjusted) currency value, unless the
            current strategy interprets it as a percentage.
            Optional. Defaults to True.

    Args:
        TODO (same args are `strategies` funcs above)

    Returns:
        A Money object corresponding to the gross contribution amount
        for the family for the year.
    """

    def _strategy_constant(self):
        """ Contribute a constant amount (in real terms) each year. """
        # TODO: Inflation-adjust the return value. This will require
        # receiving an arg that defines an inflation adjustment factor
        # (e.g. a scenario object with a real_value method and a year
        # object with an (int) year attribute)
        return Money(self.rate)

    strategies = {
        "Constant contribution": _strategy_constant
    }

    def __init__(self):  # TODO
        pass

    def gross_contribution(self, *args, **kwargs):
        """ The total amount contributed this year, before reductions.

        This method takes the same arguments as the `strategies`
        functions. See documentation for class ContributionStrategy.

        Returns:
            A Money object corresponding to the gross contribution
            amount for the family for the year.
        """
        # TODO: Explicitly define positional arguments
        return self.strategies[self.strategy](*args, **kwargs)

    def contribution_by_account(self, contribution, accounts):  # TODO
        """ Determines how much to contribute to each account.

         Contributions are determined based on the types of accounts.
         If two objects share a type (e.g. if there are two RRSP
         objects) then the total contribution to that type of account
         is split evenly between them.

        Args:
            contribution (Money): The total amount to be contributed
                (net of any reductions) to the various Account objects
                in `accounts`.
            accounts (list): A list of objects of type Account or its
                subclasses.

        Returns:
            A dict of {Account, Money} pairs, where each account in
            `accounts` is a key and the corresponding Money value is
            the amount of the contribution to that account.
        """
        # TODO: Consider building a list of classes in `accounts` (with
        # unique elements, so if there are two RRSPs `RRSP` appears just
        # once) and sorting based on priority. Check to see if there are
        # more accounts than classes; if so, then divvy up contributions
        # between accounts of the same type.
        pass

    def __call__(self, *args, **kwargs):
        """ Returns the gross contribution for the year. """
        return self.gross_contribution(*args, **kwargs)


class Strategy(object):
    """ Describes a person's (or family's) financial behaviour.

    A strategy describes one or two people. If two people are given,
    they are assumed to be spouses; if you don't want this treatment
    (which is entirely driven by tax planning considerations), build
    separate projections for the two.

    Relevant financial information includes: The age, planned retirement
    age, and life expectancy of the people; the rate at which the people
    save (which may be based on income and/or spending rates, the rate
    at which the people intend to draw from their savings in retirement,
    and the way that the people manage their savings over their lives.

    Attributes:
        person1 (Person): A person being described by the Strategy
            object.
        person2 (Person): The spouse of person1. Optional.
        contribution_strategy (TODO):
        contribution_rate (Decimal): TODO
        contribution_timing (Decimal, str): TODO
        allocation_model (TODO)
        adjust_allocation_for_early_retirement (bool): TODO
        refund_reinvestment_rate (Decimal): TODO
        withdrawal_strategy (TODO)
        withdrawal_rate (Decimal, Money): TODO
        withdrawal_timing (Decimal, str): TODO
    """

    # TODO: Make this class hierarchy flat (as is the Python way)
    # TODO: Implement __init__ function that allows for the form
    # `Strategy(settings=settings)` (see e.g. Scenario).
    # TODO: Represent person1 and person2 as attributes of this class.
    # Consider whether to move the Person class from ledger.py to here
    # TODO: For *_strategy and *_model attributes, consider defining a
    # dict of {str, function} pairs internal to the class. The user can
    # provide a string and the object is initialized to point to the
    # associated function. (TODO: Define a common function signature.)
    # TODO: Reduce contribution attributes to a single contribution
    # strategy object which contains the contribution rate and timing.
    # Do the same for investment strategy and withdrawal strategy.

    class ContributionStrategy:
        """ Defines a contribution strategy.

        Provides methods to determine the total contribution
        (gross and net of contribution reductions) for a given year. """
        @staticmethod
        def get_contribution_rate_strategies():
            """ Returns functions defining contribution strategies.

            Returns:
                A dict of contribution rate strategy descriptions (keys)
                and functions defining each corresponding contribution
                strategy (values).

                The functions are of the form `func(Money:value,
                Year:last_year, Year:this_year) -> Money`.
                `this_year` need not be fully initialized, but must
                provide at least gross and net income. """
            return 1  # TODO: complete function

    def __init__(self, retirement_age=None, contribution_strategy=None,
                 withdrawal_strategy=None):
        """ Constructor for `Strategy`. """
        self.__retirement_age = retirement_age
        if contribution_strategy is None:
            self.__contribution_strategy = self.ContributionStrategy()
        else:
            self.__contribution_strategy = contribution_strategy
