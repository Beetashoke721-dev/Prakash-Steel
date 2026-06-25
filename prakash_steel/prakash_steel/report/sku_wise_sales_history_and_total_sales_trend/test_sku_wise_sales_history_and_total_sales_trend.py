# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for sku_wise_sales_history_and_total_sales_trend — no DB required."""

import unittest
from unittest.mock import patch
from datetime import date

MOD = "prakash_steel.prakash_steel.report.sku_wise_sales_history_and_total_sales_trend.sku_wise_sales_history_and_total_sales_trend"


class TestGetColumns(unittest.TestCase):
    def test_monthly_columns_generated(self):
        from prakash_steel.prakash_steel.report.sku_wise_sales_history_and_total_sales_trend.sku_wise_sales_history_and_total_sales_trend import get_columns
        cols = get_columns(date(2026, 1, 1), date(2026, 3, 31), "Monthly")
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("item_code", fieldnames)
        # Should have at least item_code + 3 months
        self.assertGreaterEqual(len(cols), 4)

    def test_item_code_is_first_column(self):
        from prakash_steel.prakash_steel.report.sku_wise_sales_history_and_total_sales_trend.sku_wise_sales_history_and_total_sales_trend import get_columns
        cols = get_columns(date(2026, 1, 1), date(2026, 1, 31), "Monthly")
        self.assertEqual(cols[0]["fieldname"], "item_code")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_empty_when_no_allowed_customers(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sku_wise_sales_history_and_total_sales_trend.sku_wise_sales_history_and_total_sales_trend import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        mock_frappe.session.user = "test@example.com"
        mock_frappe.utils.getdate.side_effect = lambda x: x
        filters = {"from_date": date(2026, 1, 1), "to_date": date(2026, 3, 31), "calculation_mode": "Monthly"}
        result = execute(filters)
        self.assertIsInstance(result, tuple)


if __name__ == "__main__":
    unittest.main()
