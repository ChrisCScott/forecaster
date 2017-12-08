""" A module providing Canada-specific default values. """

from forecaster.settings import Settings as SuperSettings


class Settings(SuperSettings):
    """ Container for Canada-specific variables. """

    # We use triple-quoted strings as comments to group sets of related
    # settings. It's nice to have a format for heading-style comments
    # that's distinct from #-prefixed comments (which we also use.)
    # pylint: disable=pointless-string-statement

    ''' Override transaction strategy weights for Canadian accounts. '''
    transaction_in_weights = {
        'RRSP': 1, 'TFSA': 2, 'TaxableAccount': 3
        }
    transaction_out_weights = {
        'RRSP': 1, 'TFSA': 2, 'SavingsAccount': 3
        }

    ''' RESP defaults '''
    RESPChildOtherIncome = 0
    RESPStartAge = 18
    RESPYearsInSchool = 4

    ''' CPP defaults '''
    CPPPerson1InitialYearTAPE = 0
    CPPPerson1InitialYearDroppablePeriods = 0
    CPPPerson1InitialYearDroppableTAPE = 0
    CPPPerson2InitialYearTAPE = 0
    CPPPerson2InitialYearDroppablePeriods = 0
    CPPPerson2InitialYearDroppableTAPE = 0
