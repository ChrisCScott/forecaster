''' Runs all unit tests for the `Forecaster.scenario` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/scenario', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
