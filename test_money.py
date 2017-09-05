''' Unit tests for `Money` and related classes '''

import unittest
from decimal import Decimal
from settings import Settings
from money import Money

class TestMoneyMethods(unittest.TestCase):
    ''' A test suite for the `Money` class '''

    value = 100 # a default nominal value for constructing `Money` objects
    year = 2000 # a default year for constructing `Money` objects
    money = Money(value, year) # a default `Money` object for testing

    def test_init(self):
        ''' Tests `Money.__init__` '''
        money = Money(100, 2000) # typical `Money` initialization
        self.assertIsNotNone(money)
        self.assertEqual(money.nominal_value(), self.value)
        self.assertEqual(money.year(), self.year)

        Settings.display_year = self.year
        money = Money() # Empty `Money` initialization
        self.assertIsNotNone(money)
        self.assertEqual(money.nominal_value(), Decimal(0))
        self.assertEqual(money.year(), self.year)

        Settings.display_year = self.year
        money = Money(Decimal(self.value)) # no year provided
        self.assertIsNotNone(money)
        self.assertEqual(money.nominal_value(), Decimal(self.value))
        self.assertEqual(money.year(), self.year)

    def test_nominal_value(self):
        ''' Tests `Money.nominal_value()` '''
        self.assertEqual(self.money.nominal_value(), Decimal(self.value))
        self.assertIsNotNone(self.money.nominal_value())

    def test_year(self):
        ''' Tests `Money.year()` '''
        self.assertEqual(self.money.year(), self.year)

    def test_operators(self):
        ''' Tests the overloaded operators for class `Money`.
        These include `+`, `-` (unary), `-` (binary), `*`, `/`, `abs()`,
        `float()`, `round()`, and the methematical comparison operators '''
        value1 = self.value
        value2 = self.value+0.5
        money1 = Money(value1, self.year)
        money2 = Money(value2, self.year)
        money_incomparable = Money(value1, self.year+1)

        # Test __add__ and __radd__
        compare = Money(value1+value2, self.year)
        self.assertIsNotNone(money1+money2)
        self.assertEqual(money1+money2, compare)
        self.assertEqual((money1+money2).nominal_value(), value1+value2)
        self.assertEqual(money2+money1, money1+money2)
        self.assertEqual(money1+value2, compare)
        self.assertEqual(value2+money1, compare) # __radd__

        # Test __sub__ and __rsub__
        compare = Money(value1-value2, self.year)
        self.assertIsNotNone(money1-money2)
        self.assertEqual(money1-money2, compare)
        self.assertEqual(money1-value2, compare)
        self.assertEqual(value1-money2, compare) # __rsub__

        # Test __mult__ and __rmult__
        compare = Money(value1*value2, self.year)
        self.assertIsNotNone(money1*value2)
        self.assertIsNotNone(value1*money2) # __rmult__
        self.assertEqual(money1*value2, compare)
        self.assertEqual(value1*money2, compare) # __rmult__
        # Multiplication of two `Money` objects raises an error:
        with self.assertRaises(TypeError):
            compare = money1*money2

        # Test __truediv__ and __rtruediv__
        div_value = Decimal(value1)/Decimal(value2)
        compare = Money(div_value, self.year)
        self.assertIsNotNone(compare)
        self.assertIsNotNone(money1/money2)
        self.assertEqual(money1/value2, compare)
        self.assertEqual(value1/money2, compare) # __rtruediv__
        # Division of two `Money` objects returns a `Decimal`:
        self.assertIsInstance(money1/money2, Decimal)
        self.assertEqual(money1/money2, div_value)

        # Test __abs__
        neg_money = Money(-abs(value1), self.year)
        abs_money = Money(abs(value1), self.year)
        self.assertIsNotNone(neg_money)
        self.assertIsNotNone(abs_money)
        self.assertEqual(abs(neg_money), abs_money)

        # Test __float__ and __round__
        compare = float(value1+0.5) # use lossless float (assuming value1 < 2^31-1)
        float_money = Money(compare, self.year)
        self.assertIsNotNone(float_money)
        self.assertEqual(float(float_money), compare)
        self.assertEqual(round(float_money).nominal_value(), round(compare))

        # Test mathematical comparison operators (<, =, >, !=, <=, >=)
        money1_copy = Money(money1.nominal_value(), money1.year())
        self.assertEqual(money1 < money2, value1 < value2)
        self.assertEqual(money1 > money2, value1 > value2)
        self.assertFalse(money1 > money1_copy)
        self.assertFalse(money1 < money1_copy)
        self.assertTrue(money1 == money1_copy)
        self.assertEqual(money1 == money2, value1 == value2)
        self.assertEqual(money1 <= money2, value1 <= value2)
        self.assertEqual(money1 >= money2, value1 >= value2)
        self.assertTrue(money1 >= money1_copy)
        self.assertTrue(money1 <= money1_copy)
        self.assertFalse(money1 != money1_copy)
        self.assertEqual(money1 != money2, value1 != value2)

        # Ensure that `Money` objects of different years are not comparable/combinable
        with self.assertRaises(ValueError):
            money1 + money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 - money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 / money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 < money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 > money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 == money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 <= money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 >= money_incomparable # pylint: disable=W0104
        with self.assertRaises(ValueError):
            money1 != money_incomparable # pylint: disable=W0104

if __name__ == '__main__':
    unittest.main()
