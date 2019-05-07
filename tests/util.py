""" Provides convenience classes and methods for testing. """

import unittest

# How many digits to round results to:
PLACES_PRECISION = 4

class TestCaseTransactions(unittest.TestCase):
    """ A test case for non-strategy method of TransactionStrategy. """

    def assertTransactions(
            self, first, second, places=PLACES_PRECISION,
            msg=None, delta=None):
        """ Convenience method for testing transactions.

        This method allows for testing a dict of transactions (passed
        as `first`) against either a dict of transactions or a total
        value of transactions. Uses `assertAlmostEqual` for all
        comparisons.

        Args:
            first (dict[Decimal, Money]): A dict of transactions,
                as when: value pairs.
            second (Money, dict[Decimal, Money]): Either a scala
                `Money` value or a dict of transactions.
        """
        # pylint: disable=invalid-name
        # The naming here uses the style of unittest `assert*` methods.
        if isinstance(second, dict):
            # Allow testing two transaction dicts against each other:
            self.assertEqual(first.keys(), second.keys())
            for key in first.keys():
                self.assertAlmostEqual(
                    first[key], second[key], places=places,
                    msg=msg, delta=delta)
        else:
            # Allow testing a transaction dict against a scalar, which
            # is interpreted as a total:
            self.assertAlmostEqual(
                sum(first.values()), second,
                places=places, msg=msg, delta=delta)

    def assertAccountTransactionsTotal(
            self, first, second, places=PLACES_PRECISION,
            msg=None, delta=None):
        """ Tests the total value of transactions across all accounts.

        Args:
            first (dict[Account, dict[Decimal, Money]]): A mapping of
                accounts to transactions.
            second (Money): The total value of all transactions in
                `first`.
        """
        # pylint: disable=invalid-name
        # The naming here uses the style of unittest `assert*` methods.
        self.assertAlmostEqual(
            sum(sum(transactions.values()) for transactions in first.values()),
            second, places=places, msg=msg, delta=delta)

    def assertAlmostEqual(
            self, first, second, places=None, msg=None, delta=None):
        """ Overrides assertAlmostEqual to round more aggressively. """
        if places is None:
            places = PLACES_PRECISION
        super().assertAlmostEqual(
            first, second, places=places, msg=msg, delta=delta)

def make_available(total, timing=None):
    """ Generates an `available` dict of cashflows. """
    if timing is None:
        # Default timing: Everything contributed/withdrawn at t=0.5.
        timing = {0.5: 1}
    normalization = sum(timing.values())
    return {
        when: total * weight / normalization
        for when, weight in timing.items()}
