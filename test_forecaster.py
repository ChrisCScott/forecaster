""" Unit tests for `Forecaster`. """

import unittest
import collections
from copy import copy, deepcopy
from settings import Settings
from tax import Tax
from ledger import Person, Account, Debt
from scenario import Scenario
from strategy import ContributionStrategy, WithdrawalStrategy, \
    TransactionStrategy, AllocationStrategy, DebtPaymentStrategy
from forecaster import Forecaster
from utility import Money
# pylint: disable=W0614,W0401,
from test_helper import *


class TestForecaster(unittest.TestCase):
    """ Tests Forecaster. """

    def setUp(self):
        """ Builds default strategies, persons, etc. """
        self.initial_year = Settings.initial_year
        self.scenario = Scenario(
            inflation=Settings.inflation,
            stock_return=Settings.stock_return,
            bond_return=Settings.bond_return,
            other_return=Settings.other_return,
            management_fees=Settings.management_fees,
            initial_year=Settings.initial_year,
            num_years=Settings.num_years
        )
        self.contribution_strategy = ContributionStrategy(
            strategy=Settings.contribution_strategy,
            base_amount=Settings.contribution_base_amount,
            rate=Settings.contribution_rate,
            refund_reinvestment_rate=Settings.contribution_refund_reinvestment_rate,  # noqa
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.withdrawal_strategy = WithdrawalStrategy(
            strategy=Settings.withdrawal_strategy,
            base_amount=Settings.withdrawal_base_amount,
            rate=Settings.withdrawal_rate,
            timing=Settings.transaction_out_timing,
            income_adjusted=Settings.withdrawal_income_adjusted,
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.transaction_in_strategy = TransactionStrategy(
            strategy=Settings.transaction_in_strategy,
            weights=Settings.transaction_in_weights,
            timing=Settings.transaction_in_timing
        )
        self.transaction_out_strategy = TransactionStrategy(
            strategy=Settings.transaction_out_strategy,
            weights=Settings.transaction_out_weights,
            timing=Settings.transaction_out_timing
        )

        # We use different target values for different strategies.
        if (
            # pylint: disable=E1101
            Settings.allocation_strategy ==
            AllocationStrategy.strategy_n_minus_age.strategy_key
        ):
            target = Settings.allocation_constant_strategy_target
        elif (
            # pylint: disable=E1101
            Settings.allocation_strategy ==
            AllocationStrategy.strategy_transition_to_const.strategy_key
        ):
            target = Settings.allocation_transition_strategy_target
        self.allocation_strategy = AllocationStrategy(
            strategy=Settings.allocation_strategy,
            min_equity=Settings.allocation_min_equity,
            max_equity=Settings.allocation_max_equity,
            target=target,
            standard_retirement_age=Settings.allocation_standard_retirement_age,  # noqa
            risk_transition_period=Settings.allocation_risk_transition_period,
            adjust_for_retirement_plan=Settings.allocation_adjust_for_retirement_plan,  # noqa
            scenario=self.scenario
        )
        self.debt_payment_strategy = DebtPaymentStrategy(
            strategy=Settings.debt_payment_strategy,
            timing=Settings.debt_payment_timing
        )
        self.tax_treatment = Tax(
            tax_brackets={self.initial_year: {0: 0}},
            personal_deduction={},
            credit_rate={},
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.person1 = Person(
            name=Settings.person1_name,
            birth_date=Settings.person1_birth_date,
            retirement_date=Settings.person1_retirement_date,
            gross_income=Settings.person1_gross_income,
            raise_rate=Settings.person1_raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment,
            allocation_strategy=self.allocation_strategy,
            initial_year=self.initial_year
        )
        if Settings.person2_name is None:
            self.person2 = None
        else:
            self.person2 = Person(
                name=Settings.person2_name,
                birth_date=Settings.person2_birth_date,
                retirement_date=Settings.person2_retirement_date,
                gross_income=Settings.person2_gross_income,
                raise_rate=Settings.person2_raise_rate,
                spouse=self.person1,
                tax_treatment=None,
                allocation_strategy=self.allocation_strategy,
                initial_year=self.initial_year
            )

    @staticmethod
    def complex_equal(first, second, memo=None):
        """ Tests complicated class instances for equality.

        This method is used (instead of __eq__) because equality
        semantics are only needed for testing code and can mess up
        things like set membership, require extensive (and inefficient)
        comparisons, and/or can result in infinite recursion.
        """
        # The memo dict maps each object to the set of objects that it's
        # been compared to. If they've been compared, that means that we
        # don't need to re-evaluate their equality - if they're unequal,
        # that'll be discovered at a higher level of recursion:
        if memo is None:
            memo = collections.defaultdict(set)
        if id(second) in memo[id(first)]:
            return True
        else:
            memo[id(first)].add(id(second))
            memo[id(second)].add(id(first))

        # There are a few cases to deal with:
        # 1) These are dicts, in which case we need to compare keys and
        #    values.
        # 2) These are complicated objects, in which case we need to
        #    recurse onto their attributes dict (i.e. obj.__dict__)
        # 3) These are non-dict iterables, in which case we can try
        #    to recurse onto their elements in sequence.
        #    (NOTE: This is tricky for unordered iterables like set,
        #    since two sets with equal objects might iterate in
        #    different orders if member ids are different.)
        # 4) These are non-iterable, uncomplicated objects, in which
        #    case we can use the == operator.

        if (  # Objects of unrelated types can be assumed to be nonequal
                not isinstance(first, type(second)) and
                not isinstance(second, type(first))
        ):
            return False
        elif isinstance(first, dict):
            # For dicts, confirm that they represent the same keys and
            # then recurse onto each of the values:
            return first.keys() == second.keys() and \
                all(
                    TestForecaster.complex_equal(first[key], second[key], memo)
                    for key in first
                )
        elif hasattr(first, '__dict__'):
            # For complicated objects, recurse onto the attributes dict:
            return TestForecaster.complex_equal(
                first.__dict__, second.__dict__, memo)
        elif isinstance(first, list):
            # For lists, iterate over the elements in sequence:
            return len(first) == len(second) and all(
                TestForecaster.complex_equal(first[i], second[i], memo)
                for i in range(0, len(first))
            )
        elif isinstance(first, set):
            # For sets, we can't rely on `in`, so we want to test each
            # element in one set against every element in the other set.
            # This will involve comparing objects which are not equal,
            # so we need to copy the dict before recursing.
            # NOTE: Ideally we would update memo for each successful
            # comparison, but this would complicate the logic below.
            # This refinement only adds efficiency (i.e. the code is
            # correct as-is), so we've left it in its simpler form.
            return len(first) == len(second) and all(
                any(
                    TestForecaster.complex_equal(val1, val2, copy(memo))
                    for val2 in second
                ) for val1 in first
            )
        else:
            # For simple objects, use the standard == operator
            return first == second

    def assertEqual(self, first, second, msg=None):
        """ Overloaded to test equality of complex objects. """
        self.assertTrue(TestForecaster.complex_equal(first, second), msg)

    def assertNotEqual(self, first, second, msg=None):
        """ Overloaded to test non-equality of complex objects. """
        self.assertFalse(TestForecaster.complex_equal(first, second), msg)

    def test_assertEqual(self):
        """ Tests overloaded TestForecaster.assertEqual. """
        # Compare an object to itself
        person1 = self.person1
        self.assertEqual(person1, person1)
        # Compare two idential instances of an object:
        person2 = deepcopy(person1)
        self.assertEqual(person1, person2)
        # Compare two instances of an object that differ only in a
        # complicated attribute. (Simple case: set it to None)
        allocation_strategy = person2.allocation_strategy
        person2.allocation_strategy = None
        self.assertNotEqual(person1, person2)
        # Try again, but this time the difference is in a sub-attribute
        allocation_strategy.scenario.inflation = {2000: 1, 2001: 1.5}
        person2.allocation_strategy = allocation_strategy
        self.assertNotEqual(person1, person2)

    def test_init(self):
        """ Tests Forecaster.__init__ """
        # Test default init:
        forecaster = Forecaster()
        # TODO: Test attributes of Scenario, Strategy, etc. directly.
        # (Yes, this will be lengthy and tedious.)
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
            forecaster.withdrawal_strategy, self.withdrawal_strategy)
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

        # Test init with custom settings:
        settings = Settings()
        settings.person1_name = 'Test Name'
        person1 = Person(
            name='Test Name',
            birth_date=settings.person1_birth_date,
            retirement_date=settings.person1_retirement_date,
            gross_income=settings.person1_gross_income,
            raise_rate=settings.person1_raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment,
            allocation_strategy=self.allocation_strategy,
            initial_year=settings.initial_year
        )
        forecaster = Forecaster(settings=settings)
        self.assertEqual(forecaster.person1, person1)  # custom person1
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
            forecaster.withdrawal_strategy, self.withdrawal_strategy)
        self.assertEqual(
            forecaster.transaction_in_strategy, self.transaction_in_strategy)
        self.assertEqual(
            forecaster.transaction_out_strategy, self.transaction_out_strategy)
        self.assertEqual(
            forecaster.allocation_strategy, self.allocation_strategy)
        self.assertEqual(
            forecaster.debt_payment_strategy, self.debt_payment_strategy)
        self.assertEqual(forecaster.settings, settings)
        self.assertEqual(forecaster.initial_year, settings.initial_year)

        # Test init with custom inputs (persons, strategies, etc.):
        forecaster = Forecaster(person1=person1)
        self.assertEqual(forecaster.person1, person1)  # custom person1
        self.assertEqual(forecaster.person2, self.person2)
        if self.person2 is not None:
            self.assertEqual(forecaster.people, {person1, self.person2})
        else:  # We don't add `None` to the `people` set.
            self.assertEqual(forecaster.people, {person1})
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertEqual(
            forecaster.contribution_strategy, self.contribution_strategy)
        self.assertEqual(
            forecaster.withdrawal_strategy, self.withdrawal_strategy)
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

        # Test init with custom initial year:
        initial_year = 1999
        forecaster = Forecaster(initial_year=initial_year)
        self.assertEqual(forecaster.initial_year, initial_year)
        self.assertEqual(forecaster.person1.initial_year, initial_year)
        if self.person2 is not None:
            self.assertEqual(forecaster.person2.initial_year, initial_year)
        for account in forecaster.assets.union(forecaster.debts):
            self.assertEqual(account.initial_year, initial_year)

    def test_add_person(self):
        """ Test Forecaster.add_person. """
        forecaster = Forecaster()
        people = copy(forecaster.people)
        person = forecaster.add_person('Test', 2000, retirement_date=2065)
        self.assertEqual(person, Person(
            self.initial_year, 'Test', 2000,
            retirement_date=2065,
            tax_treatment=forecaster.tax_treatment,
            allocation_strategy=forecaster.allocation_strategy
        ))
        self.assertEqual(forecaster.people - people, {person})

    def test_add_asset(self):
        """ Test Forecaster.add_asset. """
        forecaster = Forecaster()
        assets = copy(forecaster.assets)
        asset = forecaster.add_asset()
        self.assertEqual(asset, Account(
            owner=forecaster.person1,
            balance=Money(0),
            rate=None,
            transactions={},
            nper=1,
            default_inflow_timing=Settings.transaction_in_timing,
            default_outflow_timing=Settings.transaction_out_timing,
            inputs={},
            initial_year=forecaster.person1.initial_year
        ))
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_debt(self):
        """ Test Forecaster.add_debt. """
        forecaster = Forecaster()
        debts = copy(forecaster.debts)
        debt = forecaster.add_debt()
        self.assertEqual(debt, Debt(
            owner=forecaster.person1,
            balance=Money(0),
            rate=None,
            transactions={},
            nper=1,
            default_inflow_timing=Settings.debt_payment_timing,
            default_outflow_timing=Settings.transaction_out_timing,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            minimum_payment=Money(0),
            reduction_rate=Settings.debt_reduction_rate,
            accelerate_payment=Settings.debt_accelerate_payment
        ))
        self.assertEqual(forecaster.debts - debts, {debt})

    def test_forecast(self):
        """ Tests Forecaster.forecast """
        # Run a simple forecast with $0 income and $0 balances:
        forecaster = Forecaster()
        forecaster.set_person1(gross_income=Money(0))
        forecaster.add_asset(owner=forecaster.person1, AccountType=Account)
        forecaster.add_debt(owner=forecaster.person1, AccountType=Debt)
        forecaster.set_person2(name=None)  # Remove person2, if present
        forecast = forecaster.forecast()
        # Test that it starts and ends in the right place and that
        # income and total balance (principal) are correct (i.e. $0)
        self.assertEqual(
            forecast.scenario.initial_year, forecaster.initial_year)
        self.assertEqual(
            len(forecast.principal), forecaster.scenario.num_years)
        for principal in forecast.principal.values():
            self.assertEqual(principal, Money(0))
        for gross_income in forecast.gross_income.values():
            self.assertEqual(gross_income, Money(0))

        # Run the simple forecast again, but this time with a different
        # scenario. All inflation_adjust and scenario attributes should
        # be updated too.
        # TODO

if __name__ == '__main__':
    unittest.main()
