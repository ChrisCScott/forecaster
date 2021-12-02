""" A module providing Canada-specific default values. """

from forecaster.settings import Settings, Attr

FILENAME_DEFAULT = 'canada.settings.json'

class SettingsCanada(Settings):
    """ Container for Canada-specific settings.

    See `Settings` for documation on the use of this class, including
    its arguments.

    Objects of this class provide the same attributes as `Settings`,
    with the addition of the attributes listed below.

    Attributes:
        saving_weights (dict[str, float]): Defaults for this attribute
            are overridden to
            `{'RRSP': 2, 'TFSA': 1, 'TaxableAccount': 3}`.
        withdrawal_weights (dict[str, float]): Defaults for this attribute
            are overridden to
            `{'RRSP': 1, 'TFSA': 2, 'SavingsAccount': 3}`.
        tax_province (str): A default value for building `TaxCanada`
            objects. Defaults to "BC".
        resp_child_other_income (float): A default value for building
            `TaxCanada` objects. Defaults to 0.
        resp_start_age (int): A default value for building `TaxCanada`
            objects. Defaults to 18.
        resp_withdrawal_years (int): A default value for building
            `TaxCanada` objects. Defaults to 4.
        cpp_person1_init_tape (float): A default value for building
            `CPP` objects for Person1. Defaults to 0.
        cpp_person1_init_drop_periods (int): A default value for building
            `CPP` objects for Person1. Defaults to 0.
        cpp_person1_init_drop_tape (float): A default value for building
            `CPP` objects for Person1. Defaults to 0.
        cpp_person2_init_tape (float): A default value for building
            `CPP` objects for Person2. Defaults to 0.
        cpp_person2_init_drop_periods (int): A default value for building
            `CPP` objects for Person2. Defaults to 0.
        cpp_person2_init_drop_tape (float): A default value for building
            `CPP` objects for Person2. Defaults to 0.
    """

    # Override transaction strategy weights for Canadian accounts.
    saving_weights = Attr({
        'RRSP': 2,
        'TFSA': 1,
        'TaxableAccount': 3})
    withdrawal_weights = Attr({
        'RRSP': 1,
        'TFSA': 2,
        'SavingsAccount': 3})

    # TaxCanada defaults
    tax_province = Attr("BC")

    # RESP defaults
    resp_child_other_income = Attr(0)
    resp_start_age = Attr(18)
    resp_withdrawal_years = Attr(4)

    # CPP defaults
    cpp_person1_init_tape = Attr(0)
    cpp_person1_init_drop_periods = Attr(0)
    cpp_person1_init_drop_tape = Attr(0)
    cpp_person2_init_tape = Attr(0)
    cpp_person2_init_drop_periods = Attr(0)
    cpp_person2_init_drop_tape = Attr(0)

    def __init__(self, filename=None, **kwargs):
        # Use the correct filename and default settings for Canada:
        if filename is None:
            filename = FILENAME_DEFAULT
        super().__init__(filename=filename, **kwargs)
