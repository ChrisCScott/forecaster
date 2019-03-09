''' Runs all unit tests for the `Forecaster` package '''

import unittest

if __name__ == '__main__':
    SUITE = unittest.TestLoader().discover('.', pattern='test_*.py')
    unittest.TextTestRunner().run(SUITE)
    # unittest.main()
