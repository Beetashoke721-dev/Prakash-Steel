# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for new_procurement_tracker report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.new_procurement_tracker.new_procurement_tracker"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_list_with_fieldnames(self, mock_frappe):
        from prakash_steel.prakash_steel.report.new_procurement_tracker.new_procurement_tracker import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.new_procurement_tracker.new_procurement_tracker import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
