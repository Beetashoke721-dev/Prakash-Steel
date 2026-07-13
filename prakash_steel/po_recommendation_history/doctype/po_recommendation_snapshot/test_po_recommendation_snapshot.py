# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for PO Recommendation Snapshot doctype — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

MOD = "prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot"


class TestPORecommendationSnapshot(FrappeTestCase):
    def test_class_importable(self):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import PORecommendationSnapshot
        self.assertTrue(callable(PORecommendationSnapshot))

    def test_before_save_sets_item_count(self):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import PORecommendationSnapshot
        doc = PORecommendationSnapshot.__new__(PORecommendationSnapshot)
        doc.items = [MagicMock(), MagicMock(), MagicMock()]
        doc.item_count = 0
        doc.before_save()
        self.assertEqual(doc.item_count, 3)

    def test_before_save_empty_items(self):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import PORecommendationSnapshot
        doc = PORecommendationSnapshot.__new__(PORecommendationSnapshot)
        doc.items = []
        doc.item_count = 99
        doc.before_save()
        self.assertEqual(doc.item_count, 0)

    @patch(MOD + ".frappe")
    def test_capture_snapshot_success(self, mock_frappe):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import _capture_snapshot

        mock_snap = MagicMock()
        mock_snap.name = "SNAP-001"
        mock_frappe.new_doc.return_value = mock_snap
        mock_frappe._dict = MagicMock(side_effect=lambda x=None: x or {})

        with patch(MOD + ".execute", return_value=([], [])):
            with patch(MOD + ".require_all_permissions"):
                result = _capture_snapshot(trigger="Manual")

        mock_snap.insert.assert_called_once()
        mock_frappe.db.commit.assert_called_once()

    @patch(MOD + ".frappe")
    def test_capture_snapshot_on_failure_saves_failed_doc(self, mock_frappe):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import _capture_snapshot

        mock_doc = MagicMock()
        mock_frappe.new_doc.return_value = mock_doc
        mock_frappe._dict = MagicMock(side_effect=RuntimeError("boom"))

        result = _capture_snapshot(trigger="Scheduled")

        mock_doc.insert.assert_called_once()
        self.assertEqual(mock_doc.status, "Failed")

    def test_capture_daily_po_snapshot_importable(self):
        from prakash_steel.po_recommendation_history.doctype.po_recommendation_snapshot.po_recommendation_snapshot import capture_daily_po_snapshot
        self.assertTrue(callable(capture_daily_po_snapshot))


if __name__ == "__main__":
    unittest.main()
