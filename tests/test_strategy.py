""" Unit tests for `Strategy` and related classes. """
# pylint: disable=too-many-lines
# This module requires a lot of tests. I'd rather not split up the file.

import unittest
import decimal
from decimal import Decimal
from random import Random
from forecaster import (
    Person, Debt, Money, ContributionStrategy, WithdrawalStrategy,
    TransactionStrategy, AllocationStrategy, DebtPaymentStrategy)
from forecaster.strategy import Strategy, strategy_method
from forecaster.canada import RRSP, TFSA, TaxableAccount, constants


class TestStrategyMethods(unittest.TestCase):
    """ A test suite for the `Strategy` class """

    # Strategy has no strategy methods by default, which means
    # __init__ will fail for every input. The easiest fix is to
    # create a subclass with a validly-decorated strategy.
    class Subclass(Strategy):
        """ Example subclass for testing purposes. """
        @strategy_method('Test')
        def test_strategy(self, val=1):  # pylint: disable=no-self-use
            """ A test strategy. """
            return val

        @strategy_method('Test2')
        def test_strategy2(self, val=2):  # pylint: disable=no-self-use
            """ Another test strategy. """
            return val

    def test_init(self):
        """ Test Strategy.__init__ """
        # Test a basic initialization
        strategy = self.Subclass('Test')

        # pylint: disable=no-member
        # Pylint has trouble with Strategy; the strategies member is
        # created at class-definition time by the StrategyType metaclass
        self.assertEqual(strategy.strategies, {
            'Test': self.Subclass.test_strategy,
            'Test2': self.Subclass.test_strategy2}
        )
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a function
        strategy = self.Subclass(self.Subclass.test_strategy)

        self.assertEqual(strategy.strategies, {
            'Test': self.Subclass.test_strategy,
            'Test2': self.Subclass.test_strategy2}
        )
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a bound method
        strategy = self.Subclass(strategy.test_strategy)

        self.assertEqual(strategy.strategies, {
            'Test': self.Subclass.test_strategy,
            'Test2': self.Subclass.test_strategy2}
        )
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        self.assertEqual(strategy.strategies, {
            'Test': self.Subclass.test_strategy,
            'Test2': self.Subclass.test_strategy2}
        )
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test invalid initializations
        with self.assertRaises(ValueError):
            strategy = self.Subclass('Not a strategy')
        with self.assertRaises(TypeError):
            strategy = self.Subclass(1)
        with self.assertRaises(TypeError):
            # pylint: disable=too-many-function-args
            strategy = self.Subclass('Test', 1)

        # Also test to ensure that regular subclasses' strategy methods
        # are being added to `strategies`. We use ContributionStrategy
        # for this test. It should have at least these four strategies:
        strategies = {
            ContributionStrategy.strategy_const_contribution.strategy_key:
                ContributionStrategy.strategy_const_contribution,
            ContributionStrategy.strategy_const_living_expenses.strategy_key:  # noqa
                ContributionStrategy.strategy_const_living_expenses,
            ContributionStrategy.strategy_gross_percent.strategy_key:
                ContributionStrategy.strategy_gross_percent,
            ContributionStrategy.strategy_net_percent.strategy_key:
                ContributionStrategy.strategy_net_percent
        }
        # Unfortunately, unittest.assertDictContainsSubset is deprecated
        # so we'll have to do this the long way...
        for strategy in strategies:
            self.assertIn(strategy, ContributionStrategy.strategies.keys())
            self.assertIn(strategies[strategy],
                          ContributionStrategy.strategies.values())

        # Also made sure that no strategies for other subclasses are
        # being added to this particular subclass instance.
        self.assertNotIn(WithdrawalStrategy.strategy_principal_percent,
                         ContributionStrategy.strategies.values())

        # Finally, repeat the above with object instances instead of
        # classes. (Be careful - functions defined in class scope and
        # methods bound to objects are not the same. `s.strategies`
        # contains unbound functions, not comparable to s.strategy_*
        # methods)
        strategy = ContributionStrategy(
            ContributionStrategy.strategy_const_contribution)
        for key in strategies:
            self.assertIn(key, strategy.strategies.keys())
            self.assertIn(strategies[key], strategy.strategies.values())


