# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for bright_product_analysis report.

Pure logic tests (no DB) use unittest.TestCase with mocked frappe calls.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.bright_product_analysis.test_bright_product_analysis
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.bright_product_analysis.bright_product_analysis"
_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


def _import():
	import prakash_steel.prakash_steel.report.bright_product_analysis.bright_product_analysis as m

	return m


# ---------------------------------------------------------------------------
# _get_columns
# ---------------------------------------------------------------------------


class TestGetColumns(unittest.TestCase):
	def setUp(self):
		self.fn = _import()._get_columns

	def _labels(self, cols):
		return [c["label"] for c in cols]

	def _fieldnames(self, cols):
		return [c["fieldname"] for c in cols]

	def test_empty_period_returns_only_item_code_column(self):
		cols = self.fn([])
		self.assertEqual(len(cols), 1)
		self.assertEqual(cols[0]["fieldname"], "item_code")
		self.assertEqual(cols[0]["fieldtype"], "Link")

	def test_single_month_adds_one_column(self):
		cols = self.fn([(2025, 6)])
		self.assertEqual(len(cols), 2)
		self.assertEqual(cols[1]["fieldname"], "m_2025_06")
		self.assertEqual(cols[1]["label"], "Jun 25")

	def test_multi_month_columns_in_order(self):
		period = [(2025, 6), (2025, 7), (2025, 8)]
		cols = self.fn(period)
		self.assertEqual(self._fieldnames(cols), ["item_code", "m_2025_06", "m_2025_07", "m_2025_08"])
		self.assertEqual(self._labels(cols)[1:], ["Jun 25", "Jul 25", "Aug 25"])

	def test_cross_year_columns(self):
		period = [(2025, 12), (2026, 1), (2026, 2)]
		cols = self.fn(period)
		self.assertEqual(self._fieldnames(cols)[1:], ["m_2025_12", "m_2026_01", "m_2026_02"])
		self.assertEqual(self._labels(cols)[1:], ["Dec 25", "Jan 26", "Feb 26"])

	def test_year_shows_last_two_digits(self):
		cols = self.fn([(2025, 4)])
		self.assertEqual(cols[1]["label"], "Apr 25")

	def test_month_columns_are_float_type(self):
		cols = self.fn([(2025, 6)])
		self.assertEqual(cols[1]["fieldtype"], "Float")


# ---------------------------------------------------------------------------
# _get_data — pivot logic (mocked frappe.db.sql)
# ---------------------------------------------------------------------------


class TestGetData(unittest.TestCase):
	def _call(self, filters, period_months, sql_rows):
		fn = _import()._get_data
		with patch(f"{MOD}.frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = sql_rows
			return fn(filters, period_months)

	def test_empty_period_months_returns_empty(self):
		result = _import()._get_data({}, [])
		self.assertEqual(result, [])

	def test_unsupported_view_throws(self):
		fn = _import()._get_data
		with patch(f"{MOD}.frappe.throw", side_effect=Exception("not implemented")):
			with self.assertRaises(Exception):
				fn({"view_by": "Throughput"}, _PERIOD)

	def test_single_item_single_month_sale_quantity(self):
		period = [(2025, 6)]
		rows = [SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=50.0)]
		result = self._call({"view_by": "Sale Quantity"}, period, rows)

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["item_code"], "ITEM-001")
		self.assertEqual(result[0]["m_2025_06"], 50.0)

	def test_single_item_aggregates_across_months(self):
		period = [(2025, 6), (2025, 7)]
		rows = [
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=30.0),
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=7, val=20.0),
		]
		result = self._call({"view_by": "Sale Quantity"}, period, rows)
		self.assertEqual(result[0]["m_2025_06"], 30.0)
		self.assertEqual(result[0]["m_2025_07"], 20.0)

	def test_missing_month_for_item_defaults_to_zero(self):
		period = [(2025, 6), (2025, 7)]
		rows = [SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=10.0)]
		result = self._call({}, period, rows)
		self.assertEqual(result[0]["m_2025_07"], 0.0)

	def test_multiple_items_sorted_alphabetically(self):
		period = [(2025, 6)]
		rows = [
			SimpleNamespace(item_code="ITEM-B", yr=2025, mo=6, val=5.0),
			SimpleNamespace(item_code="ITEM-A", yr=2025, mo=6, val=10.0),
		]
		result = self._call({}, period, rows)
		self.assertEqual(result[0]["item_code"], "ITEM-A")
		self.assertEqual(result[1]["item_code"], "ITEM-B")

	def test_val_none_treated_as_zero(self):
		period = [(2025, 6)]
		rows = [SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=None)]
		result = self._call({}, period, rows)
		self.assertEqual(result[0]["m_2025_06"], 0.0)

	def test_out_of_period_row_is_ignored(self):
		period = [(2025, 6)]
		rows = [
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=10.0),
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=9, val=99.0),
		]
		result = self._call({}, period, rows)
		self.assertNotIn("m_2025_09", result[0])
		self.assertEqual(result[0]["m_2025_06"], 10.0)

	def test_sale_value_uses_same_pivot_logic(self):
		period = [(2025, 6)]
		rows = [SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=1500.0)]
		result = self._call({"view_by": "Sale Value"}, period, rows)
		self.assertEqual(result[0]["m_2025_06"], 1500.0)

	def test_default_view_by_is_sale_quantity(self):
		period = [(2025, 6)]
		rows = [SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=7.0)]
		result = self._call({}, period, rows)
		self.assertEqual(result[0]["m_2025_06"], 7.0)

	def test_cross_year_period_pivot(self):
		period = [(2025, 12), (2026, 1)]
		rows = [
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=12, val=100.0),
			SimpleNamespace(item_code="ITEM-001", yr=2026, mo=1, val=200.0),
		]
		result = self._call({}, period, rows)
		self.assertEqual(result[0]["m_2025_12"], 100.0)
		self.assertEqual(result[0]["m_2026_01"], 200.0)


if __name__ == "__main__":
	unittest.main()
