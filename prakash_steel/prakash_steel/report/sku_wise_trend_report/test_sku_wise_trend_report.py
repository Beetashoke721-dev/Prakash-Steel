# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for sku_wise_trend_report — no DB required."""

import unittest
from unittest.mock import patch
from datetime import date

MOD = "prakash_steel.prakash_steel.report.sku_wise_trend_report.sku_wise_trend_report"


class TestCalculateSkuType(unittest.TestCase):
    """Pure function — no mocking needed."""

    def _run(self, buffer_flag, item_type):
        from prakash_steel.prakash_steel.report.sku_wise_trend_report.sku_wise_trend_report import calculate_sku_type
        return calculate_sku_type(buffer_flag, item_type)

    def test_bb_buffer(self):      self.assertEqual(self._run("Buffer", "BB"), "BBMTA")
    def test_bb_non_buffer(self):  self.assertEqual(self._run("Non-Buffer", "BB"), "BBMTO")
    def test_rb_buffer(self):      self.assertEqual(self._run("Buffer", "RB"), "RBMTA")
    def test_rb_non_buffer(self):  self.assertEqual(self._run("Non-Buffer", "RB"), "RBMTO")
    def test_bo_buffer(self):      self.assertEqual(self._run("Buffer", "BO"), "BOTA")
    def test_rm_buffer(self):      self.assertEqual(self._run("Buffer", "RM"), "PTA")
    def test_rm_non_buffer(self):  self.assertEqual(self._run("Non-Buffer", "RM"), "PTO")
    def test_traded_buffer(self):  self.assertEqual(self._run("Buffer", "Traded"), "TRMTA")
    def test_no_item_type(self):   self.assertIsNone(self._run("Buffer", None))
    def test_unknown_type(self):   self.assertIsNone(self._run("Buffer", "UNKNOWN"))


class TestGetColumns(unittest.TestCase):
    def test_requires_filters(self):
        from prakash_steel.prakash_steel.report.sku_wise_trend_report.sku_wise_trend_report import execute
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])

    def test_with_sku_type_filter_returns_columns(self):
        from prakash_steel.prakash_steel.report.sku_wise_trend_report.sku_wise_trend_report import get_columns
        cols = get_columns(date(2026, 1, 1), date(2026, 1, 3))
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("item_name", fieldnames)
        # date columns should be generated
        self.assertIn("date_2026_01_01", fieldnames)
        self.assertIn("date_2026_01_02", fieldnames)
        self.assertIn("date_2026_01_03", fieldnames)

    def test_single_day_range(self):
        from prakash_steel.prakash_steel.report.sku_wise_trend_report.sku_wise_trend_report import get_columns
        cols = get_columns(date(2026, 6, 1), date(2026, 6, 1))
        self.assertEqual(len(cols), 2)  # item_name + 1 date


if __name__ == "__main__":
    unittest.main()