class TestContributionStrategyMethods(unittest.TestCase):
    """ A test case for the ContributionStrategy class """

    @classmethod
    def setUpClass(cls):

        inflation_adjustments = {
            2000: Decimal(0.5),
            2001: Decimal(1),
            2002: Decimal(2)
        }

        @staticmethod
        def variable_inflation(year, base_year=None):
            """ Returns different inflation rates for different years. """
            if base_year is None:
                base_year = 2001
            # Store a convenient inflation_adjust function that returns
            # 50% for 2000, 100% for 2001, and 200% for 2002:
            return (
                inflation_adjustments[year] /
                inflation_adjustments[base_year]
            )

        # pylint: disable=unused-argument
        @staticmethod
        def constant_2x_inflation(year, base_year=None):
            """ Returns the same inflation rate for each year. """
            # A convenient inflation_adjust function that returns 200%
            # for any input (and doesn't require any particular `year`)
            return Decimal('2')

        cls.variable_inflation = variable_inflation
        cls.constant_2x_inflation = constant_2x_inflation

    def test_init(self):
        """ Test ContributionStrategy.__init__ """
        # Test default init:
        method = "Constant contribution"
        strategy = ContributionStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.rate, Decimal(0))
        self.assertEqual(strategy.refund_reinvestment_rate, Decimal(1))

        # Test explicit init:
        method = 'Constant contribution'
        base_amount = Money('1000')
        rate = Decimal('0.5')
        refund_reinvestment_rate = Decimal('0.5')
        inflation_adjust = self.constant_2x_inflation
        strategy = ContributionStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            refund_reinvestment_rate=refund_reinvestment_rate,
            inflation_adjust=inflation_adjust)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.rate, rate)
        self.assertEqual(
            strategy.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(strategy.inflation_adjust, inflation_adjust)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = ContributionStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = ContributionStrategy(strategy=1)
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(strategy=method, base_amount='a')
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(strategy=method, rate='a')
        # Test invalid refund_reinvestment_rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(
                strategy=method, refund_reinvestment_rate='a')

    def test_strategy_const_contrib(self):
        """ Test ContributionStrategy.strategy_const_contribution. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_const_contribution

        # Default strategy. Set to $1 constant contributions.
        strategy = ContributionStrategy(method, base_amount=Money(1))
        # Test all default parameters (no inflation adjustments here)
        self.assertEqual(strategy(), strategy.base_amount)
        # Test refunds ($1) and other income ($2), for a total of $3
        # plus the default contribution rate.
        self.assertEqual(
            strategy(refund=Money(1), other_contribution=Money(2)),
            Money(strategy.base_amount) +
            Money(1) * strategy.refund_reinvestment_rate +
            Money(2))
        # Test that changing net_income and gross_income has no effect
        self.assertEqual(
            strategy(
                refund=0, other_contribution=0, net_income=Money(100000),
                gross_income=Money(200000)
            ),
            Money(strategy.base_amount)
        )
        # Test different inflation_adjustments
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        self.assertEqual(
            strategy(year=2000),
            Money(strategy.base_amount) * self.variable_inflation(2000)
        )
        self.assertEqual(
            strategy(year=2001),
            Money(strategy.base_amount) * self.variable_inflation(2001)
        )
        self.assertEqual(
            strategy(year=2002),
            Money(strategy.base_amount) * self.variable_inflation(2002)
        )

        # Customize some inputs
        base_amount = Money(500)
        rate = Decimal('0.5')
        refund_reinvestment_rate = 1
        strategy = ContributionStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            refund_reinvestment_rate=refund_reinvestment_rate)
        # Test all default parameters.
        self.assertEqual(strategy(), base_amount)
        # Test that changing net_income, gross_income have no effect on
        # a constant contribution:
        self.assertEqual(
            strategy(
                net_income=Money(100000), gross_income=Money(200000)
            ),
            base_amount)

    def test_strategy_const_living_exp(self):
        """ Test ContributionStrategy.strategy_const_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_const_living_expenses

        # Default strategy
        strategy = ContributionStrategy(
            method, base_amount=Money(1000), inflation_adjust=lambda year:
            {2000: Decimal(0.5), 2001: Decimal(1), 2002: Decimal(2)}[year])
        excess = Money(1500)  # excess money (this is the contribution)
        net_income = strategy.base_amount + excess  # net income
        # This method requires net_income
        self.assertEqual(strategy(year=2001, net_income=net_income), excess)
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(
                year=2001, net_income=net_income, gross_income=Money(20000)
            ),
            excess
        )

        # Test different inflation_adjustments for different years.
        # First, test nominal $2000 in a year where the inflation
        # adjustment is 50%. Our real-value $1000 living expenses is
        # reduced by 50% to $500 in nominal terms, leaving $2000 to
        # contribute.
        self.assertEqual(
            strategy(year=2000, net_income=Money(2500)), Money('2000'))
        # For 2002, the inflation adjustment is 200%, meaning that our
        # living expenses are $2000 nominally. For income of $2500
        # the contribution is now just $500
        self.assertEqual(
            strategy(year=2002, net_income=Money(2500)), Money('500'))
        # Test a lower net_income than the living standard:
        strategy = ContributionStrategy(method, Money(1000))
        self.assertEqual(strategy(year=2000, net_income=Money(500)), 0)

    def test_strategy_net_percent(self):
        """ Test ContributionStrategy.strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_net_percent

        # Default strategy
        strategy = ContributionStrategy(method)
        net_income = Money(1000)
        # This method requires net_income
        self.assertEqual(
            strategy(net_income=net_income), net_income * strategy.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(net_income=net_income, gross_income=Money(20000)),
            net_income * strategy.rate
        )
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        # Test different inflation_adjustments
        # (Since the net_income argument is nominal, inflation should
        # have no effect)
        self.assertEqual(
            strategy(net_income=net_income, year=2000),
            net_income * strategy.rate
        )
        self.assertEqual(
            strategy(net_income=net_income, year=2002),
            net_income * strategy.rate
        )

    def test_strategy_gross_percent(self):
        """ Test ContributionStrategy.strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_gross_percent

        # Default strategy
        strategy = ContributionStrategy(method)
        gross_income = Money(1000)  # gross income
        # This method requires gross_income
        self.assertEqual(
            strategy(gross_income=gross_income),
            gross_income * strategy.rate
        )
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(gross_income=gross_income, net_income=Money(20000)),
            gross_income * strategy.rate
        )
        # Test different inflation_adjustments
        # (Since the gross_income argument is nominal, inflation_adjustment
        # should have no effect)
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        self.assertEqual(
            strategy(gross_income=gross_income, year=2000),
            gross_income * strategy.rate
        )
        self.assertEqual(
            strategy(gross_income=gross_income, year=2002),
            gross_income * strategy.rate
        )

    def test_strategy_earnings_percent(self):
        """ Test ContributionStrategy.strategy_earnings_percent. """
        method = ContributionStrategy.strategy_earnings_percent

        # Default strategy
        strategy = ContributionStrategy(
            method, inflation_adjust=self.variable_inflation)
        net_income = strategy.base_amount * 2
        # This method requires net_income
        # Also need to provide `year` because inflation_adjust needs it
        # (2001 is the year for which inflation adjustment is 1)
        self.assertEqual(
            strategy(net_income=net_income, year=2001),
            (net_income - strategy.base_amount) * strategy.rate
        )
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(
                net_income=net_income, gross_income=Money(20000), year=2001),
            (net_income - strategy.base_amount) * strategy.rate
        )
        # Test different inflation_adjustments
        # (This should inflation_adjust base_amount)
        self.assertEqual(
            strategy(net_income=net_income, year=2000),
            (net_income - strategy.base_amount * Decimal(0.5)) * strategy.rate)
        self.assertEqual(
            strategy(net_income=net_income, year=2002),
            (net_income - strategy.base_amount * Decimal(2)) * strategy.rate)


