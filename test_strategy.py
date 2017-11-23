""" Unit tests for `Strategy` and related classes. """

import unittest
import decimal
from decimal import Decimal
from random import Random
from ledger import *
from ledger_Canada import *
from settings import Settings
from constants import Constants
from strategy import *


class TestStrategyMethods(unittest.TestCase):
    """ A test suite for the `Strategy` class """

    # Strategy has no strategy methods by default, which means
    # __init__ will fail for every input. The easiest fix is to
    # create a subclass with a validly-decorated strategy.
    class Subclass(Strategy):
        @strategy('Test')
        def test_strategy(self, val=1):
            return val

    def test_init(self):
        """ Tests Strategy.__init__ """
        # Test a basic initialization
        s = self.Subclass('Test')

        self.assertEqual(s.strategies, {'Test': self.Subclass.test_strategy})
        self.assertEqual(s(), 1)
        self.assertEqual(s(2), 2)

        # Test a basic initialization where we pass a function
        s = self.Subclass(self.Subclass.test_strategy)

        self.assertEqual(s.strategies, {'Test': self.Subclass.test_strategy})
        self.assertEqual(s(), 1)
        self.assertEqual(s(2), 2)

        # Test a basic initialization where we pass a bound method
        s = self.Subclass(s.test_strategy)

        self.assertEqual(s.strategies, {'Test': self.Subclass.test_strategy})
        self.assertEqual(s(), 1)
        self.assertEqual(s(2), 2)

        # Test a fully-argumented initialization
        settings = Settings()
        s = self.Subclass('Test', settings)

        self.assertEqual(s.strategies, {'Test': self.Subclass.test_strategy})
        self.assertEqual(s(), 1)
        self.assertEqual(s(2), 2)

        # Test invalid initializations
        with self.assertRaises(ValueError):
            s = self.Subclass('Not a strategy')
        with self.assertRaises(TypeError):
            s = self.Subclass(1)
        with self.assertRaises(TypeError):
            s = self.Subclass('Test', 1)

        # Also test to ensure that regular subclasses' strategy methods
        # are being added to `strategies`. We use ContributionStrategy
        # for this test. It should have at least these four strategies:
        strategies = {
            ContributionStrategy._strategy_constant_contribution.strategy_key:
                ContributionStrategy._strategy_constant_contribution,
            ContributionStrategy._strategy_constant_living_expenses.strategy_key:  # noqa
                ContributionStrategy._strategy_constant_living_expenses,
            ContributionStrategy._strategy_gross_percent.strategy_key:
                ContributionStrategy._strategy_gross_percent,
            ContributionStrategy._strategy_net_percent.strategy_key:
                ContributionStrategy._strategy_net_percent
        }
        # Unfortunately, unittest.assertDictContainsSubset is deprecated
        # so we'll have to do this the long way...
        for strategy in strategies:
            self.assertIn(strategy, ContributionStrategy.strategies.keys())
            self.assertIn(strategies[strategy],
                          ContributionStrategy.strategies.values())

        # Also made sure that no strategies for other subclasses are
        # being added to this particular subclass instance.
        self.assertNotIn(WithdrawalStrategy._strategy_principal_percent,
                         ContributionStrategy.strategies.values())

        # Finally, repeat the above with object instances instead of
        # classes. (Be careful - functions defined in class scope and
        # methods bound to objects are not the same. `s.strategies`
        # contains unbound functions, not comparable to s._strategy_*
        # methods)
        s = ContributionStrategy()
        for strategy in strategies:
            self.assertIn(strategy, s.strategies.keys())
            self.assertIn(strategies[strategy], s.strategies.values())


