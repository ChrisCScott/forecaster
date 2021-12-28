""" Unit tests for `forecaster.scenario.util` functions. """

import unittest
from datetime import datetime
from decimal import Decimal
import dateutil
from forecaster.scenario import util

class TestUtilMethod(unittest.TestCase):
    """ Superclass for test cases for methods in `util`.

    The purpose of this class is to provide common set-up/tear-down
    methods for the various method-specific test cases.
    """

    def setUp(self):
        # Build a sequence of dates:
        self.dates = [
            datetime(1999,1,1), datetime(2000,1,1),
            datetime(2001,1,1), datetime(2002,1,1)]
        # Build two equivalent (annual) datasets, one expressed as
        # absolute portfolio values and the other expressed as relative
        # returns. This will make comparisons a bit easier:
        self.values = {
            self.dates[0]: 100,
            self.dates[1]: 100,
            self.dates[2]: 200,
            self.dates[3]: 150}
        self.returns = {
            # Don't represent `dates[0]` in `returns`
            self.dates[1]: 0,
            self.dates[2]: 1,
            self.dates[3]: -.25}

    def setUp_decimal(self):
        """ Convert values to Decimal. """
        # pylint: disable=invalid-name
        # We're basing this name on the standard library method `setUp`.
        self.values = {
            datetime(1999,1,1): Decimal(100),
            datetime(2000,1,1): Decimal(100),
            datetime(2001,1,1): Decimal(200),
            datetime(2002,1,1): Decimal(150)}
        self.returns = {
            datetime(2000,1,1): Decimal(0),
            datetime(2001,1,1): Decimal(1),
            datetime(2002,1,1): Decimal(-.25)}

class TestUtilArrayMethod(TestUtilMethod):
    """ Superclass for test cases for array-based methods in `util`.

    The purpose of this class is to provide common set-up/tear-down
    methods for the various method-specific test cases.

    This class can be used as a second superclass for subclasses of
    `TestUtilMethod` subclasses. For example, `TestInterpolateValue`
    is a `TestUtilMethod` subclass. `TestInterpolateValueArray` is a
    subclass of `TestInterpolateValue`, and uses `TestUtilArrayMethod`
    as a second superclass. As a result, `TestInterpolateValueArray`
    calls this class's methods, which replace `values` and `returns`
    attrs with array-type attrs.
    """

    @property
    def values(self):
        """ Gets `values` attr. """
        return self._values

    @values.setter
    def values(self, val):
        """ Converts dict-type value to array-type """
        if isinstance(val, dict):
            self._values = util.mapping_to_arrays(val)
        else:
            self._values = val

    @property
    def returns(self):
        """ Gets `returns` attr. """
        return self._returns

    @returns.setter
    def returns(self, val):
        """ Converts dict-type value to array-type """
        if isinstance(val, dict):
            self._returns = util.mapping_to_arrays(val)
        else:
            self._returns = val

    def assertEqual(self, first, second, *args, **kwargs):
        """ Allow for comparison between dict and array-typed inputs """
        # If it looks like we're comparing a dict of date-value pairs to
        # a pair of lists, convert the dict to a pair of lists and
        # compare the lists via the conventional assertEqual:
        if (
                isinstance(first, dict) and
                isinstance(second, (tuple, list)) and
                len(second) == 2):
            return super().assertEqual(
                util.mapping_to_arrays(first), second, *args, **kwargs)
        # If the dict/array are passed in reverse order, swap them and
        # try again via this method:
        if isinstance(first, (tuple, list)) and isinstance(second, dict):
            # pylint: disable=arguments-out-of-order
            # We're intentionally swapping the first two arguments.
            return self.assertEqual(second, first, *args, **kwargs)
            # pylint: enable=arguments-out-of-order
        # In any other case, use the standard assertEqual:
        return super().assertEqual(first, second, *args, **kwargs)

