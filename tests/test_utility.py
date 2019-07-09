""" Tests free methods and classes in the utility module. """

import unittest
import decimal
from decimal import Decimal
from forecaster.ledger.money import Money
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
        """ Init `Timing` with a single parameter, `when`. """
        timing = Timing(0.5)
        self.assertEqual(set(timing.keys()), {0.5})

    def test_init_str_freq(self):
        """ Init `Timing` with a single str parameter, `frequency`. """
        # There are 12 occurances with a monthly frequency:
        timing = Timing(frequency="M")
        self.assertEqual(len(timing), 12)

    def test_init_str_when(self):
        """ Init `Timing` with a single str parameter, `when`. """
        # 'start' should convert to 0:
        timing = Timing(when='start')
        self.assertEqual(set(timing.keys()), {0})

    def test_init_dict_pos(self):
        """ Init `Timing` with a dict of all-positive values. """
        # Technically we use non-negative values:
        timing_dict = {0: 0, 0.5: 1, 1: 1}
        # Should convert directly to `Timing` (the 0 value is optional):
        timing = Timing(timing_dict)
        total_weight = sum(timing.values())
        for key, value in timing_dict.items():
            if value != 0:
                # Each non-0 value should be present...
                self.assertIn(key, timing)
                # ... and both non-0 values should be equally weighted.
                self.assertEqual(timing[key], total_weight / 2)
            elif key in timing:
                # The zero value, if it exists, should remain 0:
                self.assertEqual(timing[key], 0)

    def test_init_dict_neg(self):
        """ Init `Timing` with a dict of all-negative values. """
        # This returns the same result as `test_init_dict_pos`;
        # the inputs have their sign flipped, but output is the same.

        # Technically we use non-positive values:
        timing_dict = {0: 0, 0.5: -1, 1: -1}
        # Should convert directly to `Timing`, except that all values
        # have their sign flipped (the 0 value is optional):
        timing = Timing(timing_dict)
        # Ensure that `total_weight` is positive; the later assertEqual
        # tests will thus also check that all values are non-negative:
        total_weight = abs(sum(timing.values()))
        for key, value in timing_dict.items():
            if value != 0:
                # Each non-0 value should be present...
                self.assertIn(key, timing)
                # ... and both non-0 values should be equally weighted.
                self.assertEqual(timing[key], total_weight / 2)
            elif key in timing:
                # The zero value, if it exists, should remain 0:
                self.assertEqual(timing[key], 0)

    def test_init_dict_mixed_pos(self):
        """ Init `Timing` with a net-positive dict of mixed values.

        "Mixed" in this context means it has both positive and negative
        values. The sum of those values is positive in this test.
        """
        # Large inflow followed by small outflow (for small net inflow):
        timing_dict = {0: 0, 0.5: 2, 1: -1}
        timing = Timing(timing_dict)
        # There should be only one key with non-zero weight:
        self.assertNotEqual(timing[0.5], 0)
        # All other keys must have zero weight, if they exist:
        self.assertTrue(
            all(value == 0 for key, value in timing.items() if key != 0.5))

    def test_init_dict_mixed_neg(self):
        """ Init `Timing` with a net-negative dict of mixed values.

        "Mixed" in this context means it has both positive and negative
        values. The sum of those values is negative in this test.
        """
        # Large outflow followed by small inflow and then another large
        # outflow:
        timing_dict = {0: 0, 0.5: -2, 0.75: 1, 1: -2}
        timing = Timing(timing_dict)
        # This should result in a time-series of {0.5: 2, 1: 1} to
        # balance the net flows at each outflow.
        # NOTE: The behaviour is different than is provided for inflows!
        self.assertNotEqual(timing[0.5], 0)
        self.assertNotEqual(timing[1], 0)
        # Key 0.5 should have 2x the weight of key 1:
        self.assertEqual(timing[0.5], timing[1] * 2)
        # All other keys must have zero weight, if they exist:
        self.assertTrue(
            all(
                value == 0 for key, value in timing.items()
                if key not in (0.5, 1)))

    def test_init_dict_mixed_zero(self):
        """ Init `Timing` with a net-zero dict of mixed values.

        "Mixed" in this context means it has both positive and negative
        values. The sum of those values is zero in this test.
        """
        # Large outflow followed by equally large inflow:
        timing_dict = {0: 0, 0.5: -2, 1: 2}
        timing = Timing(timing_dict)
        # This should result in either an empty time-series or one with
        # all-zero values.
        self.assertTrue(all(value == 0 for value in timing.values()))

    def test_init_dict_money(self):
        """ Init `Timing` with a dict of `Money` values. """
        # It doesn't matter what this dict is; if we wrap its values as
        # `Money` objects, it should parse to the same result:
        timing_dict = {0: 0, 0.5: -2, 1: 1}
        money_dict = {key: Money(value) for key, value in timing_dict.items()}
        # Build timings based on the (otherwise-identical) Money and
        # non-Money inputs and confirm that the results are the same:
        timing1 = Timing(timing_dict)
        timing2 = Timing(money_dict)
        self.assertEqual(timing1, timing2)

    def test_init_dict_mixed_neg_2(self):
        """ Init `Timing` with a net-negative dict of mixed values.

        This tests basically the same behaviour as
        `test_init_dict_mixed_neg`, but was written much earlier
        (as `test_init_dict_accum`) and helped to track down some
        erroneous behaviour. It's retained for historical reasons.
        """
        available = {0: 1000, 0.25: -11000, 0.5: 1000, 0.75: -11000}
        timing = Timing(available)
        target = Timing({0.25: 10000, 0.75: 10000})
        self.assertEqual(timing, target)

    def test_time_series_basic(self):
        """ Tests `time_series` for a simple `Timing` object. """
        # start and end are equally weighted:
        timing = Timing({0: 1, 1: 1})
        result = timing.time_series(2)
        # Spreading a value of 2 equally across start and end means
        # allocating 1 at start and 1 at end:
        self.assertEqual(result, {0: 1, 1: 1})

    def test_time_series_subset(self):
        """ TODO """
        pass

    def test_normalized_basic(self):
        """ TODO """
        pass

    def test_normalized_subset(self):
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
