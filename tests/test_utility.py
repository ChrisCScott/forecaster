""" Tests free methods and classes in the utility module. """

import unittest
import decimal
from decimal import Decimal
from forecaster.utility import (
    Timing, transactions_from_timing,
    nearest_year, extend_inflation_adjusted,
    when_conv, frequency_conv)

class TestTiming(unittest.TestCase):
    """ A test case for Timing. """

    # TODO: Test all four modes of Timing.__init__:
    # 1) Init with two arguments: `when` and `frequency`
    # 2) Init with dict of {when: value} pairs.
    #    This has 3 major variations:
    #    a) All values are non-negative (positive or 0)
    #    b) All values are non-positive (negative or 0)
    #    c) Values have varying sign (behaviour differs depending on
    #       whether the sum is positive, negative, or 0).
    # 3) Init with string denoting a frequency (e.g. `Timing('BW')`)
    # 4) Init with `when`-convertible value (e.g. Timing('start'),
    #    `Timing(1)`)

    def test_init_when_freq(self):
        """ TODO """
        pass

    def test_init_str_freq(self):
        """ TODO """
        pass

    def test_init_str_when(self):
        """ TODO """
        pass

    def test_init_dict_pos(self):
        """ TODO """
        pass

    def test_init_dict_neg(self):
        """ TODO """
        pass

    def test_init_dict_mixed(self):
        """ TODO """
        pass

    def test_init_dict_money(self):
        """ TODO """
        pass

    def test_init_dict_accum(self):
        """ TODO """
        available = {0: 1000, 0.25: -11000, 0.5: 1000, 0.75: -11000}
        timing = Timing(available)
        target = Timing({0.25: 10000, 0.75: 10000})
        self.assertEqual(timing, target)

    def test_time_series(self):
        """ TODO """
        pass

class TestFreeMethods(unittest.TestCase):
    """ A test case for the free methods in the utility module. """

    def test_when_conv_simple(self):
        """ Tests `when_conv` on a simple, single-valued input. """
        when = when_conv(1)
        self.assertEqual(when, Decimal(1))

    def test_when_conv_start(self):
        """ Tests `when_conv` on 'start'. """
        when = when_conv('start')
        self.assertEqual(when, Decimal(0))

    def test_when_conv_end(self):
        """ Tests `when_conv` on 'end'. """
        when = when_conv('end')
        self.assertEqual(when, Decimal(1))

    def test_when_conv_str(self):
        """ Tests `when_conv` on a non-magic str input. """
        when = when_conv('1')
        self.assertEqual(when, Decimal(1))

    def test_when_conv_invalid(self):
        """ Tests `when_conv` on an invalid input. """
        with self.assertRaises(decimal.InvalidOperation):
            _ = when_conv('invalid input')

    def test_frequency_continuous(self):
        """ Test setting frequency to 'C' and 'None' (equivalent). """
        frequency = frequency_conv('C')
        self.assertEqual(frequency, None)
        self.assertIsInstance(frequency, type(None))

        frequency = frequency_conv(None)
        self.assertEqual(frequency, None)
        self.assertIsInstance(frequency, type(None))

    def test_frequency_daily(self):
        """ Test setting frequency to 'D'. """
        frequency = frequency_conv('D')
        self.assertEqual(frequency, 365)
        self.assertIsInstance(frequency, int)

    def test_frequency_weekly(self):
        """ Test setting frequency to 'W'. """
        frequency = frequency_conv('W')
        self.assertEqual(frequency, 52)

    def test_frequency_biweekly(self):
        """ Test setting frequency to 'BW'. """
        frequency = frequency_conv('BW')
        self.assertEqual(frequency, 26)

    def test_frequency_semimonthly(self):
        """ Test setting frequency to 'SM'. """
        frequency = frequency_conv('SM')
        self.assertEqual(frequency, 24)

    def test_frequency_monthly(self):
        """ Test setting frequency to 'M'. """
        frequency = frequency_conv('M')
        self.assertEqual(frequency, 12)

    def test_frequency_bimonthly(self):
        """ Test setting frequency to 'BM'. """
        frequency = frequency_conv('BM')
        self.assertEqual(frequency, 6)

    def test_frequency_quarterly(self):
        """ Test setting frequency to 'Q'. """
        frequency = frequency_conv('Q')
        self.assertEqual(frequency, 4)

    def test_frequency_semiannually(self):
        """ Test setting frequency to 'SA'. """
        frequency = frequency_conv('SA')
        self.assertEqual(frequency, 2)

    def test_frequency_annually(self):
        """ Test setting frequency to 'A'. """
        frequency = frequency_conv('A')
        self.assertEqual(frequency, 1)

    def test_frequency_invalid_0(self):
        """ Test setting frequency to 0, an invalid value. """
        with self.assertRaises(ValueError):
            _ = frequency_conv(0)

    def test_frequency_invalid_negative(self):
        """ Test setting frequency to -1, an invalid value. """
        with self.assertRaises(ValueError):
            _ = frequency_conv(-1)

    def test_frequency_invalid_fraction(self):
        """ Test setting frequency to 0.5, an invalid value. """
        with self.assertRaises(TypeError):
            _ = frequency_conv(0.5)

    def test_frequency_invalid_str(self):
        """ Test setting frequency to 'invalid', an invalid value. """
        with self.assertRaises(ValueError):
            _ = frequency_conv('invalid')

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
            """ Inflation from base_year to target_year. """
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
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
