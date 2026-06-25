# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bom_wise_buffer_details_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.bom_wise_buffer_details_report.bom_wise_buffer_details_report"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_list_with_fieldnames(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_wise_buffer_details_report.bom_wise_buffer_details_report import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    @patch(MOD + ".require_permission")
    def test_returns_tuple(self, mock_perm, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_wise_buffer_details_report.bom_wise_buffer_details_report import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
