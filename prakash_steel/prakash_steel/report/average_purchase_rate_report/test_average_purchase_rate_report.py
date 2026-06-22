# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for average_purchase_rate_report — no DB required."""

import unittest
from unittest.mock import patch

MODULE = "prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report"


class TestValidateFilters(unittest.TestCase):
	def _validate(self, filters):
		from prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report import (
			validate_filters,
		)
		validate_filters(filters)

	@patch(MODULE + ".frappe")
	def test_missing_both_throws(self, mock_frappe):
		mock_frappe.throw.side_effect = Exception("validation")
		with self.assertRaises(Exception):
			self._validate({})

	@patch(MODULE + ".frappe")
	def test_item_code_only_passes(self, mock_frappe):
		mock_frappe.throw.side_effect = Exception("should not throw")
		self._validate({"item_code": "ITEM-001"})
		mock_frappe.throw.assert_not_called()

	@patch(MODULE + ".frappe")
	def test_grade_only_passes(self, mock_frappe):
		mock_frappe.throw.side_effect = Exception("should not throw")
		self._validate({"grade": "MS"})
		mock_frappe.throw.assert_not_called()

	@patch(MODULE + ".frappe")
	def test_from_after_to_throws(self, mock_frappe):
		mock_frappe.throw.side_effect = Exception("date validation")
		with self.assertRaises(Exception):
			self._validate({"item_code": "X", "from_date": "2025-06-01", "to_date": "2025-05-01"})

	@patch(MODULE + ".frappe")
	def test_equal_dates_passes(self, mock_frappe):
		mock_frappe.throw.side_effect = Exception("should not throw")
		self._validate({"item_code": "X", "from_date": "2025-06-01", "to_date": "2025-06-01"})
		mock_frappe.throw.assert_not_called()


class TestGetData(unittest.TestCase):
	def _get_data(self, filters, sql_rows):
		from prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report import (
			get_data,
		)
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = sql_rows
			return get_data(filters)

	def test_item_code_filter(self):
		rows = [{"po_date": "2025-05-01", "party_name": "Vendor A", "item_name": "Bar", "item_grade": "MS", "rate": 100.0, "purchase_order_no": "PO-001"}]
		result = self._get_data({"item_code": "BAR-001"}, rows)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["rate"], 100.0)

	def test_empty_result(self):
		result = self._get_data({"grade": "MS"}, [])
		self.assertEqual(result, [])

	def test_both_filters_combined(self):
		rows = [{"po_date": "2025-05-01", "party_name": "V", "item_name": "I", "item_grade": "MS", "rate": 50.0, "purchase_order_no": "PO-002"}]
		result = self._get_data({"item_code": "X", "grade": "MS"}, rows)
		self.assertEqual(len(result), 1)

	def test_date_range_included(self):
		from prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report import (
			get_data,
		)
		with patch(MODULE + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = []
			get_data({"item_code": "X", "from_date": "2025-01-01", "to_date": "2025-12-31"})
			call_args = mock_frappe.db.sql.call_args
			params = call_args[0][1]
			self.assertIn("from_date", params)
			self.assertIn("to_date", params)


class TestGetColumns(unittest.TestCase):
	def test_returns_six_columns(self):
		from prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report import (
			get_columns,
		)
		cols = get_columns()
		self.assertEqual(len(cols), 6)
		fieldnames = [c["fieldname"] for c in cols]
		self.assertIn("rate", fieldnames)
		self.assertIn("purchase_order_no", fieldnames)


if __name__ == "__main__":
	unittest.main()
