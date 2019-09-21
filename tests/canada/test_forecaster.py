""" Tests a Canada-specific implementation of ForecastBuilder. """

import unittest
from forecaster import Parameter
from forecaster.canada import (
    ForecastBuilderCanada, TaxCanada, SettingsCanada, TaxableAccount)
from tests.test_forecaster import TestForecastBuilder


class TestForecastBuilderCanada(TestForecastBuilder):
    """ Test forecaster.canada.ForecastBuilderCanada """

    def setUp(self):
        """ Sets up class to use Canadian default values. """
        # Override settings/forecast builder types to use Canadian
        # subclasses. (This is conditional so that subclasses can assign
        # their own objects before calling super().setUp())
        if not hasattr(self, 'settings'):
            self.settings = SettingsCanada()
        if not hasattr(self, 'forecast_builder_type'):
            self.forecast_builder_type = ForecastBuilderCanada
        # Let the superclass handle setup:
        super().setUp()

        # Override tax_treatment to use TaxCanada object:
        self.tax_treatment = TaxCanada(
            inflation_adjust=self.scenario.inflation_adjust,
            province=self.settings.tax_province)
        # The AccountTransactionStrategy settings for
        # ForecastBuilderCanada don't include an Account object; replace
        # it with an otherwise-identical TaxableAccount, which is
        # represented in the settings.
        self.account = TaxableAccount(
            owner=self.person,
            balance=self.account.balance,
            rate=self.account.rate,
            nper=self.account.nper)

    def test_init_default(self):
        """ Test ForecastBuilder (Canada) init. """
        self.forecast_builder = ForecastBuilderCanada()
        self.assertIsInstance(self.forecast_builder.settings, SettingsCanada)

    def test_build_tax_treatment(self):
        """ Test ForecastBuilder.build_param for tax_treatment. """
        param = self.forecast_builder.get_param(Parameter.TAX_TREATMENT)
        self.assertEqual(param, self.tax_treatment)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
