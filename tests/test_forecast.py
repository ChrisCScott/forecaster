""" Unit tests for `Forecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Money, Person, Account, Debt, Scenario, ContributionStrategy,
    WithdrawalStrategy, TransactionStrategy, AllocationStrategy,
    DebtPaymentStrategy, Tax, Forecast, Forecaster, Settings)
from tests.test_helper import type_check


class TestForecast(unittest.TestCase):
    """ Tests Forecast. """

    def setUp(self):
        """ Build a forecaster for 2-year forecasts with 100% inflation.

        This is just for convenience, since building a forecast manually
        is quite laborious.
        """
        self.settings = Settings()
        self.settings.num_years = 2
        self.settings.inflation = 1
        self.forecaster = Forecaster(settings=self.settings)

    def test_manual_forecast(self):
        """ Test with one account, one debt, and constant Scenario.

        For simplicity, this Scenario extends over 4 years: an initial
        year, a second year, a retirement year, and a final year.
        There is no inflation in this example.
        """
        initial_year = 2000
        scenario = Scenario(
            initial_year=initial_year,
            num_years=4,
            inflation=Decimal(0),  # No inflation
            stock_return=Decimal(2),  # 200% growth in stocks
            bond_return=Decimal(0),  # 0% growth in bonds
            other_return=0,  # No growth in other assets
            management_fees=Decimal(0),  # TODO: Refactor this attribute
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
        contribution_strategy = ContributionStrategy(
            strategy=ContributionStrategy.strategy_const_contribution,
            base_amount=Money('50000'),
            rate=Decimal(0),
            refund_reinvestment_rate=1,
            inflation_adjust=scenario.inflation_adjust
        )
        withdrawal_strategy = WithdrawalStrategy(
            strategy=WithdrawalStrategy.strategy_const_withdrawal,
            base_amount=Money('50000'),
            timing='end',
            income_adjusted=False,
            inflation_adjust=scenario.inflation_adjust
        )
        contribution_trans_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={'Account': 1},
            timing='end'
        )
        withdrawal_trans_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={'Account': 1},
            timing='end'
        )
        # Constant 50-50 split between stocks and bonds
        # (100% growth of 50-50 portfolio):
        allocation_strategy = AllocationStrategy(
            strategy=AllocationStrategy.strategy_n_minus_age,
            min_equity=Decimal(0.5),
            max_equity=Decimal(0.5),
            target=Decimal(0.5),
            standard_retirement_age=65,
            risk_transition_period=20,
            adjust_for_retirement_plan=True
        )
        debt_payment_strategy = DebtPaymentStrategy(
            strategy=DebtPaymentStrategy.strategy_avalanche,
            timing='end'
        )
        person = Person(
            initial_year, 'Test', 1980,
            retirement_date=2002,
            gross_income=Money(100000),
            raise_rate=Decimal(0.5),
            tax_treatment=tax
        )
        account = Account(
            person,
            balance=1000,
            # 100% growth rate (50-50 portfolio with 200% growth of
            # stocks and 0% growth of bonds)
            rate=allocation_strategy.rate_function(person, scenario),
            nper=1
        )
        debt = Debt(
            person,
            balance=-1000,
            rate=1,  # 100% interest rate
            minimum_payment=Money(100),
            reduction_rate=1,
            accelerate_payment=True
        )

        forecast = Forecast(
            {person}, {account}, {debt}, scenario, contribution_strategy,
            withdrawal_strategy, contribution_trans_strategy,
            withdrawal_trans_strategy,
            debt_payment_strategy, tax
        )

        # Calculate the expected results for the values of principal
        # importance in each year and test them here.
        # Year 1:
        year = initial_year
        # Gross income: $100,000, taxes: $25,000
        self.assertEqual(forecast.net_income[year], Money(75000))
        # Gross contribution: $50,000, debt payments: $2000 (this will
        # pay off the debt's $1000 principal and $1000 interest)
        self.assertEqual(forecast.net_contributions[year],
                         Money(48000))
        # Account initial balance: $1000
        self.assertEqual(forecast.principal[year], Money(1000))
        # Growth: 100%
        # NOTE: We should implement growth based on allocation (in this
        # case 100% for stocks, 50% for bonds, portfolio split evenly),
        # which would yield $750. No taxes/etc.
        self.assertEqual(forecast.net_return[year], Money(1000))
        # No withdrawals
        self.assertEqual(forecast.net_withdrawals[year], Money(0))
        # Taxable income: $100,000 + $1000. All income over $50,000 is
        # taxable at 50%, for a total of $25500
        self.assertEqual(forecast.total_tax_owing[year],
                         Money(25500))
        # Living standard: $100,000 - $25,500 - $50,000 = $24,500
        self.assertEqual(forecast.living_standard[year], Money(24500))

        # Year 2:
        year += 1
        # Gross income: $150,000 (50% raise), taxes: $50,000
        self.assertEqual(forecast.net_income[year], Money(100000))
        # Gross contribution: $50,000, debt payments: $0
        self.assertEqual(forecast.net_contributions[year],
                         Money(50000))
        # Account initial balance: $50000 ($48000 contribution, plus
        # $1000 initial balance and $1000 return last year)
        self.assertEqual(forecast.principal[year], Money(50000))
        # Growth: 100%
        # NOTE: We should set growth based on allocation (see above)
        self.assertEqual(forecast.net_return[year], Money(50000))
        # No withdrawals - retirement is next year
        self.assertEqual(forecast.net_withdrawals[year], Money(0))
        # Taxable income: $150,000 + $50000. All income over $50,000 is
        # taxable at 50%, for a total of $75000
        self.assertEqual(forecast.total_tax_owing[year],
                         Money(75000))
        # Living standard: $150,000 - $75000 - $50,000 = $25,000
        # TODO: Review Excel sheet; the living standard formula needs
        # to be updated so that all taxes owing aren't held against
        # it. (Any taxes paid out of accounts shouldn't be - perhaps
        # only deduct taxes withheld?)
        self.assertEqual(forecast.living_standard[year], Money(25000))

        # Year 3:
        year += 1
        # Gross income: $225,000 (50% raise), taxes: $87,500
        self.assertEqual(forecast.net_income[year], Money(137500))
        # Gross contribution: $50,000, debt payments: $0
        self.assertEqual(forecast.net_contributions[year],
                         Money(50000))
        # Account initial balance: $150000 ($50000 contribution, plus
        # $50000 initial balance and $50000 return last year)
        self.assertEqual(forecast.principal[year], Money(150000))
        # Growth: 100%
        # NOTE: We should set growth based on allocation (see above)
        self.assertEqual(forecast.net_return[year], Money(150000))
        # No withdrawals - retirement is this year, so withdrawals start
        # next year.
        self.assertEqual(forecast.net_withdrawals[year], Money(0))
        # Taxable income: $225000 + $150000. All income over $50,000 is
        # taxable at 50%, for a total of $162500
        self.assertEqual(forecast.total_tax_owing[year],
                         Money(162500))
        # Living standard: $225,000 - $162,500 - $50,000 = $12,500
        # TODO: Review Excel sheet; the living standard formula needs
        # to be updated so that all taxes owing aren't held against
        # it. (Any taxes paid out of accounts shouldn't be - perhaps
        # only deduct taxes withheld?)
        self.assertEqual(forecast.living_standard[year], Money(12500))

        # Year 4:
        year += 1
        # Gross income: $0 (retired), taxes: $0
        self.assertEqual(forecast.net_income[year], Money(0))
        # Gross contribution: $0, debt payments: $0
        self.assertEqual(forecast.net_contributions[year],
                         Money(0))
        # Account initial balance: $350000 ($50000 contribution, plus
        # $150000 initial balance and $150000 return last year)
        self.assertEqual(forecast.principal[year], Money(350000))
        # Growth: 100%
        # NOTE: We should set growth based on allocation (see above)
        self.assertEqual(forecast.net_return[year], Money(350000))
        # $50,000 withdrawal
        self.assertEqual(forecast.net_withdrawals[year], Money(50000))
        # Taxable income: $350000. All income over $50,000 is
        # taxable at 50%, for a total of $150,000
        self.assertEqual(forecast.total_tax_owing[year],
                         Money(150000))
        # Living standard: $0 + $50000 - $150000 = -$100,000
        # TODO: Review Excel sheet; the living standard formula needs
        # to be updated so that all taxes owing aren't held against
        # it. (Any taxes paid out of accounts shouldn't be - perhaps
        # only deduct taxes withheld?)
        self.assertEqual(forecast.living_standard[year], Money(-100000))

    def test_types(self):
        """ Tests types of objects in Forecast attribute dicts. """
        # Use Forecaster to build a Forecast easily:
        forecaster = Forecaster()
        forecaster.add_asset(owner=forecaster.person1)
        forecaster.add_debt(owner=forecaster.person1)
        forecast = forecaster.forecast()

        self.assertTrue(
            type_check(forecast.asset_sale, {int: Money}))
        self.assertTrue(
            type_check(forecast.carryover, {int: Money}))
        self.assertTrue(
            type_check(forecast.contribution_reductions, {int: Money}))
        self.assertTrue(
            type_check(forecast.gross_contributions, {int: Money}))
        self.assertTrue(
            type_check(forecast.gross_income, {int: Money}))
        self.assertTrue(
            type_check(forecast.gross_return, {int: Money}))
        self.assertTrue(
            type_check(forecast.gross_withdrawals, {int: Money}))
        self.assertTrue(
            type_check(forecast.living_standard, {int: Money}))
        self.assertTrue(
            type_check(forecast.net_contributions, {int: Money}))
        self.assertTrue(
            type_check(forecast.net_income, {int: Money}))
        self.assertTrue(
            type_check(forecast.net_return, {int: Money}))
        self.assertTrue(
            type_check(forecast.net_withdrawals, {int: Money}))
        self.assertTrue(
            type_check(forecast.principal, {int: Money}))
        self.assertTrue(
            type_check(forecast.reduction_from_debt, {int: Money}))
        self.assertTrue(
            type_check(forecast.reduction_from_other, {int: Money}))
        self.assertTrue(
            type_check(forecast.refund, {int: Money}))
        self.assertTrue(
            type_check(forecast.tax_withheld_on_return, {int: Money}))
        self.assertTrue(
            type_check(forecast.tax_withheld_on_withdrawals, {int: Money}))
        self.assertTrue(
            type_check(forecast.tax_withheld_on_income, {int: Money}))
        self.assertTrue(
            type_check(forecast.total_tax_owing, {int: Money}))
        self.assertTrue(
            type_check(forecast.total_tax_withheld, {int: Money}))
        self.assertTrue(
            type_check(forecast.withdrawals_for_other, {int: Money}))
        self.assertTrue(
            type_check(
                forecast.withdrawals_for_retirement, {int: Money}))

    def test_record_income(self):
        """ Test gross and net income. """
        # Set up tax so $150,000 gross results in $100,000 net
        self.forecaster.set_tax_treatment(
            tax_brackets={
                self.settings.initial_year: {0: 0, 50000: Decimal(0.5)}
            }
        )
        self.forecaster.set_person1(gross_income=Money(150000), raise_rate=1)
        forecast = self.forecaster.forecast()
        # Test the first year:
        self.assertEqual(
            forecast.gross_income[self.settings.initial_year],
            Money(150000)
        )
        self.assertEqual(
            forecast.tax_withheld_on_income[self.settings.initial_year],
            Money(50000)
        )
        self.assertEqual(
            forecast.net_income[self.settings.initial_year],
            Money(100000)
        )
        # Test the second year, taking into account the 100% inflation
        # and 100% raise:
        self.assertEqual(
            forecast.gross_income[self.settings.initial_year + 1],
            Money(300000)
        )
        self.assertEqual(
            forecast.tax_withheld_on_income[self.settings.initial_year + 1],
            Money(100000)
        )
        self.assertEqual(
            forecast.net_income[self.settings.initial_year + 1],
            Money(200000)
        )

    def test_record_gross_contribution(self):
        """ Test gross contributions. """
        # Simple contribution strategy:
        self.forecaster.set_contribution_strategy(
            strategy='Constant contribution', base_amount=Money(50000)
        )
        # No tax, to make this easy:
        self.forecaster.set_tax_treatment(
            tax_brackets={self.settings.initial_year: {0: 0}})
        self.forecaster.set_person1(gross_income=Money(100000))
        forecast = self.forecaster.forecast()
        # Test the first year:
        # TODO: refund, carryover, and asset_sale are not implemented;
        # we'll need to update these tests when they are.
        self.assertEqual(
            forecast.refund[self.settings.initial_year], Money(0))
        self.assertEqual(
            forecast.carryover[self.settings.initial_year], Money(0))
        self.assertEqual(
            forecast.asset_sale[self.settings.initial_year], Money(0))
        self.assertEqual(
            forecast.gross_contributions[self.settings.initial_year],
            Money(50000)
        )
        # Test the second year, keeping in mind the 100% inflation:
        self.assertEqual(
            forecast.refund[self.settings.initial_year + 1], Money(0))
        self.assertEqual(
            forecast.carryover[self.settings.initial_year + 1], Money(0))
        self.assertEqual(
            forecast.asset_sale[self.settings.initial_year + 1], Money(0))
        self.assertEqual(
            forecast.gross_contributions[self.settings.initial_year + 1],
            Money(100000)
        )

    def test_record_contribution_reduc(self):
        """ Test contribution reductions. """
        # Ensure there's enough money available to repay debts in full:
        self.forecaster.set_person1(gross_income=Money(100000))
        self.forecaster.set_contribution_strategy(
            strategy="Constant contribution", base_amount=Money(10000)
        )
        # $200 to pay off this debt:
        self.forecaster.add_debt(
            balance=Money(100), rate=1, reduction_rate=1,
            accelerate_payment=True)
        # $100 payment in each year, $50 of which is drawn from savings.
        self.forecaster.add_debt(
            balance=Money(200), rate=0, reduction_rate=0.5,
            accelerate_payment=False, minimum_payment=Money(100))
        forecast = self.forecaster.forecast()
        # Test the first year
        # TODO: reduction_from_other isn't implemented; update this test
        # once behaviour has been defined.
        self.assertEqual(
            forecast.reduction_from_other[self.settings.initial_year],
            Money(0))
        self.assertEqual(
            forecast.reduction_from_debt[self.settings.initial_year],
            Money(250))
        self.assertEqual(
            forecast.contribution_reductions[self.settings.initial_year],
            Money(250))
        # Check that one debt got $200 in inflows and the other debt got
        # $100 in inflows:
        self.assertTrue(
            any(
                debt.inflows_history[self.settings.initial_year] == Money(200)
                for debt in forecast.debts
            )
        )
        self.assertTrue(
            any(
                debt.inflows_history[self.settings.initial_year] == Money(100)
                for debt in forecast.debts
            )
        )
        # Test the second year
        # TODO: reduction_from_other isn't implemented; update this test
        # once behaviour has been defined.
        self.assertEqual(
            forecast.reduction_from_other[self.settings.initial_year + 1],
            Money(0))
        self.assertEqual(
            forecast.reduction_from_debt[self.settings.initial_year + 1],
            Money(50))
        self.assertEqual(
            forecast.contribution_reductions[self.settings.initial_year + 1],
            Money(50))
        # Check that one debt got no inflows and the other debt got $100
        # in inflows:
        self.assertTrue(
            any(
                debt.inflows_history[self.settings.initial_year + 1]
                == Money(0)
                for debt in forecast.debts
            )
        )
        self.assertTrue(
            any(
                debt.inflows_history[self.settings.initial_year + 1]
                == Money(100)
                for debt in forecast.debts
            )
        )

    def test_record_net_contributions(self):
        """ Test net contributions. """
        # Set up $1000 in gross contributions:
        self.forecaster.set_person1(gross_income=Money(100000))
        self.forecaster.set_contribution_strategy(
            strategy="Constant contribution", base_amount=Money(1000)
        )
        # $200 to pay off this debt (total net contributions of $800):
        self.forecaster.add_debt(
            balance=Money(100), rate=1, reduction_rate=1,
            accelerate_payment=True)
        # Here's an account to toss transactions into:
        self.forecaster.add_asset(
            balance=Money(0)
        )
        forecast = self.forecaster.forecast()
        account = next(iter(forecast.assets))
        # Test the first year
        self.assertEqual(
            forecast.net_contributions[self.settings.initial_year],
            Money(800))
        self.assertEqual(
            account.inflows_history[self.settings.initial_year],
            Money(800)
        )
        # Test the second year, keeping in mind 100% inflation.
        # (The contribution is inflation-adjusted, so it doubles here.)
        self.assertEqual(
            forecast.net_contributions[self.settings.initial_year + 1],
            Money(2000))
        self.assertEqual(
            account.inflows_history[self.settings.initial_year + 1],
            Money(2000)
        )

    def test_record_principal(self):
        """ Test principal. """
        self.forecaster.set_person1(gross_income=Money(100000), raise_rate=0)
        self.forecaster.set_contribution_strategy(
            strategy="Constant contribution", base_amount=Money(1000)
        )
        self.forecaster.add_asset(balance=Money(100), rate=1)
        forecast = self.forecaster.forecast()
        # Test the first year (balance before returns/inflows: $100):
        self.assertEqual(
            forecast.principal[self.settings.initial_year],
            Money(100))
        # Test the second year ($100 balance grew to $200 last year,
        # plus $1000 in contributions):
        self.assertEqual(
            forecast.principal[self.settings.initial_year + 1],
            Money(1200)
        )

    def test_record_withdrawals(self):
        """ Test withdrawals. """
        # Set up a situation where we retire in the first year with
        # $1,000,000 in savings and $50,000 in (inflation-adjusted)
        # annual withdrawals.
        self.forecaster.set_withdrawal_strategy(
            strategy="Constant withdrawal", base_amount=Money(50000))
        self.forecaster.set_person1(
            gross_income=100000, raise_rate=0,
            retirement_date=self.settings.initial_year)
        self.forecaster.add_asset(balance=1000000, rate=0)
        forecast = self.forecaster.forecast()
        # Test the initial year; there should be no withdrawals, since
        # retirement is modelled at the end of the year.
        self.assertEqual(
            forecast.withdrawals_for_retirement[self.settings.initial_year],
            Money(0))
        self.assertEqual(
            forecast.withdrawals_for_other[self.settings.initial_year],
            Money(0))  # TODO: Update when we implement this feature
        self.assertEqual(
            forecast.gross_withdrawals[self.settings.initial_year],
            Money(0))
        # TODO: Update these tests when we implement the below features:
        # self.assertEqual(
        #     forecast.tax_withheld_on_withdrawals[self.settings.initial_year],
        #     Money(0))  # TODO
        # self.assertEqual(
        #     forecast.net_withdrawals[self.settings.initial_year],
        #     Money(0))  # TODO

        # Test second year withdrawals. Don't forget the 100% inflation!
        self.assertEqual(
            forecast.withdrawals_for_retirement[
                self.settings.initial_year + 1],
            Money(100000))
        self.assertEqual(
            forecast.withdrawals_for_other[self.settings.initial_year + 1],
            Money(0))  # TODO: Update when we implement this feature
        self.assertEqual(
            forecast.gross_withdrawals[self.settings.initial_year + 1],
            Money(100000))
        # TODO: Update these tests when we implement the below features:
        # self.assertEqual(
        #     forecast.tax_withheld_on_withdrawals[self.settings.initial_year],
        #     Money(0))  # TODO
        # self.assertEqual(
        #     forecast.net_withdrawals[self.settings.initial_year],
        #     Money(0))  # TODO

    def test_record_returns(self):
        """ Test gross and net returns, plus tax on returns. """
        # Set up income and tax treatment so that net income is $100,000
        self.forecaster.set_tax_treatment(
            tax_brackets={self.settings.initial_year: {0: 0, 50000: 0.5}})
        self.forecaster.set_contribution_strategy(
            strategy="Constant contribution", base_amount=50000)
        self.forecaster.set_transaction_in_strategy(timing='end')
        self.forecaster.set_person1(gross_income=Money(150000), raise_rate=0)
        # $100,000 portfolio with 100% annual return.
        self.forecaster.add_asset(balance=Money(100000), rate=1)
        forecast = self.forecaster.forecast()
        # Test the first year:
        self.assertEqual(
            forecast.gross_return[self.settings.initial_year],
            Money(100000))
        self.assertEqual(
            forecast.tax_withheld_on_return[self.settings.initial_year],
            Money(0))  # TODO: Update this when implemented.
        self.assertEqual(
            forecast.net_return[self.settings.initial_year],
            forecast.gross_return[self.settings.initial_year]
            - forecast.tax_withheld_on_return[self.settings.initial_year])

        # Test the second year. Don't forget the 100% inflation!
        # We grew $100,000 to $200,000 (less taxes) and contributed
        # $50,000 at year-end, for a new balance of $250,000 less taxes:
        balance = (
            Money(250000)
            - forecast.tax_withheld_on_return[self.settings.initial_year])
        self.assertEqual(
            forecast.gross_return[self.settings.initial_year + 1],
            balance)
        self.assertEqual(
            forecast.tax_withheld_on_return[self.settings.initial_year + 1],
            Money(0))  # TODO: Update this when implemented.
        self.assertEqual(
            forecast.net_return[self.settings.initial_year + 1],
            forecast.gross_return[self.settings.initial_year + 1]
            - forecast.tax_withheld_on_return[self.settings.initial_year + 1])

    def test_record_total_tax(self):
        """ Test total tax. """
        # Set up several income streams, some with and some without
        # withholding taxes (e.g. income [withheld] and returns [not
        # withheld])
        self.forecaster.set_tax_treatment(
            tax_brackets={self.settings.initial_year: {0: 0, 100000: 0.5}})
        self.forecaster.set_contribution_strategy(
            strategy="Constant contribution", base_amount=Money(0))
        self.forecaster.set_person1(gross_income=Money(100000), raise_rate=2)
        # $100,000 portfolio with 100% annual return.
        self.forecaster.add_asset(balance=Money(100000), rate=1)
        forecast = self.forecaster.forecast()
        # Test the first year:
        # $100,000 taxable income from returns, $100,000 from employment
        # for $200,000 in total taxable income, $100,000 of which is
        # taxed at 50%, for total tax liability of $50,000.
        # None with withheld from income in this year.
        self.assertEqual(
            forecast.total_tax_owing[self.settings.initial_year],
            Money(50000))
        self.assertEqual(
            forecast.total_tax_withheld[self.settings.initial_year],
            Money(0))

        # Test the second year. Don't forget 100% inflation!
        # $200,000 taxable income from returns, $300,000 from employment
        # for $500,000 in total taxable income, $300,000 of which is
        # taxed at 50%, for total tax liability of $150,000.
        # $50,000 is withheld in this year:
        # TODO: Update this to take into account reduced balance (and
        # thus returns) after taxes are paid for in year 1.
        self.assertEqual(
            forecast.total_tax_owing[self.settings.initial_year + 1],
            Money(150000))
        self.assertEqual(
            forecast.total_tax_withheld[self.settings.initial_year + 1],
            Money(50000))

    def test_record_living_standard(self):
        """ Test living standard. """
        # TODO: Write this test once an implementation of the living
        # standard calculation has been decided on.
        pass


if __name__ == '__main__':
    unittest.main()
