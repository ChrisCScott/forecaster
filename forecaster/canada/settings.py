""" A module providing Canada-specific default values. """

from forecaster.settings import Settings, DEFAULTS

FILENAME_DEFAULT = 'canada.settings.json'

# Canadian defaults are the same as in `Settings`, except for a few
# overridden values and some Canada-specific values:
DEFAULTS_CANADA = dict(DEFAULTS).update({

    # Override transaction strategy weights for Canadian accounts.
    'saving_weights': {
        'RRSP': 2,
        'TFSA': 1,
        'TaxableAccount': 3},
    'withdrawal_weights': {
        'RRSP': 1,
        'TFSA': 2,
        'SavingsAccount': 3},

    # TaxCanada defaults
    'tax_province': "BC",

    # RESP defaults
    'resp_child_other_income': 0,
    'resp_start_age': 18,
    'resp_withdrawal_years': 4,

    # CPP defaults
    'cpp_person1_init_tape': 0,
    'cpp_person1_init_drop_periods': 0,
    'cpp_person1_init_drop_tape': 0,
    'cpp_person2_init_tape': 0,
    'cpp_person2_init_drop_periods': 0,
    'cpp_person2_init_drop_tape': 0,
})

class SettingsCanada(Settings):
    """ Container for Canada-specific variables. """

    def __init__(self, filename=None, defaults=None, **kwargs):
        # Use the correct filename and default settings for Canada:
        if filename is None:
            filename = FILENAME_DEFAULT
        if defaults is None:
            defaults = DEFAULTS_CANADA
        super().__init__(filename=filename, defaults=defaults, **kwargs)
