''' This module provides classes for creating and managing Forecasts. '''

from copy import copy, deepcopy
from functools import reduce
from itertools import islice
from enum import Enum
from typing import Hashable
from forecaster.forecast import (
    Forecast, IncomeForecast, LivingExpensesForecast,
    SavingForecast, WithdrawalForecast, TaxForecast)
from forecaster.tax import Tax
from forecaster.strategy import (
    LivingExpensesStrategy, TransactionStrategy, AllocationStrategy)
from forecaster.scenario import Scenario, ScenarioSampler
from forecaster.settings import Settings
from forecaster.utility.precision import HighPrecisionHandler


# The `Forecaster` class makes frequent reference to the names of
# parameters. Rather than hard-code these strings, it's better practice
# to define them here as an enum.
class Parameter(Enum):
    """ Defines names of `Forecaster` parameters. """
    SCENARIO = "scenario"
    LIVING_EXPENSES_STRATEGY = "living_expenses_strategy"
    SAVING_STRATEGY = "saving_strategy"
    WITHDRAWAL_STRATEGY = "withdrawal_strategy"
    ALLOCATION_STRATEGY = "allocation_strategy"
    TAX_TREATMENT = "tax_treatment"
    # Not actually a param to `Forecaster`, but this built by `sample()`
    # so define it here to facilitate building:
    SCENARIO_SAMPLER = "sampler"

    def __str__(self):
        """ Cast enum members directly to their string value. """
        return self.value

# This mapping has the following form:
#   dict[str: dict[str, str]]
# The key provides an attribute name (as a string).
# The {str: str} value is a mapping from the name of an __init__
# arg for attribute (see DEFAULTTYPES for each attribute's type) to the
# name of the corresponding `Settings` attribute that provides its
# default value.
# EXAMPLE:
#   `{"scenario": {"inflation": "scenario_inflation"}}`
#   implies that `Forecaster.scenario` receives the parameter
#   `inflation` when initialized and its default value is provided by
#   `Forecaster.settings.scenario_inflation`.
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
        "payment_timing": "settings.tax_payment_timing"},
    str(Parameter.SCENARIO_SAMPLER): {
        "sampler": "settings.scenario_sampler_sampler",
        "data": "settings.scenario_sampler_filenames",
        "default_scenario": "scenario",
        "num_samples": "settings.scenario_sampler_num_samples",
        "returns": "settings.scenario_sampler_returns",
        "fast_read": "settings.scenario_sampler_fast_read"
    }
}

# This maps each of the above parameters to a type:
DEFAULTTYPES = {
    str(Parameter.SCENARIO): Scenario,
    str(Parameter.LIVING_EXPENSES_STRATEGY): LivingExpensesStrategy,
    str(Parameter.SAVING_STRATEGY): TransactionStrategy,
    str(Parameter.WITHDRAWAL_STRATEGY): TransactionStrategy,
    str(Parameter.ALLOCATION_STRATEGY): AllocationStrategy,
    str(Parameter.TAX_TREATMENT): Tax,
    str(Parameter.SCENARIO_SAMPLER): ScenarioSampler}

# This maps certain parameters that need special init logic to
# the method name that provides that logic.
DEFAULTBUILDERS = {
    # str(Parameter.TAX_TREATMENT): "build_tax_treatment"
}

# Types that can receive the callable argument `high_precision` at init:
HIGHPRECISIONTYPES = frozenset((
    # Scenario,
    LivingExpensesStrategy,
    TransactionStrategy,
    AllocationStrategy,
    Tax,
    ScenarioSampler,
    HighPrecisionHandler))

