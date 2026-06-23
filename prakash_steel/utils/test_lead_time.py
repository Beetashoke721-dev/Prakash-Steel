# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for utils/lead_time.py — no DB required.

Tests the core recursive algorithm via _calculate_lead_time_recursive,
which is the pure-logic heart of the lead time calculation.
"""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.lead_time"


def _make_item(item_code, lead_time=0, item_group="Finished Goods", buffer_flag="Non-Buffer"):
    doc = MagicMock()
    doc.name = item_code
    doc.get = lambda k, d=None: {
        "lead_time_days": lead_time,
        "item_group": item_group,
        "custom_buffer_flag": buffer_flag,
    }.get(k, d)
    return doc


def _make_bom(*child_codes):
    bom = MagicMock()
    bom.items = [MagicMock(item_code=c) for c in child_codes]
    return bom


class TestCalculateLeadTimeRecursive(unittest.TestCase):
    """Tests for _calculate_lead_time_recursive — pure BOM traversal logic."""

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value=None)
    @patch(MOD + ".flt", side_effect=float)
    def test_raw_material_returns_own_lead_time(self, mock_flt, mock_bom, mock_frappe):
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        mock_frappe.get_doc.return_value = _make_item("RM-001", lead_time=14, item_group="Raw Material")
        result = _calculate_lead_time_recursive("RM-001", set())
        self.assertEqual(result, 14)
        mock_bom.assert_not_called()  # BOM lookup skipped for Raw Material

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value=None)
    @patch(MOD + ".flt", side_effect=float)
    def test_no_bom_returns_own_lead_time(self, mock_flt, mock_bom, mock_frappe):
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        mock_frappe.get_doc.return_value = _make_item("FG-001", lead_time=5)
        result = _calculate_lead_time_recursive("FG-001", set())
        self.assertEqual(result, 5)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value="BOM-001")
    @patch(MOD + ".flt", side_effect=float)
    def test_single_non_buffer_child_adds_to_parent(self, mock_flt, mock_bom, mock_frappe):
        """FG(3) → child(10) = 3 + 10 = 13"""
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        fg = _make_item("FG-001", lead_time=3)
        child = _make_item("CHILD-001", lead_time=10)
        bom = _make_bom("CHILD-001")

        def get_doc(doctype, name=None):
            if doctype == "Item":
                return {"FG-001": fg, "CHILD-001": child}[name or doctype]
            if doctype == "BOM":
                return bom
            return MagicMock()

        mock_frappe.get_doc.side_effect = get_doc
        result = _calculate_lead_time_recursive("FG-001", set())
        self.assertEqual(result, 13)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value="BOM-001")
    @patch(MOD + ".flt", side_effect=float)
    def test_buffer_child_contributes_zero(self, mock_flt, mock_bom, mock_frappe):
        """FG(3) → buffer_child(10) = 3 + 0 = 3 (buffer stops path)"""
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        fg = _make_item("FG-001", lead_time=3)
        child = _make_item("BUF-001", lead_time=10, buffer_flag="Buffer")
        bom = _make_bom("BUF-001")

        def get_doc(doctype, name=None):
            mapping = {"FG-001": fg, "BUF-001": child}
            if doctype == "Item":
                return mapping[name or doctype]
            if doctype == "BOM":
                return bom
            return MagicMock()

        mock_frappe.get_doc.side_effect = get_doc
        result = _calculate_lead_time_recursive("FG-001", set())
        self.assertEqual(result, 3)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value="BOM-001")
    @patch(MOD + ".flt", side_effect=float)
    def test_takes_max_of_multiple_children(self, mock_flt, mock_bom, mock_frappe):
        """FG(2) → [child_a(5), child_b(15)] = 2 + max(5,15) = 17"""
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        fg = _make_item("FG-001", lead_time=2)
        child_a = _make_item("CHILD-A", lead_time=5)
        child_b = _make_item("CHILD-B", lead_time=15)
        bom = _make_bom("CHILD-A", "CHILD-B")

        item_map = {"FG-001": fg, "CHILD-A": child_a, "CHILD-B": child_b}

        def get_doc(doctype, name=None):
            if doctype == "Item":
                return item_map[name or doctype]
            if doctype == "BOM":
                return bom
            return MagicMock()

        mock_frappe.get_doc.side_effect = get_doc
        # get_default_bom must return None for leaf items
        mock_bom.side_effect = lambda code: "BOM-001" if code == "FG-001" else None
        result = _calculate_lead_time_recursive("FG-001", set())
        self.assertEqual(result, 17)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value=None)
    @patch(MOD + ".flt", side_effect=float)
    def test_circular_reference_guard(self, mock_flt, mock_bom, mock_frappe):
        """Item already in visited_items returns 0."""
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        visited = {"ITEM-001"}
        result = _calculate_lead_time_recursive("ITEM-001", visited)
        self.assertEqual(result, 0)
        mock_frappe.get_doc.assert_not_called()

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value=None)
    @patch(MOD + ".flt", side_effect=float)
    def test_empty_item_code_returns_zero(self, mock_flt, mock_bom, mock_frappe):
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        result = _calculate_lead_time_recursive("", set())
        self.assertEqual(result, 0)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value=None)
    @patch(MOD + ".flt", side_effect=float)
    def test_item_with_zero_lead_time(self, mock_flt, mock_bom, mock_frappe):
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        mock_frappe.get_doc.return_value = _make_item("ITEM-001", lead_time=0)
        result = _calculate_lead_time_recursive("ITEM-001", set())
        self.assertEqual(result, 0)

    @patch(MOD + ".frappe")
    @patch(MOD + ".get_default_bom", return_value="BOM-001")
    @patch(MOD + ".flt", side_effect=float)
    def test_raw_material_child_contributes_own_lead_time(self, mock_flt, mock_bom, mock_frappe):
        """FG(2) → raw_material_child(7) = 2 + 7 = 9 (raw material has no BOM)"""
        from prakash_steel.utils.lead_time import _calculate_lead_time_recursive
        fg = _make_item("FG-001", lead_time=2)
        rm = _make_item("RM-001", lead_time=7, item_group="Raw Material")
        bom = _make_bom("RM-001")
        cache = {"RM-001": "Raw Material"}

        def get_doc(doctype, name=None):
            if doctype == "Item":
                return {"FG-001": fg, "RM-001": rm}[name or doctype]
            if doctype == "BOM":
                return bom
            return MagicMock()

        mock_frappe.get_doc.side_effect = get_doc
        mock_bom.side_effect = lambda code: "BOM-001" if code == "FG-001" else None
        result = _calculate_lead_time_recursive("FG-001", set(), cache)
        self.assertEqual(result, 9)


if __name__ == "__main__":
    unittest.main()
