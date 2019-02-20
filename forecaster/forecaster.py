''' This module provides classes for creating and managing Forecasts. '''

from copy import copy, deepcopy
from enum import Enum
from forecaster.forecast import (
    Forecast, IncomeForecast, LivingExpensesForecast, ReductionForecast,
    ContributionForecast, WithdrawalForecast, TaxForecast)
from forecaster.tax import Tax
from forecaster.strategy import (
    LivingExpensesStrategy, AccountTransactionStrategy,
    DebtPaymentStrategy, AllocationStrategy)
from forecaster.scenario import Scenario
from forecaster.settings import Settings


# The `Forecaster` class makes frequent reference to the names of
# parameters. Rather than hard-code these strings, it's better practice
# to define them here as an enum.
class Parameter(Enum):
    """ TODO """
    SCENARIO = "scenario"
    LIVING_EXPENSES_STRATEGY = "living_expenses_strategy"
    DEBT_PAYMENT_STRATEGY = "debt_payment_strategy"
    CONTRIBUTION_STRATEGY = "contribution_strategy"
    WITHDRAWAL_STRATEGY = "withdrawal_strategy"
    ALLOCATION_STRATEGY = "allocation_strategy"
    TAX_TREATMENT = "tax_treatment"

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
    Parameter.SCENARIO: {
        "inflation": "inflation",
        "stock_return": "stock_return",
        "bond_return": "bond_return",
        "other_return": "other_return",
        "management_fees": "management_fees",
        "num_years": "num_years"},
    Parameter.LIVING_EXPENSES_STRATEGY: {
        "strategy": "living_expenses_strategy",
        "base_amount": "living_expenses_base_amount",
        "rate": "living_expenses_rate",
        "inflation_adjust": "living_expenses_inflation_adjust"},
    Parameter.CONTRIBUTION_STRATEGY: {
        "strategy": "contribution_strategy",
        "base_amount": "contribution_base_amount",
        "rate": "contribution_rate",
        "reinvestment_rate": "contribution_reinvestment_rate",
        "inflation_adjusted": "withdrawal_inflation_adjusted"},
    Parameter.WITHDRAWAL_STRATEGY: {
        "strategy": "withdrawal_strategy",
        "base_amount": "withdrawal_base_amount",
        "rate": "withdrawal_rate",
        "reinvestment_rate": "withdrawal_reinvestment_rate",
        "inflation_adjusted": "withdrawal_inflation_adjusted"},
    Parameter.ALLOCATION_STRATEGY: {
        "strategy": "allocation_strategy",
        "target": "allocation_target",
        "min_equity": "allocation_min_equity",
        "max_equity": "allocation_max_equity",
        "standard_retirement_age": "allocation_std_retirement_age",
        "risk_transition_period": "allocation_risk_trans_period",
        "adjust_for_retirement_plan": "allocation_adjust_retirement"},
    Parameter.DEBT_PAYMENT_STRATEGY: {
        "strategy": "debt_payment_strategy",
        "timing": "debt_payment_timing"},
    Parameter.TAX_TREATMENT: {
        "tax_brackets": "tax_brackets",
        "personal_deduction": "tax_personal_deduction",
        "credit_rate": "tax_credit_rate",
        # See build_tax_treatment for special logic dealing with this:
        #  "inflation_adjust": None,
        "payment_timing": "tax_payment_timing"}
}

# This maps each of the above parameters to a type:
DEFAULTTYPES = {
    Parameter.SCENARIO: Scenario,
    Parameter.LIVING_EXPENSES_STRATEGY: LivingExpensesStrategy,
    Parameter.DEBT_PAYMENT_STRATEGY: DebtPaymentStrategy,
    Parameter.CONTRIBUTION_STRATEGY: AccountTransactionStrategy,
    Parameter.WITHDRAWAL_STRATEGY: AccountTransactionStrategy,
    Parameter.ALLOCATION_STRATEGY: AllocationStrategy,
    Parameter.TAX_TREATMENT: Tax}

# This maps certain parameters that need special init logic to
# the method name that provides that logic.
DEFAULTBUILDERS = {
    Parameter.TAX_TREATMENT: "build_tax_treatment"}