class Forecaster(HighPrecisionHandler):
    """ A convenience class for building Forecasts based on settings.

    `Forecaster` takes in information for building a `Forecast`
    (explicitly, via a `Settings` object, or via a combination of the
    two) and builds one or more `Forecast` objects from that
    information.

    One of the purposes of this class is to enable building `Forecast`
    objects solely from a `Settings` object and some `Ledger` objects
    (i.e. people, assets, and debts.) Client code may optionally
    provide certain parameters required by `Forecast` or its members,
    which will be used as-is without values from `Settings`. Client
    code may also (or alternatively) build parameters with partial
    init args; `Forecaster` will fill in any remaining init args with
    the appropriate values from `Settings`.

    `Forecaster` also can be used to build certain objects which
    are used by `Ledger` arguments to `Forecaster.run_forecast()`,
    such as `Tax` and `AllocationStrategy` objects (used
    by `Person` and some `Account` objects, respectively.)

    `Forecaster` does not mutate values provided to it. `Ledger`
    objects passed by client code are copied (actually deepcopied, so
    that relationships between them are preserved), and the copies are
    mutated and returned. This makes it easy to tweak a few parameters
    and run another forecast, e.g. via Monte Carlo sampling.
    """

    def __init__(
            self,
            settings=None,
            scenario=None,
            living_expenses_strategy=None,
            saving_strategy=None,
            withdrawal_strategy=None,
            tax_treatment=None,
            high_precision=None
    ):
        """ Inits an instance of `Forecaster`. """
        # Set up instance:
        super().__init__(high_precision=high_precision)
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

    def _get_attr_recursive(self, name, memo=None):
        """ Get an attribute based on a dot-delimited identifier.

        If the first element of `name` is an optional parameter
        (e.g. `scenario`), then if that parameter hasn't been explicitly
        provided this method will build the parameter via
        `build_param`.

        Example:
            `forecaster._get_attr_recursive('settings.initial_year')`
            Returns the value of `forecaster.settings.initial_year`

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

    def run_forecast(self, people, accounts, debts, scenario=None):
        """ Generates a `Forecast` object.

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
            scenario (Scenario): A `Scenario` defining a sequences of
                returns for different asset classes, as well as
                inflation and other values.
                Optional. If not provided, the instance's `scenario`
                attribute will be used. This arg is provided primarily
                to make generating Monte Carlo simulations easier.

        Returns:
            Forecast: A forecast of the plannees income, savings,
            and withdrawals over the years.
        """
        # We don't want to mutate the inputs, so create copies:
        memo = {}
        # Replace `self.scenario` in args with passed `scenario`:
        if scenario is not None and self.scenario is not None:
            memo = _replace_deepcopy_memo(self.scenario, scenario)
        people = deepcopy(people, memo=memo)
        accounts = deepcopy(accounts, memo=memo)
        debts = deepcopy(debts, memo=memo)

        # The format for `memo` is different in `get_param`.
        # Whereas `deepcopy` uses `id(obj)` for keys, `get_param` uses
        # the str-valued name of each parameter for keys.
        # So clear `memo` for sharing between params.
        memo.clear()
        # Build Scenario first so that we have access to initial_year:
        if scenario is None:  # Don't overwrite passed `scenario` arg
            scenario = self.get_param(Parameter.SCENARIO, memo=memo)
        # If `scenario` was passed in, remember it while copying:
        else:
            memo[str(Parameter.SCENARIO)] = scenario
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
            people=people,
            high_precision=self.high_precision)
        living_expenses_forecast = LivingExpensesForecast(
            initial_year=initial_year,
            people=people,
            living_expenses_strategy=living_expenses_strategy,
            high_precision=self.high_precision)
        saving_forecast = SavingForecast(
            initial_year=initial_year,
            retirement_accounts=accounts,
            debt_accounts=debts,
            transaction_strategy=saving_strategy,
            high_precision=self.high_precision)
        withdrawal_forecast = WithdrawalForecast(
            initial_year=initial_year,
            people=people,
            accounts=accounts,
            transaction_strategy=withdrawal_strategy,
            high_precision=self.high_precision)
        tax_forecast = TaxForecast(
            initial_year=initial_year,
            people=people,
            tax_treatment=tax_treatment,
            high_precision=self.high_precision)

        # With these SubForecasts defined, building Forecast is trivial:
        forecast = Forecast(
            income_forecast=income_forecast,
            living_expenses_forecast=living_expenses_forecast,
            saving_forecast=saving_forecast,
            withdrawal_forecast=withdrawal_forecast,
            tax_forecast=tax_forecast,
            scenario=scenario,
            high_precision=self.high_precision)

        # Forecasts run automatically on init, so we're done!
        return forecast

    def build_param(
            self, param_name, *args,
            param_type=None, memo=None, _special_builder=True, **kwargs):
        """ Builds a parameter based on settings and explicit args.

        This method does not set any attributes of `Forecaster`, it only
        builds an object and returns it.

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
            # attribute of the `Forecaster` object:
            for key, value in default_values.items():
                default_values[key] = self._get_attr_recursive(value, memo=memo)
            # If any values have been provided explicitly, override
            # the defaults with that:
            default_values.update(kwargs)
            kwargs = default_values
        # Build a new object (note that we don't set the corresponding
        # attribute of Forecaster; if this is called again, we'll build
        # a new object)
        if param_type is None:
            param_type = self.default_types[param_name]
        # Pass `high_precision` as a kwarg if the type supports it:
        is_high_precision_type = any(
            issubclass(param_type, high_precision_type)
            for high_precision_type in HIGHPRECISIONTYPES)
        if is_high_precision_type and 'high_precision' not in kwargs:
            kwargs['high_precision'] = self.high_precision
        param = param_type(*args, **kwargs)
        memo[param_name] = param
        return param

    def get_param(self, param_name, memo=None):
        """ Gets a parameter, builds one if none is explicitly provided.

        If a parameter has been explicitly assigned to this `Forecaster`
        instance then that object is returned. Otherwise, this method
        calls `build_param` to build it dynamically and returns it
        without setting any attributes of the `Forecaster` object.

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
        param_name = str(param_name)
        explicit_attr = getattr(self, param_name)
        # If the attribute isn't provided, try to build one:
        if explicit_attr is None:
            explicit_attr = self.build_param(param_name, memo=memo)

        # We'll try to convert strings to numeric types below, but for
        # any other type we're already done:
        if not isinstance(explicit_attr, str):
            return explicit_attr

        # Try to convert strings to numeric types:
        try:
            # Numerical types can be cast to float (if not, an exception
            # will bring us to the catch block and return the str value)
            float_attr = float(explicit_attr)
        except ValueError: # Can't convert from a str value to float
            # If we can't convert to a numerical type, use the str:
            return explicit_attr

        # If the number is losslessly representable as an int, use that:
        int_attr = int(float_attr)
        if float_attr == int_attr:
            return int_attr

        # Otherwise, if this is a true float, try to convert to
        # a high-precision numerical type if appropriate:
        if self.high_precision is not None:
            try:
                return self.high_precision(explicit_attr)
            # pylint: disable=bare-except
            # We don't know what kind of exception the high-precision
            # conversion method will throw (e.g. `Decimal` can throw
            # `decimal.InvalidOperation`, whereas `numpy` uses different
            # exceptions). So a bare except is necessary:
            except:
                return self.high_precision(float_attr)
            # pylint: enable=bare-except
        # Use a float value if no conversion is possible:
        return float_attr

    def set_param(
            self, param_name, *args,
            param_type=None, memo=None, **kwargs):
        """ Builds a parameter and sets the corresponding attribute.

        This is a convenience method that calls `build_param` and
        sets the result as the value of the corresponding attribute of
        this `Forecaster` object.

        Note that by calling this method, the resulting object will be
        used without modification by `run_forecast` even if the
        `settings` object changes. You can un-set the parameter by
        assigning `None` to that attribute.

        This method does not set any attributes of `Forecaster`, it only
        builds an object and returns it.

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
        param_name = str(param_name)
        param = self.build_param(
            param_name, *args, param_type=param_type, memo=memo, **kwargs)
        setattr(self, param_name, param)

    def build_allocation_strategy(self, *args, **kwargs):
        """ Convenience method to build an allocation strategy.

        Any arguments are passed on to AllocationStrategy.__init__. Any
        arguments that aren't passed explicitly to this function are
        instead pulled from the `Forecaster` instance's `settings`
        attribute.

        The reason this specific object gets its own method is that
        client code will likely need to call it to initialize `Account`
        objects. In the future, we may provide similar methods for
        other parameters.
        """
        return self.build_param(
            Parameter.ALLOCATION_STRATEGY, AllocationStrategy, *args,
            _special_builder=False, **kwargs)

    def sample(self, *args, sampler=None, num_samples=None, **kwargs):
        """ Yields `num_samples` forecasts based on a sampled scenarios.

        `sampler` can be any iterable that yields `Scenario` objects,
        such as a list of `Scenario` objects or an instance of
        `ScenarioSampler`. If not provided, a key-value will be read
        from `settings`.

        If `sampler` could be a key for a `ScenarioSampler` method, or a
        reference to such a method, then this method will attempt to
        instantiate a `ScenarioSampler` object (and will pass `sampler`
        as the `sampler` init arg). This will be attempted if `sampler`
        is hashable (e.g. a str) or callable; if instantiation fails, no
        exception will be raised and the method will go on to attempt to
        iterate over `sampler`.

        If a non-empty `sampler_kwargs` is provided, or if `sampler` is
        read from `settings`, it is assumed that the caller intended
        this method to instantiate a `ScenarioSampler`. In that case,
        `sampler` will be passed to `ScenarioSampler.__init__`
        regardless of its value, and will raise an exception on failure.

        **NOTE**: It is a good idea to ensure that the `scenario`
        attribute of this `Forecaster` is the same object that is
        stored as the `scenario` attribute of any `Person` objects (or
        which is used by the `rate_callable` attribute of any `Account`
        objects). You can do this by passing it as the `scenario` arg at
        init time to `Forecaster`. That scenario won't be used in any
        samples, but this is needed to allow `Forecaster` to replace it

        Arguments:
            args (list[Any]): Positional arguments are
                passed to `run_forecast`. Must provide at least as many
                arguments as `run_forecast` expects.
            sampler (str | Callable | Hashable | ScenarioSampler |
                Iterable[Scenario] | None): A `registered_method_named`
                of `ScenarioSampler`, or a key for such a method, or any
                iterable of Scenario objects (e.g. a `ScenarioSampler`
                object).
                Optional. If not provided, a value will be read from
                `settings`.
            num_samples (int | None): The number of forecasts to
                generate. Optional. If not provided, a value will be
                read from `settings`.
            kwargs (dict[str: Any]): Any remaining keyword
                arguments will be passed to `ScenarioSampler` at init.
                Optional. If provided (and non-empty), `sampler` must be
                passable to `ScenarioSampler` as the first argument.

        Raises:
            (KeyError): `sampler` is not a valid `ScenarioSampler key.
                A valid key is expected when `sampler_kwargs` is passed.
            (ValueError): `run_forecast_args` does not have enough
                values to unpack.
        """
        # If `sampler` looks like a key or a method, or if the user has
        # passed kwargs for sampler's init, build a `ScenarioSampler`:
        if (
                sampler is None or  # building ScenarioSampler from settings
                isinstance(sampler, (str, Hashable)) or  # maybe a key?
                callable(sampler) or  # maybe a method?
                kwargs):  # user intends to init ScenarioSampler
            try:
                # We expose `sampler` and `num_samples` for convenience;
                # bundle them up with other `ScenarioSampler` args:
                sampler_kwargs = dict(kwargs)
                sampler_kwargs.update(
                    {'sampler': sampler, 'num_samples': num_samples})
                # Build a `ScenarioSampler` based on passed args and
                # falling back to `settings` for any missing args:
                # (A side-benefit of this approach is that it passes
                # `high_precision if needed`)
                sampler = self.build_param(
                    Parameter.SCENARIO_SAMPLER, **sampler_kwargs)
            except KeyError as err:
                # If the user passed `scenario_kwargs`, strictly enforce
                # instantiation of a ScenarioSampler. Otherwise, simply
                # continue on to try to sample from `sampler`:
                if kwargs or sampler is None:
                    raise KeyError(
                        str(sampler) + ' is not a valid ScenarioSampler key. ' +
                        'A valid key is expected when sampler_kwargs is passed'
                    ) from err
        # Otherwise, treat `sampler` as an iterable
        elif num_samples is not None:
            # Limit iterable `sampler` to `num_samples` elements:
            sampler = islice(sampler, num_samples)
        # Generate a `Forecast` for each scenario:
        # (Start by unpacking `run_forecast` args for Pylint's sake.
        # Raises `ValueError` if insufficient arguments)
        (people, accounts, debts, *other_args) = args
        for scenario in sampler:  # Raises TypeError if sampler not iterable
            yield self.run_forecast(
                people, accounts, debts, *other_args, scenario=scenario)

def _replace_deepcopy_memo(original, replacement, memo=None):
    """ Returns a memo dict that replaces `original` with `replacement`. """
    # Avoid mutating default value:
    if memo is None:
        memo = {}
    # Don't recurse onto entities already in `memo`, to avoid infinite
    # recursion.
    elif id(original) in memo:
        return memo
    # deepcopy maps the id of the original object to a copied instance.
    # We want to replace the copied instance with `replacement`:
    memo[id(original)] = replacement
    # Recurse onto attributes of the original:
    if hasattr(original, '__dict__'):
        for name in original.__dict__:
            # Replace with the corresponding attribute of the
            # replacement, if it exists
            if (
                    hasattr(replacement, '__dict__') and
                    name in replacement.__dict__):
                memo.update(_replace_deepcopy_memo(
                    getattr(original, name), getattr(replacement, name)))
    return memo
