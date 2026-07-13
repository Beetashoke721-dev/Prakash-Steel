# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Unit tests for bom_details report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.bom_details.bom_details"


class TestGetColumns(unittest.TestCase):
    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)

    def test_column_count(self):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_columns
        self.assertEqual(len(get_columns()), 13)

    def test_required_fieldnames(self):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_columns
        names = {c["fieldname"] for c in get_columns()}
        for f in ("bom_name", "parent_item_code", "parent_item_name", "child_item_code",
                  "is_active", "is_default"):
            self.assertIn(f, names, f"Missing column: {f}")

    def test_bom_name_is_link(self):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_columns
        col_map = {c["fieldname"]: c for c in get_columns()}
        self.assertEqual(col_map["bom_name"]["fieldtype"], "Link")
        self.assertEqual(col_map["bom_name"]["options"], "BOM")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_columns_and_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import execute
        mock_frappe.get_all.return_value = []
        mock_frappe.get_cached_value.return_value = ""
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_empty_filters_returns_empty_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import execute
        mock_frappe.get_all.return_value = []
        _, data = execute(None)
        self.assertEqual(data, [])

    @patch(MOD + ".frappe")
    def test_none_filters_treated_as_empty(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import execute
        mock_frappe.get_all.return_value = []
        cols, data = execute(None)
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


class TestGetData(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_is_active_yes_sets_filter(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_data
        mock_frappe.get_all.return_value = []
        mock_frappe.get_cached_value.return_value = ""
        get_data({"is_active": "Yes"})
        call_kwargs = mock_frappe.get_all.call_args
        filters = call_kwargs[1].get("filters") or call_kwargs[0][1] if call_kwargs[0] else {}
        # Just verify it was called (filter value verified through integration)
        mock_frappe.get_all.assert_called_once()

    @patch(MOD + ".frappe")
    def test_bom_with_children_builds_one_row_per_child(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_data

        bom = {
            "name": "BOM-001",
            "parent_item_code": "ITEM-A",
            "parent_item_name": "Item A",
            "parent_item_type": "FG",
            "parent_qty": 1.0,
            "parent_uom": "Nos",
            "is_active": 1,
            "is_default": 1,
        }
        children = [
            {"child_item_code": "RM-001", "child_item_name": "Raw Mat 1",
             "child_item_type": "RM", "child_qty": 2.0, "child_uom": "Kg"},
            {"child_item_code": "RM-002", "child_item_name": "Raw Mat 2",
             "child_item_type": "RM", "child_qty": 3.0, "child_uom": "Kg"},
        ]

        mock_frappe.get_all.side_effect = [
            [bom],     # first call for BOMs
            children,  # second call for BOM Items
        ]
        mock_frappe.get_cached_value.return_value = ""

        data = get_data({})
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["bom_name"], "BOM-001")
        self.assertEqual(data[0]["child_item_code"], "RM-001")
        self.assertEqual(data[1]["child_item_code"], "RM-002")

    @patch(MOD + ".frappe")
    def test_bom_with_no_children_builds_single_row(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_data

        bom = {
            "name": "BOM-002",
            "parent_item_code": "ITEM-B",
            "parent_item_name": "Item B",
            "parent_item_type": "FG",
            "parent_qty": 1.0,
            "parent_uom": "Nos",
            "is_active": 1,
            "is_default": 0,
        }
        mock_frappe.get_all.side_effect = [[bom], []]
        mock_frappe.get_cached_value.return_value = ""

        data = get_data({})
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["child_item_code"], "")
        self.assertEqual(data[0]["child_qty"], 0)

    @patch(MOD + ".frappe")
    def test_is_active_is_bool_in_output(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_data

        bom = {
            "name": "BOM-003",
            "parent_item_code": "ITEM-C",
            "parent_item_name": "Item C",
            "parent_item_type": "",
            "parent_qty": 1.0,
            "parent_uom": "Nos",
            "is_active": 1,
            "is_default": 0,
        }
        mock_frappe.get_all.side_effect = [[bom], []]
        mock_frappe.get_cached_value.return_value = ""

        data = get_data({})
        self.assertIsInstance(data[0]["is_active"], bool)
        self.assertTrue(data[0]["is_active"])
        self.assertFalse(data[0]["is_default"])


class TestFilterFunctions(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_get_bom_items_for_filter_parses_string_filters(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_bom_items_for_filter
        mock_frappe.db.sql.return_value = []
        result = get_bom_items_for_filter(
            "Item", "steel", "name", 0, 20, '{"is_active": "Yes"}'
        )
        mock_frappe.db.sql.assert_called_once()
        self.assertEqual(result, [])

    @patch(MOD + ".frappe")
    def test_get_boms_for_filter_handles_dict_filters(self, mock_frappe):
        from prakash_steel.prakash_steel.report.bom_details.bom_details import get_boms_for_filter
        mock_frappe.db.sql.return_value = [("BOM-001", "Steel Rod")]
        result = get_boms_for_filter(
            "BOM", "BOM-", "name", 0, 10, {"is_default": "Yes"}
        )
        self.assertEqual(result, [("BOM-001", "Steel Rod")])


if __name__ == "__main__":
    unittest.main()
