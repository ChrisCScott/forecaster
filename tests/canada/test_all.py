''' Runs all unit tests for the `Forecaster.canada` module. '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover(
        './tests/canada', pattern='test_*.py')

    unittest.TextTestRunner().run(SUITE)
