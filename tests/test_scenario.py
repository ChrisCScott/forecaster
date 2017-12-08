""" Unit tests for `Scenario` and related classes """

import unittest
from decimal import Decimal
from random import Random
from forecaster.scenario import Scenario


class TestScenarioMethods(unittest.TestCase):
    """ A test suite for the `Scenario` class """

    @staticmethod
    def get_random_scenario(initial_year=None, length=None):
        """ Returns a random `Scenario` of length `length` starting in `initial_year`.
        (each parameter is randomized if not provided) """
        rand = Random()
        # If inputs aren't given, randomly choose reasonable values.
        if initial_year is None:
            initial_year = rand.randint(2000, 2100)
        if length is None:
            length = rand.randint(2, 200)
        # Initialize empty lists
        inflation = []
        stock_return = []
        bond_return = []
        other_return = []
        management_fees = []
        # Build lists for each variable using a reasonable range.
        #   inflation:          [0, 30%]
        #   stock_return:       [-50%, 50%]
        #   bond_return:        [-25%, 25%]
        #   other_return:       [-10%, 10%]
        #   management_fees:    [0.15%, 2%]
        for _ in range(length):
            inflation.append(rand.random() * 0.3)
            stock_return.append(rand.random() - 0.5)
            bond_return.append(rand.random() * 0.5 - 0.5)
            other_return.append(rand.random() * 0.2 - 0.1)
            management_fees.append(rand.random() * 0.0185 + 0.0015)
        return Scenario(
            initial_year=initial_year, num_years=length,
            inflation=inflation, stock_return=stock_return,
            bond_return=bond_return, other_return=other_return,
            management_fees=management_fees)

    @classmethod
    def setUpClass(cls):
        """ Set up default values for tests """
        cls.initial_year = 2000
        # Set up a simple `Scenario` with constant values
        cls.constant_initial_year = cls.initial_year
        cls.constant_inflation = 0.02
        cls.constant_stock_return = 0.07
        cls.constant_bond_return = 0.04
        cls.constant_other_return = 0.03
        cls.constant_management_fees = 0.01
        cls.constant_num_years = 100
        cls.constant_scenario = Scenario(
            inflation=cls.constant_inflation,
            stock_return=cls.constant_stock_return,
            bond_return=cls.constant_bond_return,
            other_return=cls.constant_other_return,
            management_fees=cls.constant_management_fees,
            initial_year=cls.constant_initial_year,
            num_years=100)

        # Set up a `Scenario` with varying elements,
        # including at least one 0 in each list
        cls.varying_initial_year = cls.initial_year
        cls.varying_num_years = 100
        cls.varying_inflation = [0]
        cls.varying_stock_return = [0]
        cls.varying_bond_return = [0]
        cls.varying_other_return = [0]
        cls.varying_management_fees = [0]
        # Values will jump around, but will generally increase in magnitude
        for i in range(cls.varying_num_years-1):
            cls.varying_inflation.append(0.0025 * i)
            cls.varying_stock_return.append(pow(-1, i) * 0.01 * i)
            cls.varying_bond_return.append(pow(-1, i+1) * 0.005 * i)
            cls.varying_other_return.append(pow(-1, i) * 0.001 * i)
            cls.varying_management_fees.append(0.0002 * i)
        cls.varying_scenario = Scenario(
            inflation=cls.varying_inflation,
            stock_return=cls.varying_stock_return,
            bond_return=cls.varying_bond_return,
            other_return=cls.varying_other_return,
            management_fees=cls.varying_management_fees,
            initial_year=cls.varying_initial_year,
            num_years=cls.varying_num_years)

        cls.scenarios = [cls.constant_scenario, cls.varying_scenario]
        # Add a scenario of all 0 values
        cls.scenarios.append(Scenario(
            inflation=0, stock_return=0, bond_return=0, other_return=0,
            management_fees=0, initial_year=cls.constant_initial_year,
            num_years=10))
        for _ in range(10):  # add some random scenarios to the test set
            cls.scenarios.append(cls.get_random_scenario())

    def test_init(self):
        """ Tests `Scenario.__init__()` and basic properties.

        Also tests `inflation()`, `stock_return()`, and `bond_return()`
        """
        # Test initialization with scalar values.
        scenario = Scenario(
            inflation=0, stock_return=0, bond_return=0, other_return=0,
            management_fees=0, initial_year=2000, num_years=100)
        # Confirm we can pull 100 (identical) years from the scenario
        for i in range(100):
            year = i + 2000
            self.assertEqual(scenario.inflation[year], 0)
            self.assertEqual(scenario.stock_return[year], 0)
            self.assertEqual(scenario.bond_return[year], 0)
            self.assertEqual(scenario.other_return[year], 0)
            self.assertEqual(scenario.management_fees[year], 0)
        self.assertEqual(scenario.initial_year, 2000)

        # Test the varying scenario next, using list inputs
        scenario = Scenario(
            self.varying_initial_year, self.varying_num_years,
            inflation=self.varying_inflation,
            stock_return=self.varying_stock_return,
            bond_return=self.varying_bond_return,
            other_return=self.varying_other_return,
            management_fees=self.varying_management_fees)

        # Do an elementwise comparison to confirm initialization worked
        for i in range(self.varying_num_years):
            year = i + self.varying_initial_year
            self.assertEqual(scenario.inflation[year],
                             self.varying_inflation[i])
            self.assertEqual(scenario.stock_return[year],
                             self.varying_stock_return[i])
            self.assertEqual(scenario.bond_return[year],
                             self.varying_bond_return[i])
            self.assertEqual(scenario.other_return[year],
                             self.varying_other_return[i])
            self.assertEqual(scenario.management_fees[year],
                             self.varying_management_fees[i])
        self.assertEqual(scenario.initial_year, self.varying_initial_year)

        # Construct a varying scenario from dicts instead of lists
        years = list(range(self.varying_initial_year,
                           self.varying_initial_year +
                           len(self.varying_inflation)))
        inflation = dict(zip(years, self.varying_inflation))
        stock_return = dict(zip(years, self.varying_stock_return))
        bond_return = dict(zip(years, self.varying_bond_return))
        other_return = dict(zip(years, self.varying_other_return))
        management_fees = dict(zip(years, self.varying_management_fees))

        # Do an elementwise comparison to confirm initialization worked
        for year in years:
            self.assertEqual(scenario.inflation[year], inflation[year])
            self.assertEqual(scenario.stock_return[year], stock_return[year])
            self.assertEqual(scenario.bond_return[year], bond_return[year])
            self.assertEqual(scenario.other_return[year], other_return[year])
            self.assertEqual(scenario.management_fees[year],
                             management_fees[year])
        self.assertEqual(scenario.initial_year, self.varying_initial_year)

        # Mix constant, list, and dict inputs
        scenario = Scenario(
            initial_year=self.initial_year,
            num_years=len(self.varying_stock_return),
            inflation=0.02, stock_return=self.varying_stock_return,
            bond_return=bond_return, other_return=Decimal(0.03),
            management_fees=self.varying_management_fees)

        for i in range(scenario.num_years):
            year = i + scenario.initial_year
            self.assertEqual(scenario.inflation[year], 0.02)
            self.assertEqual(scenario.stock_return[year],
                             self.varying_stock_return[i])
            self.assertEqual(scenario.bond_return[year], bond_return[year])
            self.assertEqual(scenario.other_return[year], Decimal(0.03))
            self.assertEqual(scenario.management_fees[year],
                             self.varying_management_fees[i])
        self.assertEqual(scenario.initial_year, self.initial_year)

    def test_accumulation_function(self):
        """ Tests `Scenario.accumulation_function()` """
        # use a simple exponentiation to test the constant-valued `Scenario`
        scenario = self.constant_scenario
        for year in range(self.initial_year,
                          self.initial_year + 100):
            self.assertAlmostEqual(
                scenario.accumulation_function(
                    self.constant_initial_year, year),
                pow(Decimal(1 + self.constant_inflation),
                    year - self.constant_initial_year),
                4)

        # for arbitrary scenarios, test against a year-by-year accumulation
        for scenario in self.scenarios:
            accum = 1
            for year in range(scenario.initial_year,
                              scenario.initial_year + len(scenario)):
                self.assertAlmostEqual(
                    scenario.accumulation_function(
                        scenario.initial_year, year),
                    accum)
                accum *= 1 + scenario.inflation[year]

    def test_inflation_adjust(self):
        """ Tests `Scenario.inflation_adjust()` """
        # Test a selection of the scenarios in the set
        # (We could test all, but it's slooow)
        for scenario in self.scenarios[0:9]:
            initial_year = scenario.initial_year
            last_year = scenario.initial_year + len(scenario) - 1
            for base_year in range(initial_year, last_year + 1):
                # This test takes forever if we iterate over every pair
                # of nominal and real years, so keep real_year to within
                # 10 years of nominal_year.
                for this_year in range(max(initial_year, base_year - 10),
                                       min(last_year + 1, base_year + 10)):
                    # Test the real value associated with this
                    # (nominal_year, real_year) pair by taking the
                    # product of all annual inflation factors
                    # (1 + inflation) between nominal_year and real_year
                    accum = 1
                    if base_year < this_year:
                        # If we're inflation-adjusting to a future year,
                        # then inflation_adjust should increase with inflation
                        for year in range(base_year, this_year):
                            accum *= Decimal(1 + scenario.inflation[year])
                    else:
                        # If we're inflation-adjusting to a past year,
                        # then inflation_adjust should decrease with inflation
                        for year in range(this_year, base_year):
                            accum /= Decimal(1 + scenario.inflation[year])
                    # Now that we know the cumulative inflation, we can
                    # express in real-valued terms simply by multiplying
                    self.assertAlmostEqual(
                        Decimal(100) * Decimal(scenario.inflation_adjust(
                            this_year, base_year)),
                        Decimal(100) * accum, 4)
                # Sanity check: Confirm that real = nominal for the year
                # that we're using for expressing real values.
                self.assertEqual(
                    scenario.inflation_adjust(base_year, base_year),
                    1)

    def test_len(self):
        """ Tests `Scenario.__len__`. """

        # Some variables that we'll use multiple times:
        num_years = 100
        initial_year = 2000

        # Test a constant scenario
        scenario = Scenario(
            inflation=0, stock_return=0, bond_return=0, other_return=0,
            management_fees=0, initial_year=initial_year, num_years=num_years)
        self.assertEqual(len(scenario), num_years)

        # Test a scenario built from lists/constants
        scenario = Scenario(
            initial_year=initial_year, num_years=num_years,
            inflation=[0 for _ in range(0, num_years)],
            stock_return=[0 for _ in range(0, num_years)],
            bond_return=[0 for _ in range(0, num_years)])
        self.assertEqual(len(scenario), num_years)

        # Test a scenario built from dicts:
        num_years = 100
        scenario = Scenario(
            initial_year=initial_year,
            num_years=num_years,
            inflation={
                year: 0
                for year in range(initial_year, initial_year + num_years)
            },
            stock_return={
                year: 0
                for year in range(initial_year, initial_year + num_years - 1)
            },
            bond_return=0,
            other_return=0,
            management_fees=0)
        self.assertEqual(len(scenario), num_years)

        # Test a scenario built from dicts and (longer) lists:
        num_years = 100
        scenario = Scenario(
            initial_year=initial_year,
            num_years=num_years,
            inflation={
                year: 0
                for year in range(initial_year, initial_year + num_years)
            },
            stock_return={
                year: 0
                for year in range(initial_year, initial_year + num_years - 1)
            },
            bond_return=[0 for _ in range(0, num_years)],
            other_return=0,
            management_fees=0)
        self.assertEqual(len(scenario), num_years)

if __name__ == '__main__':
    unittest.main()
