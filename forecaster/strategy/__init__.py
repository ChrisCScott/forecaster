""" A package for providing user-definable behaviour ("strategies"). """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'allocation', 'gross_transaction', 'account_transaction', 'debt_payment'
]

from forecaster.strategy.allocation import AllocationStrategy
from forecaster.strategy.gross_transaction import (
    LivingExpensesStrategy, LivingExpensesStrategySchedule)
from forecaster.strategy.account_transaction import AccountTransactionStrategy
from forecaster.strategy.transaction import TransactionStrategy
from forecaster.strategy.debt_payment import DebtPaymentStrategy
