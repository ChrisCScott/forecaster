""" Unit tests for `ForecasterTester`, a helper TestCase. """

import unittest
from copy import deepcopy
from forecaster import Settings, Tax, Person, Scenario
from tests.forecaster_tester import ForecasterTester

class TestForecaster(ForecasterTester):
    """ Tests ForecasterTester. """

    def setUp(self):
        """ Builds a default Person for testing of complex objects. """

        # Build inputs to Person:
        self.settings = Settings()  # default settings object
        self.initial_year = self.settings.initial_year  # convenience
        self.scenario = Scenario(
            inflation=self.settings.inflation,
            stock_return=self.settings.stock_return,
            bond_return=self.settings.bond_return,
            other_return=self.settings.other_return,
            management_fees=self.settings.management_fees,
            initial_year=self.settings.initial_year,
            num_years=self.settings.num_years)
        self.tax_treatment = Tax(
            tax_brackets=self.settings.tax_brackets,
            personal_deduction=self.settings.tax_personal_deduction,
            credit_rate=self.settings.tax_credit_rate,
            inflation_adjust=self.scenario.inflation_adjust)

        # Build a Person object to test against later:
        self.person = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2040",
            gross_income=10000,
            raise_rate=0,
            spouse=None,
            tax_treatment=self.tax_treatment)

    def test_assertEqual_identical(self):  # pylint: disable=invalid-name
        """ Tests assertEqual with identical arguments. """
        # Compare an object to itself
        self.assertEqual(self.person, self.person)

    def test_assertEqual_copy(self): # pylint: disable=invalid-name
        """ Tests assertEqual with equal operands (produced by copying). """
        # Compare two idential instances of an object:
        person2 = deepcopy(self.person)
        self.assertEqual(self.person, person2)

    def test_assertNotEqual(self): # pylint: disable=invalid-name
        """ Tests assertNotEqual with non-equal operands. """
        # Compare two instances of an object that differ only in a
        # complicated attribute. (Simple case: set it to None)
        person2 = deepcopy(self.person)
        person2.tax_treatment = None
        self.assertNotEqual(self.person, person2)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
