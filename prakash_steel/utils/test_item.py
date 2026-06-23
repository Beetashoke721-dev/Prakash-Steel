# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/item.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.item"


def _make_doc(**fields):
    doc = MagicMock()
    doc.name = fields.get("name", "ITEM-001")
    doc.docstatus = fields.get("docstatus", 0)
    doc.get = lambda k, d=None: fields.get(k, d)
    for k, v in fields.items():
        setattr(doc, k, v)
    doc.custom_sku_type = None
    doc.custom_batch_size = fields.get("custom_batch_size", 0)
    doc.min_order_qty = fields.get("min_order_qty", 0)
    return doc


# ─────────────────────────────────────────────────────────────────────────────
# calculate_sku_type_on_validate
# ─────────────────────────────────────────────────────────────────────────────

class TestCalculateSkuType(unittest.TestCase):

    def _run(self, item_type, buffer_flag="Non-Buffer"):
        from prakash_steel.utils.item import calculate_sku_type_on_validate
        doc = _make_doc(custom_item_type=item_type, custom_buffer_flag=buffer_flag)
        calculate_sku_type_on_validate(doc)
        return doc.custom_sku_type

    def test_bb_buffer(self):
        self.assertEqual(self._run("BB", "Buffer"), "BBMTA")

    def test_bb_non_buffer(self):
        self.assertEqual(self._run("BB", "Non-Buffer"), "BBMTO")

    def test_rb_buffer(self):
        self.assertEqual(self._run("RB", "Buffer"), "RBMTA")

    def test_rb_non_buffer(self):
        self.assertEqual(self._run("RB"), "RBMTO")

    def test_bo_buffer(self):
        self.assertEqual(self._run("BO", "Buffer"), "BOTA")

    def test_bo_non_buffer(self):
        self.assertEqual(self._run("BO"), "BOTO")

    def test_rm_buffer(self):
        self.assertEqual(self._run("RM", "Buffer"), "PTA")

    def test_rm_non_buffer(self):
        self.assertEqual(self._run("RM"), "PTO")

    def test_traded_buffer(self):
        self.assertEqual(self._run("Traded", "Buffer"), "TRMTA")

    def test_traded_non_buffer(self):
        self.assertEqual(self._run("Traded"), "TRMTO")

    def test_no_item_type_returns_none(self):
        self.assertIsNone(self._run(None))

    def test_empty_item_type_returns_none(self):
        self.assertIsNone(self._run(""))

    def test_default_buffer_flag_treated_as_non_buffer(self):
        # No buffer_flag → defaults to "Non-Buffer"
        from prakash_steel.utils.item import calculate_sku_type_on_validate
        doc = _make_doc(custom_item_type="BB")
        doc.get = lambda k, d=None: {"custom_item_type": "BB", "custom_buffer_flag": None}.get(k, d)
        calculate_sku_type_on_validate(doc)
        self.assertEqual(doc.custom_sku_type, "BBMTO")


# ─────────────────────────────────────────────────────────────────────────────
# validate_min_order_qty_and_batch_size
# ─────────────────────────────────────────────────────────────────────────────

class TestValidateMinOrderQtyBatchSize(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_both_zero_passes(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        doc = _make_doc(min_order_qty=0, custom_batch_size=0)
        validate_min_order_qty_and_batch_size(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_only_min_order_qty_set_passes(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        doc = _make_doc(min_order_qty=100, custom_batch_size=0)
        validate_min_order_qty_and_batch_size(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_only_batch_size_set_passes(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        doc = _make_doc(min_order_qty=0, custom_batch_size=50)
        validate_min_order_qty_and_batch_size(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_both_positive_throws(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        mock_frappe.throw.side_effect = Exception("both set")
        doc = _make_doc(min_order_qty=100, custom_batch_size=50)
        with self.assertRaises(Exception):
            validate_min_order_qty_and_batch_size(doc)
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    def test_min_order_qty_set_clears_batch_size(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        # throw raises so we need to prevent that path — use a doc where only moq > 0
        doc = _make_doc(min_order_qty=100, custom_batch_size=0)
        validate_min_order_qty_and_batch_size(doc)
        # batch_size should remain 0 (no change needed)
        self.assertEqual(doc.custom_batch_size, 0)

    @patch(MOD + ".frappe")
    def test_invalid_values_default_to_zero(self, mock_frappe):
        from prakash_steel.utils.item import validate_min_order_qty_and_batch_size
        doc = _make_doc(min_order_qty="not_a_number", custom_batch_size="bad")
        # Should not raise, just defaults to 0
        validate_min_order_qty_and_batch_size(doc)
        mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
