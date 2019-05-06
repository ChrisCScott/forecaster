""" Utility methods for DebtPaymentStrategy. """

# This module is split off from debt_payment_strategy to allow for
# TransactionStrategy to import the below methods:

# Expose the logic for turning iterables of debts into priority trees
# here so that, if client code wants, it can build a subtree for debts
# and insert it into a larger tree for handling all contributions
# to accounts (i.e. without invoking DebtPaymentStrategy at all.)

def avalanche_priority(debts):
    """ A priority tree of debts according to the avalanche strategy.

    Under the avalanche strategy, accounts with the highest rates are
    repaid first, regardless of balance size.

    This uses the priority tree pattern of `TransactionTraversal`; see
    that class for more information.

    Returns:
        list[Debt]: An ordered list of Debts.
    """
    return sorted(
        debts, key=lambda account: account.rate, reverse=True)

def snowball_priority(debts):
    """ A priority tree of debts according to the snowball strategy.

    Under the avalanche strategy, accounts with the lowest balances are
    repaid first, regardless of their rates.

    This uses the priority tree pattern of `TransactionTraversal`; see
    that class for more information.

    Returns:
        list[Debt]: An ordered list of Debts.
    """
    return sorted(
        debts, key=lambda account: abs(account.balance), reverse=False)

# Make it easy for client code to find the keys for the available
# strategies (and then use them with DebtPaymentStrategy or to look
# up the appropriate priority-generating method):
AVALANCHE_KEY = "Avalanche"
SNOWBALL_KEY = "Snowball"

PRIORITY_METHODS = {
    AVALANCHE_KEY: avalanche_priority,
    SNOWBALL_KEY: snowball_priority}
