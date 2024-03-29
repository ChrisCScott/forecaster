""" A package with various self-contained methods and classes.

These are used throughout the application and provide ways to:
represent series of events (e.g. transactions) at various times,
modelling inflation, and handling support for high-precision numerical
types.
"""

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'timing', 'inflation', 'precision']

from forecaster.utility import timing, precision, inflation
from forecaster.utility.timing import (
    FREQUENCY_MAPPING, WHEN_DEFAULT,
    when_conv, frequency_conv,
    Timing, transactions_from_timing,
    add_transactions, subtract_transactions)
from forecaster.utility.inflation import (
    nearest_year, extend_inflation_adjusted, build_inflation_adjust)
from forecaster.utility.precision import (
    EPSILON, HighPrecisionOptional, HighPrecisionOptionalProperty,
    HighPrecisionOptionalPropertyCached)
