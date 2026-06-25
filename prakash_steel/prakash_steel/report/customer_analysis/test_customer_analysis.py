# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for customer_analysis report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MODULE = "prakash_steel.prakash_steel.report.customer_analysis.customer_analysis"

_PERIOD = [(2025, 4), (2025, 5), (2025, 6)]


class TestCustomerAnalysisColumns(unittest.TestCase):
	def test_columns_count(self):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_columns
		cols = _get_columns(_PERIOD)
		# 1 group_name + 1 hbt + 3 month columns
		self.assertEqual(len(cols), 5)

	def test_first_column_is_group_name(self):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_columns
		cols = _get_columns(_PERIOD)
		self.assertEqual(cols[0]["fieldname"], "group_name")

	def test_month_column_labels(self):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_columns
		cols = _get_columns([(2025, 4)])
		self.assertIn("Apr", cols[2]["label"])
		self.assertIn("25", cols[2]["label"])

	def test_empty_period(self):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_columns
		cols = _get_columns([])
		self.assertEqual(len(cols), 2)  # group_name + hbt


class TestCustomerAnalysisData(unittest.TestCase):
	@patch(MODULE + ".get_customer_hbt_map", return_value={})
	@patch(MODULE + ".frappe")
	def test_aggregates_by_group_and_month(self, mock_frappe, _mock_hbt):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		mock_frappe.db.sql.return_value = [
			MagicMock(group_name="GroupA", yr=2025, mo=4, val=100.0),
			MagicMock(group_name="GroupA", yr=2025, mo=5, val=200.0),
			MagicMock(group_name="GroupB", yr=2025, mo=4, val=50.0),
		]
		result = _get_data({}, _PERIOD)
		self.assertEqual(len(result), 2)
		ga = next(r for r in result if r["group_name"] == "GroupA")
		self.assertAlmostEqual(ga["m_2025_04"], 100.0)
		self.assertAlmostEqual(ga["m_2025_05"], 200.0)
		self.assertAlmostEqual(ga["m_2025_06"], 0.0)

	@patch(MODULE + ".get_customer_hbt_map", return_value={})
	@patch(MODULE + ".frappe")
	def test_sorted_alphabetically(self, mock_frappe, _mock_hbt):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		mock_frappe.db.sql.return_value = [
			MagicMock(group_name="Zebra", yr=2025, mo=4, val=10.0),
			MagicMock(group_name="Alpha", yr=2025, mo=4, val=20.0),
		]
		result = _get_data({}, _PERIOD)
		self.assertEqual(result[0]["group_name"], "Alpha")
		self.assertEqual(result[1]["group_name"], "Zebra")

	@patch(MODULE + ".get_customer_hbt_map", return_value={})
	@patch(MODULE + ".frappe")
	def test_empty_result(self, mock_frappe, _mock_hbt):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		mock_frappe.db.sql.return_value = []
		result = _get_data({}, _PERIOD)
		self.assertEqual(result, [])

	@patch(MODULE + ".frappe")
	def test_empty_period_returns_empty(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		result = _get_data({}, [])
		mock_frappe.db.sql.assert_not_called()
		self.assertEqual(result, [])

	@patch(MODULE + ".frappe")
	def test_unsupported_view_throws(self, mock_frappe):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		mock_frappe.throw.side_effect = Exception("not implemented")
		with self.assertRaises(Exception):
			_get_data({"view_by": "Throughput"}, _PERIOD)

	@patch(MODULE + ".get_customer_hbt_map", return_value={})
	@patch(MODULE + ".frappe")
	def test_months_outside_period_ignored(self, mock_frappe, _mock_hbt):
		from prakash_steel.prakash_steel.report.customer_analysis.customer_analysis import _get_data
		mock_frappe.db.sql.return_value = [
			MagicMock(group_name="GroupA", yr=2025, mo=1, val=999.0),  # January not in period
			MagicMock(group_name="GroupA", yr=2025, mo=4, val=50.0),
		]
		result = _get_data({}, _PERIOD)
		self.assertAlmostEqual(result[0]["m_2025_04"], 50.0)


if __name__ == "__main__":
	unittest.main()
