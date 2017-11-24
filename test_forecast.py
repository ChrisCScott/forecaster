""" Unit tests for `Forecast`. """

import unittest
import decimal
from decimal import Decimal
from collections import defaultdict
from settings import Settings
from tax import Tax
from ledger import Person, Account, Debt
from scenario import Scenario
from strategy import *
from forecast import Forecast
from test_helper import *


class TestForecast(unittest.TestCase):
    """ Tests Forecast. """

    def test_basic(self):
        """ Test with one account, one debt, and constant Scenario.

        For simplicity, this Scenario will extend over 4 years: an
        initial year, a second year, a retirement year, and a final year
        """
        initial_year = 2000
        scenario = Scenario(
            # At 100% inflation, adjustments will be [1, 2, 4, 8]
            inflation=Decimal(1),
            stock_return=Decimal(1),  # 100% growth in stocks
            bond_return=Decimal(0.5),  # 50% growth in bonds
            other_return=0,  # No growth in other assets
            management_fees=Decimal(0),  # TODO: Refactor this attribute
            person1_raise_rate=Decimal(0.5),  # TODO: Refactor this attr
            initial_year=initial_year
        )
        tax = Tax(
            {
                initial_year: {
                    # 0% tax from $0 to $50,000
                    Decimal(0): Decimal(0),
                    # 50% bracket on income over $50,000
                    Decimal(50000): Decimal('0.5')
                }
            },
            personal_deduction={initial_year: Decimal(0)},
            credit_rate={initial_year: 0.5},
            inflation_adjust=scenario.inflation_adjust
        )
        person = Person(
            'Test', 1980,
            retirement_date=2002,
            gross_income=Money(100000),
            raise_rate=scenario.person1_raise_rate,
            tax_treatment=tax,
            initial_year=initial_year
        )
        account = Account(
            person, balance=1000, rate=1, nper=1, initial_year=initial_year
        )
        debt = Debt(
            person, balance=-1000, rate=1, minimum_payment=Money(100),
            reduction_rate=1, accelerate_payment=True
        )
        contribution_strategy = ContributionStrategy(
            strategy=ContributionStrategy._strategy_constant_contribution,
            base_amount=Money('50000'),
            rate=Decimal(0),
            refund_reinvestment_rate=1,
            inflation_adjusted=True
        )
        withdrawal_strategy = WithdrawalStrategy(
            strategy=WithdrawalStrategy._strategy_constant_withdrawal,
            rate=Money('50000'),
            min_living_standard=Money(0),
            timing='end',
            benefit_adjusted=False,
            inflation_adjusted=True
        )
        contribution_transaction_strategy = TransactionInStrategy(
            strategy=TransactionInStrategy._strategy_ordered,
            weights={'Account': 1},
            timing='end'
        )
        withdrawal_transaction_strategy = TransactionOutStrategy(
            strategy=TransactionInStrategy._strategy_ordered,
            weights={'Account': 1},
            timing='end'
        )
        # Constant 50-50 split between stocks and bonds:
        allocation_strategy = AllocationStrategy(
            strategy=AllocationStrategy._strategy_n_minus_age,
            min_equity=Decimal(0.5),
            max_equity=Decimal(0.5),
            target=Decimal(0.5),
            standard_retirement_age=65,
            risk_transition_period=20,
            adjust_for_retirement_plan=True
        )
        debt_payment_strategy = DebtPaymentStrategy(
            strategy=DebtPaymentStrategy._strategy_avalanche,
            timing='end'
        )

        forecast = Forecast(
            {person}, {account}, {debt}, scenario, contribution_strategy,
            withdrawal_strategy, contribution_transaction_strategy,
            withdrawal_transaction_strategy, allocation_strategy,
            debt_payment_strategy, tax
        )

if __name__ == '__main__':
    unittest.main()
