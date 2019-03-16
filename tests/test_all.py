''' Runs all unit tests for the `Forecaster` package '''

import unittest
import warnings

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover('.', pattern='test_*.py')
    # Money throws a lot of deprecation warnings. Ignore these when
    # running a global test.
    warnings.simplefilter("ignore", DeprecationWarning)

    unittest.TextTestRunner().run(SUITE)