class Forecaster(object):
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
            settings=Settings,
            scenario=None,
            living_expenses_strategy=None,
            debt_payment_strategy=None,
            contribution_strategy=None,
            withdrawal_strategy=None,
            tax_treatment=None
    ):
        """ Inits an instance of `Forecaster`. """
        # Set up instance:
        super().__init__()
        self.default_values = copy(DEFAULTVALUES)
        self.default_types = copy(DEFAULTTYPES)
        self.default_builders = copy(DEFAULTBUILDERS)
        # Store args as attributes:
        self.settings = settings
        self.scenario = scenario
        self.living_expenses_strategy = living_expenses_strategy
        self.debt_payment_strategy = debt_payment_strategy
        self.contribution_strategy = contribution_strategy
        self.withdrawal_strategy = withdrawal_strategy
        self.tax_treatment = tax_treatment

    def run_forecast(self, people, accounts, debts):
        """ TODO """
        # We don't want to mutate the inputs, so create copies:
        memo = {}
        people = deepcopy(people, memo=memo)
        accounts = deepcopy(accounts, memo=memo)
        debts = deepcopy(debts, memo=memo)

        # Build Scenario first so that we have access to initial_year:
        scenario = self.get_param(Parameter.SCENARIO)
        initial_year = scenario.initial_year  # extract for convenience

        # Retrieve the necessary strategies for building SubForecasts:
        living_expenses_strategy = self.get_param(
            Parameter.LIVING_EXPENSES_STRATEGY)
        debt_payment_strategy = self.get_param(
            Parameter.DEBT_PAYMENT_STRATEGY)
        contribution_strategy = self.get_param(
            Parameter.CONTRIBUTION_STRATEGY)
        withdrawal_strategy = self.get_param(
            Parameter.WITHDRAWAL_STRATEGY)
        tax_treatment = self.get_param(
            Parameter.TAX_TREATMENT)

        # Now build each of the SubForecast objects required by Forecast
        income_forecast = IncomeForecast(
            initial_year=initial_year,
            people=people)
        living_expenses_forecast = LivingExpensesForecast(
            initial_year=initial_year,
            people=people,
            living_expenses_strategy=living_expenses_strategy)
        reduction_forecast = ReductionForecast(
            initial_year=initial_year,
            debts=debts,
            debt_payment_strategy=debt_payment_strategy)
        contribution_forecast = ContributionForecast(
            initial_year=initial_year,
            accounts=accounts,
            account_transaction_strategy=contribution_strategy)
        withdrawal_forecast = WithdrawalForecast(
            initial_year=initial_year,
            people=people,
            accounts=accounts,
            account_transaction_strategy=withdrawal_strategy)
        tax_forecast = TaxForecast(
            initial_year=initial_year,
            people=people,
            tax_treatment=tax_treatment)

        # With these SubForecasts defined, building Forecast is trivial:
        forecast = Forecast(
            income_forecast=income_forecast,
            living_expenses_forecast=living_expenses_forecast,
            reduction_forecast=reduction_forecast,
            contribution_forecast=contribution_forecast,
            withdrawal_forecast=withdrawal_forecast,
            tax_forecast=tax_forecast,
            scenario=scenario)

        # Forecasts run automatically on init, so we're done!
        return forecast

    def build_param(self, param_name, param_type, *args, _special_builder=True, **kwargs):
        """ TODO """
        # If there's special logic for this parameter, use that instead:
        # (The special builder method can call this one by setting
        # `_special_builder` to False.)
        if _special_builder and param_name in self.default_builders:
            return getattr(
                self, self.default_builders[param_name])(*args, **kwargs)
        # For everything else, use the user-provided defaults and fill
        # in the gaps with the settings-provided defaults:
        if param_name in self.default_values:
            default_values = {
                key: getattr(self.settings, value)
                for key, value in DEFAULTVALUES[param_name]}
            default_values.update(kwargs)
            kwargs = default_values
        # Build a new object (note that we don't set the corresponding
        # attribute of Forecaster; if this is called again, we'll build
        # a new object)
        return param_type(*args, **kwargs)

    def get_param(self, param_name):
        """ TODO """
        explicit_attr = getattr(self, param_name)
        if explicit_attr is not None:
            return explicit_attr
        else:
            param_type = self.default_types[param_name]
            return self.build_param(param_name, param_type)

    def set_param(self, param_name, param_type, *args, **kwargs):
        """ TODO """
        param = self.build_param(param_name, param_type, *args, **kwargs)
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

    def build_tax_treatment(self, *args, **kwargs):
        """ Convenience method to build a Tax instance.

        Any arguments are passed on to Tax.__init__. Any arguments that
        aren't passed explicitly to this function are instead pulled
        from the `Forecaster` instance's `settings` attribute.

        The reason this specific object gets its own method is that
        client code will likely need to call it to initialize `Person`
        objects. In the future, we may provide similar methods for
        other parameters.
        """
        # Tax can take an inflation_adjust argument. This is a callable,
        # which Settings ordinarily does not represent. Intead, check
        # to see whether inflation_adjust was provided; if not, use
        # inflation_adjust from `scenario`
        if "inflation_adjust" not in kwargs:
            scenario = self.get_param(Parameter.SCENARIO)
            kwargs = copy(kwargs)
            kwargs["inflation_adjust"] = scenario.inflation_adjust
        return self.build_param(
            Parameter.TAX_TREATMENT, Tax, *args,
            _special_builder=False, **kwargs)
