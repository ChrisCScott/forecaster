""" A package for providing user-definable behaviour ("strategies"). """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'allocation', 'gross_transaction', 'transaction', 'debt_payment']

from forecaster.strategy.allocation import AllocationStrategy
from forecaster.strategy.gross_transaction import (
    LivingExpensesStrategy, LivingExpensesStrategySchedule)
from forecaster.strategy.debt_payment import (
    DebtPaymentStrategy, avalanche_priority, snowball_priority,
    PRIORITY_METHODS, AVALANCHE_KEY, SNOWBALL_KEY)
from forecaster.strategy.transaction import (
    TransactionStrategy, TransactionTraversal, TransactionNode,
    LimitTuple, reduce_node)
