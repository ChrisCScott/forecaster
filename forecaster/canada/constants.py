""" Constant values used by the application to describe, e.g., tax
brackets, research data describing safe withdrawal rates, contribution
room accrual rates, and other non-user-modifiable constants. """

from decimal import Decimal

# We use triple-quoted strings as comments to group sets of related
# settings. It's nice to have a format for heading-style comments
# that's distinct from #-prefixed comments (which we also use.)
# pylint: disable=pointless-string-statement

# TODO: Revise these values to be dicts of {year: value} pairs?
# This is what is used in Settings.

""" RESP constants """
RESP_CONTRIBUTION_ROOM = Decimal('50000')
RESP_CESG_ANNUAL_ACCRUAL = Decimal('500')
RESP_CESG_ANNUAL_ACCRUAL_MAX = Decimal('1000')
RESP_CESG_MATCHING_RATE = Decimal('0.2')
RESP_CESG_LIFETIME_MAX = Decimal('7200')
RESP_BCSTEG_AMOUNT = Decimal('1200')

""" RRSP constants """
RRSP_ACCRUAL_RATE = Decimal('0.18')
RRSP_ACCRUAL_MAX = {
    2017: Decimal('25750.55')
}
RRSP_WITHHOLDING_TAX_RATE = {
    2017: {
        Decimal(0): Decimal('0.1'),
        Decimal(5000): Decimal('0.2'),
        Decimal(15000): Decimal('0.3')
    }
}
RRSP_RRIF_CONVERSION_AGE = 71
RRSP_RRIF_WITHDRAWAL_MIN = {
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
TFSA_ANNUAL_ACCRUAL = {
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
TFSA_ELIGIBILITY_AGE = 18
TFSA_ACCRUAL_ROUNDING_FACTOR = 500

""" CPP constants """
CPP_MAX_MONTHLY_BENEFIT = {2017: Decimal('1114.17')}
CPP_YMPE = {2017: Decimal('55300')}
CPP_DROPOUT_RATE = Decimal('0.17')
CPP_START_AGE_STANDARD = 65
CPP_START_AGE_EARLIEST = 60
CPP_START_AGE_LATEST = 70
CPP_AGE_ADJUSTMENT_FACTOR = Decimal('0.006')

""" OAS constants """
OAS_MAX_MONTHLY_BENEFIT = {2017: Decimal('585.49')}
OAS_START_AGE = 65
OAS_RECOVERY_THRESHOLD = {2017: Decimal('72809')}
OAS_RECOVERY_TAX_RATE = Decimal('0.15')

# NOTE: This structure assumes that federal and provincial tax
# logic will be essentially the same (which is currently true).
# If we move to implementing various province-specific classes,
# consider splitting these apart for readability.
""" Tax constants """
TAX_PERSONAL_DEDUCTION = {
    'Federal': {2017: Decimal('11635')},
    'BC': {2017: Decimal('10208')}
}
TAX_PENSION_CREDIT = {
    'Federal': {2017: Decimal('2000')},
    'BC': {2017: Decimal('1000')}
}
TAX_CREDIT_RATE = {
    'Federal': {2017: Decimal('0.15')},
    'BC': {2017: Decimal('0.0506')}
}
TAX_BRACKETS = {
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

TAX_SPOUSAL_AMOUNT = {
    'Federal': {2017: Decimal(11635)},
    'BC': {2017: Decimal(9614)}
}
