""" Tests a Canada-specific implementation of Forecaster. """

import unittest
from decimal import Decimal
from forecaster import Parameter
from forecaster.canada import (
    ForecasterCanada, TaxCanada, SettingsCanada, TaxableAccount, constants)
from tests.test_forecaster import TestForecaster


class TestForecasterCanada(TestForecaster):
    """ Test forecaster.canada.Forecaster """

    def setUp(self):
        """ Sets up class to use Canadian default values. """
        # Override settings/forecaster types to use Canadian subclasses.
        # (This is conditional so that subclasses can assign their own
        # objects before calling super().setUp())
        if not hasattr(self, 'settings'):
            self.settings = SettingsCanada()
        if not hasattr(self, 'forecaster_type'):
            self.forecaster_type = ForecasterCanada
        # Let the superclass handle setup:
        super().setUp()

        self.constants = constants.ConstantsCanada()

        # Override tax_treatment to use TaxCanada object:
        self.tax_treatment = TaxCanada(
            inflation_adjust=self.scenario.inflation_adjust,
            province=self.settings.tax_province, constants=self.constants)
        # The AccountTransactionStrategy settings for ForecasterCanada
        # don't include an Account object; replace it with an
        # otherwise-identical TaxableAccount, which is represented in
        # the settings.
        self.account = TaxableAccount(
            owner=self.person,
            balance=self.account.balance,
            rate=self.account.rate,
            nper=self.account.nper)

    def setUp_decimal(self):
        """ Sets up class to use Canadian default values. """
        # This handles almost everything:
        super().setUp_decimal()

        self.settings = SettingsCanada(high_precision=Decimal)
        self.constants = constants.ConstantsCanada(high_precision=Decimal)

        # Override tax_treatment to use TaxCanada object:
        self.tax_treatment = TaxCanada(
            inflation_adjust=self.scenario.inflation_adjust,
            province=self.settings.tax_province,
            high_precision=Decimal,
            constants=self.constants)
        # The AccountTransactionStrategy settings for ForecasterCanada
        # don't include an Account object; replace it with an
        # otherwise-identical TaxableAccount, which is represented in
        # the settings.
        self.account = TaxableAccount(
            owner=self.person,
            balance=self.account.balance,
            rate=self.account.rate,
            nper=self.account.nper,
            high_precision=Decimal)

    def test_init_default(self):
        """ Test Forecaster (Canada) init. """
        self.forecaster = ForecasterCanada()
        self.assertIsInstance(self.forecaster.settings, SettingsCanada)

    def test_build_tax_treatment(self):
        """ Test Forecaster.build_param for tax_treatment. """
        param = self.forecaster.get_param(Parameter.TAX_TREATMENT)
        self.assertEqual(param, self.tax_treatment)

    def test_decimal(self):
        """ Test Forecaster.build_param with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()
        param = self.forecaster.get_param(Parameter.TAX_TREATMENT)
        self.assertEqual(param, self.tax_treatment)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))
