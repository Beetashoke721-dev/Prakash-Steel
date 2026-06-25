# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for tog_calculation_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.tog_calculation_report.tog_calculation_report"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_list(self, mock_frappe):
        from prakash_steel.prakash_steel.report.tog_calculation_report.tog_calculation_report import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_data", return_value=[])
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe, mock_get_data):
        from prakash_steel.prakash_steel.report.tog_calculation_report.tog_calculation_report import execute
        mock_frappe.has_permission.return_value = True
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
