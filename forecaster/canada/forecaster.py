""" Provides a Canada-specific implementation of Forecaster. """

from forecaster.forecaster import Forecaster
from forecaster.canada.accounts import RRSP, TFSA, TaxableAccount
from forecaster.canada.tax import TaxCanada
from forecaster.canada.settings import SettingsCanada


class ForecasterCanada(Forecaster):
    """ Tests Forecaster (Canada). """

    def __init__(self, settings=SettingsCanada, **kwargs):
        """ Inits Forecaster with Canada-specific settings.

        In addition to using a Canada-specific Settings object by
        default, this class also provides Canada-specific defaults and
        init logic for RRSPs, TFSAs, TaxableAccounts, and Tax objects.
        """
        super().__init__(settings=settings, **kwargs)

    def add_rrsp(
            self, inflation_adjust=None, rrif_conversion_year=None, cls=RRSP,
            **kwargs):
        """ Adds an RRSP to the forecast. """
        self.set_kwarg(
            kwargs, 'inflation_adjust', inflation_adjust,
            self.scenario.inflation_adjust)
        self.set_kwarg(
            kwargs, 'rrif_conversion_year', rrif_conversion_year, None)
        return self.add_contribution_limit_account(cls=cls, **kwargs)

    def add_tfsa(
            self, inflation_adjust=None, cls=TFSA, **kwargs):
        """ Adds a TFSA to the forecast. """
        self.set_kwarg(
            kwargs, 'inflation_adjust', inflation_adjust,
            self.scenario.inflation_adjust)
        return self.add_contribution_limit_account(cls=cls, **kwargs)

    def add_taxable_account(
            self, acb=None, cls=TaxableAccount, **kwargs):
        """ Adds a TaxableAccount to the forecast. """
        self.set_kwarg(kwargs, 'acb', acb, None)
        return self.add_asset(cls=cls, **kwargs)

    def set_tax_treatment(
            self, inflation_adjust=None, province=None, cls=TaxCanada,
            **kwargs):
        """ Sets tax treatment for the forecast.

        Overrides set_tax_treatment to deal with different parameter
        list for canada.tax objects.
        """
        # canada.tax has a different call signature than forecaster.tax,
        # so it's appropriate for this method to take different args.
        # pylint: disable=arguments-differ

        self.set_kwarg(
            kwargs, 'inflation_adjust', inflation_adjust,
            self.scenario.inflation_adjust)
        self.set_kwarg(kwargs, 'province', province, None)
        self.tax_treatment = cls(**kwargs)
        return self.tax_treatment
