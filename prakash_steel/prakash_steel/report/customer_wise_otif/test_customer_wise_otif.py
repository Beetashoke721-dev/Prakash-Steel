# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for customer_wise_otif report — no DB required."""

import unittest
from datetime import date
from unittest.mock import patch

from prakash_steel.prakash_steel.report.customer_wise_otif import customer_wise_otif as MOD


def _line(customer, week, book_value, sales_value, line_otif, customer_name=None):
	return {
		"customer": customer,
		"customer_name": customer_name or customer,
		"week": week,
		"book_value": book_value,
		"sales_value": sales_value,
		"line_otif": line_otif,
	}


class TestGetColumns(unittest.TestCase):
	def test_customer_then_53_week_columns(self):
		cols = MOD.get_columns()
		self.assertEqual(cols[0]["fieldname"], "customer_name")
		self.assertEqual(len(cols), 54)
		self.assertEqual(cols[1]["fieldname"], "week_1")
		self.assertEqual(cols[1]["label"], "Week 1")
		self.assertEqual(cols[-1]["fieldname"], "week_53")


class TestBuildCustomerRows(unittest.TestCase):
	def test_one_row_per_customer_with_week_percentage(self):
		data = MOD.build_customer_rows(
			[
				_line("C1", "1-26", 1000, 1000, 100),
				_line("C1", "1-26", 1000, 500, 0),
				_line("C2", "1-26", 1000, 1000, 100),
			]
		)
		by_name = {r["customer_name"]: r for r in data}
		self.assertEqual(len(data), 2)
		# C1 week 1: only the OTIF line's sales value counts → 1000 / 2000
		self.assertEqual(by_name["C1"]["week_1"], 50)
		self.assertEqual(by_name["C2"]["week_1"], 100)

	def test_weeks_kept_separate_and_empty_weeks_left_blank(self):
		data = MOD.build_customer_rows(
			[
				_line("C1", "1-26", 1000, 1000, 100),
				_line("C1", "12-26", 1000, 1000, 0),
			]
		)
		row = data[0]
		self.assertEqual(row["week_1"], 100)
		self.assertEqual(row["week_12"], 0)
		# Explicit None (not missing) so the Percent formatter shows blank, not "0%"
		self.assertIn("week_2", row)
		self.assertIsNone(row["week_2"])
		self.assertIsNone(row["week_53"])

	def test_lines_without_week_are_skipped(self):
		self.assertEqual(MOD.build_customer_rows([_line("C1", None, 1000, 1000, 100)]), [])

	def test_groups_by_customer_id_not_name(self):
		data = MOD.build_customer_rows(
			[
				_line("C1", "1-26", 1000, 1000, 100, customer_name="Same Name"),
				_line("C2", "1-26", 1000, 0, 0, customer_name="Same Name"),
			]
		)
		self.assertEqual(sorted(r["week_1"] for r in data), [0, 100])

	def test_zero_book_value_gives_zero(self):
		data = MOD.build_customer_rows([_line("C1", "3-26", 0, 0, 100)])
		self.assertEqual(data[0]["week_3"], 0)

	def test_sorted_by_customer_name(self):
		data = MOD.build_customer_rows(
			[_line("C2", "1-26", 1, 1, 100, "beta"), _line("C1", "1-26", 1, 1, 100, "Alpha")]
		)
		self.assertEqual([r["customer_name"] for r in data], ["Alpha", "beta"])


class TestGetData(unittest.TestCase):
	def test_no_fiscal_year_returns_empty(self):
		self.assertEqual(MOD.get_data({}), [])

	@patch.object(MOD, "get_otif_data", return_value=[])
	@patch.object(MOD, "frappe")
	def test_passes_fiscal_year_dates_company_and_customer(self, mock_frappe, mock_get_otif_data):
		mock_frappe.db.get_value.return_value = (date(2026, 4, 1), date(2027, 3, 31))

		MOD.execute({"fiscal_year": "26-27", "company": "PSP", "customer": "C1"})

		mock_get_otif_data.assert_called_once_with(
			{
				"from_date": date(2026, 4, 1),
				"to_date": date(2027, 3, 31),
				"company": "PSP",
				"customer": "C1",
			}
		)


if __name__ == "__main__":
	unittest.main()
