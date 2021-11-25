""" This module provides user-modifiable settings for the application.

It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application.
"""

import datetime
from forecaster.value_reader import ValueReader

INITIAL_YEAR_DEFAULT = datetime.datetime.now().year
FILENAME_DEFAULT = 'settings.json'

# This dict is useful for two reasons:
#   1) It provides sensible defaults for each attribute of Settings
#   2) It represents each value using the appropriate type, which
#       facilitates type-checking of user-provided files if desired.
DEFAULTS = {
    # Application-level and UI defaults
    'initial_year': INITIAL_YEAR_DEFAULT,  # Model starts with this year
    'display_year': INITIAL_YEAR_DEFAULT,  # Base year for real-valued amounts
    'currency': 'CAD',  # Use Canadian dollars as the default currency

    # Defaults for `Scenario`
    'inflation': 0.02,
    'stock_return': 0.07,
    'bond_return': 0.04,
    'other_return': 0.03,
    'management_fees': 0.005,
    'num_years': 100,  # Model this number of years from the initial_year

    # LivingExpensesStrategy defaults
    'living_expenses_strategy': 'Constant living expenses',
    'living_expenses_base_amount': 60000,
    'living_expenses_rate': 0.2,
    'living_expenses_inflation_adjust': True,

    # SavingStrategy defaults
    'saving_strategy': "Ordered",
    'saving_weights': {"Account": 1},

    # WithdrawalStrategy defaults
    'withdrawal_strategy': "Ordered",
    'withdrawal_weights': {"Account": 1},

    # AllocationStrategy defaults
    'allocation_strategy': 'n-age',
    'allocation_min_equity': 0.3,
    'allocation_max_equity': 0.3,
    'allocation_std_retirement_age': 65,
    'allocation_target': 65,
    'allocation_risk_trans_period': 20,
    'allocation_adjust_retirement': True,

    # DebtPaymentStrategy defaults
    'debt_payment_strategy': 'Avalanche',

    # Tax defaults
    'tax_brackets': {INITIAL_YEAR_DEFAULT: {0: 0}},
    'tax_personal_deduction': {INITIAL_YEAR_DEFAULT: 0},
    'tax_credit_rate': {INITIAL_YEAR_DEFAULT: 0},
    'tax_payment_timing': 'start'
}

class Settings(ValueReader):
    """ Container for variables used to control application settings.

    All settings are exposed as attributes of `Settings` objects. For
    example, Settings().initial_year will return the value of the
    `'initial_year'` key in `data/settings.json`.

    Although a filename can be specified for loading settings, by
    default this class reads from `forecaster/data/settings.json`. All
    relative paths are resolved from `forecaster/data`, so if you want
    to open a file elsewhere use an absolute path!

    This class takes all of the same args as `ValueReader`, except
    `make_attr` (which is forced to `True`) and with the addition of
    `defaults` (to support convenient subclassing).

    Arguments:
        filename (str): The filename of a JSON file to read.
            The file must be UTF-8 encoded.
            Optional. Defaults to `forecaster/data/settings.json`.
        encoder_cls (JSONEncoder): A custom JSONEncoder with an
            overloaded `default` method for serializing additional
            types. See documentation for the `cls` argument to
            `json.dump` for more information.
            Optional. Defaults to `HighPrecisionJSONEncoder`.
        decoder_cls (JSONDecoder): A custom JSONDecoder that supports
            reading in high-precision numeric types serialized in the
            way that `encoder_cls` emits.
            Optional. Defaults to `JSONDecoder`.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.
        high_precision_serialize (Callable[[HighPrecisionType], str]):
            A callable object that converts a high-precision numeric
            type to str.
            Optional. Defaults to HighPrecisionType.__str__.
        numeric_convert (bool): If True, any float-convertible str
            keys or values will be converted to a numeric type on read
            (int if appropriate, otherwise a high-precision type or
            float, depending on whether this instance supports
            high-precision). Optional. Defaults to True.
        defaults (dict[str, Any]): Default values for each setting
            supported by this class. Will be added as attributes.
            Optional. Defaults to `settings.DEFAULTS`.
    """

    def __init__(self, filename=None, *,
            encoder_cls=None, decoder_cls=None,
            high_precision=None, high_precision_serialize=None,
            numeric_convert=True, defaults=None):
        # Create attributes with default values:
        for (key, val) in defaults.items():
            self.add_json_attribute(key, val)

        if filename is None:
            # Use default settings file (at forecaster/data/settings.json)
            filename = FILENAME_DEFAULT
        if defaults is None:
            defaults = DEFAULTS

        # Load values from file, overwriting defaults where applicable:
        super().__init__(
            filename, make_attr=True,
            encoder_cls=encoder_cls, decoder_cls=decoder_cls,
            high_precision=high_precision,
            high_precision_serialize=high_precision_serialize,
            numeric_convert=numeric_convert)