class TestWithdrawalStrategyMethods(unittest.TestCase):
    """ A test case for the WithdrawalStrategy class """

    def setUp(self):
        """ Sets up TestWithdrawalStrategyMethods. """
        # Several methods use varying inflation adjustment figures.
        self.year_half = 1999  # -50% inflation (values halved) in this year
        self.year_1 = 2000  # baseline year; no inflation
        self.year_2 = 2001  # 100% inflation (values doubled) in this year
        self.year_10 = 2002  # Values multiplied by 10 in this year
        self.inflation_adjustment = {
            self.year_half: Decimal(0.5),
            self.year_1: Decimal(1),
            self.year_2: Decimal(2),
            self.year_10: Decimal(10)
        }

        def inflation_adjust(year, base_year=self.year_1):
            """ Returns inflation-adjustment factor between two years. """
            return (
                self.inflation_adjustment[year] /
                self.inflation_adjustment[base_year]
            )

        self.inflation_adjust = inflation_adjust

    def test_init(self):
        """ Test WithdrawalStrategy.__init__ """
        # Test default init:
        method = "Constant withdrawal"
        strategy = WithdrawalStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.rate, Decimal(0))
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.timing, 'end')
        self.assertEqual(strategy.income_adjusted, False)

        # Test explicit init:
        method = 'Constant withdrawal'
        rate = Decimal('1000')
        base_amount = Decimal('500')
        timing = 'end'
        income_adjusted = True
        inflation_adjust = self.inflation_adjust
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            timing=timing, income_adjusted=income_adjusted,
            inflation_adjust=inflation_adjust
        )

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.rate, rate)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.timing, timing)
        self.assertEqual(strategy.income_adjusted, income_adjusted)
        self.assertEqual(strategy.inflation_adjust, inflation_adjust)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = WithdrawalStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = WithdrawalStrategy(strategy=1)
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = WithdrawalStrategy(strategy=method, rate='a')
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            strategy = WithdrawalStrategy(strategy=method, base_amount='a')
        # Test invalid timing
        with self.assertRaises(ValueError):
            strategy = WithdrawalStrategy(strategy=method, timing='a')
        # No need to test bool-valued attributes - everything is
        # bool-convertible!

    def test_strategy_const_withdrawal(self):
        """ Test WithdrawalStrategy.strategy_const_withdrawal. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_const_withdrawal

        # Default strategy
        strategy = WithdrawalStrategy(method, base_amount=Money(100))
        # Test all default parameters. (We don't need to provide any
        # inflation data since this instance is not inflation-adjusted.)
        self.assertEqual(strategy(), Money(100))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            method, base_amount=Money(100),
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(year=year),
                Money(strategy.base_amount) * self.inflation_adjustment[year]
            )

    def test_strategy_principal_percent(self):
        """ Test WithdrawalStrategy.strategy_principal_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_principal_percent

        rand = Random()
        principal = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            principal[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(strategy=method, rate=0.5)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    principal_history=principal,
                    retirement_year=retirement_year),
                Money(strategy.rate * principal[retirement_year]))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                principal_history=principal,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = (
                Money(strategy.rate * principal[retirement_year]) *
                inflation_adjustment
            )
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_strategy_net_percent(self):
        """ Test WithdrawalStrategy.strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_net_percent

        rand = Random()
        net_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            net_income[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(strategy=method, rate=0.5, base_amount=0)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    net_income_history=net_income,
                    retirement_year=retirement_year),
                Money(strategy.rate * net_income[retirement_year]))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, base_amount=0,
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                net_income_history=net_income,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = Money(
                strategy.rate * net_income[retirement_year]
            ) * inflation_adjustment
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_strategy_gross_percent(self):
        """ Test WithdrawalStrategy.strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_gross_percent

        rand = Random()
        gross_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            gross_income[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(method, rate=0.5, base_amount=0)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    gross_income_history=gross_income,
                    retirement_year=retirement_year
                ),
                Money(strategy.rate * gross_income[retirement_year])
            )

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, base_amount=0,
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                gross_income_history=gross_income,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = Money(
                strategy.rate * gross_income[retirement_year]
            ) * inflation_adjustment
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_call(self):
        """ Test __call__ logic (but not strategy-specific logic). """
        # Select a simple, constant withdrawal strategy.
        method = WithdrawalStrategy.strategy_const_withdrawal

        # Test other income. No inflation adjustment.
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=Money(100), rate=0,
            timing='end', income_adjusted=True)
        # $0 benefits -> no change:
        self.assertEqual(strategy(other_income=Money(0)),
                         Money(strategy.base_amount))
        # $1 benefits -> $1 reduction
        self.assertEqual(strategy(other_income=Money(1)),
                         Money(strategy.base_amount) - Money(1))
        # Benefits = withdrawal rate -> $0 withdrawal
        self.assertEqual(strategy(other_income=Money(strategy.base_amount)),
                         Money(0))
        # Benefits > withdrawal rate -> $0 withdrawal
        self.assertEqual(
            strategy(other_income=Money(strategy.base_amount) + Money(1)),
            Money(0))

        # Re-run above tests, but this time with income_adjusted=False
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=Money(100), rate=0, timing='end',
            income_adjusted=False)
        # In every case, there should be no change:
        self.assertEqual(strategy(Money(0)), Money(strategy.base_amount))
        self.assertEqual(strategy(Money(1)), Money(strategy.base_amount))
        self.assertEqual(
            strategy(Money(strategy.base_amount)),
            Money(strategy.base_amount))
        self.assertEqual(strategy(Money(strategy.base_amount) + Money(1)),
                         Money(strategy.base_amount))


