""" Unit tests for `Ledger` class. """

import unittest
from forecaster.ledger import (
    Ledger, recorded_property, recorded_property_cached)


class ExampleLedger(Ledger):
    """ Test class with cached and uncached recorded properties. """

    def __init__(self):
        """ Init method that adds a `counter` attribute """
        super().__init__(0)
        self.counter = 0
        self.side_effect = False

    @recorded_property
    def uncached(self):
        """ A recorded property that is not cached. """
        self.counter += 1
        return self.counter

    @uncached.setter  # type: ignore[no-redef]
    def uncached(self, val):
        """ Sets `uncached` and toggles `flag` as a side-effect. """
        self.counter = val
        self.side_effect = True

    @uncached.deleter  # type: ignore[no-redef]
    def uncached(self):
        """ Sets counter to 0 and toggles `flag` as a side-effect. """
        self.counter = 0
        self.side_effect = True

    @recorded_property_cached
    def cached(self):
        """ A recorded property that is cached. """
        self.counter += 1
        return self.counter

    @cached.setter  # type: ignore[no-redef]
    def cached(self, val):
        """ Sets `cached` and toggles `flag` as a side-effect. """
        self.counter = val
        self.side_effect = True

    @cached.deleter  # type: ignore[no-redef]
    def cached(self):
        """ Toggles `flag` as a side-effect. """
        # NOTE: We do *not* modify counter here so that we can
        # more easily confirm that the cache is cleared.
        self.side_effect = True


class TestLedgerMethods(unittest.TestCase):
    """ A test suite for the `Ledger` class. """

    def setUp(self):
        """ Sets up stock attributes for testing. """
        self.ledger = ExampleLedger()

    def test_uncached_get(self):
        """ Tests getting uncached properties. """
        self.assertEqual(self.ledger.uncached, 1)
        self.assertEqual(self.ledger.uncached, 2)

    def test_uncached_set(self):
        """ Tests setting uncached properties. """
        self.ledger.uncached = 10
        # Should return 1 more because `fget` increments `counter`:
        self.assertEqual(self.ledger.uncached, 11)
        # Side effect should be observed:
        self.assertTrue(self.ledger.side_effect)

    def test_uncached_del(self):
        """ Tests deleting uncached properties. """
        self.ledger.counter = 10
        # Deleting `uncached` should reset `counter` to 0:
        del self.ledger.uncached
        # Should return 1 because `fget` increments `counter`:
        self.assertEqual(self.ledger.uncached, 1)
        # Side effect should be observed:
        self.assertTrue(self.ledger.side_effect)

    def test_cached_get(self):
        """ Tests cached properties. """
        # `cached` will be cached when it is first called:
        self.ledger.counter = 5
        self.assertEqual(self.ledger.cached, 6)
        # `cached` should return the same value on every
        # subsequent call no matter what `counter` is:
        self.ledger.counter = 10
        self.assertEqual(self.ledger.cached, 6)

    def test_cached_set(self):
        """ Tests setting cached properties. """
        self.ledger.cached = 10
        # Should return 1 more because `fget` increments `counter`:
        self.assertEqual(self.ledger.cached, 11)
        # (Try again to ensure setting doesn't interfere with cached
        # behaviour)
        self.assertEqual(self.ledger.cached, 11)
        # Side effect should be observed:
        self.assertTrue(self.ledger.side_effect)

    def test_cached_del(self):
        """ Tests deleting cached properties. """
        self.ledger.counter = 10
        # Call `cached` to ensure it's cached (should be 11):
        _ = self.ledger.cached
        # Call `cached` again (should be unchanged, since it's cached):
        _ = self.ledger.cached
        # Deleting `cached` should uncache it:
        del self.ledger.cached
        # Should now return 12 because the cache is cleared:
        self.assertEqual(self.ledger.cached, 12)
        # (Try again to ensure setting doesn't interfere with cached
        # behaviour)
        self.assertEqual(self.ledger.cached, 12)
        # Side effect should be observed:
        self.assertTrue(self.ledger.side_effect)

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
