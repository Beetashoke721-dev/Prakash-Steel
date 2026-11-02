# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for purchase report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.purchase.purchase"


class TestGetColumns(unittest.TestCase):
	def test_returns_list_with_fieldnames(self):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_columns

		cols = get_columns()
		self.assertIsInstance(cols, list)
		self.assertGreater(len(cols), 0)
		for col in cols:
			self.assertIn("fieldname", col)
			self.assertIn("label", col)
			self.assertIn("fieldtype", col)

	def test_includes_expected_fieldnames(self):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_columns

		fieldnames = {col["fieldname"] for col in get_columns()}
		self.assertEqual(
			fieldnames,
			{
				"date",
				"id",
				"vendor_name",
				"item_name",
				"qty",
				"rate",
				"amount",
				"category",
				"month",
				"net_value",
				"avg_rate",
			},
		)


class TestExecute(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_returns_tuple(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import execute

		mock_frappe.db.sql.return_value = []
		cols, data = execute({})
		self.assertIsInstance(cols, list)
		self.assertIsInstance(data, list)

	@patch(MOD + ".frappe")
	def test_execute_defaults_empty_filters(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import execute

		mock_frappe.db.sql.return_value = []
		cols, data = execute()
		self.assertIsInstance(cols, list)
		self.assertEqual(data, [])


class TestGetData(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_defaults_from_and_to_date_when_missing(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		filters = {}
		get_data(filters)
		self.assertEqual(filters["from_date"], "2020-01-01")
		self.assertEqual(filters["to_date"], "2030-12-31")

	@patch(MOD + ".frappe")
	def test_keeps_supplied_date_range(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		filters = {"from_date": "2026-01-01", "to_date": "2026-01-31"}
		get_data(filters)
		self.assertEqual(filters["from_date"], "2026-01-01")
		self.assertEqual(filters["to_date"], "2026-01-31")

	@patch(MOD + ".frappe")
	def test_supplier_filter_adds_condition(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		get_data({"supplier": "Supplier A"})
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("pi.supplier = %(supplier)s", query)

	@patch(MOD + ".frappe")
	def test_item_code_filter_adds_condition(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		get_data({"item_code": "ITEM-001"})
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("pii.item_code = %(item_code)s", query)

	@patch(MOD + ".frappe")
	def test_no_optional_filters_omits_conditions(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		get_data({})
		query = mock_frappe.db.sql.call_args[0][0]
		self.assertNotIn("pi.supplier = %(supplier)s", query)
		self.assertNotIn("pii.item_code = %(item_code)s", query)

	@patch(MOD + ".frappe")
	def test_net_value_is_amount_over_qty(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = [
			{"amount": 100, "qty": 4, "month": "1-26", "category": None},
		]
		data = get_data({})
		self.assertEqual(data[0]["net_value"], 25)

	@patch(MOD + ".frappe")
	def test_net_value_zero_when_qty_is_zero(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = [
			{"amount": 100, "qty": 0, "month": "1-26", "category": None},
		]
		data = get_data({})
		self.assertEqual(data[0]["net_value"], 0)

	@patch(MOD + ".frappe")
	def test_avg_rate_none_when_row_has_no_category(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = [
			{"amount": 100, "qty": 4, "month": "1-26", "category": None},
		]
		data = get_data({})
		self.assertIsNone(data[0]["avg_rate"])

	@patch(MOD + ".frappe")
	def test_avg_rate_is_group_average_by_month_and_category(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		# Two rows in the same (month, category) bucket -> net_value 25 and 15 -> avg 20.
		mock_frappe.db.sql.return_value = [
			{"amount": 100, "qty": 4, "month": "1-26", "category": "Wire"},
			{"amount": 60, "qty": 4, "month": "1-26", "category": "Wire"},
		]
		data = get_data({})
		self.assertEqual(data[0]["avg_rate"], 20)
		self.assertEqual(data[1]["avg_rate"], 20)

	@patch(MOD + ".frappe")
	def test_avg_rate_separates_different_months_or_categories(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = [
			{"amount": 100, "qty": 4, "month": "1-26", "category": "Wire"},
			{"amount": 200, "qty": 4, "month": "2-26", "category": "Wire"},
			{"amount": 300, "qty": 4, "month": "1-26", "category": "Rod"},
		]
		data = get_data({})
		self.assertEqual(data[0]["avg_rate"], 25)
		self.assertEqual(data[1]["avg_rate"], 50)
		self.assertEqual(data[2]["avg_rate"], 75)

	@patch(MOD + ".frappe")
	def test_empty_data_returns_empty_list(self, mock_frappe):
		from prakash_steel.prakash_steel.report.purchase.purchase import get_data

		mock_frappe.db.sql.return_value = []
		self.assertEqual(get_data({}), [])


if __name__ == "__main__":
	unittest.main()
