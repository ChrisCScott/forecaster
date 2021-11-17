""" Unit tests for `Strategy` and related classes. """

import unittest
from forecaster import LivingExpensesStrategy
from forecaster.strategy.base import Strategy, strategy_method


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
        self.assertEqual(
            strategy.strategies,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a function
        strategy = self.Subclass(self.Subclass.test_strategy)

        self.assertEqual(
            strategy.strategies,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test a basic initialization where we pass a bound method
        strategy = self.Subclass(strategy.test_strategy)

        self.assertEqual(
            strategy.strategies,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        self.assertEqual(
            strategy.strategies,
            {
                'Test': self.Subclass.test_strategy,
                'Test2': self.Subclass.test_strategy2})
        self.assertEqual(strategy(), 1)
        self.assertEqual(strategy(2), 2)

        # Test invalid initializations
        with self.assertRaises(ValueError):
            strategy = self.Subclass('Not a strategy')
        with self.assertRaises(TypeError):
            strategy = self.Subclass(1)

        # Also test to ensure that regular subclasses' strategy methods
        # are being added to `strategies`. We use ContributionStrategy
        # for this test. It should have at least these four strategies:
        strategies = {
            LivingExpensesStrategy.strategy_const_contribution.strategy_key:
                LivingExpensesStrategy.strategy_const_contribution,
            LivingExpensesStrategy.strategy_const_living_expenses.strategy_key:
                LivingExpensesStrategy.strategy_const_living_expenses,
            LivingExpensesStrategy.strategy_gross_percent.strategy_key:
                LivingExpensesStrategy.strategy_gross_percent,
            LivingExpensesStrategy.strategy_net_percent.strategy_key:
                LivingExpensesStrategy.strategy_net_percent
        }
        # Unfortunately, unittest.assertDictContainsSubset is deprecated
        # so we'll have to do this the long way...
        for strategy in strategies:
            self.assertIn(strategy, LivingExpensesStrategy.strategies.keys())
            self.assertIn(strategies[strategy],
                          LivingExpensesStrategy.strategies.values())

        # Finally, repeat the above with object instances instead of
        # classes. (Be careful - functions defined in class scope and
        # methods bound to objects are not the same. `s.strategies`
        # contains unbound functions, not comparable to s.strategy_*
        # methods)
        strategy = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_contribution)
        for key in strategies:
            self.assertIn(key, strategy.strategies.keys())
            self.assertIn(strategies[key], strategy.strategies.values())


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
