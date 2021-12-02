""" Unit tests for `Strategy` and related classes. """

import unittest
from forecaster import LivingExpensesStrategy
from forecaster.strategy.base import Strategy, strategy_method
from forecaster.utility.register import _REGISTERED_METHOD_KEY


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

        self.assertEqual(
            strategy.registered_methods,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a function
        strategy = self.Subclass(self.Subclass.test_strategy)

        self.assertEqual(
            strategy.registered_methods,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a bound method
        strategy = self.Subclass(strategy.test_strategy)

        self.assertEqual(
            strategy.registered_methods,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        self.assertEqual(
            strategy.registered_methods,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test invalid arguments:
        with self.assertRaises(KeyError):
            strategy = self.Subclass('Not a strategy')
            _ = strategy()

        # Also test to ensure that regular subclasses' strategy methods
        # are being added to `registered_methods`. We use
        # ContributionStrategy for this test. It should have at least
        # these four strategies:
        strategies = {
            getattr(
                LivingExpensesStrategy.strategy_const_contribution,
                _REGISTERED_METHOD_KEY):
                LivingExpensesStrategy.strategy_const_contribution,
            getattr(
                LivingExpensesStrategy.strategy_const_living_expenses,
                _REGISTERED_METHOD_KEY):
                LivingExpensesStrategy.strategy_const_living_expenses,
            getattr(
                LivingExpensesStrategy.strategy_gross_percent,
                _REGISTERED_METHOD_KEY):
                LivingExpensesStrategy.strategy_gross_percent,
            getattr(
                LivingExpensesStrategy.strategy_net_percent,
                _REGISTERED_METHOD_KEY):
                LivingExpensesStrategy.strategy_net_percent
        }
        # Unfortunately, unittest.assertDictContainsSubset is deprecated
        # so we'll have to do this the long way...
        for strategy in strategies:
            self.assertIn(
                strategy, LivingExpensesStrategy.registered_methods.keys())
            self.assertIn(
                strategies[strategy],
                LivingExpensesStrategy.registered_methods.values())

        # Finally, repeat the above with object instances instead of
        # classes. (Be careful - functions defined in class scope and
        # methods bound to objects are not the same. `s.strategies`
        # contains unbound functions, not comparable to s.strategy_*
        # methods)
        strategy = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_contribution)
        for key in strategies:
            self.assertIn(key, strategy.registered_methods.keys())
            self.assertIn(strategies[key], strategy.registered_methods.values())


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
