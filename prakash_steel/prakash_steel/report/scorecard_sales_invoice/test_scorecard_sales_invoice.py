# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for scorecard_sales_invoice report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice"


class TestGetColumns(unittest.TestCase):
    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_columns
        self.assertIsInstance(get_columns(), list)

    def test_column_count(self):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_columns
        self.assertEqual(len(get_columns()), 12)

    def test_required_fieldnames(self):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_columns
        names = {c["fieldname"] for c in get_columns()}
        for f in ("invoice_date", "invoice_number", "customer_name", "item_code", "qty", "item_price"):
            self.assertIn(f, names, f"Missing column: {f}")

    def test_invoice_number_links_to_sales_invoice(self):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_columns
        col_map = {c["fieldname"]: c for c in get_columns()}
        self.assertEqual(col_map["invoice_number"]["options"], "Sales Invoice")

    def test_item_price_is_currency(self):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_columns
        col_map = {c["fieldname"] for c in get_columns()}
        col_detail = {c["fieldname"]: c for c in
                      __import__("prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice",
                                 fromlist=["get_columns"]).get_columns()}
        self.assertEqual(col_detail["item_price"]["fieldtype"], "Currency")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple_of_lists(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_empty_filters_runs_without_error(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute(None)
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


class TestGetData(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_always_includes_docstatus_condition(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({})
        call_args = mock_frappe.db.sql.call_args
        query = call_args[0][0]
        self.assertIn("si.docstatus = 1", query)

    @patch(MOD + ".frappe")
    def test_always_excludes_items_without_item_type(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({})
        call_args = mock_frappe.db.sql.call_args
        query = call_args[0][0]
        self.assertIn("COALESCE(i.custom_item_type, '') != ''", query)

    @patch(MOD + ".frappe")
    def test_from_date_filter_appended(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"from_date": "2026-01-01"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("si.posting_date >= %(from_date)s", query)

    @patch(MOD + ".frappe")
    def test_to_date_filter_appended(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"to_date": "2026-01-31"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("si.posting_date <= %(to_date)s", query)

    @patch(MOD + ".frappe")
    def test_customer_filter_appended(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"customer": "CUST-001"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("si.customer = %(customer)s", query)

    @patch(MOD + ".frappe")
    def test_company_filter_appended(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"company": "Prakash Steel"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("si.company = %(company)s", query)

    @patch(MOD + ".frappe")
    def test_no_optional_filter_does_not_add_extra_conditions(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({})
        query = mock_frappe.db.sql.call_args[0][0]
        # Only the mandatory docstatus=1 condition should be present
        self.assertNotIn("si.customer = %(customer)s", query)
        self.assertNotIn("si.company = %(company)s", query)

    @patch(MOD + ".frappe")
    def test_item_code_filter_appended(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"item_code": "STEEL-ROD-10MM"})
        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("sii.item_code = %(item_code)s", query)

    @patch(MOD + ".frappe")
    def test_returns_db_results(self, mock_frappe):
        from prakash_steel.prakash_steel.report.scorecard_sales_invoice.scorecard_sales_invoice import get_data
        expected = [{"invoice_number": "SI-001", "customer_name": "ABC Corp"}]
        mock_frappe.db.sql.return_value = expected
        result = get_data({})
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
