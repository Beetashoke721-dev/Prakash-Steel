# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for otif_report report — no DB required."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.otif_report.otif_report"


class TestGetColumns(unittest.TestCase):
	def test_returns_list_with_fieldnames(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_columns

		cols = get_columns()
		self.assertIsInstance(cols, list)
		self.assertGreater(len(cols), 0)
		for col in cols:
			self.assertIn("fieldname", col)
			self.assertIn("label", col)
			self.assertIn("fieldtype", col)

	def test_includes_otif_fieldnames(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_columns

		fieldnames = {col["fieldname"] for col in get_columns()}
		self.assertIn("line_otif", fieldnames)
		self.assertIn("order_otif", fieldnames)
		self.assertIn("line_percentage", fieldnames)
		self.assertIn("order_percentage", fieldnames)


class TestExecute(unittest.TestCase):
	@patch(MOD + ".frappe")
	def test_returns_tuple(self, mock_frappe):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import execute

		mock_frappe.db.sql.return_value = []
		mock_frappe.db.get_single_value.return_value = "Monday"
		mock_frappe.get_all.return_value = []
		mock_frappe.get_cached_doc.return_value = MagicMock(
			delivered_qty_tolerance=0, delivery_date_tolerance=0
		)
		cols, data = execute({})
		self.assertIsInstance(cols, list)
		self.assertIsInstance(data, list)

	@patch(MOD + ".frappe")
	def test_execute_adds_week_and_percentage_columns(self, mock_frappe):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import execute

		mock_frappe.db.sql.return_value = [
			{
				"so_detail": "SOI-1",
				"delivery_date": date(2026, 4, 5),
				"order_date": date(2026, 4, 1),
				"book_value": 1000,
				"sales_value": 1000,
				"line_otif": 100,
				"order_otif": 100,
			}
		]
		mock_frappe.db.get_single_value.return_value = "Monday"
		mock_frappe.get_all.return_value = [
			{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)}
		]
		mock_frappe.get_cached_doc.return_value = MagicMock(
			delivered_qty_tolerance=0, delivery_date_tolerance=0
		)
		cols, data = execute({})
		self.assertEqual(data[0]["week"], "1-26")
		self.assertEqual(data[0]["booking_week"], "1-26")
		self.assertEqual(data[0]["line_percentage"], 100)
		self.assertEqual(data[0]["order_percentage"], 100)


class TestGetWeekLabel(unittest.TestCase):
	def test_none_delivery_date_returns_none(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		self.assertIsNone(get_week_label(None, "Monday", []))

	def test_no_matching_fiscal_year_returns_none(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		fiscal_years = [{"year_start_date": date(2025, 4, 1), "year_end_date": date(2026, 3, 31)}]
		self.assertIsNone(get_week_label(date(2026, 5, 1), "Monday", fiscal_years))

	def test_first_week_when_fy_start_matches_week_start_day(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		# 2026-04-01 is a Wednesday; fiscal year starts on that weekday.
		fiscal_years = [{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)}]
		self.assertEqual(get_week_label(date(2026, 4, 1), "Wednesday", fiscal_years), "1-26")
		self.assertEqual(get_week_label(date(2026, 4, 7), "Wednesday", fiscal_years), "1-26")

	def test_second_week_rolls_over_after_seven_days(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		fiscal_years = [{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)}]
		self.assertEqual(get_week_label(date(2026, 4, 8), "Wednesday", fiscal_years), "2-26")

	def test_offset_when_week_start_day_differs_from_fy_start_weekday(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		# FY starts Wednesday 2026-04-01, but weeks are configured to start Monday.
		# offset = (2 - 0) % 7 = 2, so week 1 covers the 5 days 2026-04-01..04-05
		# before rolling into week 2 on 2026-04-06.
		fiscal_years = [{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)}]
		self.assertEqual(get_week_label(date(2026, 4, 1), "Monday", fiscal_years), "1-26")
		self.assertEqual(get_week_label(date(2026, 4, 5), "Monday", fiscal_years), "1-26")
		self.assertEqual(get_week_label(date(2026, 4, 6), "Monday", fiscal_years), "2-26")

	def test_picks_correct_fiscal_year_among_several(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_label

		fiscal_years = [
			{"year_start_date": date(2025, 4, 1), "year_end_date": date(2026, 3, 31)},
			{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)},
		]
		label = get_week_label(date(2026, 4, 1), "Wednesday", fiscal_years)
		self.assertEqual(label, "1-26")


class TestFindFiscalYearStart(unittest.TestCase):
	def test_returns_none_for_empty_list(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _find_fiscal_year_start

		self.assertIsNone(_find_fiscal_year_start(date(2026, 1, 1), []))

	def test_returns_start_date_of_matching_year(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _find_fiscal_year_start

		fiscal_years = [
			{"year_start_date": date(2025, 4, 1), "year_end_date": date(2026, 3, 31)},
			{"year_start_date": date(2026, 4, 1), "year_end_date": date(2027, 3, 31)},
		]
		self.assertEqual(
			_find_fiscal_year_start(date(2026, 2, 1), fiscal_years), date(2025, 4, 1)
		)
		self.assertEqual(
			_find_fiscal_year_start(date(2026, 5, 1), fiscal_years), date(2026, 4, 1)
		)

	def test_returns_none_when_date_outside_all_ranges(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _find_fiscal_year_start

		fiscal_years = [{"year_start_date": date(2025, 4, 1), "year_end_date": date(2026, 3, 31)}]
		self.assertIsNone(_find_fiscal_year_start(date(2024, 1, 1), fiscal_years))


class TestWeekTotals(unittest.TestCase):
	def test_sums_book_value_per_week(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _week_totals

		data = [
			{"week": "1-26", "book_value": 100, "sales_value": 100, "line_otif": 100, "order_otif": 100},
			{"week": "1-26", "book_value": 200, "sales_value": 0, "line_otif": 0, "order_otif": 0},
		]
		totals = _week_totals(data)
		self.assertEqual(totals["1-26"]["all"], 300)
		self.assertEqual(totals["1-26"]["line"], 100)
		self.assertEqual(totals["1-26"]["order"], 100)

	def test_only_counts_sales_value_when_otif_is_100(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _week_totals

		data = [
			{"week": "2-26", "book_value": 50, "sales_value": 50, "line_otif": 0, "order_otif": 100},
		]
		totals = _week_totals(data)
		self.assertEqual(totals["2-26"]["line"], 0)
		self.assertEqual(totals["2-26"]["order"], 50)

	def test_separates_buckets_by_week(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _week_totals

		data = [
			{"week": "1-26", "book_value": 100, "sales_value": 100, "line_otif": 100, "order_otif": 100},
			{"week": "2-26", "book_value": 50, "sales_value": 50, "line_otif": 100, "order_otif": 100},
		]
		totals = _week_totals(data)
		self.assertEqual(set(totals.keys()), {"1-26", "2-26"})
		self.assertEqual(totals["1-26"]["all"], 100)
		self.assertEqual(totals["2-26"]["all"], 50)

	def test_missing_values_treated_as_zero(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import _week_totals

		data = [{"week": "1-26"}]
		totals = _week_totals(data)
		self.assertEqual(totals["1-26"], {"all": 0.0, "line": 0.0, "order": 0.0})


class TestAddWeekPercentages(unittest.TestCase):
	def test_computes_percentages_against_week_total(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import add_week_percentages

		data = [
			{"week": "1-26", "book_value": 100, "sales_value": 100, "line_otif": 100, "order_otif": 0},
			{"week": "1-26", "book_value": 100, "sales_value": 0, "line_otif": 0, "order_otif": 0},
		]
		add_week_percentages(data)
		self.assertEqual(data[0]["line_percentage"], 50)
		self.assertEqual(data[0]["order_percentage"], 0)
		# Both rows share the same week bucket, so they get the same percentage.
		self.assertEqual(data[1]["line_percentage"], 50)

	def test_zero_total_gives_zero_percentage(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import add_week_percentages

		data = [{"week": "1-26", "book_value": 0, "sales_value": 0, "line_otif": 0, "order_otif": 0}]
		add_week_percentages(data)
		self.assertEqual(data[0]["line_percentage"], 0)
		self.assertEqual(data[0]["order_percentage"], 0)

	def test_rounds_to_two_decimal_places(self):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import add_week_percentages

		data = [
			{"week": "1-26", "book_value": 3, "sales_value": 1, "line_otif": 100, "order_otif": 100},
			{"week": "1-26", "book_value": 3, "sales_value": 3, "line_otif": 0, "order_otif": 0},
		]
		add_week_percentages(data)
		# line total = 1 (only row0 has line_otif == 100), week total = 3 + 3 = 6.
		self.assertEqual(data[0]["line_percentage"], round(1 / 6 * 100, 2))


class TestGetWeekBreakdown(unittest.TestCase):
	@patch(MOD + ".get_data")
	@patch(MOD + ".frappe")
	def test_filters_rows_to_requested_week(self, mock_frappe, mock_get_data):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_breakdown

		mock_frappe.parse_json.return_value = {}
		mock_frappe.db.sql.return_value = []
		mock_get_data.return_value = [
			{
				"week": "1-26",
				"so_detail": "SOI-1",
				"book_value": 100,
				"sales_value": 100,
				"line_otif": 100,
				"order_otif": 100,
				"line_percentage": 100,
				"order_percentage": 100,
			},
			{
				"week": "2-26",
				"so_detail": "SOI-2",
				"book_value": 50,
				"sales_value": 50,
				"line_otif": 100,
				"order_otif": 100,
				"line_percentage": 100,
				"order_percentage": 100,
			},
		]
		result = get_week_breakdown(filters="{}", week="1-26")
		self.assertEqual(result["week"], "1-26")
		self.assertEqual(len(result["rows"]), 1)
		self.assertEqual(result["rows"][0]["sales_order_number"], None)
		self.assertEqual(result["book_total"], 100)

	@patch(MOD + ".get_data")
	@patch(MOD + ".frappe")
	def test_no_matching_rows_returns_zero_totals(self, mock_frappe, mock_get_data):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_breakdown

		mock_frappe.parse_json.return_value = {}
		mock_get_data.return_value = []
		result = get_week_breakdown(filters="{}", week="9-26")
		self.assertEqual(result["rows"], [])
		self.assertEqual(result["book_total"], 0.0)
		self.assertEqual(result["line_percentage"], 0)
		self.assertEqual(result["order_percentage"], 0)

	@patch(MOD + ".get_data")
	@patch(MOD + ".frappe")
	def test_checks_permission_before_reading(self, mock_frappe, mock_get_data):
		from prakash_steel.prakash_steel.report.otif_report.otif_report import get_week_breakdown

		mock_frappe.parse_json.return_value = {}
		mock_get_data.return_value = []
		get_week_breakdown(filters="{}", week="1-26")
		mock_frappe.has_permission.assert_called_once_with("Sales Order", "read", throw=True)


if __name__ == "__main__":
	unittest.main()
