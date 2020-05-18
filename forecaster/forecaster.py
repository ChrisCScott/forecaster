''' This module provides classes for creating and managing Forecasts. '''

from typing import Any, Optional, Dict, Set, Type, Union
from copy import copy, deepcopy
from functools import reduce
from enum import Enum
from forecaster.forecast import (
    Forecast, IncomeForecast, LivingExpensesForecast,
    SavingForecast, WithdrawalForecast, TaxForecast)
from forecaster.tax import Tax
from forecaster.strategy import (
    LivingExpensesStrategy, TransactionStrategy, AllocationStrategy)
from forecaster.scenario import Scenario
from forecaster.settings import Settings
# Importing these just for typing
# TODO: Define ABCs for Person/Account/Debt and use them here:
from forecaster.accounts import Account, Debt
from forecaster.person import Person


# The `ForecastBuilder` class makes frequent reference to the names of
# parameters. Rather than hard-code these strings, it's better practice
# to define them here as an enum.
class Parameter(Enum):
    """ Defines names of `ForecastBuilder` parameters. """
    SCENARIO = "scenario"
    LIVING_EXPENSES_STRATEGY = "living_expenses_strategy"
    SAVING_STRATEGY = "saving_strategy"
    WITHDRAWAL_STRATEGY = "withdrawal_strategy"
    ALLOCATION_STRATEGY = "allocation_strategy"
    TAX_TREATMENT = "tax_treatment"

    def __str__(self) -> str:
        """ Cast enum members directly to their string value. """
        return str(self.value)

# This mapping has the following form:
#   dict[str: dict[str, str]]
# The key provides an attribute name (as a string).
# The {str: str} value is a mapping from the name of an __init__
# arg for attribute (see DEFAULTTYPES for each attribute's type) to the
# name of the corresponding `Settings` attribute that provides its
# default value.
# EXAMPLE:
#   `{"scenario": {"inflation": "scenario_inflation"}}`
#   implies that `ForecastBuilder.scenario` receives the parameter
#   `inflation` when initialized and its default value is provided by
#   `ForecastBuilder.settings.scenario_inflation`.
DEFAULTVALUES = {
    str(Parameter.SCENARIO): {
        "initial_year": "settings.initial_year",
        "inflation": "settings.inflation",
        "stock_return": "settings.stock_return",
        "bond_return": "settings.bond_return",
        "other_return": "settings.other_return",
        "management_fees": "settings.management_fees",
        "num_years": "settings.num_years"},
    str(Parameter.LIVING_EXPENSES_STRATEGY): {
        "strategy": "settings.living_expenses_strategy",
        "base_amount": "settings.living_expenses_base_amount",
        "rate": "settings.living_expenses_rate",
        "inflation_adjust": "scenario.inflation_adjust"},
    str(Parameter.SAVING_STRATEGY): {
        "strategy": "settings.saving_strategy",
        "weights": "settings.saving_weights"},
    str(Parameter.WITHDRAWAL_STRATEGY): {
        "strategy": "settings.withdrawal_strategy",
        "weights": "settings.withdrawal_weights"},
    str(Parameter.ALLOCATION_STRATEGY): {
        "strategy": "settings.allocation_strategy",
        "target": "settings.allocation_target",
        "min_equity": "settings.allocation_min_equity",
        "max_equity": "settings.allocation_max_equity",
        "standard_retirement_age": "settings.allocation_std_retirement_age",
        "risk_transition_period": "settings.allocation_risk_trans_period",
        "adjust_for_retirement_plan": "settings.allocation_adjust_retirement"},
    str(Parameter.TAX_TREATMENT): {
        "tax_brackets": "settings.tax_brackets",
        "personal_deduction": "settings.tax_personal_deduction",
        "credit_rate": "settings.tax_credit_rate",
        "inflation_adjust": "scenario.inflation_adjust",
        "payment_timing": "settings.tax_payment_timing"}
}

# This maps each of the above parameters to a type:
DEFAULTTYPES = {
    str(Parameter.SCENARIO): Scenario,
    str(Parameter.LIVING_EXPENSES_STRATEGY): LivingExpensesStrategy,
    str(Parameter.SAVING_STRATEGY): TransactionStrategy,
    str(Parameter.WITHDRAWAL_STRATEGY): TransactionStrategy,
    str(Parameter.ALLOCATION_STRATEGY): AllocationStrategy,
    str(Parameter.TAX_TREATMENT): Tax}

# This maps certain parameters that need special init logic to
# the method name that provides that logic.
DEFAULTBUILDERS: Dict[str, str] = {
    # str(Parameter.TAX_TREATMENT): "build_tax_treatment"
}

