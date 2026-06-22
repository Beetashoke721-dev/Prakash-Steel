# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for prakash_steel/utils/hbt_utils.py — no DB required."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

MODULE = "prakash_steel.utils.hbt_utils"


class TestMonthKey(unittest.TestCase):
	def test_zero_padded(self):
		from prakash_steel.utils.hbt_utils import month_key
		self.assertEqual(month_key(2025, 4), "m_2025_04")

	def test_double_digit(self):
		from prakash_steel.utils.hbt_utils import month_key
		self.assertEqual(month_key(2025, 12), "m_2025_12")

	def test_january(self):
		from prakash_steel.utils.hbt_utils import month_key
		self.assertEqual(month_key(2026, 1), "m_2026_01")


class TestPeriodDateRange(unittest.TestCase):
	def test_single_month(self):
		from prakash_steel.utils.hbt_utils import period_date_range
		from_d, to_d = period_date_range([(2025, 6)])
		self.assertEqual(from_d, date(2025, 6, 1))
		self.assertEqual(to_d, date(2025, 6, 30))

	def test_span(self):
		from prakash_steel.utils.hbt_utils import period_date_range
		from_d, to_d = period_date_range([(2025, 4), (2025, 5), (2025, 6)])
		self.assertEqual(from_d, date(2025, 4, 1))
		self.assertEqual(to_d, date(2025, 6, 30))

	def test_february_non_leap(self):
		from prakash_steel.utils.hbt_utils import period_date_range
		_, to_d = period_date_range([(2025, 2)])
		self.assertEqual(to_d, date(2025, 2, 28))

	def test_february_leap(self):
		from prakash_steel.utils.hbt_utils import period_date_range
		_, to_d = period_date_range([(2024, 2)])
		self.assertEqual(to_d, date(2024, 2, 29))


class TestAssignHbtLabels(unittest.TestCase):
	def test_empty(self):
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		result = assign_hbt_labels([])
		self.assertEqual(result, [])

	def test_single_row_is_h(self):
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		rows = [{"total": 100.0}]
		assign_hbt_labels(rows)
		self.assertEqual(rows[0]["hbt"], "H")
		self.assertAlmostEqual(rows[0]["contr_pct"], 100.0)
		self.assertAlmostEqual(rows[0]["cumu_pct"], 100.0)

	def test_grand_total_zero(self):
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		rows = [{"total": 0.0}, {"total": 0.0}]
		assign_hbt_labels(rows)
		for row in rows:
			self.assertAlmostEqual(row["contr_pct"], 0.0)
		self.assertEqual(rows[0]["hbt"], "H")

	def test_h_b_t_boundaries(self):
		"""50 rows of 2% each: first 25 = H (50%), next 20 = B (40%), last 5 = T"""
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		rows = [{"total": 2.0} for _ in range(50)]
		assign_hbt_labels(rows)
		h_count = sum(1 for r in rows if r["hbt"] == "H")
		b_count = sum(1 for r in rows if r["hbt"] == "B")
		t_count = sum(1 for r in rows if r["hbt"] == "T")
		self.assertEqual(h_count, 25)
		self.assertEqual(b_count, 20)
		self.assertEqual(t_count, 5)

	def test_custom_total_key(self):
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		rows = [{"total_value": 80.0}, {"total_value": 20.0}]
		assign_hbt_labels(rows, total_key="total_value")
		self.assertAlmostEqual(rows[0]["contr_pct"], 80.0)
		self.assertAlmostEqual(rows[1]["contr_pct"], 20.0)

	def test_returns_rows(self):
		from prakash_steel.utils.hbt_utils import assign_hbt_labels
		rows = [{"total": 10.0}]
		result = assign_hbt_labels(rows)
		self.assertIs(result, rows)


class TestGetPeriodMonths(unittest.TestCase):
	def _make_settings(self, fiscal_year="FY 2025-2026", from_month="April", to_month="September"):
		s = MagicMock()
		s.fiscal_year = fiscal_year
		s.from_month = from_month
		s.to_month = to_month
		return s

	def _make_fy_doc(self, start="2025-04-01", end="2026-03-31"):
		doc = MagicMock()
		doc.year_start_date = start
		doc.year_end_date = end
		return doc

	@patch(MODULE + ".frappe")
	def test_april_to_september(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_period_months
		mock_frappe.get_single.return_value = self._make_settings("FY 2025-2026", "April", "September")
		mock_frappe.get_doc.return_value = self._make_fy_doc()
		result = get_period_months()
		self.assertEqual(result, [(2025, 4), (2025, 5), (2025, 6), (2025, 7), (2025, 8), (2025, 9)])

	@patch(MODULE + ".frappe")
	def test_january_to_march_maps_to_end_year(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_period_months
		mock_frappe.get_single.return_value = self._make_settings("FY 2025-2026", "January", "March")
		mock_frappe.get_doc.return_value = self._make_fy_doc()
		result = get_period_months()
		self.assertEqual(result, [(2026, 1), (2026, 2), (2026, 3)])

	@patch(MODULE + ".frappe")
	def test_missing_settings_throws(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_period_months
		s = MagicMock()
		s.fiscal_year = None
		s.from_month = "April"
		s.to_month = "September"
		mock_frappe.get_single.return_value = s
		mock_frappe.throw.side_effect = Exception("Missing config")
		with self.assertRaises(Exception):
			get_period_months()

	@patch(MODULE + ".frappe")
	def test_from_after_to_throws(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_period_months
		mock_frappe.get_single.return_value = self._make_settings("FY 2025-2026", "October", "April")
		mock_frappe.get_doc.return_value = self._make_fy_doc()
		mock_frappe.throw.side_effect = Exception("Invalid range")
		with self.assertRaises(Exception):
			get_period_months()


class TestGetCustomerHbtMap(unittest.TestCase):
	@patch(MODULE + ".frappe")
	def test_returns_correct_buckets(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_customer_hbt_map
		mock_frappe.db.sql.return_value = [
			{"group_name": "Alpha", "total": 60.0},
			{"group_name": "Beta", "total": 30.0},
			{"group_name": "Gamma", "total": 10.0},
		]
		result = get_customer_hbt_map(date(2025, 4, 1), date(2025, 9, 30), "sii.qty")
		self.assertEqual(result["Alpha"], "H")
		self.assertEqual(result["Beta"], "B")
		self.assertEqual(result["Gamma"], "T")

	@patch(MODULE + ".frappe")
	def test_empty_returns_empty(self, mock_frappe):
		from prakash_steel.utils.hbt_utils import get_customer_hbt_map
		mock_frappe.db.sql.return_value = []
		result = get_customer_hbt_map(date(2025, 4, 1), date(2025, 9, 30), "sii.qty")
		self.assertEqual(result, {})


if __name__ == "__main__":
	unittest.main()
