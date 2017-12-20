""" A module providing Canada-specific default values. """

from forecaster.settings import Settings


class SettingsCanada(Settings):
    """ Container for Canada-specific variables. """

    # We use triple-quoted strings as comments to group sets of related
    # settings. It's nice to have a format for heading-style comments
    # that's distinct from #-prefixed comments (which we also use.)
    # pylint: disable=pointless-string-statement
    # Settings is really just a data container right now, but the plan
    # is to subclass from a proper class with file-reading logic.
    # pylint: disable=too-few-public-methods

    """ Override transaction strategy weights for Canadian accounts. """
    transaction_in_weights = {
        'RRSP': 1, 'TFSA': 2, 'TaxableAccount': 3
    }
    transaction_out_weights = {
        'RRSP': 1, 'TFSA': 2, 'SavingsAccount': 3
    }

    """ RESP defaults """
    resp_child_other_income = 0
    resp_start_age = 18
    resp_withdrawal_years = 4

    """ CPP defaults """
    cpp_person1_init_tape = 0
    cpp_person1_init_drop_periods = 0
    cpp_person1_init_drop_tape = 0
    cpp_person2_init_tape = 0
    cpp_person2_init_drop_periods = 0
    cpp_person2_init_drop_tape = 0