class TestContributionStrategyMethods(unittest.TestCase):
    """ A test case for the ContributionStrategy class """

    def test_init(self):
        """ Tests ContributionStrategy.__init__ """
        # Test default init:
        s = ContributionStrategy()

        self.assertEqual(s.strategy, Settings.contribution_strategy)
        self.assertEqual(s.base_amount, Settings.contribution_base_amount)
        self.assertEqual(s.rate, Settings.contribution_rate)
        self.assertEqual(s.refund_reinvestment_rate,
                         Settings.contribution_refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted,
                         Settings.contribution_inflation_adjusted)

        # Test explicit init:
        strategy = 'Constant contribution'
        base_amount = Money('1000')
        rate = Decimal('0.5')
        refund_reinvestment_rate = Decimal('0.5')
        inflation_adjusted = True
        settings = Settings()
        s = ContributionStrategy(strategy, base_amount, rate,
                                 refund_reinvestment_rate, inflation_adjusted,
                                 settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.base_amount, base_amount)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test implicit init via Settings
        settings.contribution_strategy = strategy
        settings.contribution_base_amount = base_amount
        settings.contribution_rate = rate
        settings.contribution_refund_reinvestment_rate = \
            refund_reinvestment_rate
        settings.contribution_inflation_adjusted = inflation_adjusted
        s = ContributionStrategy(settings=settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.base_amount, base_amount)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = ContributionStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = ContributionStrategy(strategy=1)
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            s = ContributionStrategy(base_amount='a')
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            s = ContributionStrategy(rate='a')
        # Test invalid refund_reinvestment_rate
        with self.assertRaises(decimal.InvalidOperation):
            s = ContributionStrategy(refund_reinvestment_rate='a')

    def test_strategy_constant_contribution(self):
        """ Tests ContributionStrategy._strategy_constant_contribution. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_constant_contribution

        # Default strategy
        s = ContributionStrategy(method)
        # Test all default parameters (set inflation_adjustment to 1 in case
        # inflation_adjusted == True)
        self.assertEqual(s(inflation_adjustment=1),
                         Money(Settings.contribution_base_amount))
        # Test refunds ($1) and other income ($2), for a total of $3
        # plus the default contribution rate.
        self.assertEqual(s(Money(1), Money(2), inflation_adjustment=1),
                         Money(s.base_amount) +
                         Money(1) * s.refund_reinvestment_rate +
                         Money(2))
        # Test that changing net_income and gross_income has no effect
        self.assertEqual(s(0, 0, Money(100000), Money(200000), 1),
                         Money(s.base_amount))
        # Test different inflation_adjustments
        self.assertEqual(s(inflation_adjustment=Decimal('0.5')),
                         Money(s.base_amount)*Decimal('0.5'))
        self.assertEqual(s(inflation_adjustment=Decimal('2')),
                         Money(s.base_amount)*Decimal('2'))

        # Customize some inputs
        base_amount = Money(500)
        rate = Decimal('0.5')
        refund_reinvestment_rate = 1
        inflation_adjusted = False
        s = ContributionStrategy(method, base_amount, rate,
                                 refund_reinvestment_rate, inflation_adjusted)
        # Test all default parameters.
        self.assertEqual(s(), base_amount)
        # Test that changing net_income, gross_income, and inflation_adjustment
        # have no effect (note that inflation_adjusted==False)
        self.assertEqual(s(0, 0, Money(100000), Money(200000), 2),
                         base_amount)

        # Turn inflation adjustment back on so we can test inflation_adjustment
        s = ContributionStrategy(method, base_amount, rate,
                                 refund_reinvestment_rate, True)
        self.assertEqual(s(inflation_adjustment=Decimal('0.5')),
                         base_amount * Decimal('0.5'))
        self.assertEqual(s(inflation_adjustment=Decimal('2.0')),
                         base_amount * Decimal('2.0'))

    def test_strategy_constant_living_expenses(self):
        """ Tests ContributionStrategy._strategy_constant_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_constant_living_expenses

        # Default strategy
        s = ContributionStrategy(method, Money(1000))
        ex = Money(1500)  # excess money (this is the contribution)
        ni = s.base_amount + ex  # net income
        # This method requires net_income and inflation_adjustment
        self.assertEqual(s(net_income=ni, inflation_adjustment=1), ex)
        # Test that changing gross_income has no effect
        self.assertEqual(s(net_income=ni, gross_income=Money(20000),
                           inflation_adjustment=1), ex)
        # Test different inflation_adjustments.
        # Recall that arguments to s() are in nominal terms for an
        # arbitrary year, whereas arguments to __init__ are in real
        # terms (if inflation_adjustment==True). Thus, our living
        # standard of $1000 is affected by the discount rate, and
        # our net income of $2500 is not.
        # For inflation_adjustment=0.5, this means that our living expenses are
        # $500 nominally and our income is $2500, for a contribution of
        # $2000.
        self.assertEqual(s(net_income=ni, inflation_adjustment=Decimal('0.5')),
                         Money('2000'))
        # For inflation_adjustment=2, this means that our living expenses are
        # $2000 nominally and our income is $2500, for a contribution of
        # $500
        self.assertEqual(s(net_income=ni, inflation_adjustment=Decimal('2')),
                         Money('500'))
        # Test a lower net_income than the living standard:
        s = ContributionStrategy(method, Money(1000))
        self.assertEqual(s(net_income=Money(500), inflation_adjustment=1), 0)

    def test_strategy_net_percent(self):
        """ Tests ContributionStrategy._strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_net_percent

        # Default strategy
        s = ContributionStrategy(method)
        ni = Money(1000)
        # This method requires net_income and inflation_adjustment
        self.assertEqual(s(net_income=ni, inflation_adjustment=1), ni * s.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(s(net_income=ni, gross_income=Money(20000),
                           inflation_adjustment=1), ni * s.rate)
        # Test different inflation_adjustments
        # (Since the net_income argument is nominal, inflation_adjustment
        # should have no effect)
        self.assertEqual(s(net_income=ni, inflation_adjustment=Decimal('0.5')),
                         ni * s.rate)
        self.assertEqual(s(net_income=ni, inflation_adjustment=Decimal('2')),
                         ni * s.rate)

    def test_strategy_gross_percent(self):
        """ Tests ContributionStrategy._strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_gross_percent

        # Default strategy
        s = ContributionStrategy(method)
        gi = Money(1000)  # gross income
        # This method requires gross_income and inflation_adjustment
        self.assertEqual(s(gross_income=gi, inflation_adjustment=1),
                         gi * s.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(s(gross_income=gi, net_income=Money(20000),
                           inflation_adjustment=1), gi * s.rate)
        # Test different inflation_adjustments
        # (Since the gross_income argument is nominal, inflation_adjustment
        # should have no effect)
        self.assertEqual(s(gross_income=gi,
                         inflation_adjustment=Decimal('0.5')), gi * s.rate)
        self.assertEqual(s(gross_income=gi, inflation_adjustment=Decimal('2')),
                         gi * s.rate)

    def test_strategy_earnings_percent(self):
        """ Tests ContributionStrategy._strategy_earnings_percent. """
        method = ContributionStrategy._strategy_earnings_percent

        # Default strategy
        s = ContributionStrategy(method)
        ni = s.base_amount * 2
        # This method requires net_income and inflation_adjustment
        self.assertEqual(s(net_income=ni, inflation_adjustment=1),
                         (ni - s.base_amount) * s.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(s(net_income=ni, gross_income=Money(20000),
                           inflation_adjustment=1),
                         (ni - s.base_amount) * s.rate)
        # Test different inflation_adjustments
        # (This should inflation_adjust base_amount)
        inflation = Decimal('0.5')
        self.assertEqual(s(net_income=ni, inflation_adjustment=inflation),
                         (ni - s.base_amount * inflation) * s.rate)
        inflation = Decimal('2')
        self.assertEqual(s(net_income=ni, inflation_adjustment=inflation),
                         (ni - s.base_amount * inflation) * s.rate)


class TestWithdrawalStrategyMethods(unittest.TestCase):
    """ A test case for the WithdrawalStrategy class """

    def setUp(self):
        """ Sets up TestWithdrawalStrategyMethods. """
        # Several methods use varying inflation adjustment figures.
        self.year_half = 1999  # -50% inflation (values halved) in this year
        self.year_1 = 2000  # baseline year; no inflation
        self.year_2 = 2001  # 100% inflation (values doubled) in this year
        self.year_10 = 2002  # Values multiplied by 10 in this year
        self.inflation_adjustment = {self.year_half: Decimal(0.5),
                                     self.year_1: Decimal(1),
                                     self.year_2: Decimal(2),
                                     self.year_10: Decimal(10)}

    def test_init(self):
        """ Tests WithdrawalStrategy.__init__ """
        # Test default init:
        s = WithdrawalStrategy()

        self.assertEqual(s.strategy, Settings.withdrawal_strategy)
        self.assertEqual(s.rate, Settings.withdrawal_rate)
        self.assertEqual(s.min_living_standard,
                         Settings.withdrawal_min_living_standard)
        self.assertEqual(s.timing, Settings.transaction_out_timing)
        self.assertEqual(s.benefit_adjusted,
                         Settings.withdrawal_benefit_adjusted)
        self.assertEqual(s.inflation_adjusted,
                         Settings.withdrawal_inflation_adjusted)

        # Test explicit init:
        strategy = 'Constant withdrawal'
        rate = Decimal('1000')
        min_living_standard = Decimal('500')
        timing = 'end'
        benefit_adjusted = True
        inflation_adjusted = True
        settings = Settings()
        s = WithdrawalStrategy(strategy, rate, min_living_standard, timing,
                               inflation_adjusted, settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.min_living_standard, min_living_standard)
        self.assertEqual(s.timing, timing)
        self.assertEqual(s.benefit_adjusted, benefit_adjusted)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test implicit init via Settings
        settings.withdrawal_strategy = strategy
        settings.withdrawal_rate = rate
        settings.withdrawal_min_living_standard = min_living_standard
        settings.withdrawal_benefit_adjusted = benefit_adjusted
        settings.withdrawal_inflation_adjusted = inflation_adjusted
        s = WithdrawalStrategy(settings=settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.min_living_standard, min_living_standard)
        self.assertEqual(s.timing, timing)
        self.assertEqual(s.benefit_adjusted, benefit_adjusted)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = WithdrawalStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = WithdrawalStrategy(strategy=1)
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            s = WithdrawalStrategy(rate='a')
        # Test invalid min_living_standard
        with self.assertRaises(decimal.InvalidOperation):
            s = WithdrawalStrategy(min_living_standard='a')
        # Test invalid timing
        with self.assertRaises(ValueError):
            s = WithdrawalStrategy(timing='a')
        # No need to test bool-valued attributes - everything is
        # bool-convertible!

    def test_strategy_constant_withdrawal(self):
        """ Tests WithdrawalStrategy._strategy_constant_withdrawal. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy._strategy_constant_withdrawal

        # Default strategy
        s = WithdrawalStrategy(method, min_living_standard=0,
                               inflation_adjusted=False)
        # Test all default parameters. (We don't need to provide any
        # inflation data since this instance is not inflation-adjusted.)
        self.assertEqual(s(), Money(s.rate))

        # Test that providing inflation-adjusted data has no effect when
        # inflation_adjusted=False
        s = WithdrawalStrategy(method, min_living_standard=0,
                               inflation_adjusted=False)
        # We should get the same result no matter which year we use.
        for year in self.inflation_adjustment:
            self.assertEqual(
                s(0, inflation_adjustment=self.inflation_adjustment,
                  this_year=year),
                s.rate)

        # Test different inflation_adjustments
        s = WithdrawalStrategy(method, min_living_standard=0,
                               inflation_adjusted=True)
        for year in self.inflation_adjustment:
            self.assertEqual(s(inflation_adjustment=self.inflation_adjustment,
                               this_year=year),
                             Money(s.rate) * self.inflation_adjustment[year])

        # Customize the rate
        rate = Money(500)
        s = WithdrawalStrategy(method, rate, 0, 'end', False, False)
        self.assertEqual(s(), rate)

    def test_strategy_principal_percent(self):
        """ Tests WithdrawalStrategy._strategy_principal_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy._strategy_principal_percent

        rand = Random()
        principal = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            principal[year] = Money(rand.randint(0, 100000000)/100)

        s = WithdrawalStrategy(method, rate=0.5, min_living_standard=0,
                               inflation_adjusted=False)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(s(principal=principal,
                               retirement_year=retirement_year),
                             Money(s.rate * principal[retirement_year]))

        # Test that providing inflation-adjusted data has no effect when
        # inflation_adjusted=False
        for year in self.inflation_adjustment:
            self.assertEqual(
                s(principal=principal, retirement_year=retirement_year,
                  inflation_adjustment=self.inflation_adjustment,
                  this_year=year),
                Money(s.rate * principal[retirement_year]))

        # Test different inflation_adjustments
        s.inflation_adjusted = True
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            self.assertEqual(s(principal=principal,
                               retirement_year=retirement_year,
                               inflation_adjustment=self.inflation_adjustment,
                               this_year=year),
                             Money(s.rate * principal[retirement_year]) *
                             inflation_adjustment)

        # Customize the rate
        rate = Decimal('0.04')
        s = WithdrawalStrategy(method, rate, 0, 'end', False, False)
        for year in self.inflation_adjustment:
            self.assertEqual(s(principal=principal,
                               retirement_year=retirement_year),
                             rate * principal[retirement_year])

    def test_strategy_net_percent(self):
        """ Tests WithdrawalStrategy._strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy._strategy_net_percent

        rand = Random()
        net_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            net_income[year] = Money(rand.randint(0, 100000000)/100)

        s = WithdrawalStrategy(method, rate=0.5, min_living_standard=0,
                               inflation_adjusted=False)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(s(net_income=net_income,
                               retirement_year=retirement_year),
                             Money(s.rate * net_income[retirement_year]))

        # Test that providing inflation-adjusted data has no effect when
        # inflation_adjusted=False
        for year in self.inflation_adjustment:
            self.assertEqual(
                s(net_income=net_income, retirement_year=retirement_year,
                  inflation_adjustment=self.inflation_adjustment,
                  this_year=year),
                Money(s.rate * net_income[retirement_year]))

        # Test different inflation_adjustments
        s.inflation_adjusted = True
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            self.assertEqual(s(net_income=net_income,
                               retirement_year=retirement_year,
                               inflation_adjustment=self.inflation_adjustment,
                               this_year=year),
                             Money(s.rate * net_income[retirement_year]) *
                             inflation_adjustment)

        # Customize the rate
        rate = Decimal('0.04')
        s = WithdrawalStrategy(method, rate, 0, 'end', False, False)
        for year in self.inflation_adjustment:
            self.assertEqual(s(net_income=net_income,
                               retirement_year=retirement_year),
                             rate * net_income[retirement_year])

    def test_strategy_gross_percent(self):
        """ Tests WithdrawalStrategy._strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy._strategy_gross_percent

        rand = Random()
        gross_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            gross_income[year] = Money(rand.randint(0, 100000000)/100)

        s = WithdrawalStrategy(method, rate=0.5, min_living_standard=0,
                               inflation_adjusted=False)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(s(gross_income=gross_income,
                               retirement_year=retirement_year),
                             Money(s.rate * gross_income[retirement_year]))

        # Test that providing inflation-adjusted data has no effect when
        # inflation_adjusted=False
        for year in self.inflation_adjustment:
            self.assertEqual(
                s(gross_income=gross_income, retirement_year=retirement_year,
                  inflation_adjustment=self.inflation_adjustment,
                  this_year=year),
                Money(s.rate * gross_income[retirement_year]))

        # Test different inflation_adjustments
        s.inflation_adjusted = True
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            self.assertEqual(s(gross_income=gross_income,
                               retirement_year=retirement_year,
                               inflation_adjustment=self.inflation_adjustment,
                               this_year=year),
                             Money(s.rate * gross_income[retirement_year]) *
                             inflation_adjustment)

        # Customize the rate
        rate = Decimal('0.04')
        s = WithdrawalStrategy(method, rate, 0, 'end', False, False)
        for year in self.inflation_adjustment:
            self.assertEqual(s(gross_income=gross_income,
                               retirement_year=retirement_year),
                             rate * gross_income[retirement_year])

    def test_call(self):
        """ Tests __call__ logic (but not strategy-specific logic). """
        # Select a simple, constant withdrawal strategy.
        method = WithdrawalStrategy._strategy_constant_withdrawal

        # Test min_living_standard.
        # No inflation-adjustment of target withdrawal rate
        # (NOTE: min_withdrawal_strategy is always inflation-adjusted)
        rate = Money(500)
        s = WithdrawalStrategy(method, rate, Money(250), 'end', False, False)
        # For each year, confirm that we withdraw either the
        # non-inflation-adjusted rate or the inflation-adjusted min.
        # living standard, whichever is greater.
        for year in self.inflation_adjustment:
            self.assertEqual(s(0,
                               inflation_adjustment=self.inflation_adjustment,
                               this_year=year),
                             max(s.rate,
                                 Money(250) * self.inflation_adjustment[year]))

        # Test benefits. No inflation adjustment or living standard.
        s = WithdrawalStrategy(method, rate, 0, 'end', True, False)
        # $0 benefits -> no change:
        self.assertEqual(s(Money(0)), Money(s.rate))
        # $1 benefits -> $1 reduction
        self.assertEqual(s(Money(1)), Money(s.rate) - Money(1))
        # Benefits = withdrawal rate -> $0 withdrawal
        self.assertEqual(s(Money(s.rate)), Money(0))
        # Benefits > withdrawal rate -> $0 withdrawal
        self.assertEqual(s(Money(s.rate) + Money(1)), Money(0))

        # Re-run above tests, but this time with benefit_adjusted=False
        s = WithdrawalStrategy(method, rate, 0, 'end', False, False)
        # In every case, there should be no change:
        self.assertEqual(s(Money(0)), Money(s.rate))
        self.assertEqual(s(Money(1)), Money(s.rate))
        self.assertEqual(s(Money(s.rate)), Money(s.rate))
        self.assertEqual(s(Money(s.rate) + Money(1)), Money(s.rate))


class TestTransactionStrategyMethods(unittest.TestCase):
    """ A test case for the TransactionStrategy class """

    @classmethod
    def setUpClass(cls):
        cls.person = Person('Testy McTesterson', 1980, retirement_date=2045)
        cls.initial_year = 2000
        cls.inflation_adjustments = {
            cls.initial_year: Decimal(1),
            cls.initial_year + 1: Decimal(1.25),
            min(Constants.RRSPContributionRoomAccrualMax): Decimal(1)}

        # Set up some accounts for the tests.
        cls.rrsp = RRSP(cls.person, inflation_adjust=cls.inflation_adjustments,
                        balance=Money(200), contribution_room=Money(200),
                        initial_year=min(cls.inflation_adjustments.keys()))
        cls.tfsa = TFSA(cls.person, inflation_adjust=cls.inflation_adjustments,
                        balance=Money(100), contribution_room=Money(100),
                        initial_year=min(cls.inflation_adjustments.keys()))
        cls.taxableAccount = TaxableAccount(cls.person, balance=Money(1000))
        cls.accounts = [cls.rrsp, cls.tfsa, cls.taxableAccount]

    def test_init(self):
        """ Tests TransactionStrategy.__init__ """
        # TransactionStrategy doesn't have a default init, so test with
        # TransactionInStrategy defaults:
        s = TransactionStrategy(Settings.transaction_in_strategy,
                                Settings.transaction_in_weights,
                                Settings.transaction_in_timing)
        self.assertEqual(s.strategy, Settings.transaction_in_strategy)
        self.assertEqual(s.weights, Settings.transaction_in_weights)
        self.assertEqual(s.timing, Settings.transaction_in_timing)

        # Try default init with TransactionInStrategy:
        s = TransactionInStrategy()
        self.assertEqual(s.strategy, Settings.transaction_in_strategy)
        self.assertEqual(s.weights, Settings.transaction_in_weights)
        self.assertEqual(s.timing, Settings.transaction_in_timing)

        # Try default init with TransactionOutStrategy:
        s = TransactionOutStrategy()
        self.assertEqual(s.strategy, Settings.transaction_out_strategy)
        self.assertEqual(s.weights, Settings.transaction_out_weights)
        self.assertEqual(s.timing, Settings.transaction_out_timing)

        # Test explicit init for subclasses:
        strategy = 'Weighted'
        weights = {'RRSP': Decimal(0.5),
                   'TFSA': Decimal(0.25),
                   'TaxableAccount': Decimal(0.25)}
        timing = 'end'
        settings = Settings()
        s = TransactionInStrategy(strategy, weights, timing, settings)
        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.weights, weights)
        self.assertEqual(s.timing, timing)

        # Test implicit init via Settings
        settings.transaction_in_strategy = strategy
        settings.transaction_in_weights = weights
        settings.transaction_in_timing = timing
        s = TransactionInStrategy(settings=settings)
        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.weights, weights)
        self.assertEqual(s.timing, timing)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = TransactionInStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = TransactionInStrategy(strategy=1)
        # Test invalid weight
        with self.assertRaises(TypeError):  # not a dict
            s = TransactionInStrategy(weights='a')
        with self.assertRaises(TypeError):  # dict with non-str keys
            s = TransactionInStrategy(weights={1: 5})
        with self.assertRaises(TypeError):  # dict with non-numeric values
            s = TransactionInStrategy(weights={'RRSP', 'Not a number'})
        # Test invalid timing
        with self.assertRaises(TypeError):
            s = TransactionInStrategy(timing={})

    def test_strategy_ordered(self):
        """ Tests TransactionStrategy._strategy_ordered. """
        # Run each test on inflows and outflows
        method = TransactionStrategy._strategy_ordered
        s_in = TransactionInStrategy(method, {
            'RRSP': 1,
            'TFSA': 2,
            'TaxableAccount': 3
            })
        s_out = TransactionOutStrategy(method, {
            'RRSP': 1,
            'TFSA': 2,
            'TaxableAccount': 3
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room in the top-weighted
        # account type.
        results = s_in(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxableAccount], Money(0))
        # Try again with outflows.
        results = s_out(-Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxableAccount], Money(0))

        # Now contribute more than the rrsp will accomodate. The extra
        # $50 should go to the tfsa, which is next in line.
        results = s_in(Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(50))
        self.assertEqual(results[self.taxableAccount], Money(0))
        results = s_out(-Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-50))
        self.assertEqual(results[self.taxableAccount], Money(0))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        results = s_in(Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxableAccount], Money(700))
        results = s_out(-Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxableAccount], Money(-700))

        # For outflows only, try withdrawing more than the accounts have
        results = s_out(-Money(10000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxableAccount], Money(-1000))

        # Now change the order and confirm that it still works
        s_in.weights['RRSP'] = 2
        s_in.weights['TFSA'] = 1
        results = s_in(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(0))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxableAccount], Money(0))

    def test_strategy_weighted(self):
        """ Tests TransactionStrategy._strategy_weighted. """
        # Run each test on inflows and outflows
        method = TransactionStrategy._strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxableAccount_weight = Decimal('0.3')
        s_in = TransactionInStrategy(method, {
            'RRSP': rrsp_weight,
            'TFSA': tfsa_weight,
            'TaxableAccount': taxableAccount_weight
            })
        s_out = TransactionOutStrategy(method, {
            'RRSP': rrsp_weight,
            'TFSA': tfsa_weight,
            'TaxableAccount': taxableAccount_weight
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room for each account
        val = Money(min([a.max_inflow() for a in self.accounts]))
        results = s_in(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxableAccount],
                         val * taxableAccount_weight)
        # Try again with outflows. Amount withdrawn is less than
        # the balance of each account.
        val = -Money(max([a.max_outflow() for a in self.accounts]))
        results = s_out(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxableAccount],
                         val * taxableAccount_weight)

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
        results = s_in(val, self.accounts)
        # Do tests 1-3:
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertGreater(results[self.rrsp], results[self.taxableAccount])
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
            val * taxableAccount_weight +
            overage * taxableAccount_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) *
            taxableAccount_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxableAccount],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxableAccount],
                             max(taxable_vals))

        # Try again with outflows.
        threshold = self.tfsa.max_outflow() / tfsa_weight
        overage = -overage
        val = Money(threshold + overage)
        results = s_out(val, self.accounts)
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertLess(results[self.rrsp], results[self.taxableAccount])
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxableAccount_weight +
            overage * taxableAccount_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) *
            taxableAccount_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxableAccount],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxableAccount],
                             max(taxable_vals))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(self.rrsp.max_inflow() / rrsp_weight,
                        self.tfsa.max_inflow() / tfsa_weight)
        overage = abs(overage)
        val = threshold + overage
        results = s_in(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_inflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertEqual(results[self.taxableAccount], val -
                         (self.rrsp.max_inflow() + self.tfsa.max_inflow()))
        # For withdrawals, try withdrawing just a little less than the
        # total available balance. This will clear out the RRSP and TFSA
        # NOTE: `overage` is positive; other values below are negative
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxableAccount.max_outflow() + overage
        results = s_out(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(results[self.taxableAccount],
                         self.taxableAccount.max_outflow() + overage)

        # For outflows only, try withdrawing more than the accounts have
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxableAccount.max_outflow() - overage
        results = s_out(val, self.accounts)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(results[self.taxableAccount],
                         self.taxableAccount.max_outflow())


class TestAllocationStrategyMethods(unittest.TestCase):
    """ A test case for the AllocationStrategy class """

    def test_init(self):
        """ Tests AllocationStrategy.__init__ """
        # Arguments for AllocationStrategy are:
        # strategy (str, func)
        # min_equity (Decimal)
        # max_equity (Decimal)
        # target (Decimal)
        # standard_retirement_age (int)
        # risk_transition_period (int)
        # adjust_for_retirement_plan (bool)

        # Test default init:
        s = AllocationStrategy()
        self.assertEqual(s.strategy, Settings.allocation_strategy)
        self.assertEqual(s.min_equity, Settings.allocation_min_equity)
        self.assertEqual(s.max_equity, Settings.allocation_max_equity)
        # The default target varies depending on the strategy
        if s.strategy == AllocationStrategy._strategy_n_minus_age.strategy_key:
            self.assertEqual(s.target,
                             Settings.allocation_constant_strategy_target)
        elif s.strategy == (
          AllocationStrategy._strategy_transition_to_constant.strategy_key):
            self.assertEqual(s.target,
                             Settings.allocation_transition_strategy_target)
        else:
            self.assertEqual(s.target, 0)
        self.assertEqual(s.standard_retirement_age,
                         Settings.allocation_standard_retirement_age)
        self.assertEqual(s.risk_transition_period,
                         Settings.allocation_risk_transition_period)
        self.assertEqual(s.adjust_for_retirement_plan,
                         Settings.allocation_adjust_for_retirement_plan)

        # Test explicit init:
        strategy = AllocationStrategy._strategy_n_minus_age
        min_equity = 0
        max_equity = 1
        target = '0.5'
        standard_retirement_age = 65.0
        risk_transition_period = '10'
        adjust_for_retirement_plan = 'Evaluates to True'
        settings = Settings()
        s = AllocationStrategy(strategy, min_equity, max_equity, target,
                               standard_retirement_age, risk_transition_period,
                               adjust_for_retirement_plan, settings)
        self.assertEqual(s.strategy, strategy.strategy_key)
        self.assertEqual(s.min_equity, Decimal(min_equity))
        self.assertEqual(s.max_equity, Decimal(max_equity))
        self.assertEqual(s.target, Decimal(target))
        self.assertEqual(s.standard_retirement_age,
                         int(standard_retirement_age))
        self.assertEqual(s.risk_transition_period,
                         int(risk_transition_period))
        self.assertEqual(s.adjust_for_retirement_plan,
                         bool(adjust_for_retirement_plan))

        # Type-check:
        self.assertIsInstance(s.strategy, str)
        self.assertIsInstance(s.min_equity, Decimal)
        self.assertIsInstance(s.max_equity, Decimal)
        self.assertIsInstance(s.target, Decimal)
        self.assertIsInstance(s.standard_retirement_age, int)
        self.assertIsInstance(s.risk_transition_period, int)
        self.assertIsInstance(s.adjust_for_retirement_plan, bool)

        # Test implicit init via Settings
        settings.allocation_strategy = strategy.strategy_key
        settings.allocation_min_equity = min_equity
        settings.allocation_max_equity = max_equity
        settings.allocation_constant_strategy_target = target
        settings.allocation_standard_retirement_age = standard_retirement_age
        settings.allocation_risk_transition_period = risk_transition_period
        settings.allocation_adjust_for_retirement_plan = \
            adjust_for_retirement_plan
        s = AllocationStrategy(settings=settings)
        self.assertEqual(s.strategy, strategy.strategy_key)
        self.assertEqual(s.min_equity, Decimal(min_equity))
        self.assertEqual(s.max_equity, Decimal(max_equity))
        self.assertEqual(s.target, Decimal(target))
        self.assertEqual(s.standard_retirement_age,
                         int(standard_retirement_age))
        self.assertEqual(s.risk_transition_period,
                         int(risk_transition_period))
        self.assertEqual(s.adjust_for_retirement_plan,
                         bool(adjust_for_retirement_plan))

        # Type-check:
        self.assertIsInstance(s.strategy, str)
        self.assertIsInstance(s.min_equity, Decimal)
        self.assertIsInstance(s.max_equity, Decimal)
        self.assertIsInstance(s.target, Decimal)
        self.assertIsInstance(s.standard_retirement_age, int)
        self.assertIsInstance(s.risk_transition_period, int)
        self.assertIsInstance(s.adjust_for_retirement_plan, bool)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = AllocationStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = AllocationStrategy(strategy=1)
        # Test invalid min_equity (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            s = AllocationStrategy(min_equity='invalid')
        # Test invalid max_equity (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            s = AllocationStrategy(max_equity='invalid')
        # Test invalid target (Decimal)
        with self.assertRaises(decimal.InvalidOperation):
            s = AllocationStrategy(target='invalid')
        # Test invalid standard_retirement_age (int)
        with self.assertRaises(ValueError):
            s = AllocationStrategy(standard_retirement_age='invalid')
        # Test invalid risk_transition_period (int)
        with self.assertRaises(ValueError):
            s = AllocationStrategy(risk_transition_period='invalid')
        # No need to test invalid adjust_for_retirement_plan (bool)

        # Test mismatched min and max equity thresholds
        with self.assertRaises(ValueError):
            s = AllocationStrategy(min_equity=1, max_equity=0)
        # Confirm that the thresholds *can* be the same:
        s = AllocationStrategy(min_equity=0.5, max_equity=0.5)
        self.assertEqual(s.min_equity, s.max_equity)

    def test_strategy_n_minus_age(self):
        """ Tests AllocationStrategy._strategy_n_minus_age. """
        method = AllocationStrategy._strategy_n_minus_age

        # Create a basic strategy that puts 100-age % into equity
        n = 100
        s = AllocationStrategy(method, 0, 1, n, 65, 10, False)

        for age in range(0, n):
            self.assertAlmostEqual(s(age).equity, Decimal((n - age)/100))
            self.assertAlmostEqual(s(age).fixed_income,
                                   Decimal(1 - (n - age)/100))
        for age in range(n, n + 100):
            self.assertEqual(s(age).equity, s.min_equity)
            self.assertEqual(s(age).fixed_income, 1 - s.min_equity)

        # Try with adjustments for retirement plans enabled.
        # Use n = 120, but a retirement age that's 20 years early.
        # After adjusting for retirement plans, the results should be
        # the same as in the above test
        n = 120
        standard_retirement_age = 65
        diff = -20
        retirement_age = standard_retirement_age + diff
        s = AllocationStrategy(method, 0, 1, n, standard_retirement_age, 10,
                               True)

        for age in range(0, n + diff):
            self.assertAlmostEqual(s(age, retirement_age).equity,
                                   Decimal((n + diff - age)/100))
            self.assertAlmostEqual(s(age, retirement_age).fixed_income,
                                   Decimal(1 - (n + diff - age)/100))
        for age in range(n + diff, n + diff + 100):
            self.assertEqual(s(age, retirement_age).equity,
                             s.min_equity)
            self.assertEqual(s(age, retirement_age).fixed_income,
                             1 - s.min_equity)

        # Finally, try n=120 without adjusting the retirement age to
        # confirm that max_equity is respected.
        n = 120
        standard_retirement_age = 65
        retirement_age = standard_retirement_age - 20
        s = AllocationStrategy(method, 0, 1, n, standard_retirement_age, 10,
                               False)

        for age in range(0, 20):
            self.assertEqual(s(age).equity, s.max_equity)
            self.assertEqual(s(age).fixed_income, 1 - s.max_equity)
        for age in range(20, n):
            self.assertAlmostEqual(s(age, retirement_age).equity,
                                   Decimal((n - age)/100))
            self.assertAlmostEqual(s(age, retirement_age).fixed_income,
                                   Decimal(1 - (n - age)/100))
        for age in range(n, n + 100):
            self.assertEqual(s(age, retirement_age).equity,
                             s.min_equity)
            self.assertEqual(s(age, retirement_age).fixed_income,
                             1 - s.min_equity)

    def test_strategy_transition_to_constant(self):
        """ Tests AllocationStrategy._strategy_transition_to_constant. """
        method = AllocationStrategy._strategy_transition_to_constant

        # Create a basic strategy that transitions from 100% stocks to
        # 50% stocks between the ages of 55 and 65.
        s = AllocationStrategy(method, 0, 1, 0.5, 65, 10, False)

        for age in range(18, 54):
            self.assertEqual(s(age).equity, Decimal(1))
            self.assertEqual(s(age).fixed_income, Decimal(0))
        for age in range(55, 65):
            self.assertAlmostEqual(
                s(age).equity, Decimal(1*(65-age)/10 + 0.5*(age-55)/10))
            self.assertAlmostEqual(
                s(age).fixed_income,
                Decimal(1-(1*(65-age)/10 + 0.5*(age-55)/10)))
        for age in range(66, 100):
            self.assertEqual(s(age).equity, Decimal(0.5))
            self.assertEqual(s(age).fixed_income, Decimal(0.5))


class TestDebtPaymentStrategyMethods(unittest.TestCase):
    """ A test case for the DebtPaymentStrategy class """

    @classmethod
    def setUpClass(cls):
        cls.person = Person('Testy McTesterson', 1980, retirement_date=2045)
        cls.initial_year = 2000
        cls.inflation_adjustments = {
            cls.initial_year: Decimal(1),
            cls.initial_year + 1: Decimal(1.25),
            min(Constants.RRSPContributionRoomAccrualMax): Decimal(1)}

        # Set up some accounts for the tests.
        # Debt 1: No interest, accelerated, $10 min.
        cls.debt1 = Debt(cls.person, balance=Money(200), rate=0,
                         initial_year=cls.initial_year,
                         minimum_payment=Money(10), reduction_rate=1,
                         accelerate_payment=True)
        # Debt 2: Same as debt 1, but only 50% is drawn from savings
        # (so payments should be 2x as large)
        cls.debt2 = Debt(cls.person, balance=Money(200), rate=0,
                         initial_year=cls.initial_year,
                         minimum_payment=Money(10), reduction_rate=0.5,
                         accelerate_payment=True)
        # Debt 3: Non-accelerated debt with 12.5% interest rate.
        cls.debt3 = Debt(cls.person, balance=Money(200), rate=0.125,
                         initial_year=cls.initial_year,
                         minimum_payment=Money(10), reduction_rate=1,
                         accelerate_payment=False)
        # Debt 4: Acclerated debt with 25% interest rate
        cls.debt4 = Debt(cls.person, balance=Money(200), rate=0.25,
                         initial_year=cls.initial_year,
                         minimum_payment=Money(10), reduction_rate=1,
                         accelerate_payment=True)
        # Debt 5: Debt paid entirely from living expenses
        cls.debt5 = Debt(cls.person, balance=Money(200), rate=0,
                         initial_year=cls.initial_year,
                         minimum_payment=Money(10), reduction_rate=0,
                         accelerate_payment=True)
        cls.debts = {cls.debt1, cls.debt2, cls.debt3, cls.debt4, cls.debt5}

    def test_init(self):
        """ Tests DebtPaymentStrategy.__init__ """
        s = DebtPaymentStrategy()
        # TransactionStrategy doesn't have a default init, so test with
        # TransactionInStrategy defaults:
        s = TransactionStrategy(Settings.transaction_in_strategy,
                                Settings.transaction_in_weights,
                                Settings.transaction_in_timing)
        self.assertEqual(s.strategy, Settings.transaction_in_strategy)
        self.assertEqual(s.weights, Settings.transaction_in_weights)
        self.assertEqual(s.timing, Settings.transaction_in_timing)

        # Try default init with TransactionInStrategy:
        s = TransactionInStrategy()
        self.assertEqual(s.strategy, Settings.transaction_in_strategy)
        self.assertEqual(s.weights, Settings.transaction_in_weights)
        self.assertEqual(s.timing, Settings.transaction_in_timing)

        # Try default init with TransactionOutStrategy:
        s = TransactionOutStrategy()
        self.assertEqual(s.strategy, Settings.transaction_out_strategy)
        self.assertEqual(s.weights, Settings.transaction_out_weights)
        self.assertEqual(s.timing, Settings.transaction_out_timing)

        # Test explicit init for subclasses:
        strategy = 'Weighted'
        weights = {'RRSP': Decimal(0.5),
                   'TFSA': Decimal(0.25),
                   'TaxableAccount': Decimal(0.25)}
        timing = 'end'
        settings = Settings()
        s = TransactionInStrategy(strategy, weights, timing, settings)
        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.weights, weights)
        self.assertEqual(s.timing, timing)

        # Test implicit init via Settings
        settings.transaction_in_strategy = strategy
        settings.transaction_in_weights = weights
        settings.transaction_in_timing = timing
        s = TransactionInStrategy(settings=settings)
        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.weights, weights)
        self.assertEqual(s.timing, timing)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = TransactionInStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = TransactionInStrategy(strategy=1)
        # Test invalid weight
        with self.assertRaises(TypeError):  # not a dict
            s = TransactionInStrategy(weights='a')
        with self.assertRaises(TypeError):  # dict with non-str keys
            s = TransactionInStrategy(weights={1: 5})
        with self.assertRaises(TypeError):  # dict with non-numeric values
            s = TransactionInStrategy(weights={'RRSP', 'Not a number'})
        # Test invalid timing
        with self.assertRaises(TypeError):
            s = TransactionInStrategy(timing={})

    def test_strategy_ordered(self):
        """ Tests TransactionStrategy._strategy_ordered. """
        # Run each test on inflows and outflows
        method = TransactionStrategy._strategy_ordered
        s_in = TransactionInStrategy(method, {
            'RRSP': 1,
            'TFSA': 2,
            'TaxableAccount': 3
            })
        s_out = TransactionOutStrategy(method, {
            'RRSP': 1,
            'TFSA': 2,
            'TaxableAccount': 3
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room in the top-weighted
        # account type.
        results = s_in(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxableAccount], Money(0))
        # Try again with outflows.
        results = s_out(-Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxableAccount], Money(0))

        # Now contribute more than the rrsp will accomodate. The extra
        # $50 should go to the tfsa, which is next in line.
        results = s_in(Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(50))
        self.assertEqual(results[self.taxableAccount], Money(0))
        results = s_out(-Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-50))
        self.assertEqual(results[self.taxableAccount], Money(0))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        results = s_in(Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxableAccount], Money(700))
        results = s_out(-Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxableAccount], Money(-700))

        # For outflows only, try withdrawing more than the accounts have
        results = s_out(-Money(10000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxableAccount], Money(-1000))

        # Now change the order and confirm that it still works
        s_in.weights['RRSP'] = 2
        s_in.weights['TFSA'] = 1
        results = s_in(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(0))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxableAccount], Money(0))

    def test_strategy_weighted(self):
        """ Tests TransactionStrategy._strategy_weighted. """
        # Run each test on inflows and outflows
        method = TransactionStrategy._strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxableAccount_weight = Decimal('0.3')
        s_in = TransactionInStrategy(method, {
            'RRSP': rrsp_weight,
            'TFSA': tfsa_weight,
            'TaxableAccount': taxableAccount_weight
            })
        s_out = TransactionOutStrategy(method, {
            'RRSP': rrsp_weight,
            'TFSA': tfsa_weight,
            'TaxableAccount': taxableAccount_weight
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room for each account
        val = Money(min([a.max_inflow() for a in self.accounts]))
        results = s_in(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxableAccount],
                         val * taxableAccount_weight)
        # Try again with outflows. Amount withdrawn is less than
        # the balance of each account.
        val = -Money(max([a.max_outflow() for a in self.accounts]))
        results = s_out(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxableAccount],
                         val * taxableAccount_weight)

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
        results = s_in(val, self.accounts)
        # Do tests 1-3:
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertGreater(results[self.rrsp], results[self.taxableAccount])
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
            val * taxableAccount_weight +
            overage * taxableAccount_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) *
            taxableAccount_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxableAccount],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxableAccount],
                             max(taxable_vals))

        # Try again with outflows.
        threshold = self.tfsa.max_outflow() / tfsa_weight
        overage = -overage
        val = Money(threshold + overage)
        results = s_out(val, self.accounts)
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertLess(results[self.rrsp], results[self.taxableAccount])
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxableAccount_weight +
            overage * taxableAccount_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) *
            taxableAccount_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxableAccount],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxableAccount],
                             max(taxable_vals))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(self.rrsp.max_inflow() / rrsp_weight,
                        self.tfsa.max_inflow() / tfsa_weight)
        overage = abs(overage)
        val = threshold + overage
        results = s_in(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_inflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertEqual(results[self.taxableAccount], val -
                         (self.rrsp.max_inflow() + self.tfsa.max_inflow()))
        # For withdrawals, try withdrawing just a little less than the
        # total available balance. This will clear out the RRSP and TFSA
        # NOTE: `overage` is positive; other values below are negative
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxableAccount.max_outflow() + overage
        results = s_out(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(results[self.taxableAccount],
                         self.taxableAccount.max_outflow() + overage)

        # For outflows only, try withdrawing more than the accounts have
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxableAccount.max_outflow() - overage
        results = s_out(val, self.accounts)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(results[self.taxableAccount],
                         self.taxableAccount.max_outflow())

if __name__ == '__main__':
    unittest.main()
