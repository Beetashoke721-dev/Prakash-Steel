# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for desc_code_wise_summary_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report"


class TestGetColumns(unittest.TestCase):
    def test_returns_expected_fieldnames(self):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            get_columns,
        )

        cols = get_columns()
        self.assertIsInstance(cols, list)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertEqual(
            fieldnames,
            [
                "desc_code",
                "hsn_code",
                "qty",
                "taxable_value",
                "cgst_amt",
                "sgst_amt",
                "igst_amt",
                "gross_total",
            ],
        )


class TestGetData(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_defaults_to_sales_invoice(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            get_data,
        )

        mock_frappe.db.sql.return_value = []
        get_data({"transaction_type": "Sale"})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("tabSales Invoice Item", query)
        self.assertIn("tabSales Invoice", query)
        self.assertNotIn("tabPurchase Invoice", query)

    @patch(MOD + ".frappe")
    def test_purchase_switches_to_purchase_invoice(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            get_data,
        )

        mock_frappe.db.sql.return_value = []
        get_data({"transaction_type": "Purchase"})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("tabPurchase Invoice Item", query)
        self.assertIn("tabPurchase Invoice", query)
        self.assertNotIn("tabSales Invoice", query)

    @patch(MOD + ".frappe")
    def test_returns_sql_result_as_is(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            get_data,
        )

        expected = [{"desc_code": "DC-1", "qty": 10}]
        mock_frappe.db.sql.return_value = expected
        data = get_data({"transaction_type": "Sale"})
        self.assertEqual(data, expected)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_defaults_transaction_type_to_sale_when_missing(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            execute,
        )

        mock_frappe.db.sql.return_value = []
        execute({})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("tabSales Invoice Item", query)

    @patch(MOD + ".frappe")
    def test_defaults_transaction_type_when_filters_none(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            execute,
        )

        mock_frappe.db.sql.return_value = []
        cols, data = execute(None)
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_respects_explicit_purchase_filter(self, mock_frappe):
        from prakash_steel.prakash_steel.report.desc_code_wise_summary_report.desc_code_wise_summary_report import (
            execute,
        )

        mock_frappe.db.sql.return_value = []
        execute({"transaction_type": "Purchase"})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("tabPurchase Invoice Item", query)


if __name__ == "__main__":
    unittest.main()
