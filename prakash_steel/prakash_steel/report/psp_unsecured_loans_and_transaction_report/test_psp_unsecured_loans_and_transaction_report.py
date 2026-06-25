# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for psp_unsecured_loans_and_transaction_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("month", "interest_amount", "tds_10", "total_amount"):
            self.assertIn(f, fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_data", return_value=[])
    def test_returns_tuple(self, mock_get_data):
        from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import execute
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".get_data")
    def test_total_row_appended_when_data_exists(self, mock_get_data):
        from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import execute
        mock_get_data.return_value = [
            {"month": "June 2026", "interest_amount": 5000.0, "tds_10": 500.0, "total_amount": 4500.0,
             "detail_date": "2026-06-01", "unsecured_loan": "Loan A", "interest_percent": 12.0,
             "closing_balance": 100000.0, "day_interest": 32.8, "name": "ULT-0001"}
        ]
        cols, data = execute({})
        last_row = data[-1]
        self.assertEqual(last_row.get("month"), "Total")

    @patch(MOD + ".get_data", return_value=[])
    def test_no_total_row_when_empty(self, mock_get_data):
        from prakash_steel.prakash_steel.report.psp_unsecured_loans_and_transaction_report.psp_unsecured_loans_and_transaction_report import execute
        _, data = execute({})
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
