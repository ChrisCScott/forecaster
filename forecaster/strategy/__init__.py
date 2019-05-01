""" A package for providing user-definable behaviour ("strategies"). """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'allocation', 'gross_transaction', 'transaction', 'debt_payment', 'util']

from forecaster.strategy.allocation import AllocationStrategy
from forecaster.strategy.gross_transaction import (
    LivingExpensesStrategy, LivingExpensesStrategySchedule)
from forecaster.strategy.debt_payment import (
    DebtPaymentStrategy, avalanche_priority, snowball_priority)
from forecaster.strategy.transaction import TransactionStrategy
from forecaster.strategy.util import (
    LimitTuple, transaction_default_methods, group_default_methods,
    TransactionNode, reduce_node)
