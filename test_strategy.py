""" Unit tests for `Strategy` and related classes. """

import unittest
from decimal import Decimal
from random import Random
from settings import Settings
from strategy import *


class TestStrategyABCMethods(unittest.TestCase):
    """ A test suite for the `StrategyABC` class """

    # StrategyABC has no strategy methods by default, which means
    # __init__ will fail for every input. The easiest fix is to
    # create a subclass with a validly-decorated strategy.
    class Subclass(StrategyABC):
        @strategy('Test')
        def test_strategy(self, val=1):
            return val

    def test_init(self):
        """ Tests StrategyABC.__init__ """
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
        self.assertEqual(s.rate, Settings.contribution_rate)
        self.assertEqual(s.refund_reinvestment_rate,
                         Settings.contribution_refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted,
                         Settings.contribution_inflation_adjusted)

        # Test explicit init:
        strategy = 'Constant contribution'
        rate = Decimal('1000')
        refund_reinvestment_rate = Decimal('0.5')
        inflation_adjusted = True
        settings = Settings()
        s = ContributionStrategy(strategy, rate, refund_reinvestment_rate,
                                 inflation_adjusted, settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test implicit init via Settings
        settings.contribution_strategy = strategy
        settings.contribution_rate = rate
        settings.contribution_refund_reinvestment_rate = \
            refund_reinvestment_rate
        settings.contribution_inflation_adjusted = inflation_adjusted
        s = ContributionStrategy(settings=settings)

        self.assertEqual(s.strategy, strategy)
        self.assertEqual(s.rate, rate)
        self.assertEqual(s.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(s.inflation_adjusted, inflation_adjusted)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            s = ContributionStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            s = ContributionStrategy(strategy=1)
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
        # Test all default parameters (set discount_rate to 1 in case
        # inflation_adjusted == True)
        self.assertEqual(s(discount_rate=1), Money(Settings.contribution_rate))
        # Test refunds and other income
        self.assertEqual(s(Money(1), Money(2), discount_rate=1),
                         Money(s.rate) +
                         Money(1) * s.refund_reinvestment_rate +
                         Money(2))
        # Test that changing net_income and gross_income has no effect
        self.assertEqual(s(0, 0, Money(100000), Money(200000), 1),
                         Money(s.rate))
        # Test different discount_rates
        self.assertEqual(s(discount_rate=Decimal('0.5')),
                         Money(s.rate)*Decimal('0.5'))
        self.assertEqual(s(discount_rate=Decimal('2')),
                         Money(s.rate)*Decimal('2'))

        # Customize some inputs
        rate = Money(500)
        refund_reinvestment_rate = 1
        inflation_adjusted = False
        s = ContributionStrategy(method, rate, refund_reinvestment_rate,
                                 inflation_adjusted)
        # Test all default parameters.
        self.assertEqual(s(), rate)
        # Test that changing net_income, gross_income, and discount_rate
        # have no effect (note that inflation_adjusted==False)
        self.assertEqual(s(0, 0, Money(100000), Money(200000), 2), rate)

        # Turn inflation adjustment back on so we can test discount_rate
        s = ContributionStrategy(method, rate, refund_reinvestment_rate, True)
        self.assertEqual(s(discount_rate=Decimal('0.5')), rate*Decimal('0.5'))
        self.assertEqual(s(discount_rate=Decimal('2.0')), rate*Decimal('2.0'))

    def test_strategy_constant_living_expenses(self):
        """ Tests ContributionStrategy._strategy_constant_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_constant_living_expenses

        # Default strategy
        s = ContributionStrategy(method, Money(1000))
        ex = Money(1500)  # excess money (this is the contribution)
        ni = s.rate + ex  # net income
        # This method requires net_income and discount_rate
        self.assertEqual(s(net_income=ni, discount_rate=1), ex)
        # Test that changing gross_income has no effect
        self.assertEqual(s(net_income=ni, gross_income=Money(20000),
                           discount_rate=1), ex)
        # Test different discount_rates.
        # Recall that arguments to s() are in nominal terms for an
        # arbitrary year, whereas arguments to __init__ are in real
        # terms (if inflation_adjustment==True). Thus, our living
        # standard of $1000 is affected by the discount rate, and
        # our net income of $2500 is not.
        # For discount_rate=0.5, this means that our living expenses are
        # $500 nominally and our income is $2500, for a contribution of
        # $2000.
        self.assertEqual(s(net_income=ni, discount_rate=Decimal('0.5')),
                         Money('2000'))
        # For discount_rate=2, this means that our living expenses are
        # $2000 nominally and our income is $2500, for a contribution of
        # $500
        self.assertEqual(s(net_income=ni, discount_rate=Decimal('2')),
                         Money('500'))
        # Test a lower net_income than the living standard:
        s = ContributionStrategy(method, Money(1000))
        self.assertEqual(s(net_income=Money(500), discount_rate=1), 0)

    def test_strategy_net_percent(self):
        """ Tests ContributionStrategy._strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_net_percent

        # Default strategy
        s = ContributionStrategy(method)
        ni = Money(1000)
        # This method requires net_income and discount_rate
        self.assertEqual(s(net_income=ni, discount_rate=1), ni * s.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(s(net_income=ni, gross_income=Money(20000),
                           discount_rate=1), ni * s.rate)
        # Test different discount_rates
        # (Since the net_income argument is nominal, discount_rate
        # should have no effect)
        self.assertEqual(s(net_income=ni, discount_rate=Decimal('0.5')),
                         ni * s.rate)
        self.assertEqual(s(net_income=ni, discount_rate=Decimal('2')),
                         ni * s.rate)

    def test_strategy_gross_percent(self):
        """ Tests ContributionStrategy._strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy._strategy_gross_percent

        # Default strategy
        s = ContributionStrategy(method)
        gi = Money(1000)  # gross income
        # This method requires gross_income and discount_rate
        self.assertEqual(s(gross_income=gi, discount_rate=1), gi * s.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(s(gross_income=gi, net_income=Money(20000),
                           discount_rate=1), gi * s.rate)
        # Test different discount_rates
        # (Since the gross_income argument is nominal, discount_rate
        # should have no effect)
        self.assertEqual(s(gross_income=gi, discount_rate=Decimal('0.5')),
                         gi * s.rate)
        self.assertEqual(s(gross_income=gi, discount_rate=Decimal('2')),
                         gi * s.rate)


class TestWithdrawalStrategyMethods(unittest.TestCase):
    """ A test case for the WithdrawalStrategy class """

    def test_init(self):
        """ Tests WithdrawalStrategy.__init__ """
        # TODO
        pass

    def test_strategy_constant_contribution(self):
        """ Tests ContributionStrategy._strategy_constant_contribution. """
        # TODO
        pass

    def test_strategy_principal_percent(self):
        """ Tests WithdrawalStrategy._strategy_principal_percent. """
        # TODO
        pass

    def test_strategy_net_percent(self):
        """ Tests WithdrawalStrategy._strategy_net_percent. """
        # TODO
        pass

    def test_strategy_gross_percent(self):
        """ Tests WithdrawalStrategy._strategy_gross_percent. """
        # TODO
        pass


class TestWithdrawalStrategyMethods(unittest.TestCase):
    """ A test case for the WithdrawalStrategy class """

    def test_init(self):
        """ Tests WithdrawalStrategy.__init__ """
        # TODO
        pass

    def test_strategy_constant_contribution(self):
        """ Tests ContributionStrategy._strategy_constant_contribution. """
        # TODO
        pass

    def test_strategy_principal_percent(self):
        """ Tests WithdrawalStrategy._strategy_principal_percent. """
        # TODO
        pass

    def test_strategy_net_percent(self):
        """ Tests WithdrawalStrategy._strategy_net_percent. """
        # TODO
        pass

    def test_strategy_gross_percent(self):
        """ Tests WithdrawalStrategy._strategy_gross_percent. """
        # TODO
        pass


if __name__ == '__main__':
    unittest.main()
