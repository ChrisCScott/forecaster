""" Tests classes and descriptors in the utility.precision module. """

import unittest
from decimal import Decimal
from forecaster.utility.precision import (
    HighPrecisionOptional, HighPrecisionOptionalProperty,
    HighPrecisionOptionalPropertyCached)

# Example class with high-precision
# pylint: disable=too-few-public-methods
class Example(HighPrecisionOptional):
    """ An example class with HighPrecisionProperty attributes. """
    attr = HighPrecisionOptionalProperty()
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.attr = value

class ExampleCached(HighPrecisionOptional):
    """ An example class with HighPrecisionPropertyCached attributes. """
    attr = HighPrecisionOptionalPropertyCached()
    def __init__(self, value, **kwargs):
        super().__init__(**kwargs)
        self.attr = value
# pylint: enable=too-few-public-methods

class TestHighPrecisionOptionalProperty(unittest.TestCase):
    """ A test case for HighPrecisionOptional and related descriptors. """

    def test_float(self):
        """ Tests returning a float (no conversion). """
        # If we don't pass a high-precision type conversion method,
        # the attribute should return a float value without conversion:
        obj = Example(5.0)
        self.assertIs(obj.attr, 5.0)

    def test_decimal(self):
        """ Tests returning a Decimal. """
        obj = Example(5.0, high_precision=Decimal)
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(5))

    def test_reset_value(self):
        """ Tests getting a value after the value has been changed. """
        obj = Example(5.0, high_precision=Decimal)
        _ = obj.attr # Invoke __get__
        obj.attr = 4
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(4))

    def test_reset_high_precision(self):
        """ Tests getting a value after high_precision has been changed. """
        obj = Example(5.0, high_precision=None)
        _ = obj.attr # Invoke __get__
        obj.high_precision = Decimal
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(5))

class TestHighPrecisionOptionalPropertyCached(unittest.TestCase):
    """ A test case for HighPrecisionOptional and related descriptors. """

    def test_float(self):
        """ Tests returning a float (no conversion). """
        # If we don't pass a high-precision type conversion method,
        # the attribute should return a float value without conversion:
        obj = ExampleCached(5.0)
        self.assertIs(obj.attr, 5.0)

    def test_decimal(self):
        """ Tests returning a Decimal. """
        obj = ExampleCached(5.0, high_precision=Decimal)
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(5))

    def test_reset_value(self):
        """ Tests getting a value after the value has been changed. """
        obj = ExampleCached(5.0, high_precision=Decimal)
        _ = obj.attr # Invoke __get__
        obj.attr = 4
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(4))

    def test_reset_high_precision(self):
        """ Tests getting a value after high_precision has been changed. """
        obj = ExampleCached(5.0, high_precision=None)
        _ = obj.attr # Invoke __get__
        obj.high_precision = Decimal
        self.assertIsInstance(obj.attr, Decimal)
        self.assertEqual(obj.attr, Decimal(5))


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
