# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for planning_engine_sales_invoice report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.planning_engine_sales_invoice.planning_engine_sales_invoice"


class TestMonthMap(unittest.TestCase):
    def test_all_months_mapped(self):
        from prakash_steel.prakash_steel.report.planning_engine_sales_invoice.planning_engine_sales_invoice import MONTH_MAP
        self.assertEqual(len(MONTH_MAP), 12)
        self.assertEqual(MONTH_MAP["January"], 1)
        self.assertEqual(MONTH_MAP["December"], 12)
        self.assertEqual(MONTH_MAP["April"], 4)

    def test_april_is_4(self):
        from prakash_steel.prakash_steel.report.planning_engine_sales_invoice.planning_engine_sales_invoice import MONTH_MAP
        self.assertEqual(MONTH_MAP["April"], 4)


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.planning_engine_sales_invoice.planning_engine_sales_invoice import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        self.assertIn("invoice_month", fieldnames)
        self.assertIn("invoice_date", fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.planning_engine_sales_invoice.planning_engine_sales_invoice import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
