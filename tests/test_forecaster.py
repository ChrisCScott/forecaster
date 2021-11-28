""" Unit tests for `Forecaster`. """

import unittest
from decimal import Decimal
from forecaster import (
    Settings, Tax, Person, Account, Debt, Scenario,
    LivingExpensesStrategy, TransactionStrategy,
    AllocationStrategy, DebtPaymentStrategy, Forecaster, Parameter)
from tests.forecaster_tester import ForecasterTester

class TestForecaster(ForecasterTester):
    """ Tests Forecaster. """

    def setUp(self):
        """ Builds default strategies, persons, etc. """
        # Use a default settings object:
        # (This is conditional so that subclasses can assign their own
        # settings object before calling super().setUp())
        if not hasattr(self, 'settings'):
            self.settings = Settings()

        # To simplify tests, modify Settings so that forecasts are
        # just 2 years with easy-to-predict contributions ($1000/yr)
        self.settings.num_years = 2
        self.settings.living_expenses_strategy = (
            LivingExpensesStrategy.strategy_const_contribution)
        self.settings.living_expenses_base_amount = 1000

        # Allow subclasses to use subclasses of Forecaster by assigning
        # to forecaster_type
        if not hasattr(self, 'forecaster_type'):
            self.forecaster_type = Forecaster

        # Build default `SubForecast` inputs based on `settings`:
        self.initial_year = self.settings.initial_year
        self.scenario = Scenario(
            inflation=self.settings.inflation,
            stock_return=self.settings.stock_return,
            bond_return=self.settings.bond_return,
            other_return=self.settings.other_return,
            management_fees=self.settings.management_fees,
            initial_year=self.settings.initial_year,
            num_years=self.settings.num_years)
        self.living_expenses_strategy = LivingExpensesStrategy(
            strategy=self.settings.living_expenses_strategy,
            base_amount=self.settings.living_expenses_base_amount,
            rate=self.settings.living_expenses_rate,
            inflation_adjust=self.scenario.inflation_adjust)
        self.saving_strategy = TransactionStrategy(
            strategy=self.settings.saving_strategy,
            weights=self.settings.saving_weights)
        self.withdrawal_strategy = TransactionStrategy(
            strategy=self.settings.withdrawal_strategy,
            weights=self.settings.withdrawal_weights)
        self.allocation_strategy = AllocationStrategy(
            strategy=self.settings.allocation_strategy,
            min_equity=self.settings.allocation_min_equity,
            max_equity=self.settings.allocation_max_equity,
            target=self.settings.allocation_target,
            standard_retirement_age=(
                self.settings.allocation_std_retirement_age),
            risk_transition_period=self.settings.allocation_risk_trans_period,
            adjust_for_retirement_plan=(
                self.settings.allocation_adjust_retirement))
        self.debt_payment_strategy = DebtPaymentStrategy(
            strategy=self.settings.debt_payment_strategy)
        self.tax_treatment = Tax(
            tax_brackets=self.settings.tax_brackets,
            personal_deduction=self.settings.tax_personal_deduction,
            credit_rate=self.settings.tax_credit_rate,
            inflation_adjust=self.scenario.inflation_adjust)

        # Now build some Ledger objects to test against:
        # A person making $10,000/yr
        self.person = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2040",
            gross_income=10000,
            raise_rate=0,
            spouse=None,
            tax_treatment=self.tax_treatment)
        # An account with $1000 in it (and no interest)
        self.account = Account(
            owner=self.person,
            balance=1000)
        # A debt with a $100 balance (and no interest)
        self.debt = Debt(
            owner=self.person,
            balance=100)

        # Init a Forecaster object here for convenience:
        self.forecaster = self.forecaster_type(settings=self.settings)

    def setUp_decimal(self):
        """ Builds default strategies/persons/etc. with Decimal inputs. """
        # pylint: disable=invalid-name
        # This name is based on `setUp`, which doesn't follow Pylint's rules
        # pylint: enable=invalid-name

        # Use a default settings object:
        # (This is conditional so that subclasses can assign their own
        # settings object before calling super().setUp())
        if not hasattr(self, 'settings'):
            self.settings = Settings()

        # To simplify tests, modify Settings so that forecasts are
        # just 2 years with easy-to-predict contributions ($1000/yr)
        self.settings.num_years = 2
        self.settings.living_expenses_strategy = (
            LivingExpensesStrategy.strategy_const_contribution)
        self.settings.living_expenses_base_amount = Decimal(1000)

        # Allow subclasses to use subclasses of Forecaster by assigning
        # to forecaster_type
        if not hasattr(self, 'forecaster_type'):
            self.forecaster_type = Forecaster

        # Build default `SubForecast` inputs based on `settings`:
        self.initial_year = self.settings.initial_year
        self.scenario = Scenario(
            inflation=Decimal(self.settings.inflation),
            stock_return=Decimal(self.settings.stock_return),
            bond_return=Decimal(self.settings.bond_return),
            other_return=Decimal(self.settings.other_return),
            management_fees=Decimal(self.settings.management_fees),
            initial_year=self.settings.initial_year,
            num_years=self.settings.num_years)
        self.living_expenses_strategy = LivingExpensesStrategy(
            strategy=self.settings.living_expenses_strategy,
            base_amount=Decimal(self.settings.living_expenses_base_amount),
            rate=Decimal(self.settings.living_expenses_rate),
            inflation_adjust=self.scenario.inflation_adjust)
        self.saving_strategy = TransactionStrategy(
            strategy=self.settings.saving_strategy,
            weights={
                year: Decimal(val) for (year, val) in
                self.settings.saving_weights.items()})
        self.withdrawal_strategy = TransactionStrategy(
            strategy=self.settings.withdrawal_strategy,
            weights={
                year: Decimal(val) for (year, val) in
                self.settings.withdrawal_weights.items()})
        self.allocation_strategy = AllocationStrategy(
            strategy=self.settings.allocation_strategy,
            min_equity=Decimal(self.settings.allocation_min_equity),
            max_equity=Decimal(self.settings.allocation_max_equity),
            target=Decimal(self.settings.allocation_target),
            standard_retirement_age=(
                self.settings.allocation_std_retirement_age),
            risk_transition_period=self.settings.allocation_risk_trans_period,
            adjust_for_retirement_plan=(
                self.settings.allocation_adjust_retirement))
        self.debt_payment_strategy = DebtPaymentStrategy(
            strategy=self.settings.debt_payment_strategy,
            high_precision=Decimal)
        self.tax_treatment = Tax(
            tax_brackets={
                year: {Decimal(lower): Decimal(upper)}
                for (year, vals) in self.settings.tax_brackets.items()
                for (lower, upper) in vals.items()},
            personal_deduction={
                year: Decimal(val) for (year, val) in
                self.settings.tax_personal_deduction.items()},
            credit_rate={
                year: Decimal(val) for (year, val) in
                self.settings.tax_credit_rate.items()},
            inflation_adjust=self.scenario.inflation_adjust,
            high_precision=Decimal)

        # Now build some Ledger objects to test against:
        # A person making $10,000/yr
        self.person = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2040",
            gross_income=Decimal(10000),
            raise_rate=Decimal(0),
            spouse=None,
            tax_treatment=self.tax_treatment,
            high_precision=Decimal)
        # An account with $1000 in it (and no interest)
        self.account = Account(
            owner=self.person,
            balance=Decimal(1000),
            high_precision=Decimal)
        # A debt with a $100 balance (and no interest)
        self.debt = Debt(
            owner=self.person,
            balance=Decimal(100),
            high_precision=Decimal)

        # Init a Forecaster object here for convenience:
        self.forecaster = self.forecaster_type(
            settings=self.settings,
            high_precision=Decimal)

    def test_init_default(self):
        """ Tests Forecaster.__init__ with default parameters. """
        self.forecaster = Forecaster()
        # For most params, not being passed means they should be None:
        self.assertEqual(
            self.forecaster.living_expenses_strategy, None)
        self.assertEqual(
            self.forecaster.saving_strategy, None)
        self.assertEqual(
            self.forecaster.withdrawal_strategy, None)
        self.assertEqual(
            self.forecaster.allocation_strategy, None)
        # For two of the params, they should be initialized to whatever
        # is provided by default by the Settings class:
        self.assertEqual(self.forecaster.settings, Settings())

    def test_build_living_exp_strat(self):
        """ Test Forecaster.build_param for living_expenses_strategy. """
        param = self.forecaster.get_param(Parameter.LIVING_EXPENSES_STRATEGY)
        self.assertEqual(param, self.living_expenses_strategy)

    def test_build_saving_strat(self):
        """ Test Forecaster.build_param for contribution_strategy. """
        param = self.forecaster.get_param(Parameter.SAVING_STRATEGY)
        self.assertEqual(param, self.saving_strategy)

    def test_build_withdraw_strat(self):
        """ Test Forecaster.build_param for withdrawal_strategy. """
        param = self.forecaster.get_param(Parameter.WITHDRAWAL_STRATEGY)
        self.assertEqual(param, self.withdrawal_strategy)

    def test_build_allocation_strat(self):
        """ Test Forecaster.build_param for allocation_strategy. """
        param = self.forecaster.get_param(Parameter.ALLOCATION_STRATEGY)
        self.assertEqual(param, self.allocation_strategy)

    def test_build_tax_treatment(self):
        """ Test Forecaster.build_param for tax_treatment. """
        param = self.forecaster.get_param(Parameter.TAX_TREATMENT)
        self.assertEqual(param, self.tax_treatment)

    def test_run_forecast_basic(self):
        """ Test Forecaster.run_forecast with simple arguments. """
        # Run a simple forecast with $10,000 income, $500 in annual
        # contributions, and $1000 in starting balances with no growth:
        self.forecaster = Forecaster(
            living_expenses_strategy=LivingExpensesStrategy(
                strategy=LivingExpensesStrategy.strategy_const_contribution,
                base_amount=500, inflation_adjust=None),
            settings=self.settings)
        forecast = self.forecaster.run_forecast(
            people={self.person},
            accounts={self.account},
            debts={})

        # Test that it starts and ends in the right place and that
        # income and total balance (principal) are correct
        self.assertEqual(
            forecast.scenario, self.scenario)
        # Pylint has trouble with attributes added by metaclass
        # pylint: disable=no-member
        self.assertEqual(
            len(forecast.principal_history), self.scenario.num_years)
        # pylint: enable=no-member

        # Test that the $500 in contributions have been added to the
        # initial $1000 principal by the start of year 2:
        self.assertAlmostEqual(
            forecast.principal,
            1500,
            places=2)
        # Gross income should be unchanged at $10,000:
        self.assertAlmostEqual(
            forecast.income_forecast.gross_income,
            10000,
            places=2)

    def test_run_forecast_mutation(self):
        """ Test that Forecaster.run_forecast doesn't mutate arguments. """
        # Run a forecast and check whether the inputs were mutated:
        forecast = self.forecaster.run_forecast(
            people={self.person},
            accounts={self.account},
            debts={self.debt})
        # The originally-provided Person's history dicts should have
        # length 1 (since they haven't been mutated). They should be
        # length 2 for the Person held by the Forecast.
        # pylint: disable=no-member
        self.assertEqual(len(self.person.gross_income_history), 1)
        # pylint: enable=no-member
        self.assertEqual(
            len(next(iter(forecast.people)).gross_income_history), 2)

    def test_decimal(self):
        """ Test Forecaster.run_forecast with Decimal arguments. """
        # Convert values to Decimal:
        self.setUp_decimal()

        # This test is based on test_run_forecast_basic

        # Run a simple forecast with $10,000 income, $500 in annual
        # contributions, and $1000 in starting balances with no growth:
        living_expenses_strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_const_contribution,
            base_amount=Decimal(500), inflation_adjust=None,
            high_precision=Decimal)
        self.forecaster = Forecaster(
            living_expenses_strategy=living_expenses_strategy,
            settings=self.settings,
            high_precision=Decimal)
        forecast = self.forecaster.run_forecast(
            people={self.person},
            accounts={self.account},
            debts={})

        # Test that it starts and ends in the right place and that
        # income and total balance (principal) are correct
        self.assertEqual(
            forecast.scenario, self.scenario)
        # Pylint has trouble with attributes added by metaclass
        # pylint: disable=no-member
        self.assertEqual(
            len(forecast.principal_history), self.scenario.num_years)
        # pylint: enable=no-member

        # Test that the $500 in contributions have been added to the
        # initial $1000 principal by the start of year 2:
        self.assertAlmostEqual(
            forecast.principal,
            Decimal(1500),
            places=2)
        # Gross income should be unchanged at $10,000:
        self.assertAlmostEqual(
            forecast.income_forecast.gross_income,
            Decimal(10000),
            places=2)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
