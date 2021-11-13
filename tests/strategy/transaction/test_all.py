''' Runs all unit tests for the `Forecaster.strategy.transaction` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/strategy/transaction', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
