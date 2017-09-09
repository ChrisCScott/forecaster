""" Unit tests for `Scenario` and related classes """

import unittest
from decimal import Decimal
from random import Random
from settings import Settings
from scenario import Scenario
from scenario import ConstantScenario
from scenario import DefaultScenario
from scenario import ScenarioYear


class TestScenarioMethods(unittest.TestCase):
    """ A test suite for the `Scenario` class """

    @staticmethod
    def get_random_scenario(initial_year=None, length=None):
        """ Returns a random `Scenario` of length `length` starting in `initial_year`.
        (each parameter is randomized if not provided) """
        rand = Random()
        if initial_year is None:
            initial_year = rand.randint(2000, 2100)
        if length is None:
            length = rand.randint(2, 200)
        inflation = [0]
        stock_return = [0]
        bond_return = [0]
        for _ in range(length-1):
            inflation.append(rand.random()*0.3)
            stock_return.append(rand.random()-0.5)
            bond_return.append((rand.random()-0.5)/2)
        return Scenario(inflation, stock_return, bond_return)

    def setUp(self):
        """ Set up default values for tests """
        # Set up a simple `Scenario` with constant values
        self.constant_initial_year = Settings.initial_year
        self.constant_length = 100
        self.constant_inflation = [0.02] * self.constant_length
        self.constant_stock_return = [0.07] * self.constant_length
        self.constant_bond_return = [0.04] * self.constant_length
        self.constant_scenario = Scenario(self.constant_inflation,
                                          self.constant_stock_return,
                                          self.constant_bond_return,
                                          self.constant_initial_year)

        # Set up a `Scenario` with varying elements,
        # including at least one 0 in each list
        self.varying_initial_year = Settings.initial_year
        self.varying_length = 101
        self.varying_inflation = [0]
        self.varying_stock_return = [0]
        self.varying_bond_return = [0]
        # Values will jump around, but will generally increase in magnitude
        for i in range(self.varying_length-1):
            self.varying_inflation.append(0.0025 * i)
            self.varying_stock_return.append(pow(-1, i) * 0.01 * i)
            self.varying_bond_return.append(pow(-1, i+1) * 0.005 * i)
        self.varying_scenario = Scenario(self.varying_inflation,
                                         self.varying_stock_return,
                                         self.varying_bond_return,
                                         self.varying_initial_year)

        self.scenarios = [self.constant_scenario, self.varying_scenario]
        # Include a Constant Scenario and a (the) DefaultScenario
        self.scenarios.append(ConstantScenario(self.constant_inflation[0],
                                               self.constant_stock_return[0],
                                               self.constant_bond_return[0]))
        self.scenarios.append(DefaultScenario())
        for _ in range(100):  # add some random scenarios to the test set
            self.scenarios.append(self.get_random_scenario())

    def scenario_test(self, inflation, stock_return, bond_return, length,
                      initial_year=None):
        """ Builds a `Scenario` object and runs various tests.
        Returns the object for further testing.
        A utility function for `test_init`. """
        scenario = Scenario(inflation, stock_return, bond_return, initial_year)
        self.assertIsNotNone(scenario)  # construction didn't fail
        self.assertEqual(len(inflation), len(scenario))  # all years exist
        # We need initial_year for index-calculating purposes
        if initial_year is None:
            initial_year = Settings.initial_year
        # next, test that values are as expected for each year
        for i in range(0, length):
            self.assertEqual(scenario.inflation(i + initial_year),
                             inflation[i])
            self.assertEqual(scenario.stock_return(i + initial_year),
                             stock_return[i])
            self.assertEqual(scenario.bond_return(i + initial_year),
                             bond_return[i])
        return scenario  # Return scenario for further testing

    def type_test(self, type_, inflation, stock_return, bond_return,
                  initial_year=None):
        """ Builds a `Scenario` object of type `type` and runs various tests.
        Returns the object for further testing.
        A utility function for `test_init`. """
        inf, sto, bon = [], [], []
        for i in enumerate(inflation):
            inf.append(type_(inflation[i]))
            sto.append(type_(stock_return[i]))
            bon.append(type_(bond_return[i]))
        scenario = Scenario(inf, sto, bon)
        self.assertIsNotNone(scenario)  # construction didn't fail
        self.assertEqual(len(inflation), len(scenario))  # all years exist
        if initial_year is None:
            initial_year = Settings.initial_year
        for year in range(initial_year, initial_year + len(scenario)):
            self.assertEqual(scenario.inflation(year),
                             type_(inflation[year - initial_year]))
            self.assertEqual(scenario.stock_return(year),
                             type_(stock_return[year - initial_year]))
            self.assertEqual(scenario.bond_return(year),
                             type_(bond_return[year - initial_year]))

    def test_init(self):
        """ Tests `Scenario.__init__()` and basic properties.

        Also tests `inflation()`, `stock_return()`, and `bond_return()`
        """
        # Test the constant scenario first
        self.scenario_test(self.constant_inflation, self.constant_stock_return,
                           self.constant_bond_return, self.constant_length,
                           self.constant_initial_year)
        # Test the varying scenario next
        self.scenario_test(self.varying_inflation, self.varying_stock_return,
                           self.varying_bond_return, self.varying_length,
                           self.varying_initial_year)
        # Test the varying scenario without an initial year
        self.scenario_test(self.varying_inflation, self.varying_stock_return,
                           self.varying_bond_return, self.varying_length)

        # Test initialization with other input types
        self.type_test(Decimal,
                       self.varying_inflation, self.varying_stock_return,
                       self.varying_bond_return, self.varying_initial_year)
        self.type_test(float,
                       self.varying_inflation, self.varying_stock_return,
                       self.varying_bond_return, self.varying_initial_year)
        self.type_test(int,
                       self.varying_inflation, self.varying_stock_return,
                       self.varying_bond_return, self.varying_initial_year)

        # Test initialization of subclasses

    def test_accumulation_function(self):
        """ Tests `Scenario.accumulation_function()` """
        # use a simple exponentiation to test the constant-valued `Scenario`
        scenario = self.constant_scenario
        for year in range(Settings.initial_year,
                          Settings.initial_year + self.constant_length):
            self.assertAlmostEqual(
                scenario.accumulation_function(
                    self.constant_initial_year, year),
                pow(1 + self.constant_inflation[0],
                    year - self.constant_initial_year))

        # for arbitrary scenarios, test against a year-by-year accumulation
        for scenario in self.scenarios:
            accum = 1
            for year in range(scenario.initial_year(),
                              scenario.initial_year() + len(scenario)):
                self.assertAlmostEqual(
                    scenario.accumulation_function(
                        scenario.initial_year(), year),
                    accum)
                accum *= 1 + scenario.inflation(year)

    def test_real_value(self):
        """ Tests `Scenario.real_value()` """
        # TODO: Implement test
        pass

    def test_list_methods(self):
        """ Tests Sequence-implementing methods.

        These include `__len__`, `__getitem__`, `__iter__`, and
        `ScenarioYear`
        """
        scenario = self.constant_scenario
        length = self.constant_length
        inputs = (self.constant_inflation, self.constant_stock_return,
                  self.constant_bond_return)
        initial_year = self.constant_initial_year
        for array in inputs:
            self.assertEqual(len(scenario), length)
            self.assertEqual(len(scenario), len(array))
        # test as tuple and individually
        for year in range(initial_year, initial_year + length):
            self.assertEqual(scenario[year],
                             ScenarioYear(inputs[0][year - initial_year],
                                          inputs[1][year - initial_year],
                                          inputs[2][year - initial_year]))
            self.assertEqual(scenario[year].inflation,
                             inputs[0][year - initial_year])
            self.assertEqual(scenario[year].stock_return,
                             inputs[1][year - initial_year])
            self.assertEqual(scenario[year].bond_return,
                             inputs[2][year - initial_year])

        scenario = self.varying_scenario
        length = self.varying_length
        inputs = (self.varying_inflation, self.varying_stock_return,
                  self.varying_bond_return)
        initial_year = self.varying_initial_year
        for array in inputs:
            self.assertEqual(len(scenario), length)
            self.assertEqual(len(scenario), len(array))
        # test as tuple and individually
        for year in range(initial_year, initial_year + length):
            self.assertEqual(scenario[year],
                             ScenarioYear(inputs[0][year - initial_year],
                             inputs[1][year - initial_year],
                             inputs[2][year - initial_year]))
            self.assertEqual(scenario[year].inflation,
                             inputs[0][year - initial_year])
            self.assertEqual(scenario[year].stock_return,
                             inputs[1][year - initial_year])
            self.assertEqual(scenario[year].bond_return,
                             inputs[2][year - initial_year])

        for scenario in self.scenarios:
            for year in range(initial_year, initial_year + len(scenario)):
                self.assertEqual(scenario[year].inflation,
                                 scenario.inflation(year))
                self.assertEqual(scenario[year].stock_return,
                                 scenario.stock_return(year))
                self.assertEqual(scenario[year].bond_return,
                                 scenario.bond_return(year))

if __name__ == '__main__':
    unittest.main()
