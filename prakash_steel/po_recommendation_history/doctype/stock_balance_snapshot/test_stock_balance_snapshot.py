# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for Stock Balance Snapshot doctype — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

MOD = "prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot"


class TestStockBalanceSnapshot(FrappeTestCase):
    def test_class_importable(self):
        from prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot import StockBalanceSnapshot
        self.assertTrue(callable(StockBalanceSnapshot))

    def test_before_save_sets_row_count(self):
        from prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot import StockBalanceSnapshot
        doc = StockBalanceSnapshot.__new__(StockBalanceSnapshot)
        doc.items = [MagicMock(), MagicMock()]
        doc.row_count = 0
        doc.before_save()
        self.assertEqual(doc.row_count, 2)

    def test_before_save_zero_items(self):
        from prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot import StockBalanceSnapshot
        doc = StockBalanceSnapshot.__new__(StockBalanceSnapshot)
        doc.items = []
        doc.row_count = 5
        doc.before_save()
        self.assertEqual(doc.row_count, 0)

    @patch(MOD + ".frappe")
    def test_capture_snapshot_success_inserts_doc(self, mock_frappe):
        from prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot import _capture_snapshot

        mock_snap = MagicMock()
        mock_snap.name = "SBS-001"
        mock_frappe.new_doc.return_value = mock_snap
        mock_frappe._dict = MagicMock(return_value={})

        sample_data = [
            {"item_code": "ITEM-001", "item_name": "Steel Rod", "item_group": "Raw Material",
             "category_name": "RB", "stock_uom": "Kg", "balance_qty": 100.0}
        ]
        with patch(MOD + ".execute", return_value=([], sample_data)):
            _capture_snapshot(trigger="Manual")

        mock_snap.insert.assert_called_once()
        mock_frappe.db.commit.assert_called_once()

    @patch(MOD + ".frappe")
    def test_capture_snapshot_failure_creates_failed_doc(self, mock_frappe):
        from prakash_steel.po_recommendation_history.doctype.stock_balance_snapshot.stock_balance_snapshot import _capture_snapshot

        mock_doc = MagicMock()
        mock_frappe.new_doc.return_value = mock_doc
        mock_frappe._dict = MagicMock(return_value={})

        with patch(MOD + ".execute", side_effect=Exception("report error")):
            _capture_snapshot(trigger="Scheduled")

        mock_doc.insert.assert_called_once()
        self.assertEqual(mock_doc.status, "Failed")
        self.assertEqual(mock_doc.row_count, 0)


if __name__ == "__main__":
    unittest.main()
