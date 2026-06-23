# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for overrides/stock_entry.py — no DB required.

Note: frappe.utils.flt(value, precision) returns 0.0 without a site context
because it needs rounding_method from site config. We mock flt to use plain
float() so comparison logic can be tested without a running bench.
"""

import unittest
from unittest.mock import MagicMock, patch


def _make_se_instance(**kwargs):
    from prakash_steel.overrides.stock_entry import CustomStockEntry
    obj = object.__new__(CustomStockEntry)
    obj.posting_date = kwargs.get("posting_date", "2026-01-15")
    obj.posting_time = kwargs.get("posting_time", "10:00:00")
    obj.purpose = kwargs.get("purpose", "Material Transfer")
    obj.items = kwargs.get("items", [])
    return obj


def _make_item_row(idx, item_code, s_warehouse=None, transfer_qty=10.0):
    row = MagicMock()
    row.idx = idx
    row.item_code = item_code
    row.s_warehouse = s_warehouse
    row.t_warehouse = "Target WH" if not s_warehouse else None
    row.transfer_qty = transfer_qty
    row.actual_qty = 0
    row.precision = lambda f: 3
    return row


MOD = "prakash_steel.overrides.stock_entry"

# flt with precision needs site context; replace it with plain float for these tests
_flt_mock = lambda v, p=None: float(v) if v is not None else 0.0


class TestValidateStockAvailability(unittest.TestCase):

    @patch(MOD + ".flt", side_effect=_flt_mock)
    @patch(MOD + ".is_negative_stock_allowed", return_value=False)
    @patch(MOD + ".get_previous_sle")
    def test_passes_when_sufficient_stock(self, mock_sle, mock_neg, mock_flt):
        mock_sle.return_value = {"qty_after_transaction": 50.0}
        se = _make_se_instance(items=[
            _make_item_row(1, "ITEM-001", s_warehouse="Store WH", transfer_qty=10.0)
        ])
        se.validate_stock_availability()  # should not raise

    @patch(MOD + ".frappe")
    @patch(MOD + ".flt", side_effect=_flt_mock)
    @patch(MOD + ".is_negative_stock_allowed", return_value=False)
    @patch(MOD + ".get_previous_sle")
    @patch(MOD + ".NegativeStockError", Exception)
    def test_throws_when_insufficient_stock(self, mock_sle, mock_neg, mock_flt, mock_frappe):
        mock_sle.return_value = {"qty_after_transaction": 5.0}
        mock_frappe.bold.side_effect = lambda x: str(x)
        mock_frappe.throw.side_effect = Exception("insufficient")
        se = _make_se_instance(items=[
            _make_item_row(1, "ITEM-001", s_warehouse="Store WH", transfer_qty=10.0)
        ])
        with self.assertRaises(Exception):
            se.validate_stock_availability()
        mock_frappe.throw.assert_called_once()

    @patch(MOD + ".frappe")
    @patch(MOD + ".flt", side_effect=_flt_mock)
    @patch(MOD + ".is_negative_stock_allowed", return_value=False)
    @patch(MOD + ".get_previous_sle")
    @patch(MOD + ".NegativeStockError", Exception)
    def test_collects_all_errors_before_throwing(self, mock_sle, mock_neg, mock_flt, mock_frappe):
        """All rows should be checked before throwing, not just the first failure."""
        mock_sle.return_value = {"qty_after_transaction": 0.0}
        mock_frappe.bold.side_effect = lambda x: str(x)
        mock_frappe.throw.side_effect = Exception("insufficient")
        se = _make_se_instance(items=[
            _make_item_row(1, "ITEM-A", s_warehouse="WH", transfer_qty=10.0),
            _make_item_row(2, "ITEM-B", s_warehouse="WH", transfer_qty=5.0),
        ])
        with self.assertRaises(Exception):
            se.validate_stock_availability()
        call_msg = mock_frappe.throw.call_args[0][0]
        self.assertIn("ITEM-A", call_msg)
        self.assertIn("ITEM-B", call_msg)

    @patch(MOD + ".flt", side_effect=_flt_mock)
    @patch(MOD + ".is_negative_stock_allowed", return_value=True)
    @patch(MOD + ".get_previous_sle")
    def test_skips_when_negative_stock_allowed(self, mock_sle, mock_neg, mock_flt):
        """When negative stock is allowed, no error should be raised."""
        mock_sle.return_value = {"qty_after_transaction": 0.0}
        se = _make_se_instance(items=[
            _make_item_row(1, "ITEM-001", s_warehouse="WH", transfer_qty=10.0)
        ])
        se.validate_stock_availability()  # should not raise

    @patch(MOD + ".get_previous_sle")
    def test_skips_rows_without_source_warehouse(self, mock_sle):
        """Material Receipt rows (no s_warehouse) should not be validated."""
        se = _make_se_instance(items=[
            _make_item_row(1, "ITEM-001", s_warehouse=None, transfer_qty=10.0)
        ])
        se.validate_stock_availability()  # should not raise
        mock_sle.assert_not_called()

    @patch(MOD + ".get_previous_sle")
    def test_skips_rows_without_item_code(self, mock_sle):
        se = _make_se_instance(items=[
            _make_item_row(1, "", s_warehouse="WH", transfer_qty=10.0)
        ])
        se.validate_stock_availability()
        mock_sle.assert_not_called()

    def test_empty_items_does_not_raise(self):
        se = _make_se_instance(items=[])
        se.validate_stock_availability()  # should not raise


if __name__ == "__main__":
    unittest.main()
