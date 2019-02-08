""" Unit tests for `Forecaster`. """

import unittest
import collections
from copy import copy, deepcopy
from forecaster import (
    Settings, Tax, Person, Money, Account, Debt, Scenario,
    LivingExpensesStrategy, AccountTransactionStrategy,
    AllocationStrategy, DebtPaymentStrategy, Forecaster)


class TestForecaster(unittest.TestCase):
    """ Tests Forecaster. """

    # We need a lot of instance attributes because forecasts require
    # a lot of instance attributes.
    # pylint: disable=too-many-instance-attributes

    def setUp(self):
        """ Builds default strategies, persons, etc. """
        if not hasattr(self, 'settings'):
            self.settings = Settings()

        # These tests take a long time if we're building 100-year
        # forecasts in each one. Use short forecasts as a default:
        self.settings.num_years = 3

        self.initial_year = self.settings.initial_year
        self.scenario = Scenario(
            inflation=self.settings.inflation,
            stock_return=self.settings.stock_return,
            bond_return=self.settings.bond_return,
            other_return=self.settings.other_return,
            management_fees=self.settings.management_fees,
            initial_year=self.settings.initial_year,
            num_years=self.settings.num_years
        )
        self.contribution_strategy = LivingExpensesStrategy(
            strategy=self.settings.contribution_strategy,
            base_amount=self.settings.contribution_base_amount,
            rate=self.settings.contribution_rate,
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.transaction_in_strategy = AccountTransactionStrategy(
            strategy=self.settings.transaction_in_strategy,
            weights=self.settings.transaction_in_weights,
            timing=self.settings.transaction_in_timing
        )
        self.transaction_out_strategy = AccountTransactionStrategy(
            strategy=self.settings.transaction_out_strategy,
            weights=self.settings.transaction_out_weights,
            timing=self.settings.transaction_out_timing
        )

        # We use different target values for different strategies.
        if (
            # pylint: disable=E1101
            self.settings.allocation_strategy ==
            AllocationStrategy.strategy_n_minus_age.strategy_key
        ):
            target = self.settings.allocation_const_target
        elif (
            # pylint: disable=E1101
            self.settings.allocation_strategy ==
            AllocationStrategy.strategy_transition_to_const.strategy_key
        ):
            target = self.settings.allocation_trans_target
        self.allocation_strategy = AllocationStrategy(
            strategy=self.settings.allocation_strategy,
            min_equity=self.settings.allocation_min_equity,
            max_equity=self.settings.allocation_max_equity,
            target=target,
            standard_retirement_age=(
                self.settings.allocation_std_retirement_age),
            risk_transition_period=self.settings.allocation_risk_trans_period,
            adjust_for_retirement_plan=(
                self.settings.allocation_adjust_retirement)
        )
        self.debt_payment_strategy = DebtPaymentStrategy(
            strategy=self.settings.debt_payment_strategy,
            timing=self.settings.debt_payment_timing
        )
        self.tax_treatment = Tax(
            tax_brackets={self.initial_year: {0: 0}},
            personal_deduction={},
            credit_rate={},
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.person1 = Person(
            name=self.settings.person1_name,
            birth_date=self.settings.person1_birth_date,
            retirement_date=self.settings.person1_retirement_date,
            gross_income=self.settings.person1_gross_income,
            raise_rate=self.settings.person1_raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment,
            initial_year=self.initial_year
        )
        if self.settings.person2_name is None:
            self.person2 = None
        else:
            self.person2 = Person(
                name=self.settings.person2_name,
                birth_date=self.settings.person2_birth_date,
                retirement_date=self.settings.person2_retirement_date,
                gross_income=self.settings.person2_gross_income,
                raise_rate=self.settings.person2_raise_rate,
                spouse=self.person1,
                tax_treatment=None,
                initial_year=self.initial_year
            )
        # For testing convenience, set up a custom version of Person1
        # that changes the name but keeps the rest of the data the same.
        self.custom_person = Person(
            name='Test Name',
            birth_date=self.settings.person1_birth_date,
            retirement_date=self.settings.person1_retirement_date,
            gross_income=self.settings.person1_gross_income,
            raise_rate=self.settings.person1_raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment,
            initial_year=self.settings.initial_year
        )

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
        for i in range(0, len(first)):
            self.assertEqual(first[i], second[i], msg=msg, memo=memo)

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
        person1 = self.person1
        self.assertEqual(person1, person1)
        # Compare two idential instances of an object:
        person2 = deepcopy(person1)
        self.assertEqual(person1, person2)
        # Compare two instances of an object that differ only in a
        # complicated attribute. (Simple case: set it to None)
        person2.tax_treatment = None
        self.assertNotEqual(person1, person2)

    def test_init_default(self):
        """ Tests Forecaster.__init__ with default parameters.

        This method does not provide a settings parameter, so subclasses
        should be sure to override it if they change the behaviour of
        default init.
        """
        # Modify Settings to correspond to self.settings (since we
        # don't pass settings in explicitly in this test)
        Settings.num_years = 3
        forecaster = Forecaster()
        self.assertEqual(forecaster.person1, self.person1)
        self.assertEqual(forecaster.person2, self.person2)
        if self.person2 is not None:
            self.assertEqual(forecaster.people, {self.person1, self.person2})
        else:  # We don't add `None` to the `people` set.
            self.assertEqual(forecaster.people, {self.person1})
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertEqual(
            forecaster.contribution_strategy, self.contribution_strategy)
        self.assertEqual(
            forecaster.transaction_in_strategy, self.transaction_in_strategy)
        self.assertEqual(
            forecaster.transaction_out_strategy, self.transaction_out_strategy)
        self.assertEqual(
            forecaster.allocation_strategy, self.allocation_strategy)
        self.assertEqual(
            forecaster.debt_payment_strategy, self.debt_payment_strategy)
        self.assertEqual(forecaster.settings, Settings)
        self.assertEqual(forecaster.initial_year, Settings.initial_year)

    def test_init_custom_settings(self):
        """ Tests Forecaster.__init__ with custom settings. """
        self.settings.person1_name = self.custom_person.name
        forecaster = Forecaster(settings=self.settings)
        self.assertEqual(forecaster.person1, self.custom_person)
        self.assertEqual(forecaster.person2, self.person2)
        if self.person2 is not None:
            self.assertEqual(forecaster.people,
                             {forecaster.person1, forecaster.person2})
        else:  # We don't add `None` to the `people` set.
            self.assertEqual(forecaster.people, {forecaster.person1})
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertEqual(
            forecaster.contribution_strategy, self.contribution_strategy)
        self.assertEqual(
            forecaster.transaction_in_strategy, self.transaction_in_strategy)
        self.assertEqual(
            forecaster.transaction_out_strategy, self.transaction_out_strategy)
        self.assertEqual(
            forecaster.allocation_strategy, self.allocation_strategy)
        self.assertEqual(
            forecaster.debt_payment_strategy, self.debt_payment_strategy)
        self.assertEqual(forecaster.settings, self.settings)
        self.assertEqual(forecaster.initial_year, self.settings.initial_year)

    def test_init_custom_inputs(self):
        """ Tests Forecaster.__init__ with custom inputs. """
        forecaster = Forecaster(
            person1=self.custom_person, settings=self.settings)
        self.assertEqual(forecaster.person1, self.custom_person)
        self.assertEqual(forecaster.person2, self.person2)
        if self.person2 is not None:
            self.assertEqual(
                forecaster.people, {self.custom_person, self.person2})
        else:  # We don't add `None` to the `people` set.
            self.assertEqual(forecaster.people, {self.custom_person})
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertEqual(
            forecaster.contribution_strategy, self.contribution_strategy)
        self.assertEqual(
            forecaster.transaction_in_strategy, self.transaction_in_strategy)
        self.assertEqual(
            forecaster.transaction_out_strategy, self.transaction_out_strategy)
        self.assertEqual(
            forecaster.allocation_strategy, self.allocation_strategy)
        self.assertEqual(
            forecaster.debt_payment_strategy, self.debt_payment_strategy)
        self.assertEqual(forecaster.settings, self.settings)
        self.assertEqual(forecaster.initial_year, self.settings.initial_year)

        # Test init with custom initial year:
        initial_year = 1999
        forecaster = Forecaster(
            initial_year=initial_year, settings=self.settings)
        self.assertEqual(forecaster.initial_year, initial_year)
        self.assertEqual(forecaster.person1.initial_year, initial_year)
        if self.person2 is not None:
            self.assertEqual(forecaster.person2.initial_year, initial_year)
        for account in forecaster.assets.union(forecaster.debts):
            self.assertEqual(account.initial_year, initial_year)

    def test_add_person(self):
        """ Test Forecaster.add_person. """
        forecaster = Forecaster(settings=self.settings)
        people = copy(forecaster.people)
        person = forecaster.add_person('Test', 2000, retirement_date=2065)
        self.assertEqual(person, Person(
            self.initial_year, 'Test', 2000,
            retirement_date=2065,
            tax_treatment=forecaster.tax_treatment
        ))
        self.assertEqual(forecaster.people - people, {person})

    def test_add_asset(self):
        """ Test Forecaster.add_asset. """
        forecaster = Forecaster(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_asset()
        self.assertEqual(asset, Account(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year
        ))
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_debt(self):
        """ Test Forecaster.add_debt. """
        forecaster = Forecaster(settings=self.settings)
        debts = copy(forecaster.debts)
        debt = forecaster.add_debt()
        self.assertEqual(debt, Debt(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            minimum_payment=Money(0),
            savings_rate=self.settings.debt_savings_rate,
            accelerated_payment=self.settings.debt_accelerated_payment
        ))
        self.assertEqual(forecaster.debts - debts, {debt})

    def test_forecast(self):
        """ Tests Forecaster.forecast """
        # Run a simple forecast with $0 income and $0 balances:
        forecaster = Forecaster(settings=self.settings)
        forecaster.set_person1(gross_income=Money(0))
        forecaster.add_asset(owner=forecaster.person1, cls=Account)
        forecaster.add_debt(owner=forecaster.person1, cls=Debt)
        forecaster.set_person2(name=None)  # Remove person2, if present
        forecast = forecaster.forecast()
        # Test that it starts and ends in the right place and that
        # income and total balance (principal) are correct (i.e. $0)
        self.assertEqual(
            forecast.scenario.initial_year, forecaster.initial_year)
        self.assertEqual(
            len(forecast.principal), forecaster.scenario.num_years)
        self.assertEqual(forecast.principal, Money(0))
        self.assertEqual(forecast.income_forecast.gross_income, Money(0))

    def test_forecast_substitution(self):
        """ Test Forecaster.forecast with a substituted Scenario. """
        # Build two scenarios, init Forecaster with one, and then run
        # `forecast` with the other.
        scenario1 = Scenario(
            initial_year=2000,
            num_years=2,
            inflation=0,
            stock_return=0,
            bond_return=0,
            other_return=0,
            management_fees=0
        )
        scenario2 = Scenario(
            initial_year=2000,
            num_years=2,
            inflation=0,
            stock_return=1,  # 100% growth in stocks.
            bond_return=0,
            other_return=0,
            management_fees=0
        )
        forecaster = Forecaster(
            scenario=scenario1, settings=self.settings)
        forecaster.set_person1(gross_income=Money(0))
        # Add an account with a $1 balance and 100% invested in stocks:
        allocation_strategy = AllocationStrategy(
            strategy=AllocationStrategy.strategy_transition_to_const,
            # 100% invested in stocks every year:
            target=1,
            min_equity=1,
            max_equity=1
        )
        forecaster.add_asset(
            owner=forecaster.person1,
            balance=Money(1),
            # Explicitly require that we follow the above allocation:
            rate=allocation_strategy.rate_function(
                forecaster.person1, scenario1),
            cls=Account)
        forecaster.set_person2(name=None)  # Remove person2, if present

        # Run the forecast with scenario2 (which has 100% stock growth):
        forecast = forecaster.forecast(scenario=scenario2)

        # Under scenario1, the balance in 2001 should be unchanged at
        # $1. Under scenario2, the balance in 2001 should double to $2.

        # pylint: disable=no-member
        self.assertEqual(forecast.principal_history[2001], Money(2))
        # pylint: enable=no-member


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
