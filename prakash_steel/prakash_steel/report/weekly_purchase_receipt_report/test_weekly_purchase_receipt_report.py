# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for weekly_purchase_receipt_report — no DB required."""

import unittest
from unittest.mock import patch

MODULE = "prakash_steel.prakash_steel.report.weekly_purchase_receipt_report.weekly_purchase_receipt_report"


class TestGetColumns(unittest.TestCase):
	def test_returns_six_columns(self):
		from prakash_steel.prakash_steel.report.weekly_purchase_receipt_report.weekly_purchase_receipt_report import (
			get_columns,
		)

		cols = get_columns()
		self.assertEqual(len(cols), 6)
		fieldnames = [c["fieldname"] for c in cols]
		self.assertEqual(
			fieldnames,
			["posting_date", "name", "supplier", "item_code", "stock_qty", "rate"],
		)

	def test_id_column_links_to_purchase_receipt(self):
		from prakash_steel.prakash_steel.report.weekly_purchase_receipt_report.weekly_purchase_receipt_report import (
			get_columns,
		)

		cols = {c["fieldname"]: c for c in get_columns()}
		self.assertEqual(cols["name"]["fieldtype"], "Link")
		self.assertEqual(cols["name"]["options"], "Purchase Receipt")


class TestGetData(unittest.TestCase):
	def _get_data(self, filters, sql_rows):
		from prakash_steel.prakash_steel.report.weekly_purchase_receipt_report.weekly_purchase_receipt_report import (
			get_data,
		)

		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = sql_rows
			return get_data(filters), mock_frappe

	def test_no_filters_only_docstatus_condition(self):
		result, mock_frappe = self._get_data({}, [])
		self.assertEqual(result, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("pr.docstatus = 1", query)
		self.assertEqual(params, {})

	def test_none_filters_defaults_to_empty_dict(self):
		result, mock_frappe = self._get_data(None, [])
		self.assertEqual(result, [])
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertEqual(params, {})

	def test_from_date_filter_applied(self):
		_, mock_frappe = self._get_data({"from_date": "2026-01-01"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("pr.posting_date >= %(from_date)s", query)
		self.assertEqual(params["from_date"], "2026-01-01")

	def test_to_date_filter_applied(self):
		_, mock_frappe = self._get_data({"to_date": "2026-01-31"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("pr.posting_date <= %(to_date)s", query)
		self.assertEqual(params["to_date"], "2026-01-31")

	def test_supplier_filter_applied(self):
		_, mock_frappe = self._get_data({"supplier": "Supplier A"}, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("pr.supplier = %(supplier)s", query)
		self.assertEqual(params["supplier"], "Supplier A")

	def test_all_filters_combined(self):
		filters = {
			"from_date": "2026-01-01",
			"to_date": "2026-01-31",
			"supplier": "Supplier A",
		}
		_, mock_frappe = self._get_data(filters, [])
		query = mock_frappe.db.sql.call_args[0][0]
		params = mock_frappe.db.sql.call_args[0][1]
		self.assertIn("pr.posting_date >= %(from_date)s", query)
		self.assertIn("pr.posting_date <= %(to_date)s", query)
		self.assertIn("pr.supplier = %(supplier)s", query)
		self.assertEqual(params, filters)

	def test_returns_rows_from_sql(self):
		rows = [
			{
				"posting_date": "2026-01-05",
				"name": "PR-0001",
				"supplier": "Supplier A",
				"item_code": "ITEM-001",
				"stock_qty": 10.0,
				"rate": 250.0,
			}
		]
		result, _ = self._get_data({}, rows)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["name"], "PR-0001")
		self.assertEqual(result[0]["rate"], 250.0)

	def test_sql_called_as_dict(self):
		_, mock_frappe = self._get_data({}, [])
		self.assertTrue(mock_frappe.db.sql.call_args[1]["as_dict"])


class TestExecute(unittest.TestCase):
	@patch(MODULE + ".get_data")
	@patch(MODULE + ".get_columns")
	def test_execute_returns_columns_and_data(self, mock_get_columns, mock_get_data):
		from prakash_steel.prakash_steel.report.weekly_purchase_receipt_report.weekly_purchase_receipt_report import (
			execute,
		)

		mock_get_columns.return_value = [{"fieldname": "posting_date"}]
		mock_get_data.return_value = [{"posting_date": "2026-01-05"}]

		columns, data = execute({"supplier": "Supplier A"})

		mock_get_data.assert_called_once_with({"supplier": "Supplier A"})
		self.assertEqual(columns, mock_get_columns.return_value)
		self.assertEqual(data, mock_get_data.return_value)


if __name__ == "__main__":
	unittest.main()
