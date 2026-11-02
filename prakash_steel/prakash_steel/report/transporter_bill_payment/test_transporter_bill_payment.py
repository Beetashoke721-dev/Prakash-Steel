# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for transporter_bill_payment report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment"


class TestGetInvoiceType(unittest.TestCase):
    def _run(self, invoice_type):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import get_invoice_type
        return get_invoice_type({"invoice_type": invoice_type})

    def test_purchase_default(self):
        self.assertEqual(self._run("Purchase"), "purchase")

    def test_sale_type(self):
        self.assertEqual(self._run("Sale"), "sale")

    def test_none_defaults_to_purchase(self):
        self.assertEqual(self._run(None), "purchase")

    def test_case_insensitive_sale(self):
        self.assertEqual(self._run("sale"), "sale")


class TestGetColumns(unittest.TestCase):
    def test_purchase_columns(self):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import get_columns
        cols = get_columns("purchase")
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("bill_date", fieldnames)
        self.assertIn("approval_status", fieldnames)
        purchase_invoice_idx = fieldnames.index("purchase_invoice")
        self.assertEqual(fieldnames[purchase_invoice_idx + 1], "approval_status")

    def test_sale_columns(self):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import get_columns
        cols = get_columns("sale")
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("bill_date", fieldnames)
        self.assertIn("sales_invoice", fieldnames)

    def test_purchase_and_sale_have_different_columns(self):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import get_columns
        purchase_fields = {c["fieldname"] for c in get_columns("purchase")}
        sale_fields = {c["fieldname"] for c in get_columns("sale")}
        self.assertNotEqual(purchase_fields, sale_fields)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({"invoice_type": "Purchase"})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_receiving_qty_uses_custom_weight_slip_qty(self, mock_frappe):
        from prakash_steel.prakash_steel.report.transporter_bill_payment.transporter_bill_payment import execute

        mock_frappe.db.sql.return_value = []
        execute({"invoice_type": "Purchase"})

        # Ensure the report SQL uses Purchase Invoice Item.custom_weight_slip_qty
        # as the basis for "Receiving Quantity".
        called_query = mock_frappe.db.sql.call_args[0][0]
        self.assertIn("SUM(pii.custom_weight_slip_qty)", called_query)


if __name__ == "__main__":
    unittest.main()