class ForecastBuilder(object):
    """ A convenience class for building Forecasts based on settings.

    `ForecastBuilder` takes in information for building a `Forecast`
    (explicitly, via a `Settings` object, or via a combination of the
    two) and builds one or more `Forecast` objects from that
    information.

    One of the purposes of this class is to enable building `Forecast`
    objects solely from a `Settings` object and some `Ledger` objects
    (i.e. people, assets, and debts.) Client code may optionally
    provide certain parameters required by `Forecast` or its members,
    which will be used as-is without values from `Settings`. Client
    code may also (or alternatively) build parameters with partial
    init args; `ForecastBuilder` will fill in any remaining init args
    with the appropriate values from `Settings`.

    `ForecastBuilder` also can be used to build certain objects which
    are used by `Ledger` arguments to `ForecastBuilder.build_forecast()`
    such as `Tax` and `AllocationStrategy` objects (used
    by `Person` and some `Account` objects, respectively.)

    `ForecastBuilder` does not mutate values provided to it. `Ledger`
    objects passed by client code are copied (actually deepcopied, so
    that relationships between them are preserved), and the copies are
    mutated and returned. This makes it easy to tweak a few parameters
    and run another forecast, e.g. via Monte Carlo sampling.
    """

    def __init__(
            self,
            settings: Optional[Settings] = None,
            scenario: Optional[Scenario] = None,
            living_expenses_strategy: Optional[LivingExpensesStrategy] = None,
            saving_strategy: Optional[TransactionStrategy] = None,
            withdrawal_strategy: Optional[TransactionStrategy] = None,
            tax_treatment: Optional[Tax] = None
    ) -> None:
        """ Inits an instance of `ForecastBuilder`. """
        # Set up instance:
        super().__init__()
        self.default_values = copy(DEFAULTVALUES)
        self.default_types = copy(DEFAULTTYPES)
        self.default_builders = copy(DEFAULTBUILDERS)
        # Store args as attributes:
        # For `settings` specifically, use the default values provided
        # by the class if none are provided explicitly.
        if settings is None:
            self.settings = Settings()
        else:
            self.settings = settings
        # For the rest, None is allowed:
        self.scenario = scenario
        self.living_expenses_strategy = living_expenses_strategy
        self.saving_strategy = saving_strategy
        self.withdrawal_strategy = withdrawal_strategy
        self.tax_treatment = tax_treatment
        # Some params aren't used to build Forecast and so are not
        # received as input to __init__. Create attrs for them here:
        self.allocation_strategy = None

    def _get_attr_recursive(
            self,
            name: str,
            memo: Optional[Dict[str, Any]] = None
        ) -> Any:
        """ Get an attribute based on a dot-delimited identifier.

        If the first element of `name` is an optional parameter
        (e.g. `scenario`), then if that parameter hasn't been explicitly
        provided this method will build the parameter via
        `build_param`.

        Example:
            `builder._get_attr_recursive('settings.initial_year')`
            Returns the value of `builder.settings.initial_year`

        Returns:
            (Any) The value of the requested attribute.

        Raises:
            AttributeError: The attribute does not exist.
        """
        # `name` is dot-delimited, so split it up into distinct names:
        name_list = name.split('.')
        # The first name has special treatment, since it might need to
        # be dynamically built:
        top_attr_name = name_list[0]
        # NOTE: This raises AttributeError if the attribute doesn't
        # exist. (Optional attributes should exist and be None-valued)
        attr = getattr(self, top_attr_name)
        # If this is an optional attribute and it hasn't been explicitly
        # provided, build it dynamically:
        if attr is None and top_attr_name in self.default_values:
            attr = self.build_param(top_attr_name, memo=memo)
        # If there are no further identifiers, we're done!
        if len(name_list) == 1:
            return attr
        # Otherwise, recursively call getattr on each sub-identifier.
        else:
            return reduce(getattr, name_list[1:], attr)

    def build_forecast(
            self,
            people: Set[Person], accounts: Set[Account], debts: Set[Debt]
        ) -> Forecast:
        """ Builds a `Forecast` object.

        This method builds a `Forecast` based on any explicitly-provided
        parameters (e.g. `scenario`, `living_expenses_strategy`) and
        the applicable `settings`. Any parameters that have not been
        explicitly provided are built dynamically.

        Arguments (`people`, etc.) are copied. Copies are mutated, but
        the objects passed as arguments are not so that they an be
        re-used (and because mutating arguments is considered rude).
        Relationships between arguments and their members are preserved
        via `deepcopy`.

        Arguments:
            people (set[Person]): One or more people for whom a forecast
                is being generated.
            accounts (set[Account]): Accounts belonging to the plannees.
            debts (set[Debt]): Debts owed by the plannees.

        Returns:
            Forecast: A forecast of the plannees income, savings,
            and withdrawals over the years.
        """
        # We don't want to mutate the inputs, so create copies:
        copy_memo: Dict[int, Any] = {}
        people = deepcopy(people, memo=copy_memo)
        accounts = deepcopy(accounts, memo=copy_memo)
        debts = deepcopy(debts, memo=copy_memo)

        # Build Scenario first so that we have access to initial_year:
        memo: Dict[str, Any] = {}
        scenario = self.get_param(Parameter.SCENARIO, memo=memo)
        initial_year = scenario.initial_year  # extract for convenience

        # Retrieve the necessary strategies for building SubForecasts:
        living_expenses_strategy = self.get_param(
            Parameter.LIVING_EXPENSES_STRATEGY, memo=memo)
        saving_strategy = self.get_param(
            Parameter.SAVING_STRATEGY, memo=memo)
        withdrawal_strategy = self.get_param(
            Parameter.WITHDRAWAL_STRATEGY, memo=memo)
        tax_treatment = self.get_param(
            Parameter.TAX_TREATMENT, memo=memo)

        # Now build each of the SubForecast objects required by Forecast
        income_forecast = IncomeForecast(
            initial_year=initial_year,
            people=people)
        living_expenses_forecast = LivingExpensesForecast(
            initial_year=initial_year,
            people=people,
            living_expenses_strategy=living_expenses_strategy)
        saving_forecast = SavingForecast(
            initial_year=initial_year,
            retirement_accounts=accounts,
            debt_accounts=debts,
            transaction_strategy=saving_strategy)
        withdrawal_forecast = WithdrawalForecast(
            initial_year=initial_year,
            people=people,
            accounts=accounts,
            transaction_strategy=withdrawal_strategy)
        tax_forecast = TaxForecast(
            initial_year=initial_year,
            people=people,
            tax_treatment=tax_treatment)

        # With these SubForecasts defined, building Forecast is trivial:
        forecast = Forecast(
            income_forecast=income_forecast,
            living_expenses_forecast=living_expenses_forecast,
            saving_forecast=saving_forecast,
            withdrawal_forecast=withdrawal_forecast,
            tax_forecast=tax_forecast,
            scenario=scenario)

        # Forecasts run automatically on init, so we're done!
        return forecast

    def build_param(
            self,
            param_name: Union[str, Parameter], *args: Any,
            param_type: Optional[Type] = None,
            memo: Optional[Dict[str, Any]] = None,
            _special_builder: bool = True,
            **kwargs: Any
        ) -> Any:
        """ Builds a parameter based on settings and explicit args.

        This method does not set any attributes of `ForecastBuilder`, it
        only builds an object and returns it.

        Arguments:
            param_name (str): The name of the parameter. This should
                match a key value in `self.default_values`.
            *args (Any): Positional arguments to be passed to the init
                method of the object being built. Optional.
            param_type (type): The type of the parameter. Optional.
                Defaults to the type provided by `self.default_types`.
            memo (dict[str, Any]): A mapping from parameter names to
                objects. This is not generally needed by client code;
                in cases where `build_param` needs to build other
                parameters to build the requested parameter, this dict
                is mutated to record already-built parameters. Optional.
            _special_builder (Boolean): Parameters which require special
                logic to init (as identified in `self.default_builders`)
                will only have the corresponding special builder called
                iff this value is True. Optional.
            **kwargs (Any): Keyword arguments to be passed to the init
                method of the object being built. Optional.

        Returns:
            An object of type `param_type`.
        """
        # Cast param_name to str once, for convenience:
        # (This is needed because Parameter members are Enum objects,
        # which can't be used in place of string-valued indexes)
        param_name = str(param_name)

        # build_param can recurse, either via default_builders methods
        # or via _get_attr_recursive (e.g. fetching a kwarg might
        # involve building an attribute from which this attribute
        # depends). If this is the first call, set up a dict of
        # parameters we've tried to build already to keep track:
        if memo is None:
            memo = {}
        elif param_name in memo:
            return memo[param_name]

        # If there's special logic for this parameter, use that instead:
        # (The special builder method can call this one by setting
        # `_special_builder` to False.)
        if _special_builder and param_name in self.default_builders:
            return getattr(
                self, self.default_builders[param_name])(*args, **kwargs)
        # For everything else, use the user-provided defaults and fill
        # in the gaps with the settings-provided defaults:
        if param_name in self.default_values:
            # Get the default mapping for this parameter:
            # (We copy it to avoid mutating it)
            default_values = copy(self.default_values[param_name])
            # Replace each value with the value of the same-named
            # attribute of the `ForecastBuilder` object:
            for key, value in default_values.items():
                default_values[key] = self._get_attr_recursive(value, memo=memo)
            # If any values have been provided explicitly, override
            # the defaults with that:
            default_values.update(kwargs)
            kwargs = default_values
        # Build a new object (note that we don't set the corresponding
        # attribute of ForecastBuilder; if this is called again, we'll
        # build a new object)
        if param_type is None:
            param_type = self.default_types[param_name]
        param = param_type(*args, **kwargs)
        memo[param_name] = param
        return param

    def get_param(
            self, param_name: Union[Parameter, str],
            memo: Optional[Dict[str, Any]] = None) -> Any:
        """ Gets a parameter, builds one if none is explicitly provided.

        If a parameter has been explicitly assigned to this
        `ForecastBuilder` instance then that object is returned.
        Otherwise, this method calls `build_param` to build it
        dynamically and returns it without setting any attributes of the
        `ForecastBuilder` object.

        This is a convenience method which allows one to guarantee
        that an object will be returned (if `param_name` is supported)
        whether or not it is been explicitly set.

        Arguments:
            param_name (str): The name of the parameter. This should
                match a key value in `self.default_values`.
            memo (dict[str, Any]): A mapping from parameter names to
                objects. This is not generally needed by client code;
                in cases where `build_param` needs to build other
                parameters to build the requested parameter, this dict
                is mutated to record already-built parameters. Optional.

        Returns:
            The value of the attribute with name `param_name` or, if
            that value is None, a dynamically-built object that uses
            the values of `settings` for init.
        """
        # Cast param_name to str once, for convenience:
        # (This is needed because Parameter members are Enum objects,
        # which can't be used in place of string-valued indexes)
        param = str(param_name)
        explicit_attr = getattr(self, param)
        if explicit_attr is not None:
            return explicit_attr
        else:
            return self.build_param(param, memo=memo)

    def set_param(
            self,
            param_name: Union[Parameter, str],
            *args: Any,
            param_type: Optional[Type] = None,
            memo: Optional[Dict[str, Any]] = None,
            **kwargs: Any) -> None:
        """ Builds a parameter and sets the corresponding attribute.

        This is a convenience method that calls `build_param` and
        sets the result as the value of the corresponding attribute of
        this `ForecastBuilder` object.

        Note that by calling this method, the resulting object will be
        used without modification by `build_forecast` even if the
        `settings` object changes. You can un-set the parameter by
        assigning `None` to that attribute.

        This method does not set any attributes of `ForecastBuilder`, it
        only builds an object and returns it.

        Arguments:
            param_name (str): The name of the parameter. This should
                match a key value in `self.default_values`.
            *args (Any): Positional arguments to be passed to the init
                method of the object being built. Optional.
            param_type (type): The type of the parameter. Optional.
                Defaults to the type provided by `self.default_types`.
            memo (dict[str, Any]): A mapping from parameter names to
                objects. This is not generally needed by client code;
                in cases where `build_param` needs to build other
                parameters to build the requested parameter, this dict
                is mutated to record already-built parameters. Optional.
            **kwargs (Any): Keyword arguments to be passed to the init
                method of the object being built. Optional.
        """
        # Cast param_name to str once, for convenience:
        # (This is needed because Parameter members are Enum objects,
        # which can't be used in place of string-valued indexes)
        param_str = str(param_name)
        param = self.build_param(
            param_str, *args, param_type=param_type, memo=memo, **kwargs)
        setattr(self, param_str, param)

    def build_allocation_strategy(
            self, *args: Any, **kwargs: Any) -> AllocationStrategy:
        """ Convenience method to build an allocation strategy.

        Any arguments are passed on to AllocationStrategy.__init__. Any
        arguments that aren't passed explicitly to this function are
        instead pulled from the `ForecastBuilder` instance's `settings`
        attribute.

        The reason this specific object gets its own method is that
        client code will likely need to call it to initialize `Account`
        objects. In the future, we may provide similar methods for
        other parameters.
        """
        return self.build_param(
            Parameter.ALLOCATION_STRATEGY, AllocationStrategy, *args,
            _special_builder=False, **kwargs)
