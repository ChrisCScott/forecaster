""" Unit tests for `Forecaster`. """

import unittest
import collections
from copy import copy, deepcopy
from decimal import Decimal
from forecaster import (
    Settings, Tax, Person, Account, Debt, Scenario,
    LivingExpensesStrategy, TransactionStrategy,
    AllocationStrategy, DebtPaymentStrategy, Forecaster, Parameter)


class TestForecaster(unittest.TestCase):
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
        self.settings.living_expenses_base_amount = Decimal(1000)

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
            gross_income=Decimal(10000),
            raise_rate=Decimal(0),
            spouse=None,
            tax_treatment=self.tax_treatment)
        # An account with $1000 in it (and no interest)
        self.account = Account(
            owner=self.person,
            balance=Decimal(1000))
        # A debt with a $100 balance (and no interest)
        self.debt = Debt(
            owner=self.person,
            balance=Decimal(100))

        # Init a Forecaster object here for convenience:
        self.forecaster = self.forecaster_type(settings=self.settings)

    def assertEqual_dict(self, first, second, msg=None, memo=None):
        """ Extends equality testing for dicts with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # For dicts, first confirm they represent the same keys:
        # (The superclass can handle this)
        if first.keys() != second.keys():
            super().assertEqual(first, second)
        # Then recursively check each pair of values:
        for key in first:
            self.assertEqual(first[key], second[key], msg=msg, memo=memo)

    def assertEqual_list(self, first, second, msg=None, memo=None):
        """ Extends equality testing for lists with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # First confirm that they have the same length.
        if len(first) != len(second):
            super().assertEqual(first, second)
        # Then iterate over the elements in sequence:
        for first_value, second_value in zip(first, second):
            self.assertEqual(first_value, second_value, msg=msg, memo=memo)

    def assertEqual_set(self, first, second, msg=None, memo=None):
        """ Extends equality testing for sets with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # First confirm that they have the same length.
        if len(first) != len(second):
            super().assertEqual(first, second, msg=msg)
        # For sets or other unordered iterables, we can't rely on
        # `in` (because complex objects might not have equality or
        # hashing implemented beyond the standard id()
        # implementation), so we want to test each element in one
        # set against every element in the other set.
        for val1 in first:
            match = False
            for val2 in second:
                try:
                    # Each pair of compared objects is automatically
                    # added to the memo, so make a copy (which will
                    # be discarded if the objects are not equal).
                    memo_copy = copy(memo)
                    self.assertEqual(val1, val2, msg=msg, memo=memo_copy)
                except AssertionError:
                    # If we didn't find a match, advance to the next
                    # value in second and try that.
                    continue
                # If we did find a match, record that fact and
                # advance to the next value in second.
                match = True
                memo.update(memo_copy)
                break
            if not match:
                # If we couldn't find a match, the sets are not
                # equal; the entire test should fail.
                raise AssertionError(
                    str(first) + ' != ' + str(second))

    def assertEqual_complex(self, first, second, msg=None, memo=None):
        """ Extends equality testing for complex objects. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # For complicated objects, recurse onto the attributes dict:
        self.assertEqual(
            first.__dict__, second.__dict__, msg=msg, memo=memo)

    def assertEqual(self, first, second, msg=None, memo=None):
        """ Tests complicated class instances for equality.

        This method is used (instead of __eq__) because equality
        semantics are only needed for testing code and can mess up
        things like set membership, require extensive (and inefficient)
        comparisons, and/or can result in infinite recursion.
        """
        # We add a memo argument to avoid recursion. We don't pass it
        # to the superclass, so pylint's objection isn't helpful.
        # pylint: disable=arguments-differ

        # The memo dict maps each object to the set of objects that it's
        # been compared to. If they've been compared, that means that we
        # don't need to re-evaluate their equality - if they're unequal,
        # that'll be discovered at a higher level of recursion:
        if memo is None:
            memo = collections.defaultdict(set)
        if id(second) in memo[id(first)]:
            # We've previously compared these objects and found them to
            # be equal, so return without failing.
            return
        else:
            memo[id(first)].add(id(second))
            memo[id(second)].add(id(first))

        try:
            # If these are equal under ordinary comparison, accept that
            # and don't so any further special testing.
            super().assertEqual(first, second, msg=msg)
            return
        except AssertionError as error:
            # If the superclass assertEqual doesn't find equality, run
            # a few additional equality tests based on object type:
            # 1) Dicts; keys and values both need to be checked.
            # 2) Ordered iterables; values need to be checked in order.
            # 3) Unordered iterables; check values for membership.
            # 4) Complex objects; compare attributes via __dict__.

            # Most of these tests won't work if the objects are
            # different types, and we don't deal with the case anyways.
            # In that case, accept the error and raise it on up.
            if (
                    not isinstance(first, type(second)) and
                    not isinstance(second, type(first))
            ):
                raise error
            elif isinstance(first, dict):
                self.assertEqual_dict(first, second, msg=msg, memo=memo)
            elif isinstance(first, collections.abc.Sequence):
                self.assertEqual_list(first, second, msg=msg, memo=memo)
            elif isinstance(first, collections.abc.Iterable):
                self.assertEqual_set(first, second, msg=msg, memo=memo)
            elif hasattr(first, '__dict__'):
                self.assertEqual_complex(first, second, msg=msg, memo=memo)
            else:
                # If none of our special tests apply, accept the error.
                raise error

    def assertNotEqual(self, first, second, msg=None):
        """ Overloaded to test non-equality of complex objects. """
        try:
            self.assertEqual(first, second, msg=msg)
        except AssertionError:
            # We want assertEqual to throw an error (since we're
            # expecting non-equality)
            return
        # Raise a suitable error if the equality test didn't fail:
        raise AssertionError(str(first) + ' == ' + str(second))

    def test_assertEqual(self):  # pylint: disable=invalid-name
        """ Tests overloaded TestForecaster.assertEqual. """
        # Compare an object to itself
        person1 = self.person
        self.assertEqual(person1, self.person)
        # Compare two idential instances of an object:
        person2 = deepcopy(person1)
        self.assertEqual(person1, person2)
        # Compare two instances of an object that differ only in a
        # complicated attribute. (Simple case: set it to None)
        person2.tax_treatment = None
        self.assertNotEqual(person1, person2)

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
                base_amount=Decimal(500), inflation_adjust=None),
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
            Decimal(1500),
            places=2)
        # Gross income should be unchanged at $10,000:
        self.assertAlmostEqual(
            forecast.income_forecast.gross_income,
            Decimal(10000),
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


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
