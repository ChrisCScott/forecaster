""" Unit tests for `Forecaster`. """

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
from forecaster import Forecaster
from test_helper import *


class TestForecaster(unittest.TestCase):
    """ Tests Forecaster. """

    def setUp(self):
        """ Builds default strategies, persons, etc. """
        self.initial_year = Settings.initial_year
        self.scenario = Scenario(
            inflation=Settings.inflation,
            stock_return=Settings.stock_return,
            bond_return=Settings.bond_return,
            other_return=Settings.other_return,
            management_fees=Settings.management_fees,
            initial_year=Settings.initial_year,
            num_years=Settings.num_years
        )
        self.contribution_strategy = ContributionStrategy(
            strategy=Settings.contribution_strategy,
            base_amount=Settings.contribution_base_amount,
            rate=Settings.contribution_rate,
            refund_reinvestment_rate=Settings.contribution_refund_reinvestment_rate,  # noqa
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.withdrawal_strategy = WithdrawalStrategy(
            strategy=Settings.withdrawal_strategy,
            base_amount=Settings.withdrawal_base_amount,
            rate=Settings.withdrawal_rate,
            timing=Settings.transaction_out_timing,
            income_adjusted=Settings.withdrawal_income_adjusted,
            inflation_adjust=self.scenario.inflation_adjust
        )
        self.transaction_in_strategy = TransactionStrategy(
            strategy=Settings.transaction_in_strategy,
            weights=Settings.transaction_in_weights,
            timing=Settings.transaction_in_timing
        )
        self.transaction_out_strategy = TransactionStrategy(
            strategy=Settings.transaction_out_strategy,
            weights=Settings.transaction_out_weights,
            timing=Settings.transaction_out_timing
        )

        # We use different target values for different strategies.
        if (
            Settings.allocation_strategy ==
            AllocationStrategy._strategy_n_minus_age.strategy_key
        ):
            target = Settings.allocation_constant_strategy_target
        elif (
            Settings.allocation_strategy ==
            AllocationStrategy._strategy_transition_to_constant.strategy_key
        ):
            target = Settings.allocation_transition_strategy_target
        self.allocation_strategy = AllocationStrategy(
            strategy=Settings.allocation_strategy,
            min_equity=Settings.allocation_min_equity,
            max_equity=Settings.allocation_max_equity,
            target=target,
            standard_retirement_age=Settings.allocation_standard_retirement_age,  # noqa
            risk_transition_period=Settings.allocation_risk_transition_period,
            adjust_for_retirement_plan=Settings.allocation_adjust_for_retirement_plan,  # noqa
            scenario=self.scenario
        )
        self.debt_payment_strategy = DebtPaymentStrategy(
            strategy=Settings.debt_payment_strategy,
            timing=Settings.debt_payment_timing
        )
        self.person1 = Person(
            name=Settings.person1_name,
            birth_date=Settings.person1_birth_date,
            retirement_date=Settings.person1_retirement_date,
            gross_income=Settings.person1_gross_income,
            raise_rate=Settings.person1_raise_rate,
            spouse=None,
            tax_treatment=None,
            allocation_strategy=self.allocation_strategy,
            initial_year=self.initial_year
        )
        if Settings.person2_name is None:
            self.person2 = None
        else:
            self.person2 = Person(
                name=Settings.person2_name,
                birth_date=Settings.person2_birth_date,
                retirement_date=Settings.person2_retirement_date,
                gross_income=Settings.person2_gross_income,
                raise_rate=Settings.person2_raise_rate,
                spouse=self.person1,
                tax_treatment=None,
                allocation_strategy=self.allocation_strategy,
                initial_year=self.initial_year
            )

    def test_init(self):
        """ Tests Forecaster.__init__ """
        # Test default init:
        forecaster = Forecaster()
        self.assertEqual(forecaster.person1, self.person1)
        self.assertEqual(forecaster.person2, self.person2)
        self.assertEqual(forecaster.people, {self.person1, self.person2})
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertEqual(
            forecaster.contribution_strategy, self.contribution_strategy)
        self.assertEqual(
            forecaster.withdrawal_strategy, self.withdrawal_strategy)
        self.assertEqual(
            forecaster.transaction_in_strategy, self.transaction_in_strategy)
        self.assertEqual(
            forecaster.transaction_out_strategy, self.transaction_out_strategy)
        self.assertEqual(
            forecaster.allocation_strategy, self.allocation_strategy)
        self.assertEqual(
            forecaster.debt_payment_strategy, self.debt_payment_strategy)
        self.assertEqual(forecaster.settings, Settings)
        self.assertEqual(forecaster.initial_year, Settings.initial_year)

        # Test explicit init
        settings = Settings()
        settings.person1_name = 'Test Name'
        initial_year = 2000
        forecaster = Forecaster(settings=settings, initial_year=initial_year)
        self.assertIsNone(forecaster.person1)
        self.assertIsNone(forecaster.person2)
        self.assertEqual(forecaster.people, set())
        self.assertEqual(forecaster.assets, set())
        self.assertEqual(forecaster.debts, set())
        self.assertIsNone(forecaster.contribution_strategy)
        self.assertIsNone(forecaster.withdrawal_strategy)
        self.assertIsNone(forecaster.transaction_in_strategy)
        self.assertIsNone(forecaster.transaction_out_strategy)
        self.assertIsNone(forecaster.allocation_strategy)
        self.assertIsNone(forecaster.debt_payment_strategy)
        self.assertEqual(forecaster.settings, settings)
        self.assertEqual(forecaster.settings.person1_name, 'Test Name')
        self.assertEqual(forecaster.initial_year, initial_year)

    def test_add_person(self):
        """ TODO """
        pass

    def test_add_account(self):
        """ TODO """
        pass

    def test_add_debt(self):
        """ TODO """
        pass

if __name__ == '__main__':
    unittest.main()
