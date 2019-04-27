""" Helper classes and methods for Account. """

from collections import namedtuple

FIELDS = ['min_inflow', 'max_inflow', 'min_outflow', 'max_outflow']
LimitTuple = namedtuple(
    'LimitTuple', FIELDS, defaults=(None,) * len(FIELDS))
LimitTuple.__doc__ = (
    "A data container holding different values for min/max inflow/outfow")

# Give an easy way for refactors to update references to LimitTuples:
LIMIT_TUPLE_FIELDS = LimitTuple(*FIELDS)
