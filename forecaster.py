''' This module provides classes for creating and managing Forecasts. '''

from forecast import Forecast
from ledger import Person, Account, Debt
from tax import Tax
from strategy import ContributionStrategy, WithdrawalStrategy, \
    TransactionStrategy, AllocationStrategy, DebtPaymentStrategy
from scenario import Scenario
from constants import Constants
from settings import Settings
from utility import *


class Forecaster(object):
    ''' A multi-year forecast of personal account balances and income.

    Each instance constructs several `Year` objects and can produce
    summary information describing those years (e.g. statistics/charts).
    It receives Scenario information (describing economic conditions)
    and Strategy information (describing the user's savings and
    withdrawal strategies).
    '''

    def __init__(self, settings=Settings, initial_year=None):
        """ """
        # TODO: Determine function signature.
        # We need to be able to build several accounts, perhaps several
        # of the same type (e.g. an RRSP for each Person) without having
        # an instantiated account passed as an arg.
        self.person1 = None  # Special person defined by settings
        self.person2 = None  # Special person defined by settings
        self.people = set()
        self.assets = set()
        self.debts = set()
        self.contribution_strategy = None
        self.withdrawal_strategy = None
        self.transaction_in_strategy = None
        self.transaction_out_strategy = None
        self.allocation_strategy = None
        self.debt_payment_strategy = None
        self.scenario = None
        self.settings = settings
        self.initial_year = initial_year if initial_year is not None \
            else settings.initial_year

    def run_forecast(self, scenario=None):
        """ TODO """
        # For each `None` attribute, build it dynamically from
        # self.settings.
        # Consider how to accomodate the `scenario` arg - some objects
        # (like allocation_strategy) might be tied to a particular
        # scenario.
        # IDEA: Instead of building Person/Account/etc objects, store
        # args for building them instead? This way, we can generate
        # multiple forecasts and re-use Forecaster's internal data.
        pass

    @staticmethod
    def set_kwarg(kwargs, arg, val, default) -> None:
        """ Adds a keyword arg to a dict based on an input hierarchy.

        Adds `arg` to the dict `kwargs` with value `val` (usually an
        explicit argument to the calling method) or, if that's `None`,
        `default` (usually a value from a Settings object).

        If both of these values are None, or if `arg` is already in
        `kwargs`, no value is added to `kwargs`.
        This avoids overriding the relevant parameter defaults or
        overriding args set by subclasses.

        Args:
            kwargs (dict[str, *]): A dict of keyword args to be passed
                to an `__init__` method when initializing a Person,
                Account, or other Forecast input object.
            arg (str): The keyword arg being added to `kwargs`.
            val (*): An explicitly-passed value for `arg`. May be None.
            default (*): A value from a Settings object
                corresponding to `arg`. May be None.
        """
        # If the arg is already in kwargs, don't do anything:
        if arg in kwargs:
            return
        # If the arg was already set explicitly, add it to the dict:
        if val is not None:
            kwargs[arg] = val
        # If the arg isn't set explicitly, use the default value:
        elif default is not None:
            kwargs[arg] = default
        # If there's no explicit val and no default, don't add anything.

    def add_person(
        self, name=None, birth_date=None,
        retirement_date=None, gross_income=None, raise_rate=None, spouse=None,
        tax_treatment=None, allocation_strategy=None, inputs={},
        PersonType=Person, **kwargs
    ) -> Person:
        """ Adds a Person to the forecast.

        If `name` matches `person1_name` or `person2_name` in `settings`
        then the default values for that person will be used, otherwise
        no defaults will be used (be sure to provide any mandatory
        arguments!)

        Subclasses of Forecaster that build subclasses of Person can
        make use of this method by passing in a suitable `PersonType`
        argument along with any `kwargs` specific to that `PersonType`.

        See `Person` for documentation on additional args.

        Args:
            inputs (dict[str, dict[int, *]]): `{arg: {year: val}}`
                pairs, where `arg` is the name of a @recorded_property
                of `Person` and `val` is the value of that property for
                `year`.
            PersonType (type): The class of `Person` being built by the
                method. This class's `__init__` method must accept all
                of the args of `Person`.

        Returns:
            `Person`: An object of type `PersonType` constructed with
            the relevant args, inputs, settings, and default values.
        """
        # NOTE: We don't actually need to list Person's various args
        # in the call signature here; we could just use `inputs`,
        # `PersonType` and `**kwargs`. Doing it that way would be less
        # brittle, but not as convenient for Intellisense.

        # If name isn't provided, default to person1 from settings:
        self.set_kwarg(
            kwargs, 'name', name, self.settings.person1_name)
        # For arguments with Settings default values, check whether
        # we're initialing person1, person2, or someone else:
        if kwargs['name'] == self.settings.person1_name:
            birth_date_default = self.settings.person1_birth_date
            retirement_date_default = self.settings.person1_retirement_date
            raise_rate_default = self.settings.person1_raise_rate
        elif kwargs['name'] == self.settings.person2_name:
            birth_date_default = self.settings.person2_birth_date
            retirement_date_default = self.settings.person2_retirement_date
            raise_rate_default = self.settings.person2_raise_rate
        else:  # If someone else, use Person default values:
            birth_date_default = None
            retirement_date_default = None
            raise_rate_default = None
        self.set_kwarg(
            kwargs, 'birth_date', birth_date, birth_date_default)
        self.set_kwarg(
            kwargs, 'retirement_date', retirement_date,
            retirement_date_default)
        self.set_kwarg(
            kwargs, 'raise_rate', raise_rate, raise_rate_default)
        # Set values that have no Settings default:
        self.set_kwarg(kwargs, 'gross_income', gross_income, None)
        self.set_kwarg(kwargs, 'spouse', spouse, None)
        self.set_kwarg(kwargs, 'tax_treatment', tax_treatment, None)
        self.set_kwarg(kwargs, 'allocation_strategy', allocation_strategy,
                       None)

        # Construct a person with the keyword arguments we've assembled:
        person = PersonType(
            inputs=inputs, initial_year=self.initial_year, **kwargs)
        self.people.add(person)
        if person.name == self.settings.person1_name:
            self.person1 = person
        elif person.name == self.settings.person2_name:
            self.person2 = person
        # Return the Person so that subclass methods can do
        # post-processing (if they need to)
        return person

    def add_account(
        self, owner=None, balance=0, rate=None, transactions={}, nper=1,
        default_inflow_timing=None, default_outflow_timing=None,
        inputs={}, AccountType=Account, **kwargs
    ):
        """ Adds an Account to the forecast.

        Subclasses of Forecaster that build subclasses of Account can
        make use of this method by passing in a suitable `AccountType`
        argument along with any `kwargs` specific to that `AccountType`.

        See `Account` for documentation on additional args.

        Args:
            inputs (dict[str, dict[int, *]]): `{arg: {year: val}}`
                pairs, where `arg` is the name of a @recorded_property
                of `Account` and `val` is the value of that property for
                `year`.
            AccountType (type): The class of `Account` being built by
                the method. This class's `__init__` method must accept
                all of the args of `Account`.

        Returns:
            `Account`: An object of type `AccountType` constructed with
            the relevant args, inputs, settings, and default values.
        """
        # NOTE: We don't actually need to list Account's various args
        # in the call signature here; we could just use `inputs`,
        # `AccountType` and `**kwargs`. Doing it that way would be less
        # brittle, but not as convenient for Intellisense.

        self.set_kwarg(kwargs, 'owner', owner, self.person1)
        self.set_kwarg(kwargs, 'balance', balance, None)
        self.set_kwarg(kwargs, 'rate', rate, None)
        self.set_kwarg(kwargs, 'transactions', transactions, None)
        self.set_kwarg(kwargs, 'nper', nper, None)
        self.set_kwarg(kwargs, 'default_inflow_timing',
                       default_inflow_timing, None)
        self.set_kwarg(kwargs, 'default_outflow_timing',
                       default_outflow_timing, None)
        account = AccountType(
            inputs=inputs, initial_year=self.initial_year, **kwargs)
        self.assets.add(account)
        return account

    def add_debt(
        self, minimum_payment=Money(0), reduction_rate=1,
        accelerate_payment=False, inputs={}, AccountType=Debt, **kwargs
    ):
        """ Adds a Debt to the forecast.

        Subclasses of Forecaster that build subclasses of Account can
        make use of this method by passing in a suitable `AccountType`
        argument along with any `kwargs` specific to that `AccountType`.

        See `Debt` and `Forecaster.addAccount` for documentation on
        additional args.

        Args:
            inputs (dict[str, dict[int, *]]): `{arg: {year: val}}`
                pairs, where `arg` is the name of a @recorded_property
                of `Debt` and `val` is the value of that property for
                `year`.
            AccountType (type): The class of `Debt` being built by
                the method. This class's `__init__` method must accept
                all of the args of `Debt`.

        Returns:
            `Debt`: An object of type `AccountType` constructed with
            the relevant args, inputs, settings, and default values.
        """
        self.set_kwarg(kwargs, 'minimum_payment', minimum_payment, None)
        self.set_kwarg(kwargs, 'reduction_rate', reduction_rate,
                       self.settings.debt_reduction_rate)
        self.set_kwarg(kwargs, 'accelerate_payment', accelerate_payment,
                       self.settings.debt_accelerate_payment)
        account = self.addAccount(
            AccountType=Debt, inputs=inputs, **kwargs)
        self.assets.add(account)
        return account

    def add_contribution_strategy(self):
        # TODO
        pass

    def add_withdrawal_strategy(self):
        # TODO
        pass

    def add_transaction_in_strategy(self):
        # TODO
        pass

    def add_transaction_out_strategy(self):
        # TODO
        pass

    def add_allocation_strategy(self):
        # TODO
        pass

    def add_debt_payment_strategy(self):
        # TODO
        pass
