# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# For license information, please see license.txt

"""Tests for Purchase Order Recommendation Snapshot doctype."""

import unittest


class TestPurchaseOrderRecommendationSnapshotDoctype(unittest.TestCase):

    def test_class_is_importable(self):
        from prakash_steel.po_recommendation_history.doctype.purchase_order_recommendation_snapshot.purchase_order_recommendation_snapshot import (
            PurchaseOrderRecommendationSnapshot,
        )
        self.assertIsNotNone(PurchaseOrderRecommendationSnapshot)

    def test_class_is_document_subclass(self):
        from frappe.model.document import Document
        from prakash_steel.po_recommendation_history.doctype.purchase_order_recommendation_snapshot.purchase_order_recommendation_snapshot import (
            PurchaseOrderRecommendationSnapshot,
        )
        self.assertTrue(issubclass(PurchaseOrderRecommendationSnapshot, Document))


if __name__ == "__main__":
    unittest.main()
