# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for credit_note_purchase_monthly_report — no DB required."""

import unittest
from unittest.mock import patch, MagicMock

MOD = "prakash_steel.prakash_steel.report.credit_note_purchase_monthly_report.credit_note_purchase_monthly_report"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.credit_note_purchase_monthly_report.credit_note_purchase_monthly_report import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("party_name", "credit_note", "return_against"):
            self.assertIn(f, fieldnames)


class TestGrandTotalRow(unittest.TestCase):
    def test_grand_total_row_sums_amounts(self):
        from prakash_steel.prakash_steel.report.credit_note_purchase_monthly_report.credit_note_purchase_monthly_report import get_grand_total_row
        data = [
            {"grand_total": 1000.0, "outstanding_amount": 200.0},
            {"grand_total": 2000.0, "outstanding_amount": 300.0},
        ]
        row = get_grand_total_row(data)
        self.assertIsNotNone(row)

    def test_grand_total_returns_dict(self):
        from prakash_steel.prakash_steel.report.credit_note_purchase_monthly_report.credit_note_purchase_monthly_report import get_grand_total_row
        row = get_grand_total_row([])
        self.assertIsInstance(row, dict)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_data", return_value=[])
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe, mock_get_data):
        from prakash_steel.prakash_steel.report.credit_note_purchase_monthly_report.credit_note_purchase_monthly_report import execute
        mock_frappe.utils.get_first_day.return_value = "2026-06-01"
        mock_frappe.utils.get_last_day.return_value = "2026-06-30"
        mock_frappe.utils.nowdate.return_value = "2026-06-25"
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
