# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# For license information, please see license.txt

"""Tests for SO Recommendation Snapshot doctype."""

import unittest


class TestSORecommendationSnapshotDoctype(unittest.TestCase):

    def test_class_is_importable(self):
        from prakash_steel.po_recommendation_history.doctype.so_recommendation_snapshot.so_recommendation_snapshot import (
            SORecommendationSnapshot,
        )
        self.assertIsNotNone(SORecommendationSnapshot)

    def test_class_is_document_subclass(self):
        from frappe.model.document import Document
        from prakash_steel.po_recommendation_history.doctype.so_recommendation_snapshot.so_recommendation_snapshot import (
            SORecommendationSnapshot,
        )
        self.assertTrue(issubclass(SORecommendationSnapshot, Document))


if __name__ == "__main__":
    unittest.main()