class TestInterpolateValue(TestUtilMethod):
    """ A test suite for `util.interpolate_value`. """

    def test_date_exact(self):
        """ Test `date` being a key in `returns` """
        # The easy case: `date` is in returns, so return the exact value
        date = self.dates[1]
        val = util.interpolate_value(self.values, date)
        self.assertEqual(val, 100)

    def test_date_out_of_bounds(self):
        """ Test `date` being out of bounds of the dataset """
        # Get a date one year before the earliest date:
        date = self.dates[0] - dateutil.relativedelta.relativedelta(years=1)
        with self.assertRaises(KeyError):
            _ = util.interpolate_value(self.values, date)

    def test_date_before_start(self):
        """ Test `date` being a bit earlier than the start date """
        date = self.dates[0]
        val = util.interpolate_value(self.values, date)
        self.assertEqual(val, 100)

    def test_date_between(self):
        """ Test `date` being between two represented dates """
        date = datetime(2000,7,1)
        val = util.interpolate_value(self.values, date)
        # Resulting value can be calculated various ways, but should be
        # somewhere between the starting and ending value:
        self.assertGreater(val, 100)
        self.assertLess(val, 250)

    def test_decimal_date_between(self):
        """ Test decimal support based on `test_date_between` """
        self.setUp_decimal()
        date = datetime(2000,7,1)
        val = util.interpolate_value(self.values, date, high_precision=Decimal)
        # Resulting value can be calculated various ways, but should be
        # somewhere between the starting and ending value:
        self.assertGreater(val, Decimal(100))
        self.assertLess(val, Decimal(250))

class TestInterpolateValueArray(TestInterpolateValue, TestUtilArrayMethod):
    """ A test suite for `util.interpolate_value` with array args. """
    # No need for any methods; `TestUtilArrayMethod` will substitute
    # aray-valued inputs.

class TestReturnOverPeriod(TestUtilMethod):
    """ A test suite for `util.return_over_period`. """

    def test_exact_short(self):
        """ Test adjacent `start_date` and `end_date`, both in `returns` """
        # If the period is represented exactly in `returns`, and if the
        # start and end date cover just one return period, then the
        # return for the period is just the return on the end date,
        # which in this case is 1 (i.e. 100%)
        val = util.return_over_period(
            self.returns, self.dates[1], self.dates[2])
        self.assertEqual(val, 1)

    def test_exact_long(self):
        """ Test non-adjacent `start_date`/`end_date`, both in `returns` """
        # If the dates are represented exactly in `returns`, but they
        # cover multiple represented periods, then the return
        # is just the product of returns over the represented periods,
        # which in this case is 0.5.
        val = util.return_over_period(
            self.returns, self.dates[1], self.dates[3])
        self.assertEqual(val, 0.5)

    def test_end_between(self):
        """ Test `end_date` between dates in `returns` """
        end_date = datetime(2000,7,1)  # midpoint between dates[1] and dates[2]
        val = util.return_over_period(self.returns, self.dates[1], end_date)
        # Resulting value can be calculated various ways, but should be
        # smaller than the return for `dates[2]` (i.e. 1) and have the
        # same sign:
        self.assertLess(val, 1)  # magnitude
        self.assertGreater(val, 0)  # sign

    def test_start_between(self):
        """ Test `start_date` between dates in `returns` """
        start_date = datetime(2001,7,1) # midpoint between dates[2] and dates[3]
        val = util.return_over_period(self.returns, start_date, self.dates[3])
        # Resulting value can be calculated various ways, but should be
        # smaller than the return for `dates[3]` (i.e. -.25) and have
        # the same sign:
        self.assertLess(abs(val), abs(-.25))  # magnitude
        self.assertLess(val, 0)  # sign

    def test_both_between(self):
        """ Test `start_date` and `end_date` between dates in `returns` """
        start_date = datetime(2000,7,1) # midpoint between dates[1] and dates[2]
        end_date = datetime(2001,7,1) # midpoint between dates[2] and dates[3]
        val = util.return_over_period(self.returns, start_date, end_date)
        # Resulting value can be calculated various ways.
        # In the reference data, returns in the first half are positive
        # (100% APR) and returns in the second half are negative (-25%
        # APR). Whether estimating exponentially or linearly, returns
        # should be less than the return over just the first half, but
        # still positive.
        ref_return = util.return_over_period(
            self.returns, start_date, self.dates[2])
        self.assertLess(val, ref_return)
        self.assertGreater(val, 0)

    def test_both_between_constant(self):
        """ Test `start_date`/`end_date` over constant `returns` """
        # Build a sequence of constant, annual, 200% returns:
        self.returns = {
            # Avoid 2000 - it's a leap year, which complicates the
            # result (the return over the latter half of 2000 is
            # slightly lower than in non-leap-years)
            datetime(2001,1,1): 2,
            datetime(2002,1,1): 2,
            datetime(2003,1,1): 2}
        start_date = datetime(2001,7,1)  # midpoint between first two dates
        end_date = datetime(2002,7,1)  # midpoint between last two dates
        val = util.return_over_period(self.returns, start_date, end_date)
        # Any reasonable implementation should generate returns of 200%,
        # since this is a one-year interval for a dataset of constant
        # 200% annualized returns.
        self.assertAlmostEqual(val, 2)

    def test_decimal_both_between(self):
        """ Test decimal support based on `test_both_between` """
        self.setUp_decimal()
        start_date = datetime(2000,7,1) # midpoint between dates[1] and dates[2]
        end_date = datetime(2001,7,1) # midpoint between dates[2] and dates[3]
        val = util.return_over_period(
            self.returns, start_date, end_date, high_precision=Decimal)
        # Resulting value can be calculated various ways. See test_both_between
        ref_return = util.return_over_period(
            self.returns, start_date, self.dates[2], high_precision=Decimal)
        self.assertLess(val, ref_return)
        self.assertGreater(val, Decimal(0))

