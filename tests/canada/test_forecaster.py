""" Tests a Canada-specific implementation of Forecaster. """

import unittest
from copy import copy
import context  # pylint: disable=unused-import
from forecaster.canada.forecaster import Forecaster
from forecaster.canada.accounts import RRSP, TFSA, TaxableAccount, Money
from forecaster.canada.tax import Tax
from forecaster.canada.settings import Settings
from forecaster.canada import constants
from tests.test_forecaster import TestForecaster as TestSuperForecaster


class TestForecaster(TestSuperForecaster):
    """ Test forecaster.canada.Forecaster """

    def setUp(self):
        """ Sets up class to use Canadian default values. """
        if not hasattr(self, 'settings'):
            self.settings = Settings
        super().setUp()

    def test_init_default(self):
        """ Test Forecaster (Canada) init. """
        forecaster = Forecaster()
        self.assertEqual(forecaster.settings, Settings)

    def test_add_rrsp(self):
        """ Test adding an RRSP with Forecaster (Canada). """
        forecaster = Forecaster(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_rrsp()
        self.assertEqual(asset, RRSP(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            transactions={},
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            contribution_room=Money(0),
            contributor=forecaster.person1,
            inflation_adjust=forecaster.scenario.inflation_adjust
        ))
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_tfsa(self):
        """ Test adding a TFSA with Forecaster (Canada). """
        contribution_accrued = Money(sum(
            constants.TFSA_ANNUAL_ACCRUAL[year]
            for year in constants.TFSA_ANNUAL_ACCRUAL
            if year <= self.settings.initial_year))
        forecaster = Forecaster(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_tfsa()
        self.assertEqual(asset, TFSA(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            transactions={},
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            contribution_room=contribution_accrued,
            contributor=forecaster.person1,
            inflation_adjust=forecaster.scenario.inflation_adjust
        ))
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_taxable_account(self):
        """ Test adding a TaxableAccount with Forecaster (Canada). """
        forecaster = Forecaster(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_taxable_account()
        self.assertEqual(asset, TaxableAccount(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            transactions={},
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            acb=Money(0)
        ))
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_set_tax_treatment(self):
        """ Test setting tax treatment with Forecaster (Canada). """
        forecaster = Forecaster(settings=self.settings)
        self.assertEqual(forecaster.tax_treatment, Tax(
            inflation_adjust=self.scenario.inflation_adjust,
            province='BC'
        ))

if __name__ == '__main__':
    unittest.main()
