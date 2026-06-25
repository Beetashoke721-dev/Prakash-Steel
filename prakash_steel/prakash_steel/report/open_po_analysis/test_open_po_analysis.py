# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for open_po_analysis report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis"


class TestValidateFilters(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_throws_when_to_before_from(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis import validate_filters
        mock_frappe.throw.side_effect = Exception("date error")
        with self.assertRaises(Exception):
            validate_filters({"from_date": "2026-06-01", "to_date": "2026-05-01"})

    @patch(MOD + ".frappe")
    def test_passes_valid_dates(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis import validate_filters
        validate_filters({"from_date": "2026-01-01", "to_date": "2026-12-31"})
        mock_frappe.throw.assert_not_called()


class TestExecute(unittest.TestCase):
    def test_no_filters_returns_empty(self):
        from prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis import execute
        result = execute(None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], [])

    def test_empty_filters_returns_empty(self):
        from prakash_steel.prakash_steel.report.open_po_analysis.open_po_analysis import execute
        result = execute({})
        self.assertEqual(result[0], [])


if __name__ == "__main__":
    unittest.main()
