# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Unit tests for bright_production_analysis report.

Pure logic tests (no DB) use unittest.TestCase with mocked frappe calls.
Run with:
  bench run-tests --app prakash_steel --module \
    prakash_steel.prakash_steel.report.bright_production_analysis.test_bright_production_analysis
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.bright_production_analysis.bright_production_analysis"


def _import():
	import prakash_steel.prakash_steel.report.bright_production_analysis.bright_production_analysis as m

	return m


# ---------------------------------------------------------------------------
# _month_key
# ---------------------------------------------------------------------------


class TestMonthKey(unittest.TestCase):
	def setUp(self):
		self.fn = _import()._month_key

	def test_single_digit_month_is_zero_padded(self):
		self.assertEqual(self.fn(2025, 6), "m_2025_06")

	def test_double_digit_month(self):
		self.assertEqual(self.fn(2025, 12), "m_2025_12")

	def test_january_cross_year(self):
		self.assertEqual(self.fn(2026, 1), "m_2026_01")

	def test_april_start_of_fiscal(self):
		self.assertEqual(self.fn(2025, 4), "m_2025_04")


# ---------------------------------------------------------------------------
# Constants integrity
# ---------------------------------------------------------------------------


class TestConstants(unittest.TestCase):
	def setUp(self):
		self.mod = _import()

	def test_fiscal_month_order_has_12_months(self):
		self.assertEqual(len(self.mod._FISCAL_MONTH_ORDER), 12)

	def test_fiscal_month_order_starts_with_april(self):
		self.assertEqual(self.mod._FISCAL_MONTH_ORDER[0], 4)

	def test_fiscal_month_order_ends_with_march(self):
		self.assertEqual(self.mod._FISCAL_MONTH_ORDER[-1], 3)

	def test_month_to_num_covers_all_12_months(self):
		self.assertEqual(len(self.mod._MONTH_TO_NUM), 12)
		self.assertEqual(set(self.mod._MONTH_TO_NUM.values()), set(range(1, 13)))

	def test_month_short_covers_all_12_months(self):
		self.assertEqual(len(self.mod._MONTH_SHORT), 12)
		self.assertEqual(set(self.mod._MONTH_SHORT.keys()), set(range(1, 13)))

	def test_metric_col_has_sale_quantity_and_sale_value(self):
		self.assertIn("Sale Quantity", self.mod._METRIC_COL)
		self.assertIn("Sale Value", self.mod._METRIC_COL)

	def test_metric_col_values_reference_correct_columns(self):
		self.assertEqual(self.mod._METRIC_COL["Sale Quantity"], "sii.qty")
		self.assertEqual(self.mod._METRIC_COL["Sale Value"], "sii.amount")


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
# _get_period_months (mocked frappe)
# ---------------------------------------------------------------------------


def _make_fy_doc(start_year: int, end_year: int):
	"""Build a minimal Fiscal Year doc mock."""
	doc = MagicMock()
	doc.year_start_date = f"{start_year}-04-01"
	doc.year_end_date = f"{end_year}-03-31"
	return doc


def _make_settings(fiscal_year, from_month, to_month):
	s = MagicMock()
	s.fiscal_year = fiscal_year
	s.from_month = from_month
	s.to_month = to_month
	return s


