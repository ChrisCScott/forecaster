""" Provides convenience classes and methods for testing. """

import unittest

# How many digits to round results to:
PLACES_PRECISION = 4

class TestCaseTransactions(unittest.TestCase):
    """ A test case for non-strategy method of TransactionStrategy. """

    def assertTransactions(self, transactions, value, places=PLACES_PRECISION):
        """ Convenience method for testing transactions. """
        # pylint: disable=invalid-name
        # The naming here uses the style of unittest `assert*` methods.
        self.assertAlmostEqual(
            sum(transactions.values()), value, places=places)

    def assertAlmostEqual(
            self, first, second, places=None, msg=None, delta=None):
        """ Overrides assertAlmostEqual to round more aggressively. """
        if places is None:
            places = PLACES_PRECISION
        super().assertAlmostEqual(
            first, second, places=places, msg=msg, delta=delta)
