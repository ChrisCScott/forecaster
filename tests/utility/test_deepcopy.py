""" Tests functions of the `utility.deepcopy` module. """

import unittest
from forecaster.utility.deepcopy import deepcopy, populate_deepcopy_memo

class TestForecasterFunctions(unittest.TestCase):
    """ Tests free functions of the `forecaster` module. """

    def test_deepcopy_closure(self):
        """ Test `deepcopy` with a closured function as input. """
        # Use a dummy var for inclusion in the closure:
        var = object()
        # The function simply returns the object in the closure:
        def func():
            """ A function with a non-empty closure. """
            return var
        # Ask deepcopy to replace the dummy var with a new value (1):
        memo = {id(var): 1}
        func_copy = deepcopy(func, memo=memo)
        # The function should now return the new value:
        self.assertEqual(func_copy(), 1)
