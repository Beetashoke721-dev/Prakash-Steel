# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bright_bar_sales_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.bright_bar_sales_report.bright_bar_sales_report"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.bright_bar_sales_report.bright_bar_sales_report import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("month", "date", "id", "customer", "item_code"):
            self.assertIn(f, fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_columns_and_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bright_bar_sales_report.bright_bar_sales_report import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_date_filter_applied(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bright_bar_sales_report.bright_bar_sales_report import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("posting_date", query)


if __name__ == "__main__":
    unittest.main()