class TestTransactionStrategyMethods(unittest.TestCase):
    """ A test case for the TransactionStrategy class """

    @classmethod
    def setUpClass(cls):
        cls.initial_year = 2000
        cls.person = Person(
            cls.initial_year, 'Testy McTesterson', 1980, retirement_date=2045)
        cls.inflation_adjustments = {
            cls.initial_year: Decimal(1),
            cls.initial_year + 1: Decimal(1.25),
            min(constants.RRSP_ACCRUAL_MAX): Decimal(1)}

        # Set up some accounts for the tests.
        cls.rrsp = RRSP(
            cls.person,
            inflation_adjust=cls.inflation_adjustments,
            balance=Money(200), rate=0, contribution_room=Money(200))
        cls.tfsa = TFSA(
            cls.person,
            inflation_adjust=cls.inflation_adjustments,
            balance=Money(100), rate=0, contribution_room=Money(100))
        cls.taxable_account = TaxableAccount(
            cls.person, balance=Money(1000), rate=0)
        cls.accounts = [cls.rrsp, cls.tfsa, cls.taxable_account]

    def test_init(self):
        """ Test TransactionStrategy.__init__ """
        # Test explicit init:
        method = 'Weighted'
        weights = {
            'RRSP': Decimal(0.5),
            'TFSA': Decimal(0.25),
            'TaxableAccount': Decimal(0.25)
        }
        timing = 'end'
        strategy = TransactionStrategy(method, weights, timing)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.weights, weights)
        self.assertEqual(strategy.timing, timing)

        # Test implicit init for optional args:
        strategy = TransactionStrategy(method, weights)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.weights, weights)
        self.assertEqual(strategy.timing, 'end')

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = TransactionStrategy(
                strategy='Not a strategy', weights={})
        with self.assertRaises(TypeError):
            strategy = TransactionStrategy(strategy=1, weights={})
        # Test invalid weight
        with self.assertRaises(TypeError):  # not a dict
            strategy = TransactionStrategy(strategy=method, weights='a')
        with self.assertRaises(TypeError):  # dict with non-str keys
            strategy = TransactionStrategy(strategy=method, weights={1: 5})
        with self.assertRaises(TypeError):  # dict with non-numeric values
            strategy = TransactionStrategy(
                strategy=method, weights={'RRSP', 'Not a number'})
        # Test invalid timing
        with self.assertRaises(TypeError):
            strategy = TransactionStrategy(
                strategy=method, weights={}, timing={})

    def test_strategy_ordered(self):
        """ Test TransactionStrategy.strategy_ordered. """
        # Run each test on inflows and outflows
        method = TransactionStrategy.strategy_ordered
        strategy = TransactionStrategy(
            method, {
                'RRSP': 1,
                'TFSA': 2,
                'TaxableAccount': 3
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room in the top-weighted
        # account type.
        results = strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))
        # Try again with outflows.
        results = strategy(-Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))

        # Now contribute (withdraw) more than the rrsp will accomodate.
        # The extra $50 should go to the tfsa, which is next in line.
        results = strategy(Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(50))
        self.assertEqual(results[self.taxable_account], Money(0))
        results = strategy(-Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-50))
        self.assertEqual(results[self.taxable_account], Money(0))

        # Now contribute (withdraw) a lot of money - the rrsp and tfsa
        # will get filled (emptied) and the remainder will go to the
        # taxable account.
        results = strategy(Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(700))
        results = strategy(-Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxable_account], Money(-700))

        # For outflows only, try withdrawing more than the accounts have
        results = strategy(-Money(10000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxable_account], Money(-1000))

        # Now change the order and confirm that it still works
        strategy.weights['RRSP'] = 2
        strategy.weights['TFSA'] = 1
        results = strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(0))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_strategy_weighted_out(self):
        """ Test TransactionStrategy.strategy_weighted on outflows. """
        method = TransactionStrategy.strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxable_account_weight = Decimal('0.3')
        strategy = TransactionStrategy(
            method, {
                'RRSP': rrsp_weight,
                'TFSA': tfsa_weight,
                'TaxableAccount': taxable_account_weight
            })

        # Basic test. Amount withdrawn is less than the balance of each
        # account.
        val = -Money(max([a.max_outflow() for a in self.accounts]))
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxable_account],
                         val * taxable_account_weight)

        # Now withdraw enough to exceed the TFSA's balance.
        threshold = self.tfsa.max_outflow() / tfsa_weight
        overage = -Money(50)
        val = Money(threshold + overage)
        results = strategy(val, self.accounts)
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertLess(results[self.rrsp], results[self.taxable_account])
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxable_account_weight +
            overage * taxable_account_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) *
            taxable_account_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxable_account],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxable_account],
                             max(taxable_vals))

        # For withdrawals, try withdrawing just a little less than the
        # total available balance. This will clear out the RRSP and TFSA
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxable_account.max_outflow() - overage
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow() - overage)

        # For outflows only, try withdrawing more than the accounts have
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxable_account.max_outflow() + overage
        results = strategy(val, self.accounts)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow())

    def test_strategy_weighted_in(self):
        """ Test TransactionStrategy.strategy_weighted on inflows. """
        # Run each test on inflows and outflows
        method = TransactionStrategy.strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxable_account_weight = Decimal('0.3')
        strategy = TransactionStrategy(
            method, {
                'RRSP': rrsp_weight,
                'TFSA': tfsa_weight,
                'TaxableAccount': taxable_account_weight
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room for each account
        val = Money(min([a.max_inflow() for a in self.accounts]))
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxable_account],
                         val * taxable_account_weight)

        # Now contribute enough to exceed the TFSA's contribution room.
        # This can be implemented in various reasonable ways, but we
        # should ensure that:
        # 1 - TFSA contribution is maxed
        # 2 - The total amount contributed is equal to `val`
        # 3 - More is contributed to RRSPs than taxable accounts.
        # 4 - The proportion of RRSP to taxable contributions should be
        #     in a reasonable range, depending on whether (a) only the
        #     overage is reweighted to exclude the TFSA or (b) the
        #     entire contribution to those accounts is reweighted to
        #     exclude the TFSA. (This is left to the implementation.)
        threshold = self.tfsa.max_inflow() / tfsa_weight
        overage = Money(50)
        val = Money(threshold + overage)
        results = strategy(val, self.accounts)
        # Do tests 1-3:
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertGreater(results[self.rrsp], results[self.taxable_account])
        # Now we move on to test 4, which is a bit trickier.
        # We want to be in the range defined by:
        # 1 - Only the overage is reweighted, and
        # 2 - The entire contribution to the RRSP is reweighted
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxable_account_weight +
            overage * taxable_account_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) *
            taxable_account_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxable_account],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxable_account],
                             max(taxable_vals))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(self.rrsp.max_inflow() / rrsp_weight,
                        self.tfsa.max_inflow() / tfsa_weight)
        overage = abs(overage)
        val = threshold + overage
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_inflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertEqual(results[self.taxable_account], val -
                         (self.rrsp.max_inflow() + self.tfsa.max_inflow()))


