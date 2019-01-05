''' This module provides classes for creating and managing Forecasts. '''

from copy import deepcopy
from forecaster.forecast import Forecast
from forecaster.person import Person
from forecaster.accounts import Account, ContributionLimitAccount, Debt
from forecaster.tax import Tax
from forecaster.strategy import (
    LivingExpensesStrategy, WithdrawalStrategy, TransactionStrategy,
    DebtPaymentStrategy, AllocationStrategy)
from forecaster.scenario import Scenario
from forecaster.settings import Settings


# Forecaster wraps Forecast. It replicates much of that complexity
# by necessity, but it isn't necessary for client code to interact
# with it - that's the whole point of this class. Its arguments are
# optional and its attributes are unavoidable, so suppress Pylint's
# concerns about numbers of arguments/attributes/variables
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-locals


class Forecaster(object):
    """ A convenience class for building Forecasts based on settings.

    `Forecaster` takes in information for building a `Forecast`
    (explicitly, via a `Settings` object, or via a combination of the
    two) and builds one or more `Forecast` objects from that
    information.

    One of the purposes of this class is to enable building `Forecast`
    objects solely from a `Settings` object and a set of `inputs` dicts.
    Objects of this class can be initialized with any of the parameters
    that can be provided to `Forecast` (as well as a `Settings` object).
    Any parameters that are not provided at init time can be built
    afterward via an `add_\\*` method. Each `add_\\*` method takes the
    parameters of the corresponding object being built; e.g.
    `add_person` takes the same parameters as `Person.__init__` (plus
    a `cls` parameter -- see documentation for `add_person`).

    This behaviour can be particularly useful for `Ledger` objects like
    `Person` or `Account`, which may have per-object historical
    data that can't be inferred from a Settings object (represented by
    an `inputs` dict for each such object).

    `Forecasts` may be generated based on varying `Scenario` object
    (while retaining the same `Strategy`, `Person`, and `Account`
    objects) to allow for comparison of an overarching strategy between
    various future economic performance scenarios (e.g. as in Monte
    Carlo analysis).
    """

    def __init__(
        self, person1=None, person2=None, people=None, assets=None,
        debts=None, scenario=None, contribution_strategy=None,
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
        the corresponding `add_\\*` method individually.

        Args:
            settings (Settings): An object with settings values for the
                `Forecaster` to pass to various `Account`, `Person`,
                `Strategy`, and `Scenario` objects when explicit
                arguments are not given.
            initial_year (int): The initial year for the forecast.
        """
        # This method has very simple branches - just testing for None
        # followed by a single statement. There's not much to be gained
        # by splitting this method up more.
        # pylint: disable=too-many-branches

        # NOTE: Settings defines two named persons, so store them via
        # their own named attributes (as well as in the `people` dict).
        # TODO: Make person* properties that update `people` when set
        # (or add add_person1 and add_person2 methods)?
        self.person1 = person1
        self.person2 = person2
        self.people = people if people is not None else set()
        # Ensure that person1/person2 are in the `people` set:
        if self.person1 is not None:
            self.people.add(self.person1)
        if self.person2 is not None:
            self.people.add(self.person2)
        self.assets = assets if assets is not None else set()
        self.debts = debts if debts is not None else set()
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
        # If a `scenario` has been provided, use that rather than
        # Settings, since `scenario` defines initial_year as well.
        if initial_year is not None:
            self.initial_year = initial_year
        else:
            if scenario is not None:
                self.initial_year = scenario.initial_year
            else:
                self.initial_year = settings.initial_year

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
        if self.debt_payment_strategy is None:
            self.set_debt_payment_strategy()
        # Tax treatment also depends on Scenario. Person depends on Tax,
        # so build Tax first.
        if self.tax_treatment is None:
            self.set_tax_treatment()
        # Finally, set `Person` objects.
        if self.person1 is None:
            self.set_person1()
        if self.person2 is None:
            self.set_person2()
        # Accounts will need to be set manually.

    def forecast(self, **kwargs):
        """ TODO """

        # Build a dict of args to pass to Forecast.__init__ based on
        # the `Forecaster`'s attributes:
        forecast_kwargs = {
            'scenario': self.scenario,
            'people': self.people,
            'assets': self.assets,
            'debts': self.debts,
            'contribution_strategy': self.contribution_strategy,
            'withdrawal_strategy': self.withdrawal_strategy,
            'contribution_trans_strategy': self.transaction_in_strategy,
            'withdrawal_trans_strategy': self.transaction_out_strategy,
            'debt_payment_strategy': self.debt_payment_strategy,
            'tax_treatment': self.tax_treatment
        }

        # This is the clever bit: `Forecast` mutates many of its
        # arguments, so we need to deepcopy this arg list. We also
        # want to allow the user to replace any arguments to `Forecast`
        # so that they can test out different scenarios, account mixes,
        # etc. We can do these both by using the deepcopy memo arg!
        # This memo maps each of the forecast_kwarg values to the
        # corresponding input kwarg; those values will be replaced with
        # the input values when we pass `memo` to deepcopy.
        memo = {
            id(forecast_kwargs[key]): kwargs[key]
            for key in kwargs if key in forecast_kwargs
        }
        forecast_kwargs = deepcopy(forecast_kwargs, memo=memo)
        # If any of the input kwargs aren't in forecast_kwargs, add them
        forecast_kwargs.update({
            key: kwargs[key] for key in kwargs if key not in forecast_kwargs
        })

        return Forecast(**forecast_kwargs)

    @staticmethod
    def set_kwarg(kwargs, arg, val, default):
        """ Adds a keyword arg to a dict based on an input hierarchy.

        Adds `arg` to the dict `kwargs` with value `val` (usually an
        explicit argument to the calling method) or, if that's `None`,
        `default` (usually a value from a Settings object).

        If both of these values are None, or if `arg` is already in
        `kwargs`, no value is added to `kwargs`.
        This avoids overriding the relevant parameter defaults or
        overriding args set by subclasses.

        Args:
            kwargs (dict[str, Any]): A dict of keyword args to be passed
                to an `__init__` method when initializing a Person,
                Account, or other Forecast input object.
            arg (str): The keyword arg being added to `kwargs`.
            val (Any): An explicitly-passed value for `arg`.
                May be None.
            default (Any): A value from a Settings object
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
        self, name, birth_date,
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, inputs=None, initial_year=None,
        cls=Person, **kwargs
    ):
        """ Adds a Person to the forecast.

        If `name` matches `person1_name` or `person2_name` in `settings`
        then the default values for that person will be used, otherwise
        no defaults will be used (be sure to provide any mandatory
        arguments!)

        Subclasses of Forecaster that build subclasses of Person can
        make use of this method by passing in a suitable `cls`
        argument along with any `kwargs` specific to that `cls`.

        See `Person` for documentation on additional args.

        Args:
            inputs (dict[str, dict[int, Any]]): `{arg: {year: val}}`
                pairs, where `arg` is the name of a @recorded_property
                of `Person` and `val` is the value of that property for
                `year`.
            cls (type): The class of `Person` being built by the
                method. This class's `__init__` method must accept all
                of the args of `Person`.

        Returns:
            `Person`: An object of type `cls` constructed with
            the relevant args, inputs, settings, and default values.
        """
        # NOTE: We don't actually need to list Person's various args
        # in the call signature here; we could just use `inputs`,
        # `cls` and `**kwargs`. Doing it that way would be less
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
        self.set_kwarg(kwargs, 'inputs', inputs, None)
        self.set_kwarg(kwargs, 'initial_year', initial_year, self.initial_year)

        # Construct a person with the keyword arguments we've assembled:
        person = cls(**kwargs)
        self.people.add(person)
        # Return the Person so that subclass methods can do
        # post-processing (if they need to)
        return person

    def set_person1(
        self, name=None, birth_date=None,
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, inputs=None, initial_year=None,
        cls=Person, **kwargs
    ):
        """ Adds a person to the forecast based on person1's settings.

        See `add_person` for documentation on the args and return type
        of this method.
        """
        # Remember to remove any previously-instantiated person1
        if self.person1 is not None:
            self.people.remove(self.person1)
        self.set_kwarg(kwargs, 'name', name, self.settings.person1_name)
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
        self.set_kwarg(kwargs, 'inputs', inputs, None)
        self.set_kwarg(kwargs, 'initial_year', initial_year, self.initial_year)

        self.person1 = self.add_person(cls=cls, **kwargs)
        return self.person1

    def set_person2(
        self, name=None, birth_date=None,
        retirement_date=None, gross_income=None, raise_rate=None,
        spouse=None, tax_treatment=None, inputs=None, initial_year=None,
        cls=Person, **kwargs
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
        self.set_kwarg(kwargs, 'inputs', inputs, None)
        self.set_kwarg(kwargs, 'initial_year', initial_year, self.initial_year)

        self.person2 = self.add_person(cls=cls, **kwargs)
        return self.person2

    def add_account(
        self, owner=None, balance=None, rate=None, transactions=None,
        nper=None, inputs=None, initial_year=None, cls=Account, **kwargs
    ):
        """ Adds an account (asset, debt, etc.) to the forecast. """
        # NOTE: We don't actually need to list Account's various args
        # in the call signature here; we could just use `inputs`,
        # `cls` and `**kwargs`. Doing it that way would be less
        # brittle, but not as convenient for Intellisense.

        self.set_kwarg(kwargs, 'owner', owner, self.person1)
        self.set_kwarg(kwargs, 'balance', balance, None)
        self.set_kwarg(
            kwargs, 'rate', rate,
            self.allocation_strategy.rate_function(
                kwargs['owner'], self.scenario)
        )
        self.set_kwarg(kwargs, 'transactions', transactions, None)
        self.set_kwarg(kwargs, 'nper', nper, None)
        self.set_kwarg(kwargs, 'inputs', inputs, None)
        self.set_kwarg(kwargs, 'initial_year', initial_year, self.initial_year)

        account = cls(**kwargs)
        return account

    def add_asset(
        self, owner=None, balance=None, rate=None, transactions=None,
        nper=None, inputs=None, initial_year=None, cls=Account, **kwargs
    ):
        """ Adds an asset to the forecast and to the `assets` set.

        This method should be used instead of the generic method
        `add_account` because, in addition to building an object of the
        appropriate type, it also manages object membership in the
        `assets` set.

        See `add_account` for additional documentation.

        Args:
            cls (type): The class of `Account` being built by
                the method. This class's `__init__` method must accept
                all of the args of `Account`.

        Returns:
            `Account`: An object of type `cls` constructed with
            the relevant args, inputs, settings, and default values.
        """
        account = self.add_account(
            owner=owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, inputs=inputs, initial_year=initial_year, cls=cls,
            **kwargs
        )
        self.assets.add(account)
        return account

    def add_contribution_limit_account(
        self, contribution_room=None, contributor=None,
        cls=ContributionLimitAccount, **kwargs
    ):
        """ Adds an asset to the forecast and to the `assets` set.

        This method should be used instead of the generic method
        `add_account` because, in addition to building an object of the
        appropriate type, it also manages object membership in the
        `assets` set.

        See `add_account` for additional documentation.

        Args:
            cls (type): The class of `RegisteredAccount` being built by
                the method. This class's `__init__` method must accept
                all of the args of `RegisteredAccount`.

        Returns:
            RegisteredAccount: An object of type `cls` constructed with
            the relevant args, inputs, settings, and default values.
        """
        self.set_kwarg(kwargs, 'contribution_room', contribution_room, None)
        if 'owner' in kwargs:
            contributor_default = kwargs['owner']
        else:
            contributor_default = self.person1
        self.set_kwarg(kwargs, 'contributor', contributor, contributor_default)
        account = self.add_asset(
            cls=cls, **kwargs
        )
        return account

    def add_debt(
        self, owner=None, balance=None, rate=None, transactions=None,
        nper=None, inputs=None, initial_year=None, minimum_payment=None,
        savings_rate=None, accelerated_payment=None, cls=Debt, **kwargs
    ):
        """ Adds a Debt to the forecast.

        This method should be used instead of the generic method
        `add_account` because, in addition to building an object of the
        appropriate type, it also manages object membership in the
        `assets` set.

        See `_add_account` for additional documentation.

        Args:
            cls (type): The class of `Debt` being built by
                the method. This class's `__init__` method must accept
                all of the args of `Debt`.

        Returns:
            `Debt`: An object of type `cls` constructed with
            the relevant args, inputs, settings, and default values.
        """
        self.set_kwarg(kwargs, 'minimum_payment', minimum_payment, None)
        self.set_kwarg(kwargs, 'savings_rate', savings_rate,
                       self.settings.debt_savings_rate)
        self.set_kwarg(kwargs, 'accelerated_payment', accelerated_payment,
                       self.settings.debt_accelerated_payment)

        account = self.add_account(
            owner=owner, balance=balance, rate=rate, transactions=transactions,
            nper=nper, inputs=inputs, initial_year=initial_year, cls=cls,
            **kwargs)

        self.debts.add(account)
        return account

    def set_scenario(
        self, inflation=None, stock_return=None, bond_return=None,
        other_return=None, management_fees=None, initial_year=None,
        num_years=None, cls=Scenario, **kwargs
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

        self.scenario = cls(**kwargs)

    def set_contribution_strategy(
        self, strategy=None, base_amount=None, rate=None,
        refund_reinvestment_rate=None, inflation_adjust=None,
        cls=LivingExpensesStrategy, **kwargs
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
                       self.settings.contribution_reinvestment_rate)
        self.set_kwarg(kwargs, 'inflation_adjust', inflation_adjust,
                       self.scenario.inflation_adjust)

        self.contribution_strategy = cls(**kwargs)
        return self.contribution_strategy

    def set_withdrawal_strategy(
        self, strategy=None, base_amount=None, rate=None, timing=None,
        income_adjusted=None, inflation_adjust=None,
        cls=WithdrawalStrategy, **kwargs
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
        self.set_kwarg(kwargs, 'inflation_adjust', inflation_adjust,
                       self.scenario.inflation_adjust)

        self.withdrawal_strategy = cls(**kwargs)
        return self.contribution_strategy

    def set_transaction_in_strategy(
        self, strategy=None, weights=None, timing=None,
        cls=TransactionStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.transaction_in_strategy)
        self.set_kwarg(kwargs, 'weights', weights,
                       self.settings.transaction_in_weights)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.transaction_in_timing)

        self.transaction_in_strategy = cls(**kwargs)
        return self.transaction_in_strategy

    def set_transaction_out_strategy(
        self, strategy=None, weights=None, timing=None,
        cls=TransactionStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.transaction_out_strategy)
        self.set_kwarg(kwargs, 'weights', weights,
                       self.settings.transaction_out_weights)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.transaction_out_timing)

        self.transaction_out_strategy = cls(**kwargs)
        return self.transaction_out_strategy

    def set_allocation_strategy(
        self, strategy=None, min_equity=None, max_equity=None, target=None,
        standard_retirement_age=None, risk_transition_period=None,
        adjust_for_retirement_plan=None,
        cls=AllocationStrategy, **kwargs
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
            # pylint: disable=no-member
            # Pylint thinks there's no strategy_key member. It's wrong
            kwargs['strategy'] ==
            AllocationStrategy.strategy_n_minus_age.strategy_key
        ):
            target_default = self.settings.allocation_const_target
        elif (
            # pylint: disable=no-member
            # Pylint thinks there's no strategy_key member. It's wrong
            kwargs['strategy'] ==
            AllocationStrategy.strategy_transition_to_const.strategy_key
        ):
            target_default = self.settings.allocation_trans_target
        else:
            target_default = None

        self.set_kwarg(kwargs, 'target', target, target_default)
        self.set_kwarg(kwargs, 'standard_retirement_age',
                       standard_retirement_age,
                       self.settings.allocation_std_retirement_age)
        self.set_kwarg(kwargs, 'risk_transition_period',
                       risk_transition_period,
                       self.settings.allocation_risk_trans_period)
        self.set_kwarg(kwargs, 'adjust_for_retirement_plan',
                       adjust_for_retirement_plan,
                       self.settings.allocation_adjust_retirement)

        self.allocation_strategy = cls(**kwargs)
        return self.allocation_strategy

    def set_debt_payment_strategy(
        self, strategy=None, timing=None,
        cls=DebtPaymentStrategy, **kwargs
    ):
        """ TODO """
        self.set_kwarg(kwargs, 'strategy', strategy,
                       self.settings.debt_payment_strategy)
        self.set_kwarg(kwargs, 'timing', timing,
                       self.settings.debt_payment_timing)

        self.debt_payment_strategy = cls(**kwargs)
        return self.debt_payment_strategy

    def set_tax_treatment(
        self, tax_brackets=None, personal_deduction=None, credit_rate=None,
        inflation_adjust=None, cls=Tax, **kwargs
    ):
        """ TODO """
        # By default, set a single 0% bracket starting at $0:
        self.set_kwarg(
            kwargs, 'tax_brackets', tax_brackets, {self.initial_year: {0: 0}})
        self.set_kwarg(kwargs, 'personal_deduction', personal_deduction, None)
        self.set_kwarg(kwargs, 'credit_rate', credit_rate, None)
        # default to the inflation-adjust provided by `scenario`, if
        # we have set a `scenario`
        self.set_kwarg(
            kwargs, 'inflation_adjust', inflation_adjust,
            self.scenario.inflation_adjust if self.scenario is not None
            else None
        )

        self.tax_treatment = cls(**kwargs)
        return self.tax_treatment
