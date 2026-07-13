# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for monthly_debit_note_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report"


class TestGetColumns(unittest.TestCase):
    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_columns
        self.assertIsInstance(get_columns(), list)

    def test_required_fieldnames(self):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_columns
        names = {c["fieldname"] for c in get_columns()}
        for f in ("party_name", "debit_note_no", "debit_note_date",
                  "qty_kg", "gross_amount", "taxable_amount",
                  "input_cgst", "input_sgst", "input_igst", "total_tax"):
            self.assertIn(f, names, f"Missing column: {f}")

    def test_debit_note_no_links_to_purchase_invoice(self):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_columns
        col_map = {c["fieldname"]: c for c in get_columns()}
        self.assertEqual(col_map["debit_note_no"]["options"], "Purchase Invoice")

    def test_gross_amount_is_currency(self):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_columns
        col_map = {c["fieldname"]: c for c in get_columns()}
        self.assertEqual(col_map["gross_amount"]["fieldtype"], "Currency")


class TestPrepareFilters(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_throws_if_company_missing(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import _prepare_filters
        mock_frappe.throw.side_effect = Exception("Company is mandatory.")
        with self.assertRaises(Exception) as ctx:
            _prepare_filters({})
        self.assertIn("Company", str(ctx.exception))

    @patch(MOD + ".frappe")
    @patch(MOD + ".nowdate", return_value="2026-07-10")
    @patch(MOD + ".get_first_day", return_value="2026-07-01")
    @patch(MOD + ".get_last_day", return_value="2026-07-31")
    def test_defaults_from_date_and_to_date(self, mock_last, mock_first, mock_now, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import _prepare_filters
        mock_frappe.throw.side_effect = Exception("should not throw")
        result = _prepare_filters({"company": "Prakash Steel"})
        self.assertEqual(result["from_date"], "2026-07-01")
        self.assertEqual(result["to_date"], "2026-07-31")

    @patch(MOD + ".frappe")
    def test_explicit_dates_preserved(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import _prepare_filters
        result = _prepare_filters({
            "company": "Prakash Steel",
            "from_date": "2026-01-01",
            "to_date": "2026-03-31",
        })
        self.assertEqual(result["from_date"], "2026-01-01")
        self.assertEqual(result["to_date"], "2026-03-31")

    @patch(MOD + ".frappe")
    def test_throws_if_from_date_after_to_date(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import _prepare_filters
        mock_frappe.throw.side_effect = Exception("From Date cannot be after To Date.")
        with self.assertRaises(Exception) as ctx:
            _prepare_filters({
                "company": "Prakash Steel",
                "from_date": "2026-04-01",
                "to_date": "2026-03-01",
            })
        self.assertIn("From Date", str(ctx.exception))

    @patch(MOD + ".frappe")
    def test_same_from_and_to_date_is_valid(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import _prepare_filters
        mock_frappe.throw.side_effect = Exception("should not throw")
        result = _prepare_filters({
            "company": "Prakash Steel",
            "from_date": "2026-07-10",
            "to_date": "2026-07-10",
        })
        self.assertEqual(result["from_date"], "2026-07-10")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    @patch(MOD + ".nowdate", return_value="2026-07-10")
    @patch(MOD + ".get_first_day", return_value="2026-07-01")
    @patch(MOD + ".get_last_day", return_value="2026-07-31")
    def test_returns_columns_and_data(self, mock_last, mock_first, mock_now, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import execute
        mock_frappe.throw.side_effect = None
        mock_frappe.db.sql.return_value = []
        cols, data = execute({"company": "Prakash Steel"})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_query_filters_on_is_return_and_docstatus(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"company": "Prakash Steel", "from_date": "2026-01-01", "to_date": "2026-03-31"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("pi.is_return = 1", query)
        self.assertIn("pi.docstatus = 1", query)

    @patch(MOD + ".frappe")
    def test_cgst_pattern_included_in_params(self, mock_frappe):
        from prakash_steel.prakash_steel.report.monthly_debit_note_report.monthly_debit_note_report import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"company": "Prakash Steel", "from_date": "2026-01-01", "to_date": "2026-03-31"})
        params = mock_frappe.db.sql.call_args[0][1]
        self.assertEqual(params["cgst_pattern"], "%CGST%")
        self.assertEqual(params["sgst_pattern"], "%SGST%")
        self.assertEqual(params["igst_pattern"], "%IGST%")


if __name__ == "__main__":
    unittest.main()
