""" Tests free methods and classes in the utility module. """

import unittest
from decimal import Decimal
import context  # pylint: disable=unused-import
from forecaster.utility import nearest_year, extend_inflation_adjusted


class TestFreeMethods(unittest.TestCase):
    """ A test case for the free methods in the utility module. """

    def test_nearest_year(self):
        """ Tests nearest_year(). """
        vals = {1999: 2, 2001: 4, 2003: 8, 2006: 16}

        self.assertEqual(nearest_year(vals, 1998), 1999)
        self.assertEqual(nearest_year(vals, 1999), 1999)
        self.assertEqual(nearest_year(vals, 2000), 1999)
        self.assertEqual(nearest_year(vals, 2001), 2001)
        self.assertEqual(nearest_year(vals, 2002), 2001)
        self.assertEqual(nearest_year(vals, 2003), 2003)
        self.assertEqual(nearest_year(vals, 2004), 2003)
        self.assertEqual(nearest_year(vals, 2005), 2003)
        self.assertEqual(nearest_year(vals, 2006), 2006)
        self.assertEqual(nearest_year(vals, 2007), 2006)

        self.assertEqual(nearest_year({}, 2000), None)

    def test_extend_inflation_adjusted(self):
        """ Tests extend_inflation_adjusted(). """
        inf = {
            1998: Decimal(0.25),
            1999: Decimal(0.5),
            2000: Decimal(0.75),
            2001: Decimal(1),
            2002: Decimal(2)}
        vals = {1999: 2, 2001: 4, 2003: 8}

        def inflation_adjust(target_year, base_year):
            return inf[target_year] / inf[base_year]

        # Test each year from 1997 to 2004:
        with self.assertRaises(KeyError):
            extend_inflation_adjusted(vals, inflation_adjust, 1997)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 1998), 1)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 1999), 2)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 2000), 3)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 2001), 4)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 2002), 8)
        self.assertEqual(extend_inflation_adjusted(
            vals, inflation_adjust, 2003), 8)
        with self.assertRaises(KeyError):
            extend_inflation_adjusted(vals, inflation_adjust, 2004)

    # TODO: Test build_inflation_adjust

if __name__ == '__main__':
    unittest.main()