class TestGetPeriodMonths(unittest.TestCase):
	def _call(self, fiscal_year, from_month, to_month):
		fn = _import()._get_period_months
		with (
			patch(f"{MOD}.frappe.get_single", return_value=_make_settings(fiscal_year, from_month, to_month)),
			patch(f"{MOD}.frappe.get_doc", return_value=_make_fy_doc(2025, 2026)),
			patch(f"{MOD}.frappe.throw") as mock_throw,
			patch(f"{MOD}.getdate", side_effect=lambda d: __import__("frappe.utils", fromlist=["getdate"]) and __import__("datetime").date.fromisoformat(str(d))),
		):
			result = fn()
		return result

	def _call_with_getdate(self, fiscal_year, from_month, to_month, start_year=2025, end_year=2026):
		from datetime import date as _date

		fn = _import()._get_period_months

		def fake_getdate(d):
			ns = SimpleNamespace()
			ns.year = int(str(d).split("-")[0])
			return ns

		with (
			patch(f"{MOD}.frappe.get_single", return_value=_make_settings(fiscal_year, from_month, to_month)),
			patch(f"{MOD}.frappe.get_doc", return_value=_make_fy_doc(start_year, end_year)),
			patch(f"{MOD}.getdate", side_effect=fake_getdate),
		):
			return fn()

	def test_mid_year_range_all_in_start_year(self):
		result = self._call_with_getdate("2025-2026", "June", "August")
		self.assertEqual(result, [(2025, 6), (2025, 7), (2025, 8)])

	def test_single_month(self):
		result = self._call_with_getdate("2025-2026", "April", "April")
		self.assertEqual(result, [(2025, 4)])

	def test_cross_year_range(self):
		result = self._call_with_getdate("2025-2026", "November", "February")
		self.assertEqual(result, [(2025, 11), (2025, 12), (2026, 1), (2026, 2)])

	def test_full_fiscal_year(self):
		result = self._call_with_getdate("2025-2026", "April", "March")
		self.assertEqual(len(result), 12)
		self.assertEqual(result[0], (2025, 4))
		self.assertEqual(result[-1], (2026, 3))

	def test_jan_to_march_all_in_end_year(self):
		result = self._call_with_getdate("2025-2026", "January", "March")
		self.assertEqual(result, [(2026, 1), (2026, 2), (2026, 3)])

	def test_missing_settings_calls_throw(self):
		"""When fiscal_year is missing, frappe.throw must be called and halt execution."""
		fn = _import()._get_period_months
		with (
			patch(f"{MOD}.frappe.get_single", return_value=_make_settings(None, "June", "August")),
			patch(f"{MOD}.frappe.throw", side_effect=Exception("throw")) as mock_throw,
		):
			with self.assertRaises(Exception):
				fn()
			mock_throw.assert_called_once()

	def test_reversed_months_calls_throw(self):
		"""August before June in fiscal order → invalid range."""
		fn = _import()._get_period_months

		def fake_getdate(d):
			ns = SimpleNamespace()
			ns.year = int(str(d).split("-")[0])
			return ns

		with (
			patch(f"{MOD}.frappe.get_single", return_value=_make_settings("2025-2026", "August", "June")),
			patch(f"{MOD}.frappe.get_doc", return_value=_make_fy_doc(2025, 2026)),
			patch(f"{MOD}.getdate", side_effect=fake_getdate),
			patch(f"{MOD}.frappe.throw") as mock_throw,
		):
			fn()
			mock_throw.assert_called_once()


# ---------------------------------------------------------------------------
# _get_data — pivot logic (mocked frappe.db.sql)
# ---------------------------------------------------------------------------


class TestGetData(unittest.TestCase):
	def _call(self, filters, period_months, sql_rows):
		fn = _import()._get_data
		with patch(f"{MOD}.frappe.db.sql", return_value=sql_rows):
			return fn(filters, period_months)

	# --- early exits ---

	def test_empty_period_months_returns_empty(self):
		result = _import()._get_data({}, [])
		self.assertEqual(result, [])

	def test_throughput_returns_empty(self):
		result = _import()._get_data({"view_by": "Throughput"}, [(2025, 6)])
		self.assertEqual(result, [])

	# --- Sale Quantity pivot ---

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
		"""A DB row with yr/mo outside the requested period should be ignored."""
		period = [(2025, 6)]
		rows = [
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=6, val=10.0),
			SimpleNamespace(item_code="ITEM-001", yr=2025, mo=9, val=99.0),  # not in period
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
		"""No view_by in filters should default to Sale Quantity (no throw)."""
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

	def test_unknown_view_by_calls_frappe_throw(self):
		fn = _import()._get_data
		with (
			patch(f"{MOD}.frappe.throw") as mock_throw,
			patch(f"{MOD}.frappe.db.sql", return_value=[]),
		):
			fn({"view_by": "Nonsense"}, [(2025, 6)])
			mock_throw.assert_called_once()


if __name__ == "__main__":
	unittest.main()
