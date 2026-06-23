# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for all cancel-reason validator utils — no DB required.

All five cancel validators (sales_order, purchase_order, purchase_receipt,
material_request, sales_invoice_cancel) share the same pattern:
  - throw when custom_cancel_reason is missing / empty / whitespace
  - pass when it is present
"""

import unittest
from unittest.mock import MagicMock, patch


def _doc_with_reason(reason):
    doc = MagicMock()
    doc.custom_cancel_reason = reason
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# Sales Order cancel
# ─────────────────────────────────────────────────────────────────────────────

class TestSalesOrderCancelReason(unittest.TestCase):

    MOD = "prakash_steel.utils.sales_order_cancel"

    @patch("prakash_steel.utils.sales_order_cancel.frappe")
    def test_throws_when_missing(self, mock_frappe):
        from prakash_steel.utils.sales_order_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason(""))

    @patch("prakash_steel.utils.sales_order_cancel.frappe")
    def test_throws_when_whitespace(self, mock_frappe):
        from prakash_steel.utils.sales_order_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason("   "))

    @patch("prakash_steel.utils.sales_order_cancel.frappe")
    def test_passes_when_present(self, mock_frappe):
        from prakash_steel.utils.sales_order_cancel import validate_cancel_reason
        validate_cancel_reason(_doc_with_reason("Rate Mistake"))
        mock_frappe.throw.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Order cancel
# ─────────────────────────────────────────────────────────────────────────────

class TestPurchaseOrderCancelReason(unittest.TestCase):

    @patch("prakash_steel.utils.purchase_order_cancel.frappe")
    def test_throws_when_missing(self, mock_frappe):
        from prakash_steel.utils.purchase_order_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason(""))

    @patch("prakash_steel.utils.purchase_order_cancel.frappe")
    def test_throws_when_none(self, mock_frappe):
        from prakash_steel.utils.purchase_order_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason(None))

    @patch("prakash_steel.utils.purchase_order_cancel.frappe")
    def test_passes_when_present(self, mock_frappe):
        from prakash_steel.utils.purchase_order_cancel import validate_cancel_reason
        validate_cancel_reason(_doc_with_reason("Data Entry Mistake"))
        mock_frappe.throw.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Purchase Receipt cancel
# ─────────────────────────────────────────────────────────────────────────────

class TestPurchaseReceiptCancelReason(unittest.TestCase):

    @patch("prakash_steel.utils.purchase_receipt_cancel.frappe")
    def test_throws_when_missing(self, mock_frappe):
        from prakash_steel.utils.purchase_receipt_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason(""))

    @patch("prakash_steel.utils.purchase_receipt_cancel.frappe")
    def test_passes_when_present(self, mock_frappe):
        from prakash_steel.utils.purchase_receipt_cancel import validate_cancel_reason
        validate_cancel_reason(_doc_with_reason("Quality Issue"))
        mock_frappe.throw.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Material Request cancel
# ─────────────────────────────────────────────────────────────────────────────

class TestMaterialRequestCancelReason(unittest.TestCase):

    @patch("prakash_steel.utils.material_request_cancel.frappe")
    def test_throws_when_missing(self, mock_frappe):
        from prakash_steel.utils.material_request_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason(""))

    @patch("prakash_steel.utils.material_request_cancel.frappe")
    def test_throws_when_whitespace(self, mock_frappe):
        from prakash_steel.utils.material_request_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            validate_cancel_reason(_doc_with_reason("  \t  "))

    @patch("prakash_steel.utils.material_request_cancel.frappe")
    def test_passes_when_present(self, mock_frappe):
        from prakash_steel.utils.material_request_cancel import validate_cancel_reason
        validate_cancel_reason(_doc_with_reason("Others"))
        mock_frappe.throw.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Sales Invoice cancel (whitelisted function, not a hook)
# ─────────────────────────────────────────────────────────────────────────────

class TestCancelSalesInvoiceWithReason(unittest.TestCase):

    @patch("prakash_steel.utils.sales_invoice_cancel.frappe")
    def test_throws_when_reason_empty(self, mock_frappe):
        from prakash_steel.utils.sales_invoice_cancel import cancel_sales_invoice_with_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            cancel_sales_invoice_with_reason("SI-0001", "")
        mock_frappe.throw.assert_called_once()

    @patch("prakash_steel.utils.sales_invoice_cancel.frappe")
    def test_throws_when_reason_whitespace(self, mock_frappe):
        from prakash_steel.utils.sales_invoice_cancel import cancel_sales_invoice_with_reason
        mock_frappe.throw.side_effect = Exception("required")
        with self.assertRaises(Exception):
            cancel_sales_invoice_with_reason("SI-0001", "   ")

    @patch("prakash_steel.utils.sales_invoice_cancel.frappe")
    def test_throws_when_docstatus_not_submitted(self, mock_frappe):
        from prakash_steel.utils.sales_invoice_cancel import cancel_sales_invoice_with_reason
        doc = MagicMock()
        doc.docstatus = 0
        mock_frappe.get_doc.return_value = doc
        mock_frappe.throw.side_effect = Exception("not submitted")
        with self.assertRaises(Exception):
            cancel_sales_invoice_with_reason("SI-0001", "Rate Mistake")

    @patch("prakash_steel.utils.sales_invoice_cancel.frappe")
    def test_cancels_submitted_invoice(self, mock_frappe):
        from prakash_steel.utils.sales_invoice_cancel import cancel_sales_invoice_with_reason
        doc = MagicMock()
        doc.docstatus = 1
        doc.name = "SI-0001"
        mock_frappe.get_doc.return_value = doc
        cancel_sales_invoice_with_reason("SI-0001", "Rate Mistake")
        doc.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
