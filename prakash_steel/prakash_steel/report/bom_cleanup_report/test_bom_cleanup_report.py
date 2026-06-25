# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bom_cleanup_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.bom_cleanup_report.bom_cleanup_report"


class TestGetColumns(unittest.TestCase):
    def test_returns_list_with_fieldnames(self):
        from prakash_steel.prakash_steel.report.bom_cleanup_report.bom_cleanup_report import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("parent_item", fieldnames)
        self.assertIn("bom_id", fieldnames)
        self.assertIn("child_item_code", fieldnames)


class TestExecute(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_returns_tuple_with_no_filter(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_cleanup_report.bom_cleanup_report import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({"item": None, "is_default": None, "is_active": None})
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])

    @patch(MOD + ".frappe")
    def test_item_filter_applied(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_cleanup_report.bom_cleanup_report import get_data
        mock_frappe.db.sql.return_value = [
            {"parent_item": "FG-001", "bom_id": "BOM-0001", "child_item_code": "RM-001"}
        ]
        result = get_data({"item": "FG-001", "is_default": None, "is_active": None})
        self.assertEqual(len(result), 1)

    @patch(MOD + ".frappe")
    def test_is_default_yes_filter(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_cleanup_report.bom_cleanup_report import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"item": None, "is_default": "Yes", "is_active": None})
        call_args = mock_frappe.db.sql.call_args
        # Verify the query was called with values containing is_default=1
        self.assertIn(1, call_args[0][1].values())


if __name__ == "__main__":
    unittest.main()
