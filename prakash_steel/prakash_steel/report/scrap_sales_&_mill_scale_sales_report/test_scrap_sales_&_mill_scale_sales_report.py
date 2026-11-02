# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for scrap_sales_&_mill_scale_sales_report — no DB required.

The module path contains "&", which is not valid in a Python `import`
statement or in a dotted string passed to `mock.patch`/`pkgutil.resolve_name`.
So the module is loaded via `importlib.import_module`, and `frappe` is
stubbed via `patch.object(MOD, "frappe", ...)` on the module object itself
rather than by dotted-path string.
"""

import importlib
import unittest
from unittest.mock import patch

MOD_PATH = "prakash_steel.prakash_steel.report.scrap_sales_&_mill_scale_sales_report.scrap_sales_&_mill_scale_sales_report"
MOD = importlib.import_module(MOD_PATH)


class TestGetColumns(unittest.TestCase):
    def test_returns_expected_fieldnames(self):
        cols = MOD.get_columns()
        self.assertIsInstance(cols, list)
        fieldnames = [c["fieldname"] for c in cols]
        self.assertEqual(
            fieldnames,
            [
                "item_code",
                "hsn_code",
                "qty",
                "taxable_value",
                "cgst_amt",
                "sgst_amt",
                "igst_amt",
                "total_taxes_and_charges",
                "gross_total",
            ],
        )


class TestGetData(unittest.TestCase):
    @patch.object(MOD, "frappe")
    def test_queries_sales_invoice_only(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("tabSales Invoice Item", query)
        self.assertIn("tabSales Invoice", query)
        self.assertNotIn("Purchase Invoice", query)

    @patch.object(MOD, "frappe")
    def test_filters_by_scrap_category(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("item.custom_category_name = 'Scrap'", query)

    @patch.object(MOD, "frappe")
    def test_groups_by_item_code_bucket_not_desc_code(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({})

        query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("GROUP BY item_code", query)
        self.assertNotIn("desc_code", query)

    @patch.object(MOD, "frappe")
    def test_splits_wastage_lc_bills_into_own_bucket(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({})

        query = mock_frappe.db.sql.call_args[0][0]
        values = mock_frappe.db.sql.call_args[0][1]
        # WASTAGE lines on a PSP/LC/... invoice get a "(LC)" prefix ...
        self.assertIn("CONCAT('(LC)', item.name)", query)
        self.assertIn("item.name = %(wastage_item)s AND txn.name LIKE %(lc_like)s", query)
        self.assertEqual(values["wastage_item"], MOD.WASTAGE_ITEM)
        self.assertEqual(values["lc_like"], MOD.LC_PREFIX + "%")

    @patch.object(MOD, "frappe")
    def test_includes_rent_item_alongside_scrap(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({})

        query = mock_frappe.db.sql.call_args[0][0]
        values = mock_frappe.db.sql.call_args[0][1]
        self.assertIn(
            "item.custom_category_name = 'Scrap' OR item.name = %(rent_item)s", query
        )
        self.assertEqual(values["rent_item"], MOD.RENT_ITEM)
        # Rent sorts to the bottom.
        self.assertIn("(MAX(item.name) = %(rent_item)s) ASC", query)

    @patch.object(MOD, "frappe")
    def test_applies_date_range_when_given(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        MOD.get_data({"from_date": "2026-01-01", "to_date": "2026-01-31"})

        query = mock_frappe.db.sql.call_args[0][0]
        values = mock_frappe.db.sql.call_args[0][1]
        self.assertIn("txn.posting_date BETWEEN", query)
        self.assertEqual(values["from_date"], "2026-01-01")
        self.assertEqual(values["to_date"], "2026-01-31")

    @patch.object(MOD, "frappe")
    def test_returns_sql_result_as_is(self, mock_frappe):
        expected = [{"item_code": "Mill Scale", "qty": 10}]
        mock_frappe.db.sql.return_value = expected
        data = MOD.get_data({})
        self.assertEqual(data, expected)


class TestExecute(unittest.TestCase):
    @patch.object(MOD, "frappe")
    def test_executes_without_filters(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        cols, data = MOD.execute({})

        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch.object(MOD, "frappe")
    def test_executes_when_filters_none(self, mock_frappe):
        mock_frappe.db.sql.return_value = []
        cols, data = MOD.execute(None)

        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
