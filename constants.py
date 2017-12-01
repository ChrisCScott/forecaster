""" Constant values used by the application to describe, e.g., tax
brackets, research data describing safe withdrawal rates, contribution
room accrual rates, and other non-user-modifiable constants. """

from decimal import Decimal


class Constants(object):
    """ Container for constants used by application logic.

    This class is not passed as an argument to any methods and is
    invoked directly at the class level by client code.
    """

    """ RESP constants """
    RESPContributionRoom = Decimal('50000')
    RESPCESGAnnualAccrual = Decimal('500')
    RESPCESGAnnualAccrualMax = Decimal('1000')
    RESPCESGMatchingRate = Decimal('0.2')
    RESPCESGLifetimeMax = Decimal('7200')
    RESPBCSTEGAmount = Decimal('1200')

    """ RRSP constants """
    RRSPContributionRoomAccrualRate = Decimal('0.18')
    RRSPContributionRoomAccrualMax = {
        2017: Decimal('25750.55')
    }
    RRSPWithholdingTaxRate = {
        Decimal(0): Decimal('0.1'),
        Decimal(5000): Decimal('0.2'),
        Decimal(15000): Decimal('0.3')
    }
    RRSPRRIFConversionAge = 71
    RRSPRRIFMinWithdrawal = {
        71: Decimal('0.0528'),
        72: Decimal('0.0540'),
        73: Decimal('0.0553'),
        74: Decimal('0.0567'),
        75: Decimal('0.0582'),
        76: Decimal('0.0598'),
        77: Decimal('0.0617'),
        78: Decimal('0.0636'),
        79: Decimal('0.0658'),
        80: Decimal('0.0682'),
        81: Decimal('0.0708'),
        82: Decimal('0.0738'),
        83: Decimal('0.0771'),
        84: Decimal('0.0808'),
        85: Decimal('0.0851'),
        86: Decimal('0.0899'),
        87: Decimal('0.0955'),
        88: Decimal('0.1021'),
        89: Decimal('0.1099'),
        90: Decimal('0.1192'),
        91: Decimal('0.1306'),
        92: Decimal('0.1449'),
        93: Decimal('0.1634'),
        94: Decimal('0.1879'),
        95: Decimal('0.2000')
    }

    """ TFSA constants """
    # Historical annual accrual amounts
    TFSAAnnualAccrual = {
        2009: Decimal('5000'),
        2010: Decimal('5000'),
        2011: Decimal('5000'),
        2012: Decimal('5000'),
        2013: Decimal('5500'),
        2014: Decimal('5500'),
        2015: Decimal('10000'),
        2016: Decimal('5500'),
        2017: Decimal('5500'),
    }
    TFSAAccrualEligibilityAge = 18
    TFSAInflationRoundingFactor = 500

    """ CPP constants """
    CPPMaxMonthlyBenefit = {2017: Decimal('1114.17')}
    CPPYMPE = {2017: Decimal('55300')}
    CPPDropoutRate = Decimal('0.17')
    CPPBenchmarkStartAge = 65
    CPPEarliestStartAge = 60
    CPPLatestStartAge = 70
    CPPAgeAdjustmentFactor = Decimal('0.006')

    """ OAS constants """
    OASMaxMonthlyBenefit = {2017: Decimal('585.49')}
    OASStartAge = 65
    OASRecoveryThreshold = {2017: Decimal('72809')}
    OASRecoveryTaxRate = Decimal('0.15')

    # NOTE: This structure assumes that federal and provincial tax
    # logic will be essentially the same (which is currently true).
    # If we move to implementing various province-specific classes,
    # consider splitting these apart for readability.
    """ Tax constants """
    TaxBasicPersonalDeduction = {
        'Federal': {2017: Decimal('11635')},
        'BC': {2017: Decimal('10208')}
    }
    TaxPensionCredit = {
        'Federal': {2017: Decimal('2000')},
        'BC': {2017: Decimal('1000')}
    }
    TaxCreditRate = {
        'Federal': {2017: Decimal('0.15')},
        'BC': {2017: Decimal('0.0506')}
    }
    TaxBrackets = {
        'Federal': {
            2017: {
                Decimal(0): Decimal('0.15'),
                Decimal('45961.23'): Decimal('0.205'),
                Decimal('91921.45'): Decimal('0.26'),
                Decimal('142493.82'): Decimal('0.29'),
                Decimal('203000.00'): Decimal('0.33')
            }
        },
        'BC': {
            2017: {
                Decimal(0): Decimal('0.15'),
                Decimal('45961.23'): Decimal('0.205'),
                Decimal('91921.45'): Decimal('0.26'),
                Decimal('142493.82'): Decimal('0.29'),
                Decimal('203000.00'): Decimal('0.33')
            }
        }
    }