class TestReturnOverPeriodArray(TestReturnOverPeriod, TestUtilArrayMethod):
    """ A test suite for `util.return_over_period` with array inputs. """
    # No need to overload any methods. Dict-type inputs in
    # `test_both_between_constant` are dynamically converted to arrays
    # via the `TestUtilArrayMethod.returns` property setter.

class TestRegularizeReturns(TestUtilMethod):
    """ A test suite for `util.regularize_returns`. """

    def test_interval_aligned(self):
        """ Test `interval` lining up with the data. """
        # The test data uses an annual interval.
        interval = dateutil.relativedelta.relativedelta(years=1)
        # Calling without `date` and aligned interval will regularize
        # from the first date, i.e. it will produce the same sequence
        # of returns without changes:
        vals = util.regularize_returns(self.returns, interval)
        self.assertEqual(vals, self.returns)

    def test_interval_unaligned(self):
        """ Test `interval` not lining up with the data. """
        # The test data uses an annual interval, so use 18mo:
        interval = dateutil.relativedelta.relativedelta(years=1, months=6)
        # The data covers 3 years, so the result should have two values
        # in it, one for 6 months after `date[1]` and one for `date[3]`,
        # where the values are as given by `return_over_period`:
        vals = util.regularize_returns(self.returns, interval)
        first_date = (
            self.dates[1] + dateutil.relativedelta.relativedelta(months=6))
        ref_vals = {
            first_date: util.return_over_period(
                self.returns, first_date - interval, first_date),
            self.dates[3]: util.return_over_period(
                self.returns, first_date, self.dates[3])}
        self.assertEqual(vals, ref_vals)

    def test_date_explicit(self):
        """ Test `date` set to a value between dates in `returns` """
        # Let's get annual data, but offset from the data by 6mo:
        interval = dateutil.relativedelta.relativedelta(years=1)
        offset = dateutil.relativedelta.relativedelta(months=6)
        date1 = self.dates[1] + offset
        date2 = self.dates[2] + offset
        # We should get a dict with 2 values (instead of 3) offset from
        # date[1] and date[2] by 6 months.:
        vals = util.regularize_returns(self.returns, interval, date=date1)
        ref_vals = {
            date1: util.return_over_period(
                self.returns, date1 - interval, date1),
            date2: util.return_over_period(
                self.returns, date2 - interval, date2)}
        self.assertEqual(vals, ref_vals)

    def test_date_explicit_outside(self):
        """ Test `date` set to a value outside the range in `returns` """
        # Align with the data: annual intervals, no offset
        interval = dateutil.relativedelta.relativedelta(years=1)
        date = self.dates[0] - (interval * 2)
        # As in `test_interval_aligned`, the result should be the same
        # as the input `returns`, as the dates are unchanged:
        vals = util.regularize_returns(self.returns, interval, date=date)
        self.assertEqual(vals, self.returns)

    def test_decimal_interval_unaligned(self):
        """ Test Decimal support based on `test_interval_unaligned`. """
        self.setUp_decimal()
        # The test data uses an annual interval, so use 18mo:
        interval = dateutil.relativedelta.relativedelta(years=1, months=6)
        # The data covers 3 years, so the result should have two values
        # in it, one for 6 months after `date[1]` and one for `date[3]`,
        # where the values are as given by `return_over_period`:
        vals = util.regularize_returns(
            self.returns, interval, high_precision=Decimal)
        first_date = (
            self.dates[1] + dateutil.relativedelta.relativedelta(months=6))
        ref_vals = {
            first_date: util.return_over_period(
                self.returns, first_date - interval, first_date,
                high_precision=Decimal),
            self.dates[3]: util.return_over_period(
                self.returns, first_date, self.dates[3],
                high_precision=Decimal)}
        self.assertEqual(vals, ref_vals)

