""" Unit tests for `Ledger` class. """

import unittest
from forecaster.ledger import (
    Ledger, recorded_property, recorded_property_cached)


class TestLedger(Ledger):
    """ Test class with cached and uncached recorded properties. """

    def __init__(self):
        """ Init method that adds a `counter` attribute """
        super().__init__(0)
        self.counter = 0

    @recorded_property
    def uncached(self):
        self.counter += 1
        return self.counter

    @recorded_property_cached
    def cached(self):
        self.counter += 1
        return self.counter


class TestLedgerMethods(unittest.TestCase):
    """ A test suite for the `Ledger` class. """

    def setUp(self):
        """ Sets up stock attributes for testing. """
        self.ledger = TestLedger()

    def test_uncached(self):
        """ Tests uncached properties. """
        self.assertEqual(self.ledger.uncached, 1)
        self.assertEqual(self.ledger.uncached, 2)

    def test_cached(self):
        """ Tests cached properties. """
        # `cached` will be cached when it is first called:
        self.ledger.counter = 5
        self.assertEqual(self.ledger.cached, 6)
        # `cached` should return the same value on every
        # subsequent call no matter what `counter` is:
        self.ledger.counter = 10
        self.assertEqual(self.ledger.cached, 6)

    def test_clear_cache(self):
        """ Clears cache """
        # `cached` will be cached when it is first called:
        self.ledger.counter = 2
        self.assertEqual(self.ledger.cached, 3)
        # Clearing the cache doesn't change `counter`, but
        # it does allow `cached` to re-calculate (and thus
        # increment `counter` again):
        self.ledger.clear_cache()
        self.assertEqual(self.ledger.cached, 4)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
