# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for missing_bom_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.missing_bom_report.missing_bom_report"


class TestExecute(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_returns_columns_and_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.missing_bom_report.missing_bom_report import execute
        mock_frappe.db.sql.return_value = [
            {"item_code": "BB-10MM", "item_name": "Bright Bar 10mm", "item_type": "BB"}
        ]
        cols, data = execute()
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_columns_have_required_fields(self, mock_frappe):
        from prakash_steel.prakash_steel.report.missing_bom_report.missing_bom_report import execute
        mock_frappe.db.sql.return_value = []
        cols, _ = execute()
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("item_code", fieldnames)
        self.assertIn("item_name", fieldnames)
        self.assertIn("item_type", fieldnames)

    @patch(MOD + ".frappe")
    def test_empty_db_returns_empty_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.missing_bom_report.missing_bom_report import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute()
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
