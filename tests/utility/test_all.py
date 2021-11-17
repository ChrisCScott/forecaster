''' Runs all unit tests for the `Forecaster.utility` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/utility', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
