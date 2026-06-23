# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/order_validation.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.order_validation"


def _make_row(idx, rate, item_code="ITEM-001"):
    row = MagicMock()
    row.idx = idx
    row.get = lambda k, d=None: {"rate": rate, "item_code": item_code}.get(k, d)
    row.item_code = item_code
    row.item_name = item_code
    return row


def _make_doc(rows):
    doc = MagicMock()
    doc.get = lambda k, d=None: rows if k == "items" else d
    return doc


class TestValidateNoZeroRateItems(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_passes_when_all_rates_positive(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        doc = _make_doc([_make_row(1, 100.0), _make_row(2, 250.5)])
        validate_no_zero_rate_items(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_throws_for_single_zero_rate_row(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        mock_frappe.utils.flt = float
        mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        mock_frappe.throw.side_effect = Exception("zero rate")
        doc = _make_doc([_make_row(1, 0)])
        with self.assertRaises(Exception):
            validate_no_zero_rate_items(doc)
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    def test_throws_for_multiple_zero_rate_rows(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        mock_frappe.utils.flt = float
        mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        mock_frappe.throw.side_effect = Exception("zero rate")
        doc = _make_doc([_make_row(1, 0), _make_row(2, 50.0), _make_row(3, 0)])
        with self.assertRaises(Exception):
            validate_no_zero_rate_items(doc)
        # The combined message should mention both rows
        call_args = mock_frappe.throw.call_args[0][0]
        self.assertIn("Row 1", call_args)
        self.assertIn("Row 3", call_args)

    @patch(MOD + ".frappe")
    def test_passes_with_empty_items(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        doc = _make_doc([])
        validate_no_zero_rate_items(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_passes_with_none_items(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        doc = MagicMock()
        doc.get = lambda k, d=None: None
        validate_no_zero_rate_items(doc)
        mock_frappe.throw.assert_not_called()

    @patch(MOD + ".frappe")
    def test_zero_rate_as_string_zero_throws(self, mock_frappe):
        from prakash_steel.utils.order_validation import validate_no_zero_rate_items
        mock_frappe.utils.flt = float
        mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
        mock_frappe.throw.side_effect = Exception("zero rate")
        doc = _make_doc([_make_row(1, "0")])
        with self.assertRaises(Exception):
            validate_no_zero_rate_items(doc)


if __name__ == "__main__":
    unittest.main()
