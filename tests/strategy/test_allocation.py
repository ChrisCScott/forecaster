""" Unit tests for `ContributionStrategy` and `WithdrawalStrategy`. """

import unittest
import decimal
from decimal import Decimal
from forecaster import AllocationStrategy


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


if __name__ == '__main__':
    unittest.main()