class TestRegularizeReturnsArray(TestRegularizeReturns, TestUtilArrayMethod):
    """ A test suite for `util.regularize_returns` with array inputs. """
    # No methods use custom dicts as inputs (and no need to overload to
    # convert dict-type `ref_vals` passed to `assertEqual`; those will
    # be converted dynamically via TestUtilArrayMethod.assertEqual.)

class TestInferInterval(TestUtilMethod):
    """ A test suite for `util.infer_interval`. """

    def test_annual(self):
        """ Test annual returns. """
        # Confirm that the pre-built returns are annual:
        ref = dateutil.relativedelta.relativedelta(years=1)
        val = util.infer_interval(self.returns)
        self.assertEqual(val, ref)

    def test_daily_skips(self):
        """ Test daily returns with a occasional skips. """
        self.returns = {
            datetime(2000, 1, 1): 1,
            # A weekend on Jan. 2, 3
            datetime(2000, 1, 4): 1,
            datetime(2000, 1, 5): 1,
            datetime(2000, 1, 6): 1}
        # Confirm that the above returns are daily:
        ref = dateutil.relativedelta.relativedelta(days=1)
        val = util.infer_interval(self.returns)
        self.assertEqual(val, ref)

    def test_no_interval(self):
        """ Test returns without enough data to infer an interval. """
        self.returns = {
            datetime(2000, 1, 1): 1}
        val = util.infer_interval(self.returns)
        # Should return None:
        self.assertEqual(val, None)

class TestInferIntervalArray(TestInferInterval, TestUtilArrayMethod):
    """ A test suite for `util.infer_interval` with array inputs. """
    # All custom dict inputs are converted dynamically via
    # `TestUtilArrayMethod.returns` property setter.

