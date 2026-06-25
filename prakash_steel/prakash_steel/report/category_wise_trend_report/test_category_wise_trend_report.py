# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for category_wise_trend_report — no DB required."""

import unittest
from datetime import date

MOD = "prakash_steel.prakash_steel.report.category_wise_trend_report.category_wise_trend_report"


class TestCalculateSkuType(unittest.TestCase):
    def _run(self, buffer_flag, item_type):
        from prakash_steel.prakash_steel.report.category_wise_trend_report.category_wise_trend_report import calculate_sku_type
        return calculate_sku_type(buffer_flag, item_type)

    def test_bb_buffer(self):     self.assertEqual(self._run("Buffer", "BB"), "BBMTA")
    def test_bb_non_buffer(self): self.assertEqual(self._run("Non-Buffer", "BB"), "BBMTO")
    def test_rb_buffer(self):     self.assertEqual(self._run("Buffer", "RB"), "RBMTA")
    def test_bo_non_buffer(self): self.assertEqual(self._run("Non-Buffer", "BO"), "BOTO")
    def test_rm_non_buffer(self): self.assertEqual(self._run("Non-Buffer", "RM"), "PTO")
    def test_traded_non_buffer(self): self.assertEqual(self._run("Non-Buffer", "Traded"), "TRMTO")
    def test_none_type(self):     self.assertIsNone(self._run("Buffer", None))


class TestGetColumns(unittest.TestCase):
    def test_includes_category_and_date_columns(self):
        from prakash_steel.prakash_steel.report.category_wise_trend_report.category_wise_trend_report import get_columns
        cols = get_columns(date(2026, 4, 1), date(2026, 4, 2), "BBMTA")
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("category", fieldnames)
        self.assertIn("date_2026_04_01", fieldnames)
        self.assertIn("date_2026_04_02", fieldnames)

    def test_label_contains_sku_type(self):
        from prakash_steel.prakash_steel.report.category_wise_trend_report.category_wise_trend_report import get_columns
        cols = get_columns(date(2026, 1, 1), date(2026, 1, 1), "BBMTO")
        self.assertIn("BBMTO", cols[0]["label"])


class TestExecute(unittest.TestCase):
    def test_missing_filters_returns_empty(self):
        from prakash_steel.prakash_steel.report.category_wise_trend_report.category_wise_trend_report import execute
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
