# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for custom_sales_partner_commission_summary — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.custom_sales_partner_commission_summary.custom_sales_partner_commission_summary"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_requires_doctype_filter(self, mock_frappe):
        from prakash_steel.prakash_steel.report.custom_sales_partner_commission_summary.custom_sales_partner_commission_summary import get_columns
        mock_frappe.throw.side_effect = Exception("doctype required")
        with self.assertRaises(Exception):
            get_columns({})  # no doctype

    @patch(MOD + ".frappe")
    def test_returns_columns_when_doctype_set(self, mock_frappe):
        from prakash_steel.prakash_steel.report.custom_sales_partner_commission_summary.custom_sales_partner_commission_summary import get_columns
        mock_frappe.throw.side_effect = None
        cols = get_columns({"doctype": "Sales Invoice"})
        self.assertIsInstance(cols, list)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.custom_sales_partner_commission_summary.custom_sales_partner_commission_summary import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.throw.side_effect = None
        cols, data = execute({"doctype": "Sales Invoice"})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
