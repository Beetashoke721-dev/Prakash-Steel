# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for purchase_weight_variance report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.purchase_weight_variance.purchase_weight_variance"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.purchase_weight_variance.purchase_weight_variance import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("po_no", "item_code", "po_qty", "received_qty", "weight_variation", "weight_variation_pct"):
            self.assertIn(f, fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_weight_variance.purchase_weight_variance import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.utils.getdate.side_effect = lambda x: x
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_date_filter_applied(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_weight_variance.purchase_weight_variance import get_data
        mock_frappe.db.sql.return_value = []
        mock_frappe.utils.getdate.side_effect = lambda x: x
        get_data({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("transaction_date", query)

    @patch(MOD + ".frappe")
    def test_supplier_filter_applied(self, mock_frappe):
        from prakash_steel.prakash_steel.report.purchase_weight_variance.purchase_weight_variance import get_data
        mock_frappe.db.sql.return_value = []
        mock_frappe.utils.getdate.side_effect = lambda x: x
        get_data({"supplier": "SUP-001"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("supplier", query)


if __name__ == "__main__":
    unittest.main()
