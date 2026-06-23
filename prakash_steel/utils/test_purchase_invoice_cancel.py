# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/purchase_invoice_cancel.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.purchase_invoice_cancel"


def _make_item(**kwargs):
    item = MagicMock()
    item.get = lambda k, d=None: kwargs.get(k, d)
    for k, v in kwargs.items():
        setattr(item, k, v)
    item.custom_gross_amount = None
    return item


def _make_doc(**kwargs):
    doc = MagicMock()
    items = kwargs.pop("items", [])
    doc.get = lambda k, d=None: items if k == "items" else kwargs.get(k, d)
    for k, v in kwargs.items():
        setattr(doc, k, v)
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# clear_cancel_reason_on_amend
# ─────────────────────────────────────────────────────────────────────────────

class TestClearCancelReasonOnAmend(unittest.TestCase):

    def test_clears_reason_on_amended_draft(self):
        from prakash_steel.utils.purchase_invoice_cancel import clear_cancel_reason_on_amend
        doc = MagicMock()
        doc.amended_from = "PI-0001"
        doc.docstatus = 0
        doc.custom_cancel_reason = "Old reason"
        clear_cancel_reason_on_amend(doc)
        self.assertEqual(doc.custom_cancel_reason, "")

    def test_does_not_clear_if_not_amended(self):
        from prakash_steel.utils.purchase_invoice_cancel import clear_cancel_reason_on_amend
        doc = MagicMock()
        doc.amended_from = None
        doc.docstatus = 0
        doc.custom_cancel_reason = "Some reason"
        clear_cancel_reason_on_amend(doc)
        self.assertEqual(doc.custom_cancel_reason, "Some reason")

    def test_does_not_clear_if_submitted(self):
        from prakash_steel.utils.purchase_invoice_cancel import clear_cancel_reason_on_amend
        doc = MagicMock()
        doc.amended_from = "PI-0001"
        doc.docstatus = 1
        doc.custom_cancel_reason = "Keep me"
        clear_cancel_reason_on_amend(doc)
        self.assertEqual(doc.custom_cancel_reason, "Keep me")

    def test_does_not_clear_if_reason_empty(self):
        from prakash_steel.utils.purchase_invoice_cancel import clear_cancel_reason_on_amend
        doc = MagicMock()
        doc.amended_from = "PI-0001"
        doc.docstatus = 0
        doc.custom_cancel_reason = ""
        clear_cancel_reason_on_amend(doc)
        self.assertEqual(doc.custom_cancel_reason, "")


