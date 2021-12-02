""" This module provides user-modifiable settings for the application.

It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application.
"""

import datetime
from forecaster.utility.value_reader import (
    ValueReader, ValueReaderAttribute as Attr)

INITIAL_YEAR_DEFAULT = datetime.datetime.now().year
FILENAME_DEFAULT = 'settings.json'

class Settings(ValueReader):
    """ Container for variables used to control application settings.

    All settings are exposed as attributes of `Settings` objects. For
    example, Settings().initial_year will return the value of the
    `'initial_year'` key in `data/settings.json`. This is partially
    syntactic sugar for convenience and to help with Intellisense
    (e.g. `Settings().initial_year` is equivalent to
    `Settings().values['initial_year']).

    Each attribute has a sensible default value. Some potential uses for
    these are (a) type-checking (the defaults use the structure expected
    by client code), and (b) default values for when a value isn't read
    in from file. (Defaults are only used if `use_defaults` is True.)

    Although a filename can be specified for loading settings, by
    default this class reads from `forecaster/data/settings.json`. All
    relative paths are resolved from `forecaster/data`, so if you want
    to open a file elsewhere use an absolute path!

    This class takes all of the same args as `ValueReader`.

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
        use_defaults (bool): If True, any `ValueReaderAttribute` which
            doesn't have a value read in from file will return its
            default value if one is provided in the class definition.
            Optional. Defaults to True.

    Attributes:
        initial_year (int): Starting year for the model. Defaults to
            the current year.
        display_year (int): Real values will be displayed in this year's
            currency (e.g. 2017 dollars). Defaults to the current year.
        currency (str): A three-character string representing the
            currency to use for the model. Defaults to 'CAD'.
        inflation (float): A default value for building `Scenario`
            objects. Defaults to 0.02 (i.e. 2%).
        stock_return (float): A default value for building `Scenario`
            objects. Defaults to 0.07 (i.e. 7%).
        bond_return (float): A default value for building `Scenario`
            objects. Defaults to 0.04 (i.e. 4%).
        other_return (float): A default value for building `Scenario`
            objects. Defaults to 0.03 (i.e. 3%).
        management_fees (float): A default value for building `Scenario`
            objects. Defaults to 0.005 (i.e. 0.5%).
        num_years (int): A default value for building `Scenario`
            objects. Defaults to 100.
        living_expenses_strategy (str): A default value for building
            `LivingExpensesStrategy` objects. Defaults to
            'Constant living expenses'.
        living_expenses_base_amount (float): A default value for
            building `LivingExpensesStrategy` objects. Defaults to
            60,000.
        living_expenses_rate (float): A default value for building
            `LivingExpensesStrategy` objects. Defaults to 0.2.
        living_expenses_inflation_adjust (bool): A default value for
            building `LivingExpensesStrategy` objects. Defaults to True.
        saving_strategy (str): A default value for building
            `SavingStrategy` objects. Defaults to 'Ordered'.
        saving_weights (dict[str, float]): A default value for building
            `SavingStrategy` objects. Defaults to {'Account': 1}.
        allocation_strategy (str): A default value for building
            `AllocationStrategy` objects. Defaults to 'n-age'.
        allocation_min_equity (float): A default value for building
            `AllocationStrategy` objects. Defaults to 0.3.
        allocation_max_equity (float): A default value for building
            `AllocationStrategy` objects. Defaults to 0.3.
        allocation_std_retirement_age (int): A default value for
            building `AllocationStrategy` objects. Defaults to 65.
        allocation_target (int): A default value for building
            `AllocationStrategy` objects. Defaults to 65.
        allocation_risk_trans_period (int): A default value for building
            `AllocationStrategy` objects. Defaults to 20.
        allocation_adjust_retirement (bool): A default value for
            building `AllocationStrategy` objects. Defaults to True.
        debt_payment_strategy (str): A default value for building
            `DebtPaymentStrategy` objects. Defaults to 'Avalanche'.
        tax_brackets (dict[str, dict[float, float]]): A default value
            for building `Tax` objects. {INITIAL_YEAR_DEFAULT: {0: 0}}.
        tax_personal_deduction (dict[str, float]): A default value
            for building `Tax` objects. Defaults to
            {INITIAL_YEAR_DEFAULT: 0}.
        tax_credit_rate (dict[int, float]): A default value
            for building `Tax` objects. Defaults to
            {INITIAL_YEAR_DEFAULT: 0}.
        tax_payment_timing (str | float)]: A default value
            for building `Tax` objects. Defaults to 'start'.
    """

    # ValueReaderAttributes, to be read in from file:

    # Application-level and UI defaults
    initial_year = Attr(INITIAL_YEAR_DEFAULT)  # Model starts with this year
    display_year = Attr(INITIAL_YEAR_DEFAULT)  # Base year for real values
    currency = Attr('CAD')  # Use Canadian dollars as the default currency

    # Defaults for `Scenario`
    inflation = Attr(0.02)
    stock_return = Attr(0.07)
    bond_return = Attr(0.04)
    other_return = Attr(0.03)
    management_fees = Attr(0.005)
    num_years = Attr(100)  # Model this number of years from the initial_year

    # LivingExpensesStrategy defaults
    living_expenses_strategy = Attr('Constant living expenses')
    living_expenses_base_amount = Attr(60000)
    living_expenses_rate = Attr(0.2)
    living_expenses_inflation_adjust = Attr(True)

    # SavingStrategy defaults
    saving_strategy = Attr("Ordered")
    saving_weights = Attr({"Account": 1})

    # WithdrawalStrategy defaults
    withdrawal_strategy = Attr("Ordered")
    withdrawal_weights = Attr({"Account": 1})

    # AllocationStrategy defaults
    allocation_strategy = Attr('n-age')
    allocation_min_equity = Attr(0.3)
    allocation_max_equity = Attr(0.3)
    allocation_std_retirement_age = Attr(65)
    allocation_target = Attr(65)
    allocation_risk_trans_period = Attr(20)
    allocation_adjust_retirement = Attr(True)

    # DebtPaymentStrategy defaults
    debt_payment_strategy = Attr('Avalanche')

    # Tax defaults
    tax_brackets = Attr({INITIAL_YEAR_DEFAULT: {0: 0}})
    tax_personal_deduction = Attr({INITIAL_YEAR_DEFAULT: 0})
    tax_credit_rate = Attr({INITIAL_YEAR_DEFAULT: 0})
    tax_payment_timing = Attr('start')

    def __init__(self, filename=None, *,
            encoder_cls=None, decoder_cls=None,
            high_precision=None, high_precision_serialize=None,
            numeric_convert=True, use_defaults=True):

        if filename is None:
            # Use default settings file (at forecaster/data/settings.json)
            filename = FILENAME_DEFAULT

        # Load values from file, overwriting defaults where applicable:
        super().__init__(
            filename,
            encoder_cls=encoder_cls, decoder_cls=decoder_cls,
            high_precision=high_precision,
            high_precision_serialize=high_precision_serialize,
            numeric_convert=numeric_convert,
            use_defaults=use_defaults)