class TestValuesFromReturns(TestUtilMethod):
    """ A test suite for `util.values_from_returns`. """

    def test_basic(self):
        """ Test with only the required `returns` arg """
        val = util.values_from_returns(self.returns)
        self.assertEqual(val, self.values)

    def test_interval(self):
        """ Test with explicit `interval` arg """
        interval = dateutil.relativedelta.relativedelta(years=2)
        # Revise `values` to include an earlier start date:
        self.values = {
            self.dates[1] - interval: 100,
            self.dates[1]: 100,
            self.dates[2]: 200,
            self.dates[3]: 150}
        val = util.values_from_returns(self.returns, interval=interval)
        self.assertEqual(val, self.values)

    def test_start_val(self):
        """ Test with explicit `start_val` arg """
        # Revise `values` to double all values:
        self.values = {key: 2*val for (key, val) in self.values.items()}
        # Double start_val to 200:
        val = util.values_from_returns(self.returns, start_val=200)
        self.assertEqual(val, self.values)

    def test_decimal(self):
        """ Test Decimal support based on `test_basic` """
        self.setUp_decimal()
        # No high_precision arg is needed for this function:
        val = util.values_from_returns(self.returns)
        self.assertEqual(val, self.values)

class TestValuesFromReturnsArray(TestValuesFromReturns, TestUtilArrayMethod):
    """ A test suite for `util.values_from_returns` with array inputs. """
    # `test_start_val` makes use of dict-valued `values` when building
    # custom values. Overload it here to build `values` properly:

    def test_start_val(self):
        """ Test with explicit `start_val` arg """
        # Double start_val to 200:
        val = util.values_from_returns(self.returns, start_val=200)
        # All values should be doubled:
        self.values = (self.values[0], [2*val for val in self.values[1]])
        self.assertEqual(val, self.values)

class TestReturnForDate(TestUtilMethod):
    """ A test suite for `util.return_for_date`. """

    def test_date_in_values(self):
        """ Tests a date in `values` """
        date = self.dates[1]
        val = util.return_for_date(self.values, date)
        self.assertEqual(val, 0)  # No growth between first/second dates

    def test_start_date(self):
        """ Tests the first date in `values` """
        date = self.dates[0]
        val = util.return_for_date(self.values, date)
        # We can't actually calculate the return at the first date in
        # values, as we don't know how much it grew from the preceding
        # timestep. So the function should return `None`
        self.assertEqual(val, None)

    def test_end_date(self):
        """ Tests the last date in `values` """
        # Should work the same as any other date; just checking the
        # boundary:
        date = self.dates[3]
        val = util.return_for_date(self.values, date)
        self.assertEqual(val, -.25)  # -25% growth over last period

    def test_between_dates(self):
        """ Tests a date between dates in `values` """
        offset = dateutil.relativedelta.relativedelta(months=6)
        date = self.dates[1] + offset
        val = util.return_for_date(self.values, date)
        # Find the return between 2000-1-1 and 2000-7-1,
        # which is simply the amount of growth in value between dates:
        ref_val_date = util.interpolate_value(self.values, date)  # 2000-7-1 val
        ref_val_prev = 100  # 2000-1-1 val
        ref_return = ref_val_date / ref_val_prev - 1  # Growth between dates
        self.assertAlmostEqual(val, ref_return)

    def test_interval_aligned(self):
        """ Tests an interval that lines up with `values` """
        interval = dateutil.relativedelta.relativedelta(years=1)
        date = self.dates[1]
        val = util.return_for_date(self.values, date, interval)
        self.assertEqual(val, 0)  # No growth between first/second dates

    def test_interval_not_aligned(self):
        """ Tests an interval that doesn't line up with `values` """
        interval = dateutil.relativedelta.relativedelta(years=1)
        date = self.dates[1]
        val = util.return_for_date(self.values, date, interval)
        # Calculate the growth over `interval` ending at `date`:
        ref_val_date = 100  # 2000-1-1 value
        ref_val_prev = util.interpolate_value(self.values, date - interval)
        ref_return = ref_val_date / ref_val_prev - 1  # Growth between dates
        self.assertEqual(val, ref_return)

    def test_decimal_between_dates(self):
        """ Tests Decimal support based on `test_between_dates` """
        self.setUp_decimal()
        offset = dateutil.relativedelta.relativedelta(months=6)
        date = self.dates[1] + offset
        val = util.return_for_date(self.values, date, high_precision=Decimal)
        # Find the return between 2000-1-1 and 2000-7-1,
        # which is simply the amount of growth in value between dates:
        ref_val_date = util.interpolate_value(  # 2000-7-1 val
            self.values, date, high_precision=Decimal)
        ref_val_prev = Decimal(100)  # 2000-1-1 val
        ref_return = ref_val_date / ref_val_prev - 1  # Growth between dates
        self.assertAlmostEqual(val, ref_return)

