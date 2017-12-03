""" Unit tests for `Forecaster`. """

import unittest
import decimal
from decimal import Decimal
from collections import defaultdict
from settings import Settings
from tax import Tax
from ledger import Person, Account, Debt
from scenario import Scenario
from strategy import *
from forecast import Forecast
from forecaster import Forecaster
from test_helper import *


class TestForecaster(unittest.TestCase):
    """ Tests Forecaster. """

    def test_init(self):
        """ Tests Forecaster.__init__ """
        # Test default init:
        forecaster = Forecaster()
        self.assertIsNone(forecaster.person1)
        self.assertIsNone(forecaster.person2)
        self.assertEqual(forecaster.people, set())
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertIsNone(forecaster.contribution_strategy)
        self.assertIsNone(forecaster.withdrawal_strategy)
        self.assertIsNone(forecaster.transaction_in_strategy)
        self.assertIsNone(forecaster.transaction_out_strategy)
        self.assertIsNone(forecaster.allocation_strategy)
        self.assertIsNone(forecaster.debt_payment_strategy)
        self.assertEqual(forecaster.settings, Settings)
        self.assertEqual(forecaster.initial_year, Settings.initial_year)

        # Test explicit init
        settings = Settings()
        settings.person1_name = 'Test Name'
        initial_year = 2000
        forecaster = Forecaster(settings=settings, initial_year=initial_year)
        self.assertIsNone(forecaster.person1)
        self.assertIsNone(forecaster.person2)
        self.assertEqual(forecaster.people, set())
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertIsNone(forecaster.contribution_strategy)
        self.assertIsNone(forecaster.withdrawal_strategy)
        self.assertIsNone(forecaster.transaction_in_strategy)
        self.assertIsNone(forecaster.transaction_out_strategy)
        self.assertIsNone(forecaster.allocation_strategy)
        self.assertIsNone(forecaster.debt_payment_strategy)
        self.assertEqual(forecaster.settings, settings)
        self.assertEqual(forecaster.settings.person1_name, 'Test Name')
        self.assertEqual(forecaster.initial_year, initial_year)

    def test_add_person(self):
        """ TODO """
        pass

    def test_add_account(self):
        """ TODO """
        pass

    def test_add_debt(self):
        """ TODO """
        pass

if __name__ == '__main__':
    unittest.main()
