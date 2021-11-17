''' Runs all unit tests for the `Forecaster.forecast` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/forecast', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