class TestReturnForDateArray(TestReturnForDate, TestUtilArrayMethod):
    """ A test suite for `util.return_for_date` with array inputs. """
    # No overloading needed. `TestUtilArrayMethod` converts dynamically.

class TestReturnsFromValues(TestUtilMethod):
    """ A test suite for `util.returns_from_values`. """

    def test_basic(self):
        """ Test that `values` converts to `returns` """
        val = util.returns_from_values(self.values)
        self.assertEqual(val, self.returns)

    def test_interval(self):
        """ Test `interval` longer than frequency of data in `values` """
        interval = dateutil.relativedelta.relativedelta(years=2)
        val = util.returns_from_values(self.values, interval=interval)
        # The result should have only two dates rather than 3, since
        # there isn't 2 years of data for `self.dates[1]`
        ref_val = {}
        ref_val[self.dates[2]] = (  # Return for 1999/2000
            (1 + self.returns[self.dates[2]]) *
            (1 + self.returns[self.dates[1]])
            - 1)
        ref_val[self.dates[3]] = (  # Return for 2001/2002
            (1 + self.returns[self.dates[3]]) *
            (1 + self.returns[self.dates[2]])
            - 1)
        self.assertEqual(val, ref_val)

    def test_decimal_basic(self):
        """ Test Decimal support based on `test_basic` """
        self.setUp_decimal()
        val = util.returns_from_values(self.values)
        self.assertEqual(val, self.returns)

class TestReturnsFromValuesArray(TestReturnsFromValues, TestUtilArrayMethod):
    """ A test suite for `util.returns_from_values` with array inputs. """

    def test_interval(self):
        """ Test `interval` longer than frequency of data in `values` """
        interval = dateutil.relativedelta.relativedelta(years=2)
        val = util.returns_from_values(self.values, interval=interval)
        # The result should have only two dates rather than 3, since
        # there isn't 2 years of data for `self.dates[1]`
        ref_val = ([], [])
        # Add first date:
        ref_val[0].append(self.dates[2])
        ref_val[1].append(  # Return for 1999/2000
            (1 + self.returns[1][1]) *
            (1 + self.returns[1][0])
            - 1)
        # Add second date:
        ref_val[0].append(self.dates[3])
        ref_val[1].append(  # Return for 2001/2002
            (1 + self.returns[1][2]) *
            (1 + self.returns[1][1])
            - 1)
        self.assertEqual(val, ref_val)

class TestMappingToArrays(TestUtilMethod):
    """ A test suite for `util.mapping_to_arrays`. """

    def setUp(self):
        super().setUp()
        # An array equivalent to self.values (which is dict-type):
        self.values_array = (self.dates, [100, 100, 200, 150])

    def test_dict(self):
        """ Tests mapping_to_arrays with dict input """
        vals = util.mapping_to_arrays(self.values)
        self.assertEqual(vals, self.values_array)

    def test_dict_tuple(self):
        """ Tests mapping_to_arrays with a tuple of dicts as input """
        # Use a tuple of length 2, with two identical elements:
        vals = util.mapping_to_arrays((self.values,) * 2)
        self.assertEqual(vals, (self.values_array,) * 2)

    def test_non_dict(self):
        """ Tests mapping_to_arrays with a tuple of dicts as input """
        # There should be no conversion:
        vals = util.mapping_to_arrays(self.values_array)
        self.assertEqual(vals, self.values_array)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
