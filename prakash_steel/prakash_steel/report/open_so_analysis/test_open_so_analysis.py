# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for open_so_analysis report — no DB required."""

import unittest
from unittest.mock import patch, MagicMock

MOD = "prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis"


class TestValidateFilters(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_throws_when_to_before_from(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import validate_filters
        mock_frappe.throw.side_effect = Exception("date error")
        with self.assertRaises(Exception):
            validate_filters({"from_date": "2026-06-01", "to_date": "2026-05-01"})
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    def test_passes_valid_date_range(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import validate_filters
        validate_filters({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        mock_frappe.throw.assert_not_called()


class TestGetConditions(unittest.TestCase):
    def test_date_range_added(self):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import get_conditions
        conditions = get_conditions({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        self.assertIn("transaction_date", conditions)

    def test_company_filter_added(self):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import get_conditions
        conditions = get_conditions({"from_date": "2026-01-01", "to_date": "2026-12-31", "company": "PSPL"})
        self.assertIn("company", conditions)

    def test_empty_filters_returns_empty_string(self):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import get_conditions
        result = get_conditions({})
        self.assertEqual(result, "")


class TestExecute(unittest.TestCase):
    def test_no_filters_returns_empty(self):
        from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import execute
        result = execute(None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], [])


if __name__ == "__main__":
    unittest.main()
