""" Constant values used by the application to describe, e.g., tax
brackets, research data describing safe withdrawal rates, contribution
room accrual rates, and other non-user-modifiable constants. """

from forecaster.value_reader import ValueReader, ValueReaderAttribute as Attr

FILENAME_DEFAULT = 'canada.constants.json'

class ConstantsCanada(ValueReader):
    """ Container for Canada-specific constants.

    This class is analogous to `SettingsCanada`, except that it does
    not store values that are determined by a user to customize
    assumptions, scenarios, strategies, or application behaviour.
    Rather, it provides values to define the behaviour of Canadian
    accounts, tax rules, etc. These generally are not user-defined
    and are of interest principally to developers preparing updated
    versions of the software.

    All constants are exposed as attributes of `ConstantsCanada`
    objects. For example, `ConstantsCanada().RESP_CONTRIBUTION_ROOM`
    will return the value of the `'RESP_CONTRIBUTION_ROOM'` key in
    `data/canada.constants.json`. This is partially syntactic sugar for
    convenience and to help with Intellisense (e.g.
    `ConstantsCanada().RESP_CONTRIBUTION_ROOM` is equivalent to
    `ConstantsCanada().values['RESP_CONTRIBUTION_ROOM']).

    Each constant has an appropriate default value circa 2017. (The JSON
    file may be more up-to-date.) Some potential uses for these are
    (a) type-checking (the defaults use the structure expected by client
    code), and (b) default values for when a value isn't read in from
    file. (Defaults are only used if `use_defaults` is True.)

    Although a filename can be specified for loading settings, by
    default this class reads from
    `forecaster/data/canada.constants.json`. All relative paths are
    resolved from `forecaster/data`, so if you want to open a file
    elsewhere use an absolute path!

    This class takes all of the same args as `ValueReader`.

    Attributes are generally specific to a class (e.g. `RESP_*`
    attributes are used by `RESP`.) These can be inspected via
    Intellisense and aren't listed here.
    """

    # TODO: Revise these values to be dicts of {year: value} pairs?
    # This is what is used in Settings.

    # RESP constants
    RESP_CONTRIBUTION_ROOM = Attr(50000)
    RESP_CESG_ANNUAL_ACCRUAL = Attr(500)
    RESP_CESG_ANNUAL_ACCRUAL_MAX = Attr(1000)
    RESP_CESG_MATCHING_RATE = Attr(0.2)
    RESP_CESG_LIFETIME_MAX = Attr(7200)
    RESP_BCSTEG_AMOUNT = Attr(1200)

    # RRSP constants
    RRSP_ACCRUAL_RATE = Attr(0.18)
    RRSP_ACCRUAL_MAX = Attr({
        2017: 25750.55,
    })
    RRSP_WITHHOLDING_TAX_RATE = Attr({
        2017: {
            0: 0.1,
            5000: 0.2,
            15000: 0.3,
        }
    })
    RRSP_RRIF_CONVERSION_AGE = Attr(71)
    RRSP_RRIF_WITHDRAWAL_MIN = Attr({
        71: 0.0528,
        72: 0.0540,
        73: 0.0553,
        74: 0.0567,
        75: 0.0582,
        76: 0.0598,
        77: 0.0617,
        78: 0.0636,
        79: 0.0658,
        80: 0.0682,
        81: 0.0708,
        82: 0.0738,
        83: 0.0771,
        84: 0.0808,
        85: 0.0851,
        86: 0.0899,
        87: 0.0955,
        88: 0.1021,
        89: 0.1099,
        90: 0.1192,
        91: 0.1306,
        92: 0.1449,
        93: 0.1634,
        94: 0.1879,
        95: 0.2000
    })

    # TFSA constants
    # Historical annual accrual amounts
    TFSA_ANNUAL_ACCRUAL = Attr({
        2009: 5000,
        2010: 5000,
        2011: 5000,
        2012: 5000,
        2013: 5500,
        2014: 5500,
        2015: 10000,
        2016: 5500,
        2017: 5500
    })
    TFSA_ELIGIBILITY_AGE = Attr(18)
    TFSA_ACCRUAL_ROUNDING_FACTOR = Attr(500)

    # CPP constants
    CPP_MAX_MONTHLY_BENEFIT = Attr({2017: 1114.17})
    CPP_YMPE = Attr({2017: 55300})
    CPP_DROPOUT_RATE = Attr(0.17)
    CPP_START_AGE_STANDARD = Attr(65)
    CPP_START_AGE_EARLIEST = Attr(60)
    CPP_START_AGE_LATEST = Attr(70)
    CPP_AGE_ADJUSTMENT_FACTOR = Attr(0.006)

    # OAS constants
    OAS_MAX_MONTHLY_BENEFIT = Attr({2017: 585.49})
    OAS_START_AGE = Attr(65)
    OAS_RECOVERY_THRESHOLD = Attr({2017: 72809})
    OAS_RECOVERY_TAX_RATE = Attr(0.15)

    # Tax constants
    # NOTE: This structure assumes that federal and provincial tax
    # logic will be essentially the same (which is currently true).
    # If we move to implementing various province-specific classes
    # consider splitting these apart for readability.
    TAX_PERSONAL_DEDUCTION = Attr({
        'Federal': {2017: 11635},
        'BC': {2017: 10208}
    })
    TAX_PENSION_CREDIT = Attr({
        'Federal': {2017: 2000},
        'BC': {2017: 1000}
    })
    TAX_CREDIT_RATE = Attr({
        'Federal': {2017: 0.15},
        'BC': {2017: 0.0506}
    })
    TAX_BRACKETS = Attr({
        'Federal': {
            2017: {
                0: 0.15,
                45961.23: 0.205,
                91921.45: 0.26,
                142493.82: 0.29,
                203000.00: 0.33
            }
        },
        'BC': {
            2017: {
                0: 0.15,
                45961.23: 0.205,
                91921.45: 0.26,
                142493.82: 0.29,
                203000.00: 0.33
            }
        }
    })

    TAX_SPOUSAL_AMOUNT = Attr({
        'Federal': {2017: 11635},
        'BC': {2017: 9614}
    })

    # Deadline to file is April 30th (120/365 ~= Attr(0.328), and the refund)
    # is paid shortly thereafter. Truncate this to 0.3 for simplicity.
    TAX_REFUND_TIMING = Attr(0.3,)
    # Deadline to pay any amounts owing is April 30th (120/365).
    # Truncate this to 0.3 for simplicity.
    TAX_PAYMENT_TIMING = Attr(0.3)

    def __init__(self, filename=None, **kwargs):
        # Use the correct filename for Canada:
        if filename is None:
            filename = FILENAME_DEFAULT
        super().__init__(filename=filename, **kwargs)
