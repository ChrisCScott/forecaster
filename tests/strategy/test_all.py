''' Runs all unit tests for the `Forecaster.strategy` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/strategy', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
