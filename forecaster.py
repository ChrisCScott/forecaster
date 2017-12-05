''' This module provides classes for creating and managing Forecasts. '''

from copy import copy, deepcopy
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
    """ A convenience class for building Forecasts based on settings.

    `Forecaster` takes in information for building a `Forecast`
    (explicitly, via a `Settings` object, or via a combination of the
    two) and builds one or more `Forecast`s from that information.

    One of the purposes of this class is to enable building Forecast
    objects solely from a `Settings` object and a set of `inputs` dicts.
    Objects of this class can be initialized with any of the parameters
    that can be provided to `Forecast` (as well as a `Settings` object).
    Any parameters that are not provided at init time can be built
    afterward via an `add_*` method. Each `add_*` method takes the
    parameters of the corresponding object being built; e.g.
    `add_person` takes the same parameters as `Person.__init__` (plus
    a `PersonType` parameter -- see documentation for `add_person`).

    This behaviour can be particularly useful for `Ledger` objects like
    `Person` or `Account`, which may have per-object historical
    data that can't be inferred from a Settings object (represented by
    an `inputs` dict for each such object).

    `Forecasts` may be generated based on varying `Scenario`s (while
    retaining the same `Strategy`s, `Person`s, and `Account`s) to allow
    for comparison of an overarching strategy between various future
    economic performance scenarios (e.g. as in Monte Carlo analysis).
    """

    def __init__(
        self, person1=None, person2=None, people=set(), assets=set(),
        debts=set(), scenario=None, contribution_strategy=None,
        withdrawal_strategy=None, contribution_transaction_strategy=None,
        withdrawal_transaction_strategy=None, allocation_strategy=None,
        debt_payment_strategy=None, tax_treatment=None, initial_year=None,
        settings=Settings
    ):
        """ Inits an instance of `Forecaster`.

        This method can receive any of the parameters that can be
        provided to `Forecast`. Any parameters that are not provided at
        init time can be provided afterward via an `add_*` method.

        This method automatically builds `Scenario` and `Strategy`
        objects from `Settings`, but not any `Ledger` (i.e. `Person`,
        `Debt`, or `Account`) or `Tax` objects, which must be added by
        the corresponding `add_*` method individually.

        Args:
            settings (Settings): An object with settings values for the
                `Forecaster` to pass to various `Account`, `Person`,
                `Strategy`, and `Scenario` objects when explicit arguments
                are not given.
            initial_year (int): The initial year for the forecast.
        """
        # TODO: Determine function signature.
        # We need to be able to build several accounts, perhaps several
        # of the same type (e.g. an RRSP for each Person) without having
        # an instantiated account passed as an arg.

        # NOTE: Settings defines two named persons, so store them via
        # their own named attributes (as well as in the `people` dict).
        # TODO: Make person* properties that update `people` when set
        # (or add add_person1 and add_person2 methods)?
        self.person1 = person1
        self.person2 = person1
        self.people = people
        # Ensure that person1/person2 are in the `people` set:
        if self.person1 is not None:
            self.people.add(self.person1)
        if self.person2 is not None:
            self.people.add(self.person2)
        self.assets = assets
        self.debts = debts
        self.contribution_strategy = contribution_strategy
        self.withdrawal_strategy = withdrawal_strategy
        self.transaction_in_strategy = contribution_transaction_strategy
        self.transaction_out_strategy = withdrawal_transaction_strategy
        self.allocation_strategy = allocation_strategy
        self.debt_payment_strategy = debt_payment_strategy
        self.scenario = scenario
        self.tax_treatment = tax_treatment
        self.settings = settings

        # Build any not-provided attributes based on Settings:
        # Everything takes `initial_year`, so set that first.
        self.initial_year = initial_year if initial_year is not None \
            else self.settings.initial_year
        # Scenario has no dependencies on other classes, so build it
        # first:
        if self.scenario is None:
            self.set_scenario()
        # Strategies can depend on Scenario, but not on Person/Accounts,
        # so build them next:
        if self.contribution_strategy is None:
            self.set_contribution_strategy()
        if self.withdrawal_strategy is None:
            self.set_withdrawal_strategy()
        if self.transaction_in_strategy is None:
            self.set_transaction_in_strategy()
        if self.transaction_out_strategy is None:
            self.set_transaction_out_strategy()
        if self.allocation_strategy is None:
            self.set_allocation_strategy()
        # Finally, set `Person` objects.
        if self.person1 is None:
            self.set_person1()
        if self.person2 is None:
            self.set_person2()
        # Accounts will need to be set manually.

    def forecast(self, scenario=None):
        """ TODO """
        # For each `None` attribute, build it dynamically from
        # self.settings.
        # Consider how to accomodate the `scenario` arg - some objects
        # (like allocation_strategy) might be tied to a particular
        # scenario.
        # IDEA: Instead of building Person/Account/etc objects, store
        # args for building them instead? This way, we can generate
        # multiple forecasts and re-use Forecaster's internal data.

        # `Scenario` doesn't depend on any other object and is used to
        # build several others, so build it first.
        # Scenario is not mutable, so no need to make a copy.
        scenario = scenario if scenario is not None else self.scenario
        # Person and Account objects are mutated by `Forecast`, so copy
        # them to preserve initial state for additional `Forecast`s
        # TODO: implement __deepcopy__ member for Ledger that shallow-
        # copies `inputs` (and other non-mutable attributes) but does
        # deep-copy *_history dicts.
        people = {deepcopy(person) for person in self.people}
        assets = {deepcopy(asset) for asset in self.assets}
        debts = {deepcopy(debt) for debt in self.debts}
        # Strategies are not mutated by `Forecast`, but if `Scenario` is
        # replaced by this method then we need to mutuate them here to
        # adjust their inflation_adjust attributes. A shallow copy
        # should be sufficient.
        contribution_strategy = copy(self.contribution_strategy)
        withdrawal_strategy = copy(self.withdrawal_strategy)
        transaction_in_strategy = copy(self.transaction_in_strategy)
        transaction_out_strategy = copy(self.transaction_out_strategy)
        debt_payment_strategy = copy(self.debt_payment_strategy)
        # allocation_strategy is copied as an attribute of `Person`

        if scenario != self.scenario:
            # TODO: Implement a `change_scenario` method for each Ledger
            # or other Scenario-related class and put the relevant logic
            # there (e.g. AllocationStrategy's logic involves updating
            # its `scenario` attribute, whereas ledger_Canada classes
            # involve updating their `inflation_adjust` attributes.
            # Then simplify this to just testing each object for a
            # `change_scenario` attribute and calling it.
            for person in people:
                self.replace_scenario(person.allocation_strategy, scenario)
            for account in assets.union(debts):
                self.replace_scenario(account, scenario)
            self.replace_scenario(contribution_strategy, scenario)
            self.replace_scenario(withdrawal_strategy, scenario)
            self.replace_scenario(transaction_in_strategy, scenario)
            self.replace_scenario(transaction_out_strategy, scenario)
            self.replace_scenario(debt_payment_strategy, scenario)

        # NOTE: We use the tax treatment of person1; this behaviour
        # should likely be revisited, since in the multi-person/multi-
        # jurisdiction case we're probably not dealing with person2's
        # tax treatment correctly.
        return Forecast(
            people=people, assets=assets, debts=debts, scenario=scenario,
            contribution_strategy=contribution_strategy,
            withdrawal_strategy=withdrawal_strategy,
            contribution_transaction_strategy=transaction_in_strategy,
            withdrawal_transaction_strategy=transaction_out_strategy,
            allocation_strategy=allocation_strategy,
            debt_payment_strategy=debt_payment_strategy,
            tax_treatment=self.person1.tax_treatment)

    def replace_scenario(self, obj, scenario):
        """ TODO """
        # We only replace attributes which have been set to a non-None
        # value, since a None value means that there's no Scenario to
        # replace (and can mean that the object is intentionally not
        # inflation-adjusted/etc.)
        if hasattr(obj, 'scenario') and obj.scenario is not None:
            obj.inflation_adjust = scenario
        if (
            hasattr(obj, 'inflation_adjust') and
            obj.inflation_adjust is not None
        ):
            obj.inflation_adjust = scenario.inflation_adjust

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
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, allocation_strategy=None,
        inputs=None, PersonType=Person, **kwargs
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
        # brittle, but not as convenient for Intellisense or for future
        # folks looking to extend the code to incorporate additional
        # settings defaults.

        # There are no settings defaults for persons other than person1
        # and person2.
        self.set_kwarg(kwargs, 'name', name, None)
        if kwargs['name'] is None:
            return None
        self.set_kwarg(kwargs, 'birth_date', birth_date, None)
        self.set_kwarg(kwargs, 'retirement_date', retirement_date, None)
        self.set_kwarg(kwargs, 'raise_rate', raise_rate, None)
        self.set_kwarg(kwargs, 'gross_income', gross_income, None)
        self.set_kwarg(kwargs, 'spouse', spouse, None)
        self.set_kwarg(kwargs, 'tax_treatment', tax_treatment,
                       self.tax_treatment)
        self.set_kwarg(kwargs, 'allocation_strategy', allocation_strategy,
                       self.allocation_strategy)
        self.set_kwarg(kwargs, 'inputs', inputs, None)

        # Construct a person with the keyword arguments we've assembled:
        person = PersonType(initial_year=self.initial_year, **kwargs)
        self.people.add(person)
        # Return the Person so that subclass methods can do
        # post-processing (if they need to)
        return person

    def set_person1(
        self, name=None, birth_date=None,
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, allocation_strategy=None,
        inputs=None, PersonType=Person, **kwargs
    ):
        """ Adds a person to the forecast based on person1's settings.

        See `add_person` for documentation on the args and return type
        of this method.
        """
        # Remember to remove any previously-instantiated person1
        if self.person1 is not None:
            self.people.remove(self.person1)
        self.set_kwarg(kwargs, 'name', name, self.settings.person1_birth_date)
        # `Settings` defines a non-person by setting `name` to None
        if kwargs['name'] is None:
            return None
        self.set_kwarg(kwargs, 'birth_date', birth_date,
                       self.settings.person1_birth_date)
        self.set_kwarg(kwargs, 'retirement_date', retirement_date,
                       self.settings.person1_retirement_date)
        self.set_kwarg(kwargs, 'gross_income', gross_income,
                       self.settings.person1_gross_income)
        self.set_kwarg(kwargs, 'raise_rate', raise_rate,
                       self.settings.person1_raise_rate)
        # There are no special person1-specific defaults for the
        # remaining attributes (except that we assume that the spouse of
        # person1 is person2)
        self.set_kwarg(kwargs, 'gross_income', gross_income, None)
        self.set_kwarg(kwargs, 'spouse', spouse, self.person2)
        self.set_kwarg(kwargs, 'tax_treatment', tax_treatment,
                       self.tax_treatment)
        self.set_kwarg(kwargs, 'allocation_strategy', allocation_strategy,
                       None)
        self.set_kwarg(kwargs, 'inputs', inputs, None)

        self.person1 = self.add_person(PersonType=PersonType, **kwargs)
        return self.person1

    def set_person2(
        self, name=None, birth_date=None,
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, allocation_strategy=None,
        inputs=None, PersonType=Person, **kwargs
    ):
        """ Adds a person to the forecast based on person2's settings.

        See `add_person` for documentation on the args and return type
        of this method.
        """
        # Remember to remove any previously-instantiated person2
        if self.person2 is not None:
            self.people.remove(self.person2)
        self.set_kwarg(kwargs, 'name', name, self.settings.person2_birth_date)
        # `Settings` defines a non-person by setting `name` to None,
        # which set_args interprets as not being set at all.
        if 'name' not in kwargs:
            return None
        self.set_kwarg(kwargs, 'birth_date', birth_date,
                       self.settings.person2_birth_date)
        self.set_kwarg(kwargs, 'retirement_date', retirement_date,
                       self.settings.person2_retirement_date)
        self.set_kwarg(kwargs, 'gross_income', gross_income,
                       self.settings.person2_gross_income)
        self.set_kwarg(kwargs, 'raise_rate', raise_rate,
                       self.settings.person2_raise_rate)
        # There are no special person2-specific defaults for the
        # remaining attributes (except that we assume that the spouse
        # of person2 is person1)
        self.set_kwarg(kwargs, 'gross_income', gross_income, None)
        self.set_kwarg(kwargs, 'spouse', spouse, self.person1)
        self.set_kwarg(kwargs, 'tax_treatment', tax_treatment,
                       self.tax_treatment)
        self.set_kwarg(kwargs, 'allocation_strategy', allocation_strategy,
                       None)
        self.set_kwarg(kwargs, 'inputs', inputs, None)

        self.person2 = self.add_person(PersonType=PersonType, **kwargs)
        return self.person2

    def add_account(
        self, owner=None, balance=None, rate=None, transactions=None,
        nper=None, default_inflow_timing=None, default_outflow_timing=None,
        inputs=None, AccountType=Account, **kwargs
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
        self.set_kwarg(kwargs, 'inputs', inputs, None)

        account = AccountType(initial_year=self.initial_year, **kwargs)
        self.assets.add(account)
        return account

    def add_debt(
        self, minimum_payment=None, reduction_rate=None,
        accelerate_payment=None, AccountType=Debt, **kwargs
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

        account = self.addAccount(AccountType=Debt, **kwargs)
        self.assets.add(account)
        return account

    def set_scenario(
        self, inflation=None, stock_return=None, bond_return=None,
        other_return=None, management_fees=None, initial_year=None,
        num_years=None, ScenarioType=Scenario, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'inflation', inflation, self.settings.inflation)
        self.set_kwarg(kwargs, 'stock_return', stock_return,
                       self.settings.stock_return)
        self.set_kwarg(kwargs, 'bond_return', bond_return,
                       self.settings.bond_return)
        self.set_kwarg(kwargs, 'other_return', other_return,
                       self.settings.other_return)
        self.set_kwarg(kwargs, 'management_fees', management_fees,
                       self.settings.management_fees)
        self.set_kwarg(kwargs, 'initial_year', initial_year, self.initial_year)
        self.set_kwarg(kwargs, 'num_years', num_years, self.settings.num_years)

        self.scenario = ScenarioType(**kwargs)

    def set_contribution_strategy(
        self, strategy=None, base_amount=None, rate=None,
        refund_reinvestment_rate=None, inflation_adjust=None,
        StrategyType=ContributionStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.contribution_strategy)
        self.set_kwarg(kwargs, 'base_amount', base_amount,
                       self.settings.contribution_base_amount)
        self.set_kwarg(kwargs, 'rate', rate,
                       self.settings.contribution_rate)
        self.set_kwarg(kwargs, 'refund_reinvestment_rate',
                       refund_reinvestment_rate,
                       self.settings.contribution_refund_reinvestment_rate)
        self.set_kwarg(kwargs, 'inflation_adjust', inflation_adjust, None)

        self.contribution_strategy = StrategyType(**kwargs)
        return self.contribution_strategy

    def set_withdrawal_strategy(
        self, strategy=None, base_amount=None, rate=None, timing=None,
        income_adjusted=None, inflation_adjust=None,
        StrategyType=WithdrawalStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.withdrawal_strategy)
        self.set_kwarg(kwargs, 'base_amount', base_amount,
                       self.settings.withdrawal_base_amount)
        self.set_kwarg(kwargs, 'rate', rate,
                       self.settings.withdrawal_rate)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.transaction_out_timing)
        self.set_kwarg(kwargs, 'income_adjusted', income_adjusted,
                       self.settings.withdrawal_income_adjusted)
        self.set_kwarg(kwargs, 'inflation_adjust', inflation_adjust, None)

        self.withdrawal_strategy = StrategyType(**kwargs)
        return self.contribution_strategy

    def set_transaction_in_strategy(
        self, strategy=None, weights=None, timing=None,
        StrategyType=TransactionStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.transaction_in_strategy)
        self.set_kwarg(kwargs, 'weights', weights,
                       self.settings.transaction_in_weights)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.transaction_in_timing)

        self.transaction_in_strategy = StrategyType(**kwargs)
        return self.transaction_in_strategy

    def set_transaction_out_strategy(
        self, strategy=None, weights=None, timing=None,
        StrategyType=TransactionStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.transaction_out_strategy)
        self.set_kwarg(kwargs, 'weights', weights,
                       self.settings.transaction_out_weights)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.transaction_out_timing)

        self.transaction_out_strategy = StrategyType(**kwargs)
        return self.transaction_out_strategy

    def set_allocation_strategy(
        self, strategy=None, min_equity=None, max_equity=None, target=None,
        standard_retirement_age=None, risk_transition_period=None,
        adjust_for_retirement_plan=None, scenario=None,
        StrategyType=AllocationStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.allocation_strategy)
        self.set_kwarg(kwargs, 'min_equity', min_equity,
                       self.settings.allocation_min_equity)
        self.set_kwarg(kwargs, 'max_equity', max_equity,
                       self.settings.allocation_max_equity)

        # Different strategies have different defaults in Settings:
        if (
            kwargs['strategy'] ==
            AllocationStrategy._strategy_n_minus_age.strategy_key
        ):
            target_default = \
                self.settings.allocation_constant_strategy_target
        elif (
            kwargs['strategy'] ==
            AllocationStrategy._strategy_transition_to_constant.strategy_key
        ):
            target_default = \
                self.settings.allocation_transition_strategy_target
        else:
            target_default = None

        self.set_kwarg(kwargs, 'target', target, target_default)
        self.set_kwarg(kwargs, 'standard_retirement_age',
                       standard_retirement_age,
                       self.settings.allocation_standard_retirement_age)
        self.set_kwarg(kwargs, 'risk_transition_period',
                       risk_transition_period,
                       self.settings.allocation_risk_transition_period)
        self.set_kwarg(kwargs, 'adjust_for_retirement_plan',
                       adjust_for_retirement_plan,
                       self.settings.allocation_adjust_for_retirement_plan)
        self.set_kwarg(kwargs, 'scenario', scenario, None)

        self.allocation_strategy = StrategyType(**kwargs)
        return self.allocation_strategy

    def set_debt_payment_strategy(
        self, strategy=None, timing=None,
        StrategyType=DebtPaymentStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.debt_payment_strategy)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.debt_payment_timing)

        self.debt_payment_strategy = StrategyType(**kwargs)
        return self.debt_payment_strategy

    def set_tax_treatment(
        self, tax_brackets=None, personal_deduction=None, credit_rate=None,
        inflation_adjust=None, TaxType=Tax, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'tax_brackets', tax_brackets, None)
        self.set_kwarg(kwargs, 'personal_deduction', personal_deduction, None)
        self.set_kwarg(kwargs, 'credit_rate', credit_rate, None)
        # default to the inflation-adjust provided by `scenario`, if
        # we have set a `scenario`
        self.set_kwarg(
            kwargs, 'inflation_adjust', inflation_adjust,
            self.scenario.inflation_adjust if self.scenario is not None
            else None
        )

        return TaxType(**kwargs)