# ─────────────────────────────────────────────────────────────────────────────
# update_gross_amount_on_items
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateGrossAmountOnItems(unittest.TestCase):

    def test_uses_igst_when_present(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item = _make_item(taxable_value=1000.0, igst_amount=180.0, cgst_amount=90.0, sgst_amount=90.0)
        doc = _make_doc(items=[item])
        update_gross_amount_on_items(doc)
        # igst present → taxable + igst = 1000 + 180 = 1180
        self.assertAlmostEqual(item.custom_gross_amount, 1180.0)

    def test_uses_cgst_plus_sgst_when_no_igst(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item = _make_item(taxable_value=1000.0, igst_amount=0, cgst_amount=90.0, sgst_amount=90.0)
        doc = _make_doc(items=[item])
        update_gross_amount_on_items(doc)
        # igst = 0 → taxable + cgst + sgst = 1000 + 90 + 90 = 1180
        self.assertAlmostEqual(item.custom_gross_amount, 1180.0)

    def test_falls_back_to_net_amount(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item = _make_item(taxable_value=None, net_amount=800.0, igst_amount=0, cgst_amount=0, sgst_amount=0)
        doc = _make_doc(items=[item])
        update_gross_amount_on_items(doc)
        self.assertAlmostEqual(item.custom_gross_amount, 800.0)

    def test_falls_back_to_amount(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item = _make_item(taxable_value=None, net_amount=None, amount=500.0, igst_amount=0, cgst_amount=0, sgst_amount=0)
        doc = _make_doc(items=[item])
        update_gross_amount_on_items(doc)
        self.assertAlmostEqual(item.custom_gross_amount, 500.0)

    def test_zero_gst_gives_taxable_only(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item = _make_item(taxable_value=2000.0, igst_amount=0, cgst_amount=0, sgst_amount=0)
        doc = _make_doc(items=[item])
        update_gross_amount_on_items(doc)
        self.assertAlmostEqual(item.custom_gross_amount, 2000.0)

    def test_no_items_does_not_raise(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        doc = _make_doc(items=[])
        update_gross_amount_on_items(doc)  # should not raise

    def test_multiple_items_all_computed(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_gross_amount_on_items
        item1 = _make_item(taxable_value=100.0, igst_amount=18.0, cgst_amount=0, sgst_amount=0)
        item2 = _make_item(taxable_value=200.0, igst_amount=0, cgst_amount=18.0, sgst_amount=18.0)
        doc = _make_doc(items=[item1, item2])
        update_gross_amount_on_items(doc)
        self.assertAlmostEqual(item1.custom_gross_amount, 118.0)
        self.assertAlmostEqual(item2.custom_gross_amount, 236.0)


# ─────────────────────────────────────────────────────────────────────────────
# update_total_weight_slip_qty
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateTotalWeightSlipQty(unittest.TestCase):

    def test_sums_weight_slip_qty(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_total_weight_slip_qty
        item1 = _make_item(custom_weight_slip_qty=10.0)
        item2 = _make_item(custom_weight_slip_qty=20.0)
        doc = _make_doc(total_qty=35.0, items=[item1, item2])
        update_total_weight_slip_qty(doc)
        self.assertAlmostEqual(doc.custom_total_weight_slip_qty, 30.0)

    def test_shortage_is_difference(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_total_weight_slip_qty
        item1 = _make_item(custom_weight_slip_qty=10.0)
        doc = _make_doc(total_qty=35.0, items=[item1])
        update_total_weight_slip_qty(doc)
        self.assertEqual(doc.custom_shortage_qty, 25)

    def test_handles_none_weight_slip_qty(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_total_weight_slip_qty
        item1 = _make_item(custom_weight_slip_qty=None)
        doc = _make_doc(total_qty=10.0, items=[item1])
        update_total_weight_slip_qty(doc)
        self.assertAlmostEqual(doc.custom_total_weight_slip_qty, 0.0)
        self.assertEqual(doc.custom_shortage_qty, 10)

    def test_empty_items_gives_zero(self):
        from prakash_steel.utils.purchase_invoice_cancel import update_total_weight_slip_qty
        doc = _make_doc(total_qty=0, items=[])
        update_total_weight_slip_qty(doc)
        self.assertAlmostEqual(doc.custom_total_weight_slip_qty, 0.0)
        self.assertEqual(doc.custom_shortage_qty, 0)


# ─────────────────────────────────────────────────────────────────────────────
# validate_cancel_reason
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateCancelReason(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_throws_when_reason_missing(self, mock_frappe):
        from prakash_steel.utils.purchase_invoice_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("reason required")
        doc = MagicMock()
        doc.custom_cancel_reason = ""
        with self.assertRaises(Exception):
            validate_cancel_reason(doc)
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    def test_throws_when_reason_whitespace_only(self, mock_frappe):
        from prakash_steel.utils.purchase_invoice_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("reason required")
        doc = MagicMock()
        doc.custom_cancel_reason = "   "
        with self.assertRaises(Exception):
            validate_cancel_reason(doc)

    @patch(MOD + ".frappe")
    def test_throws_when_reason_none(self, mock_frappe):
        from prakash_steel.utils.purchase_invoice_cancel import validate_cancel_reason
        mock_frappe.throw.side_effect = Exception("reason required")
        doc = MagicMock()
        doc.custom_cancel_reason = None
        with self.assertRaises(Exception):
            validate_cancel_reason(doc)

    @patch(MOD + ".frappe")
    def test_passes_when_reason_present(self, mock_frappe):
        from prakash_steel.utils.purchase_invoice_cancel import validate_cancel_reason
        doc = MagicMock()
        doc.custom_cancel_reason = "Rate Mistake"
        validate_cancel_reason(doc)
        mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
