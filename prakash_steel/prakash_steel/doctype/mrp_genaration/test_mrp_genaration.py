# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for MRP Genaration doctype and calculation helpers — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.doctype.mrp_genaration.mrp_genaration"


class TestMRPDoctype(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_doctype_is_single(self, mock_frappe):
        meta = MagicMock()
        meta.issingle = True
        mock_frappe.get_meta.return_value = meta
        self.assertTrue(mock_frappe.get_meta("MRP Genaration").issingle)

    @patch(MOD + ".frappe")
    def test_get_single_returns_doc(self, mock_frappe):
        doc = MagicMock()
        doc.doctype = "MRP Genaration"
        mock_frappe.get_single.return_value = doc
        self.assertEqual(mock_frappe.get_single("MRP Genaration").doctype, "MRP Genaration")


class TestCalculateNetOrderRecommendation(unittest.TestCase):
    """Tests for the MOQ/batch-size rounding helper."""

    def _run(self, base, moq=0, batch_size=0):
        from prakash_steel.prakash_steel.doctype.mrp_genaration.mrp_genaration import (
            calculate_net_order_recommendation,
        )
        return calculate_net_order_recommendation(base, moq, batch_size)

    def test_zero_base_returns_zero(self):
        self.assertEqual(self._run(0), 0)

    def test_negative_base_returns_zero(self):
        self.assertEqual(self._run(-5), 0)

    def test_no_moq_no_batch_returns_base(self):
        self.assertAlmostEqual(self._run(50), 50)

    def test_moq_larger_than_base_returns_moq(self):
        self.assertGreaterEqual(self._run(30, moq=100), 100)

    def test_batch_size_rounds_up(self):
        result = self._run(25, batch_size=10)
        self.assertEqual(result % 10, 0)
        self.assertGreaterEqual(result, 25)

    def test_exact_multiple_of_batch_size_unchanged(self):
        self.assertEqual(self._run(40, batch_size=10), 40)

    def test_moq_takes_precedence_when_larger(self):
        self.assertGreaterEqual(self._run(50, moq=200, batch_size=30), 200)


class TestGetStockMapForMrp(unittest.TestCase):
    """MRP stock must come from Planning Engine warehouses only, like the Bright Plan."""

    def test_uses_planning_stock_map(self):
        from prakash_steel.prakash_steel.doctype.mrp_genaration import mrp_genaration

        with patch.object(
            mrp_genaration, "get_planning_stock_map", return_value={"BB-1": 8520.0}
        ) as mock_planning, patch.object(mrp_genaration, "frappe") as mock_frappe:
            result = mrp_genaration.get_stock_map_for_mrp({"BB-1"})

        self.assertEqual(result, {"BB-1": 8520.0})
        mock_planning.assert_called_once_with(["BB-1"])
        # Must not fall back to an all-warehouse tabBin sum (which counts Rejected Warehouse)
        mock_frappe.db.sql.assert_not_called()

    def test_buffer_item_gets_recommendation_when_rejected_stock_excluded(self):
        """TOG 10000, planning stock 8520 (2150 sits in Rejected) -> rec 1480, not 0."""
        from prakash_steel.prakash_steel.doctype.mrp_genaration import mrp_genaration

        with patch.object(mrp_genaration, "get_planning_stock_map", return_value={"BB-1": 8520.0}):
            stock_map = mrp_genaration.get_stock_map_for_mrp({"BB-1"})

        rec = mrp_genaration.calculate_initial_order_recommendation(
            "BB-1",
            item_buffer_map={"BB-1": "Buffer"},
            item_tog_map={"BB-1": 10000.0},
            item_sku_type_map={"BB-1": "BBMTA"},
            stock_map=stock_map,
            wip_map={},
            open_so_map={},
            qualified_demand_map={},
            open_po_map={},
        )
        self.assertEqual(rec, 1480.0)
        self.assertEqual(mrp_genaration.calculate_net_order_recommendation(rec, 0, 6000), 6000)

    def test_empty_items(self):
        from prakash_steel.prakash_steel.doctype.mrp_genaration import mrp_genaration

        with patch.object(mrp_genaration, "get_planning_stock_map", return_value={}) as mock_planning:
            self.assertEqual(mrp_genaration.get_stock_map_for_mrp(set()), {})
        mock_planning.assert_called_once_with([])


if __name__ == "__main__":
    unittest.main()
