# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for customer_hbt report — no DB required.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.customer_hbt.test_customer_hbt
"""

import unittest
from unittest.mock import MagicMock, patch

from prakash_steel.utils.test_helpers import _Row

MOD = "prakash_steel.prakash_steel.report.customer_hbt.customer_hbt"
_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


class TestGetColumns(unittest.TestCase):
	def test_quantity_has_six_columns(self):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_columns
		cols = _get_columns("Sale Quantity")
		self.assertEqual(len(cols), 6)

	def test_value_fieldtype_currency(self):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_columns
		cols = _get_columns("Sale Value")
		total_col = next(c for c in cols if c["fieldname"] == "total")
		self.assertEqual(total_col["fieldtype"], "Currency")


class TestGetData(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_hbt_classification(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_data
		mock_frappe.db.sql.return_value = [
			_Row(group_name="Alpha", total=600.0, frequency=6),
			_Row(group_name="Beta", total=300.0, frequency=3),
			_Row(group_name="Gamma", total=100.0, frequency=1),
		]
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(len(result), 3)
		# Alpha: 60% → H; Beta: running=90% → B; Gamma: running=100% → T
		self.assertEqual(result[0]["hbt"], "H")
		self.assertEqual(result[1]["hbt"], "B")
		self.assertEqual(result[2]["hbt"], "T")

	@patch(MOD + ".frappe")
	def test_empty_returns_empty(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_data
		mock_frappe.db.sql.return_value = []
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertEqual(result, [])

	@patch(MOD + ".frappe")
	def test_contr_cumu_percentages(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_data
		mock_frappe.db.sql.return_value = [
			_Row(group_name="A", total=50.0, frequency=1),
			_Row(group_name="B", total=50.0, frequency=1),
		]
		result = _get_data(_PERIOD, "Sale Quantity")
		self.assertAlmostEqual(result[0]["contr_pct"], 50.0)
		self.assertAlmostEqual(result[1]["cumu_pct"], 100.0)

	@patch(MOD + ".frappe")
	def test_unsupported_view_throws(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import _get_data
		mock_frappe.throw.side_effect = Exception("not implemented")
		with self.assertRaises(Exception):
			_get_data(_PERIOD, "Throughput")


if __name__ == "__main__":
	unittest.main()
