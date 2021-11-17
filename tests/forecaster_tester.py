""" Provides a helper TestCase class for testing `Forecaster`. """

import unittest
import collections
from copy import copy

class ForecasterTester(unittest.TestCase):
    """ A custom TestCase for testing Forecaster.

    This class provides an overloaded equality-testing method,
    `assertEqual`, for testing equality of user-defined types without
    requiring those types to explicitly provide equality operators of
    their own. When the ordinary `assertEqual` would fail, this test
    passes if any of the following are true:
        1. The operands are dicts with equal keys and values.
        2. The operands are ordered iterables (e.g. tuples) with equal
            values in the same order.
        3. The operands are unordered iterables (e.g. sets) with equal
            membership.
        4. The operands are user-defined with `__dict__` attributes
            with equal keys and values.

    The corresponding test `assertNotEqual` works the same way.
    """

    def _assertEqual_dict(self, first, second, msg=None, memo=None):
        """ Extends equality testing for dicts with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # For dicts, first confirm they represent the same keys:
        # (The superclass can handle this)
        if first.keys() != second.keys():
            super().assertEqual(first, second)
        # Then recursively check each pair of values:
        for key in first:
            self.assertEqual( #@IgnoreException
                first[key], second[key], msg=msg, memo=memo) #@IgnoreException

    def _assertEqual_list(self, first, second, msg=None, memo=None):
        """ Extends equality testing for lists with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # First confirm that they have the same length.
        if len(first) != len(second):
            super().assertEqual(first, second)
        # Then iterate over the elements in sequence:
        for first_value, second_value in zip(first, second):
            self.assertEqual(first_value, second_value, msg=msg, memo=memo)

    def _assertEqual_set(self, first, second, msg=None, memo=None):
        """ Extends equality testing for sets with complex members. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # First confirm that they have the same length.
        if len(first) != len(second):
            super().assertEqual(first, second, msg=msg)
        # For sets or other unordered iterables, we can't rely on
        # `in` (because complex objects might not have equality or
        # hashing implemented beyond the standard id()
        # implementation), so we want to test each element in one
        # set against every element in the other set.
        for val1 in first:
            match = False
            for val2 in second:
                try:
                    # Each pair of compared objects is automatically
                    # added to the memo, so make a copy (which will
                    # be discarded if the objects are not equal).
                    memo_copy = copy(memo)
                    self.assertEqual( #@IgnoreException
                        val1, val2, msg=msg, memo=memo_copy)
                except AssertionError:
                    # If we didn't find a match, advance to the next
                    # value in second and try that.
                    continue
                # If we did find a match, record that fact and
                # advance to the next value in second.
                match = True
                memo.update(memo_copy)
                break
            if not match:
                # If we couldn't find a match, the sets are not
                # equal; the entire test should fail.
                raise AssertionError(
                    str(first) + ' != ' + str(second))

    def _assertEqual_complex(self, first, second, msg=None, memo=None):
        """ Extends equality testing for complex objects. """
        # We're mimicking the name of assertEqual, so we can live with
        # the unusual method name.
        # pylint: disable=invalid-name

        # For complicated objects, recurse onto the attributes dict:
        self.assertEqual( #@IgnoreException
            first.__dict__, second.__dict__, msg=msg, memo=memo)

    def assertEqual(self, first, second, msg=None, memo=None):
        """ Tests complicated class instances for equality.

        This method is used (instead of __eq__) because equality
        semantics are only needed for testing code and can mess up
        things like set membership, require extensive (and inefficient)
        comparisons, and/or can result in infinite recursion.
        """
        # We add a memo argument to avoid recursion. We don't pass it
        # to the superclass, so pylint's objection isn't helpful.
        # pylint: disable=arguments-differ

        # The memo dict maps each object to the set of objects that it's
        # been compared to. If they've been compared, that means that we
        # don't need to re-evaluate their equality - if they're unequal,
        # that'll be discovered at a higher level of recursion:
        if memo is None:
            memo = collections.defaultdict(set)
        if id(second) in memo[id(first)]:
            # We've previously compared these objects and found them to
            # be equal, so return without failing.
            return
        else:
            memo[id(first)].add(id(second))
            memo[id(second)].add(id(first))

        try:
            # If these are equal under ordinary comparison, accept that
            # and don't so any further special testing.
            super().assertEqual(first, second, msg=msg) #@IgnoreException
            return
        except AssertionError as error:
            # If the superclass assertEqual doesn't find equality, run
            # a few additional equality tests based on object type:
            # 1) Dicts; keys and values both need to be checked.
            # 2) Ordered iterables; values need to be checked in order.
            # 3) Unordered iterables; check values for membership.
            # 4) Complex objects; compare attributes via __dict__.

            # Most of these tests won't work if the objects are
            # different types, and we don't deal with that case anyways.
            # In that case, accept the error and raise it on up.
            if (
                    not isinstance(first, type(second)) and
                    not isinstance(second, type(first))
            ):
                raise error #@IgnoreException
            elif isinstance(first, dict):
                self._assertEqual_dict( #@IgnoreException
                    first, second, msg=msg, memo=memo)
            elif isinstance(first, collections.abc.Sequence):
                self._assertEqual_list(first, second, msg=msg, memo=memo)
            elif isinstance(first, collections.abc.Iterable):
                self._assertEqual_set(first, second, msg=msg, memo=memo)
            elif hasattr(first, '__dict__'):
                self._assertEqual_complex(first, second, msg=msg, memo=memo)
            else:
                # If none of our special tests apply, accept the error.
                raise error #@IgnoreException

    def assertNotEqual(self, first, second, msg=None):
        """ Overloaded to test non-equality of complex objects. """
        try:
            self.assertEqual(first, second, msg=msg)
        except AssertionError:
            # We want assertEqual to throw an error (since we're
            # expecting non-equality)
            return
        # Raise a suitable error if the equality test didn't fail:
        raise AssertionError(str(first) + ' == ' + str(second))


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
