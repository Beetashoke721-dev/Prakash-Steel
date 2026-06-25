# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for bright_production_hbt report — no DB required.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.bright_production_hbt.test_bright_production_hbt
"""

import unittest
from unittest.mock import MagicMock, patch

from prakash_steel.utils.test_helpers import _Row

MOD = "prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt"
_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


class TestGetColumns(unittest.TestCase):
	def _cols(self, view_by):
		from prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt import (
			_get_columns,
		)
		return _get_columns(view_by)

	def test_sale_quantity_fieldtype_float(self):
		cols = self._cols("Sale Quantity")
		total_col = next(c for c in cols if c["fieldname"] == "total")
		self.assertEqual(total_col["fieldtype"], "Float")

	def test_sale_value_fieldtype_currency(self):
		cols = self._cols("Sale Value")
		total_col = next(c for c in cols if c["fieldname"] == "total")
		self.assertEqual(total_col["fieldtype"], "Currency")

	def test_contains_hbt_and_buckets(self):
		cols = self._cols("Sale Quantity")
		fieldnames = [c["fieldname"] for c in cols]
		for fn in ("hbt", "h", "b", "t", "contr_pct", "cumu_pct", "frequency"):
			self.assertIn(fn, fieldnames)


class TestGetData(unittest.TestCase):
	@patch(MOD + ".frappe")
	@patch(MOD + ".get_customer_hbt_map", return_value={"GroupA": "H", "GroupB": "T"})
	def test_hbt_labels_assigned(self, _mock_hbt_map, mock_frappe):
		from prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt import (
			_get_data,
		)
		mock_frappe.db.sql.side_effect = [
			[_Row(item_code="BB-001", total=60.0, frequency=3),
			 _Row(item_code="BB-002", total=40.0, frequency=2)],
			[_Row(item_code="BB-001", group_name="GroupA", total=60.0),
			 _Row(item_code="BB-002", group_name="GroupB", total=40.0)],
		]
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["hbt"], "H")   # BB-001: 60% → H
		self.assertEqual(result[1]["hbt"], "B")   # BB-002: running=100% → B

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_customer_hbt_map", return_value={})
	def test_empty_rows_returns_empty(self, _mock_hbt_map, mock_frappe):
		from prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = []
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(result, [])

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_customer_hbt_map", return_value={"GroupH": "H", "GroupT": "T"})
	def test_hbt_buckets_populated(self, _mock_hbt_map, mock_frappe):
		from prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt import (
			_get_data,
		)
		mock_frappe.db.sql.side_effect = [
			[_Row(item_code="BB-001", total=100.0, frequency=5)],
			[_Row(item_code="BB-001", group_name="GroupH", total=70.0),
			 _Row(item_code="BB-001", group_name="GroupT", total=30.0)],
		]
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertAlmostEqual(result[0]["h"], 70.0)
		self.assertAlmostEqual(result[0]["t"], 30.0)
		self.assertAlmostEqual(result[0]["b"], 0.0)

	@patch(MOD + ".frappe")
	def test_unsupported_view_throws(self, mock_frappe):
		from prakash_steel.prakash_steel.report.bright_production_hbt.bright_production_hbt import (
			_get_data,
		)
		mock_frappe.throw.side_effect = Exception("not implemented")
		with self.assertRaises(Exception):
			_get_data(_PERIOD, "Throughput")


if __name__ == "__main__":
	unittest.main()
