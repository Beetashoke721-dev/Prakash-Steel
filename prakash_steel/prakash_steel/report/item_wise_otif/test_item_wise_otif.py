# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for item_wise_otif report — no DB required."""

import unittest
from datetime import date
from unittest.mock import patch

from prakash_steel.prakash_steel.report.item_wise_otif import item_wise_otif as MOD


def _line(item_code, week, book_value, sales_value, line_otif, item_name=None, customer="C1"):
	return {
		"item_code": item_code,
		"item_name": item_name or item_code,
		"customer": customer,
		"customer_name": customer,
		"week": week,
		"book_value": book_value,
		"sales_value": sales_value,
		"line_otif": line_otif,
	}


class TestGetColumns(unittest.TestCase):
	def test_item_name_then_53_week_columns(self):
		cols = MOD.get_columns()
		self.assertEqual(cols[0]["fieldname"], "item_name")
		self.assertEqual(len(cols), 54)
		self.assertEqual(cols[1]["fieldname"], "week_1")
		self.assertEqual(cols[-1]["fieldname"], "week_53")


class TestExecute(unittest.TestCase):
	def test_no_fiscal_year_returns_empty(self):
		cols, data = MOD.execute({})
		self.assertEqual(data, [])

	@patch.object(MOD, "get_otif_data")
	@patch.object(MOD, "frappe")
	def test_one_row_per_item_across_customers(self, mock_frappe, mock_get_otif_data):
		mock_frappe.db.get_value.return_value = (date(2026, 4, 1), date(2027, 3, 31))
		mock_get_otif_data.return_value = [
			_line("I1", "1-26", 1000, 1000, 100, customer="C1"),
			_line("I1", "1-26", 1000, 500, 0, customer="C2"),
			_line("I2", "2-26", 1000, 1000, 100),
		]

		cols, data = MOD.execute({"fiscal_year": "26-27", "company": "PSP", "item_code": "I1"})

		mock_get_otif_data.assert_called_once_with(
			{"from_date": date(2026, 4, 1), "to_date": date(2027, 3, 31), "company": "PSP", "item_code": "I1"}
		)
		by_name = {r["item_name"]: r for r in data}
		# I1 week 1: both customers' lines count → 1000 / 2000
		self.assertEqual(by_name["I1"]["week_1"], 50)
		self.assertIsNone(by_name["I1"]["week_2"])
		self.assertEqual(by_name["I2"]["week_2"], 100)
		self.assertIsNone(by_name["I2"]["week_1"])


if __name__ == "__main__":
	unittest.main()
