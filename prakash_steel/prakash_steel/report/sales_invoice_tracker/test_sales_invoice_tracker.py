# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for sales_invoice_tracker report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("sales_invoice", "posting_date", "customer", "item_code", "qty", "grand_total"):
            self.assertIn(f, fieldnames)


class TestGetData(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_default_dates_applied_when_missing(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker import get_data
        mock_frappe.utils.today.return_value = "2026-06-25"
        mock_frappe.utils.add_months.return_value = "2026-05-25"
        mock_frappe.db.sql.return_value = []
        filters = {}
        get_data(filters)
        self.assertIn("from_date", filters)
        self.assertIn("to_date", filters)

    @patch(MOD + ".frappe")
    def test_customer_filter_added_to_query(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"from_date": "2026-01-01", "to_date": "2026-12-31", "customer": "CUST-001"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("customer", query)

    @patch(MOD + ".frappe")
    def test_returns_list(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker import get_data
        mock_frappe.db.sql.return_value = [{"sales_invoice": "SI-0001", "qty": 100}]
        result = get_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        self.assertEqual(len(result), 1)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sales_invoice_tracker.sales_invoice_tracker import execute
        mock_frappe.utils.today.return_value = "2026-06-25"
        mock_frappe.utils.add_months.return_value = "2026-05-25"
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
