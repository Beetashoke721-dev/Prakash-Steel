# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for Average Bank Closing page — no DB required."""

import unittest
from datetime import date
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing"


class TestBuildMonthWiseSummary(unittest.TestCase):
	def test_averages_daily_closing_per_month_and_account(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_build_month_wise_summary,
		)

		rows = [
			{"detail_date": date(2026, 7, 30), "account_head": "HDFC - PSPL", "closing_balance": 100.0},
			{"detail_date": date(2026, 7, 31), "account_head": "HDFC - PSPL", "closing_balance": 200.0},
			{"detail_date": date(2026, 8, 1), "account_head": "HDFC - PSPL", "closing_balance": 300.0},
			{"detail_date": date(2026, 8, 1), "account_head": "Axis - PSPL", "closing_balance": 50.0},
		]
		summary = _build_month_wise_summary(rows)
		self.assertEqual(
			summary,
			[
				{"month": "July 2026", "account_head": "HDFC - PSPL", "closing_balance": 150.0},
				{"month": "August 2026", "account_head": "Axis - PSPL", "closing_balance": 50.0},
				{"month": "August 2026", "account_head": "HDFC - PSPL", "closing_balance": 300.0},
			],
		)

	def test_empty_details_returns_empty_summary(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_build_month_wise_summary,
		)

		self.assertEqual(_build_month_wise_summary([]), [])

	def test_month_wise_average_is_mean_of_daily_closings(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_build_month_wise_summary,
		)

		rows = [
			{"detail_date": date(2026, 8, 1), "account_head": "HDFC - PSPL", "closing_balance": 100.0},
			{"detail_date": date(2026, 8, 2), "account_head": "HDFC - PSPL", "closing_balance": 200.0},
			{"detail_date": date(2026, 8, 3), "account_head": "HDFC - PSPL", "closing_balance": 300.0},
		]
		summary = _build_month_wise_summary(rows)
		self.assertEqual(len(summary), 1)
		self.assertEqual(summary[0]["month"], "August 2026")
		self.assertEqual(summary[0]["closing_balance"], 200.0)
		self.assertNotIn("row_type", summary[0])


class TestAppendAverageAndTotal(unittest.TestCase):
	def test_empty_returns_empty(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_append_average_and_total,
		)

		self.assertEqual(_append_average_and_total([], "month"), [])

	def test_does_not_double_count_existing_footers(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_append_average_and_total,
		)

		rows = [
			{"month": "August 2026", "account_head": "HDFC - PSPL", "closing_balance": 100.0},
			{"month": "Average", "account_head": "", "closing_balance": 100.0, "row_type": "Average"},
			{"month": "Total", "account_head": "", "closing_balance": 100.0, "row_type": "Total"},
		]
		out = _append_average_and_total(rows, "month")
		self.assertEqual(len(out), 3)
		self.assertEqual(out[-2]["row_type"], "Total")
		self.assertEqual(out[-1]["row_type"], "Average")
		self.assertEqual(out[-2]["closing_balance"], 100.0)


class TestValidateDates(unittest.TestCase):
	def test_missing_dates_throws(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_validate_dates,
		)

		with self.assertRaises(Exception):
			_validate_dates(None, "2026-08-13")
		with self.assertRaises(Exception):
			_validate_dates("2026-08-01", None)

	def test_from_after_to_throws(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_validate_dates,
		)

		with self.assertRaises(Exception):
			_validate_dates("2026-08-13", "2026-08-01")

	def test_valid_range_returns_dates(self):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_validate_dates,
		)

		start, end = _validate_dates("2026-07-13", "2026-08-13")
		self.assertEqual(start, date(2026, 7, 13))
		self.assertEqual(end, date(2026, 8, 13))


class TestBuildTransactionDetails(unittest.TestCase):
	@patch(MOD + ".today", return_value=date(2026, 8, 13))
	@patch(MOD + "._get_daily_balances")
	def test_one_row_per_day_per_account(self, mock_balances, _mock_today):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_build_transaction_details,
		)

		mock_balances.return_value = {
			"2026-08-12": 1000.0,
			"2026-08-13": 1100.5,
		}
		rows = _build_transaction_details(
			["HDFC - PSPL"], date(2026, 8, 12), date(2026, 8, 13)
		)
		self.assertEqual(len(rows), 4)
		self.assertEqual(rows[0]["account_head"], "HDFC - PSPL")
		self.assertEqual(rows[0]["closing_balance"], 1000.0)
		self.assertEqual(rows[1]["closing_balance"], 1100.5)
		self.assertEqual(rows[-2]["row_type"], "Total")
		self.assertEqual(rows[-2]["closing_balance"], 2100.5)
		self.assertEqual(rows[-1]["row_type"], "Average")
		self.assertEqual(rows[-1]["closing_balance"], 1050.25)
		mock_balances.assert_called_once()

	@patch(MOD + ".today", return_value=date(2026, 8, 1))
	@patch(MOD + "._get_daily_balances")
	def test_future_to_date_is_capped_at_today(self, mock_balances, _mock_today):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			_build_transaction_details,
		)

		mock_balances.return_value = {"2026-08-01": 10.0}
		rows = _build_transaction_details(
			["HDFC - PSPL"], date(2026, 8, 1), date(2026, 8, 31)
		)
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[0]["detail_date"], date(2026, 8, 1))
		self.assertEqual(rows[-2]["row_type"], "Total")
		self.assertEqual(rows[-1]["row_type"], "Average")


class TestWhitelistedMethods(unittest.TestCase):
	@patch(MOD + "._build_transaction_details", return_value=[])
	@patch(MOD + "._get_bank_accounts", return_value=["HDFC - PSPL"])
	@patch(MOD + ".require_permission")
	def test_get_transaction_details_checks_permissions(
		self, mock_perm, mock_accounts, mock_details
	):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			get_transaction_details,
		)

		get_transaction_details(
			from_date="2026-07-13", to_date="2026-08-13", bank_account="HDFC - PSPL"
		)
		self.assertEqual(mock_perm.call_count, 2)
		mock_perm.assert_any_call("Account", "read")
		mock_perm.assert_any_call("GL Entry", "read")
		mock_accounts.assert_called_once_with("HDFC - PSPL")
		mock_details.assert_called_once()

	@patch(MOD + "._build_month_wise_summary", return_value=[{"month": "August 2026"}])
	@patch(MOD + "._build_transaction_details", return_value=[{"detail_date": date(2026, 8, 1)}])
	@patch(MOD + "._get_bank_accounts", return_value=["HDFC - PSPL"])
	@patch(MOD + ".require_permission")
	def test_get_month_wise_summary_uses_details(
		self, mock_perm, mock_accounts, mock_details, mock_summary
	):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			get_month_wise_summary,
		)

		result = get_month_wise_summary(
			from_date="2026-08-01", to_date="2026-08-13", bank_account="HDFC - PSPL"
		)
		self.assertEqual(result, [{"month": "August 2026"}])
		mock_summary.assert_called_once()
		mock_accounts.assert_called_once_with("HDFC - PSPL")

	@patch(MOD + ".require_permission")
	def test_missing_bank_account_throws(self, _mock_perm):
		from prakash_steel.prakash_steel.page.average_bank_closing.average_bank_closing import (
			get_transaction_details,
		)

		with self.assertRaises(Exception):
			get_transaction_details(from_date="2026-08-01", to_date="2026-08-13")


if __name__ == "__main__":
	unittest.main()
