""" Provides a Canada-specific implementation of Forecaster. """

from forecaster.forecaster import ForecastBuilder, Parameter
from forecaster.canada.tax import TaxCanada
from forecaster.canada.settings import SettingsCanada


# Override the arguments for initializing tax_treatment, since
# ForecasterCanada uses TaxCanada instead of Tax.
DEFAULTVALUES = {
    str(Parameter.TAX_TREATMENT): {
        "inflation_adjust": "scenario.inflation_adjust",
        "province": "settings.tax_province"}
}

# This maps each of the above parameters to a type:
DEFAULTTYPES = {str(Parameter.TAX_TREATMENT): TaxCanada}

class ForecastBuilderCanada(ForecastBuilder):
    """ Tests ForecastBuilder (Canada). """

    def __init__(self, *args, settings=None, **kwargs):
        """ Inits ForecastBuilder with Canada-specific settings.

        In addition to using a Canada-specific Settings object by
        default, this class also provides Canada-specific defaults and
        init logic for RRSPs, TFSAs, TaxableAccounts, and Tax objects.
        """
        if settings is None:
            settings = SettingsCanada()
        super().__init__(*args, settings=settings, **kwargs)
        self.default_values.update(DEFAULTVALUES)
        self.default_types.update(DEFAULTTYPES)
