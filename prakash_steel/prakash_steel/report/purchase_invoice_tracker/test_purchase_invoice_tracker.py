# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for purchase_invoice_tracker report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker"


class TestGetColumns(unittest.TestCase):
    def test_returns_required_fields(self):
        from prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("purchase_invoice_id", "status", "quantity", "date", "supplier", "grand_total"):
            self.assertIn(f, fieldnames)


class TestGetData(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_default_dates_applied_when_missing(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker import get_data
        mock_frappe.db.sql.return_value = []
        filters = {}
        get_data(filters)
        self.assertEqual(filters["from_date"], "2020-01-01")
        self.assertEqual(filters["to_date"], "2030-12-31")

    @patch(MOD + ".frappe")
    def test_returns_list(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker import get_data
        mock_frappe.db.sql.return_value = [{"purchase_invoice_id": "PI-0001", "status": "Unpaid"}]
        result = get_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        self.assertEqual(len(result), 1)

    @patch(MOD + ".frappe")
    def test_supplier_filter_respected(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"from_date": "2026-01-01", "to_date": "2026-12-31", "supplier": "SUP-001"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("supplier", query)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_invoice_tracker.purchase_invoice_tracker import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
