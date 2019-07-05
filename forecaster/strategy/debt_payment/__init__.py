""" A module for providing strategies for debt payments. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'base', 'util']

from forecaster.strategy.debt_payment.base import DebtPaymentStrategy
from forecaster.strategy.debt_payment.util import (
    avalanche_priority, snowball_priority,
    AVALANCHE_KEY, SNOWBALL_KEY, PRIORITY_METHODS)
