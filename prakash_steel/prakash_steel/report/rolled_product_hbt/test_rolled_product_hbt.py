# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for rolled_production_hbt report — no DB required.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.rolled_production_hbt.test_rolled_production_hbt
"""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.rolled_production_hbt.rolled_production_hbt"
_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


class TestGetData(unittest.TestCase):
	@patch(MOD + ".frappe")
	@patch(MOD + ".get_customer_hbt_map", return_value={})
	def test_empty_rows_returns_empty(self, _mock_hbt_map, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_production_hbt.rolled_production_hbt import (
			_get_data,
		)
		mock_frappe.db.sql.return_value = []
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(result, [])

	@patch(MOD + ".frappe")
	def test_unsupported_view_throws(self, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_production_hbt.rolled_production_hbt import (
			_get_data,
		)
		mock_frappe.throw.side_effect = Exception("not implemented")
		with self.assertRaises(Exception):
			_get_data(_PERIOD, "Throughput")

	def test_get_consumption_map_aggregates(self):
		from prakash_steel.prakash_steel.report.rolled_production_hbt.rolled_production_hbt import (
			_get_consumption_map,
		)
		with patch(MOD + ".frappe") as mock_frappe:
			mock_frappe.db.sql.return_value = [
				MagicMock(item_code="RB-001", consumption=100.0),
				MagicMock(item_code="RB-001", consumption=50.0),  # duplicate → summed
				MagicMock(item_code="RB-002", consumption=30.0),
			]
			result = _get_consumption_map(date(2025, 4, 1), date(2025, 9, 30))
		self.assertAlmostEqual(result["RB-001"], 150.0)
		self.assertAlmostEqual(result["RB-002"], 30.0)

	@patch(MOD + ".frappe")
	@patch(MOD + ".get_customer_hbt_map", return_value={})
	def test_result_has_expected_keys(self, _mock_hbt_map, mock_frappe):
		from prakash_steel.prakash_steel.report.rolled_production_hbt.rolled_production_hbt import (
			_get_data,
		)
		item_row = MagicMock()
		item_row.item_code = "RB-001"
		item_row.total = 100.0
		item_row.frequency = 4
		mock_frappe.db.sql.side_effect = [
			[item_row],  # item totals
			[],          # item_group_rows
			[],          # consumption
		]
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(len(result), 1)
		for key in ("item_code", "total", "consumption", "total_value", "contr_pct", "cumu_pct", "hbt", "frequency", "h", "b", "t"):
			self.assertIn(key, result[0])


if __name__ == "__main__":
	unittest.main()
