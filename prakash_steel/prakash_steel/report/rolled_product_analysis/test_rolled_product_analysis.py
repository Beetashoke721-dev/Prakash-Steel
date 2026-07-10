# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for rolled_product_analysis report — no DB required.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.rolled_product_analysis.test_rolled_product_analysis
"""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis"
_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


class TestGetColumns(unittest.TestCase):
	def setUp(self):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_columns,
		)
		self.fn = _get_columns

	def test_empty_period_returns_only_item_code_column(self):
		cols = self.fn([])
		self.assertEqual(len(cols), 1)
		self.assertEqual(cols[0]["fieldname"], "item_code")

	def test_single_month_adds_one_column(self):
		cols = self.fn([(2025, 6)])
		self.assertEqual(len(cols), 2)
		self.assertEqual(cols[1]["fieldname"], "m_2025_06")
		self.assertEqual(cols[1]["label"], "Jun 25")

	def test_month_columns_are_float_type(self):
		cols = self.fn([(2025, 6)])
		self.assertEqual(cols[1]["fieldtype"], "Float")


class TestGetData(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_aggregates_by_item_and_month(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = [
			MagicMock(item_code="RB-001", yr=2025, mo=4, val=500.0),
			MagicMock(item_code="RB-001", yr=2025, mo=6, val=300.0),
		]
		result = _get_data({}, _PERIOD)
		self.assertEqual(len(result), 1)
		rb1 = result[0]
		self.assertAlmostEqual(rb1["m_2025_04"], 500.0)
		self.assertAlmostEqual(rb1["m_2025_05"], 0.0)
		self.assertAlmostEqual(rb1["m_2025_06"], 300.0)

	@patch(MOD + ".frappe")
	def test_empty_sql_returns_empty(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = []
		result = _get_data({}, _PERIOD)
		self.assertEqual(result, [])

	@patch(MOD + ".frappe")
	def test_empty_period_returns_empty(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		result = _get_data({}, [])
		mock_frappe.db.sql.assert_not_called()
		self.assertEqual(result, [])

	@patch(MOD + ".frappe")
	def test_unsupported_view_throws(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		mock_frappe.throw.side_effect = Exception("not implemented")
		with self.assertRaises(Exception):
			_get_data({"view_by": "Throughput"}, _PERIOD)

	@patch(MOD + ".frappe")
	def test_query_filters_rb_items(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = []
		_get_data({}, _PERIOD)
		sql_called = mock_frappe.db.sql.call_args[0][0]
		self.assertIn("'RB'", sql_called)
		self.assertNotIn("'BB'", sql_called)

	@patch(MOD + ".frappe")
	def test_sorted_by_item_code(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_product_analysis.rolled_product_analysis import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = [
			MagicMock(item_code="ZZ", yr=2025, mo=4, val=10.0),
			MagicMock(item_code="AA", yr=2025, mo=4, val=20.0),
		]
		result = _get_data({}, _PERIOD)
		self.assertEqual(result[0]["item_code"], "AA")
		self.assertEqual(result[1]["item_code"], "ZZ")


if __name__ == "__main__":
	unittest.main()