class TestAllocationStrategyMethods(unittest.TestCase):
    """ A test case for the AllocationStrategy class """

    def test_init(self):
        """ Test AllocationStrategy.__init__ """
        # Arguments for AllocationStrategy are:
        # strategy (str, func)
        # min_equity (Decimal)
        # max_equity (Decimal)
        # target (Decimal)
        # standard_retirement_age (int)
        # risk_transition_period (int)
        # adjust_for_retirement_plan (bool)

        # Test default init:
        method = AllocationStrategy.strategy_n_minus_age
        strategy = AllocationStrategy(method, 100)
        # pylint: disable=no-member
        self.assertEqual(strategy.strategy, method.strategy_key)
        self.assertEqual(strategy.min_equity, 0)
        self.assertEqual(strategy.max_equity, 1)
        # The default target varies depending on the strategy
        self.assertEqual(strategy.target, 100)
        self.assertEqual(strategy.standard_retirement_age, 65)
        self.assertEqual(strategy.risk_transition_period, 20)
        self.assertEqual(strategy.adjust_for_retirement_plan, True)

        # Test explicit init:
        method = AllocationStrategy.strategy_n_minus_age
        min_equity = 0
        max_equity = 1
        target = '0.5'
        standard_retirement_age = 65.0
        risk_transition_period = '10'
        adjust_for_retirement_plan = 'Evaluates to True'
        strategy = AllocationStrategy(
            method, target, min_equity=min_equity, max_equity=max_equity,
            standard_retirement_age=standard_retirement_age,
            risk_transition_period=risk_transition_period,
            adjust_for_retirement_plan=adjust_for_retirement_plan)
        self.assertEqual(strategy.strategy, method.strategy_key)
        self.assertEqual(strategy.min_equity, Decimal(min_equity))
        self.assertEqual(strategy.max_equity, Decimal(max_equity))
        self.assertEqual(strategy.target, Decimal(target))
        self.assertEqual(strategy.standard_retirement_age,
                         int(standard_retirement_age))
        self.assertEqual(strategy.risk_transition_period,
                         int(risk_transition_period))
        self.assertEqual(strategy.adjust_for_retirement_plan,
                         bool(adjust_for_retirement_plan))

        # Type-check:
        self.assertIsInstance(strategy.strategy, str)
        self.assertIsInstance(strategy.min_equity, Decimal)
        self.assertIsInstance(strategy.max_equity, Decimal)
        self.assertIsInstance(strategy.target, Decimal)
        self.assertIsInstance(strategy.standard_retirement_age, int)
        self.assertIsInstance(strategy.risk_transition_period, int)
        self.assertIsInstance(strategy.adjust_for_retirement_plan, bool)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = AllocationStrategy(strategy='Not a strategy', target=1)
        with self.assertRaises(TypeError):
            strategy = AllocationStrategy(strategy=1, target=1)
        # Test invalid min_equity (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            strategy = AllocationStrategy(method, 1, min_equity='invalid')
        # Test invalid max_equity (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            strategy = AllocationStrategy(method, 1, max_equity='invalid')
        # Test invalid target (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            strategy = AllocationStrategy(method, target='invalid')
        # Test invalid standard_retirement_age (int)
        with self.assertRaises(ValueError):
            strategy = AllocationStrategy(
                method, 1, standard_retirement_age='invalid')
        # Test invalid risk_transition_period (int)
        with self.assertRaises(ValueError):
            strategy = AllocationStrategy(
                method, 1, risk_transition_period='invalid')
        # No need to test invalid adjust_for_retirement_plan (bool)

        # Test mismatched min and max equity thresholds
        with self.assertRaises(ValueError):
            strategy = AllocationStrategy(
                method, 1, min_equity=1, max_equity=0)
        # Confirm that the thresholds *can* be the same:
        strategy = AllocationStrategy(
            method, 1, min_equity=0.5, max_equity=0.5)
        self.assertEqual(strategy.min_equity, strategy.max_equity)

    def test_strategy_n_minus_age(self):
        """ Test AllocationStrategy.strategy_n_minus_age. """
        method = AllocationStrategy.strategy_n_minus_age

        # Create a basic strategy that puts 100-age % into equity
        target = 100
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        for age in range(0, target):
            self.assertAlmostEqual(
                strategy(age)['stocks'], Decimal((target - age) / 100))
            self.assertAlmostEqual(
                strategy(age)['bonds'], Decimal(1 - (target - age) / 100))
        for age in range(target, target + 100):
            self.assertEqual(strategy(age)['stocks'], strategy.min_equity)
            self.assertEqual(strategy(age)['bonds'], 1 - strategy.min_equity)

        # Try with adjustments for retirement plans enabled.
        # Use n = 120, but a retirement age that's 20 years early.
        # After adjusting for retirement plans, the results should be
        # the same as in the above test
        target = 120
        standard_retirement_age = 65
        diff = -20
        retirement_age = standard_retirement_age + diff
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=True)

        for age in range(0, target + diff):
            self.assertAlmostEqual(strategy(age, retirement_age)['stocks'],
                                   Decimal((target + diff - age) / 100))
            self.assertAlmostEqual(strategy(age, retirement_age)['bonds'],
                                   Decimal(1 - (target + diff - age) / 100))
        for age in range(target + diff, target + diff + 100):
            self.assertEqual(strategy(age, retirement_age)['stocks'],
                             strategy.min_equity)
            self.assertEqual(strategy(age, retirement_age)['bonds'],
                             1 - strategy.min_equity)

        # Finally, try n=120 without adjusting the retirement age to
        # confirm that max_equity is respected.
        target = 120
        standard_retirement_age = 65
        retirement_age = standard_retirement_age - 20
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        for age in range(0, 20):
            self.assertEqual(strategy(age)['stocks'], strategy.max_equity)
            self.assertEqual(strategy(age)['bonds'], 1 - strategy.max_equity)
        for age in range(20, target):
            self.assertAlmostEqual(
                strategy(age, retirement_age)['stocks'],
                Decimal((target - age) / 100))
            self.assertAlmostEqual(
                strategy(age, retirement_age)['bonds'],
                Decimal(1 - (target - age) / 100))
        for age in range(target, target + 100):
            self.assertEqual(
                strategy(age, retirement_age)['stocks'],
                strategy.min_equity)
            self.assertEqual(
                strategy(age, retirement_age)['bonds'],
                1 - strategy.min_equity)

    def test_strategy_trans_to_const(self):
        """ Test AllocationStrategy.strategy_transition_to_constant. """
        method = AllocationStrategy.strategy_transition_to_const

        # Create a basic strategy that transitions from 100% stocks to
        # 50% stocks between the ages of 55 and 65.
        strategy = AllocationStrategy(
            method, 0.5,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        for age in range(18, 54):
            self.assertEqual(strategy(age)['stocks'], Decimal(1))
            self.assertEqual(strategy(age)['bonds'], Decimal(0))
        for age in range(55, 65):
            self.assertAlmostEqual(
                strategy(age)['stocks'],
                Decimal(1 * (65 - age) / 10 + 0.5 * (age - 55) / 10))
            self.assertAlmostEqual(
                strategy(age)['bonds'],
                Decimal(1 - (1 * (65 - age) / 10 + 0.5 * (age - 55) / 10)))
        for age in range(66, 100):
            self.assertEqual(strategy(age)['stocks'], Decimal(0.5))
            self.assertEqual(strategy(age)['bonds'], Decimal(0.5))


class TestDebtPaymentStrategyMethods(unittest.TestCase):
    """ A test case for the DebtPaymentStrategy class """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.initial_year = 2000
        cls.person = Person(cls.initial_year, 'Testy McTesterson', 1980,
                            retirement_date=2045)

        # These accounts have different rates:
        cls.debt_big_high_interest = Debt(
            cls.person,
            balance=Money(1000), rate=1, minimum_payment=Money(100),
            reduction_rate=1, accelerate_payment=True
        )
        cls.debt_small_low_interest = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=True
        )
        cls.debt_medium = Debt(
            cls.person,
            balance=Money(500), rate=0.5, minimum_payment=Money(50),
            reduction_rate=1, accelerate_payment=True
        )

        cls.debts = {
            cls.debt_big_high_interest,
            cls.debt_medium,
            cls.debt_small_low_interest
        }

        cls.debt_not_accelerated = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=False
        )
        cls.debt_no_reduction = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=False
        )
        cls.debt_half_reduction = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=0.5, accelerate_payment=False
        )

    @staticmethod
    def min_payment(debts, timing):
        """ Finds the minimum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.min_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    @staticmethod
    def max_payment(debts, timing):
        """ Finds the maximum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.max_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    def test_init(self):
        """ Test DebtPaymentStrategy.__init__ """
        # pylint: disable=no-member
        method = DebtPaymentStrategy.strategy_avalanche.strategy_key
        strategy = DebtPaymentStrategy(method)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, 'end')

        # Test explicit init:
        method = 'Snowball'
        timing = 'end'
        strategy = DebtPaymentStrategy(method, timing)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, timing)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = DebtPaymentStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = DebtPaymentStrategy(strategy=1)
        # Test invalid timing
        with self.assertRaises(TypeError):
            strategy = DebtPaymentStrategy(strategy=method, timing={})

    def test_strategy_snowball(self):
        """ Test DebtPaymentStrategy.strategy_snowball. """
        # Run each test on inflows and outflows
        method = DebtPaymentStrategy.strategy_snowball
        strategy = DebtPaymentStrategy(method)

        # Try a simple scenario: The amount being contributed is equal
        # to the minimum payments for the accounts.
        min_payment = self.min_payment(self.debts, strategy.timing)
        excess = Money(0)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying less than the minimum. Minimum should still be paid
        payment = Money(0)
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying a bit more than the minimum
        # The smallest debt should be paid first.
        excess = Money(10)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

        # Now pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_small_low_interest}, strategy.timing) +
            self.max_payment({self.debt_small_low_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

        # Now pay more than the first and second-paid debts will
        # accomodate. The excess should go to the next-paid debt.
        payment = (
            self.min_payment({self.debt_big_high_interest}, strategy.timing) +
            self.max_payment(
                self.debts - {self.debt_big_high_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + excess
        )

        # Now contribute more than the total max.
        payment = self.max_payment(self.debts, strategy.timing) + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflow(strategy.timing))

    def test_strategy_avalanche(self):
        """ Test DebtPaymentStrategy.strategy_avalanche. """
        # Run each test on inflows and outflows
        method = DebtPaymentStrategy.strategy_avalanche
        strategy = DebtPaymentStrategy(method)

        # Try a simple scenario: The amount being contributed is equal
        # to the minimum payments for the accounts.
        min_payment = self.min_payment(self.debts, strategy.timing)
        excess = Money(0)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying less than the minimum. Minimum should still be paid
        payment = Money(0)
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying a bit more than the minimum.
        # The highest-interest debt should be paid first.
        excess = Money(10)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

        # Now pay more than the first-paid debt will accomodate.
        # The extra $50 should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_big_high_interest}, strategy.timing) +
            self.max_payment({self.debt_big_high_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

        # Now pay more than the first and second-paid debts will
        # accomodate. The excess should go to the next-paid debt.
        payment = (
            self.min_payment({self.debt_small_low_interest}, strategy.timing) +
            self.max_payment(
                self.debts - {self.debt_small_low_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + excess
        )

        # Now contribute more than the total max.
        payment = self.max_payment(self.debts, strategy.timing) + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflow(strategy.timing))

if __name__ == '__main__':
    unittest.main()
