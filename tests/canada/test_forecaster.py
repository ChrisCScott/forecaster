""" Tests a Canada-specific implementation of Forecaster. """

import unittest
from copy import copy
from forecaster import Money
from forecaster.canada import (
    ForecasterCanada, RRSP, TFSA, TaxableAccount, TaxCanada, SettingsCanada,
    constants)
from tests.test_forecaster import TestForecaster


class TestForecasterCanada(TestForecaster):
    """ Test forecaster.canada.Forecaster """

    def setUp(self):
        """ Sets up class to use Canadian default values. """
        if not hasattr(self, 'settings'):
            self.settings = SettingsCanada
        super().setUp()

    def test_init_default(self):
        """ Test Forecaster (Canada) init. """
        forecaster = ForecasterCanada()
        self.assertEqual(forecaster.settings, SettingsCanada)

    def test_add_rrsp(self):
        """ Test adding an RRSP with Forecaster (Canada). """
        forecaster = ForecasterCanada(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_rrsp()
        rrsp = RRSP(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            contribution_room=Money(0),
            contributor=forecaster.person1,
            inflation_adjust=forecaster.scenario.inflation_adjust
        )
        self.assertEqual(asset, rrsp)
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_tfsa(self):
        """ Test adding a TFSA with Forecaster (Canada). """
        contribution_accrued = Money(sum(
            constants.TFSA_ANNUAL_ACCRUAL[year]
            for year in constants.TFSA_ANNUAL_ACCRUAL
            if year <= self.settings.initial_year))
        forecaster = ForecasterCanada(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_tfsa()
        tfsa = TFSA(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            contribution_room=contribution_accrued,
            contributor=forecaster.person1,
            inflation_adjust=forecaster.scenario.inflation_adjust
        )
        self.assertEqual(asset, tfsa)
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_add_taxable_account(self):
        """ Test adding a TaxableAccount with Forecaster (Canada). """
        forecaster = ForecasterCanada(settings=self.settings)
        assets = copy(forecaster.assets)
        asset = forecaster.add_taxable_account()
        taxable_account = TaxableAccount(
            owner=forecaster.person1,
            balance=Money(0),
            rate=forecaster.allocation_strategy.rate_function(
                forecaster.person1, forecaster.scenario),
            nper=1,
            inputs={},
            initial_year=forecaster.person1.initial_year,
            acb=Money(0)
        )
        self.assertEqual(asset, taxable_account)
        self.assertEqual(forecaster.assets - assets, {asset})

    def test_set_tax_treatment(self):
        """ Test setting tax treatment with Forecaster (Canada). """
        forecaster1 = ForecasterCanada(settings=self.settings)
        tax = TaxCanada(
            inflation_adjust=self.scenario.inflation_adjust,
            province='BC'
        )
        # Forecaster sometimes prompts tax objects to fill in their
        # annual data (e.g. tax brackets), so wrap our reference object
        # in a Forecaster object as well.
        _ = ForecasterCanada(
            settings=self.settings, tax_treatment=tax)
        self.assertEqual(forecaster1.tax_treatment, tax)

if __name__ == '__main__':
    unittest.main()
