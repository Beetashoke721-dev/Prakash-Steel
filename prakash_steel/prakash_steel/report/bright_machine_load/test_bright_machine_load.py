# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bright_machine_load report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load"


class TestBuildItemMaps(unittest.TestCase):
    def test_returns_correct_keys(self):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import _build_item_maps
        items = [
            MagicMock(item_code="ITEM-A", buffer_flag="Buffer", item_type="BB", tog=100, moq=50, batch_size=0),
            MagicMock(item_code="ITEM-B", buffer_flag="Non-Buffer", item_type="RB", tog=0, moq=0, batch_size=25),
        ]
        item_codes, buffer_map, type_map, tog_map, moq_map, batch_map = _build_item_maps(items)
        self.assertIn("ITEM-A", item_codes)
        self.assertIn("ITEM-B", item_codes)
        self.assertEqual(buffer_map["ITEM-A"], "Buffer")
        self.assertEqual(type_map["ITEM-B"], "RB")
        self.assertEqual(moq_map["ITEM-A"], 50.0)
        self.assertEqual(batch_map["ITEM-B"], 25.0)

    def test_empty_items(self):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import _build_item_maps
        result = _build_item_maps([])
        item_codes = result[0]
        self.assertEqual(len(item_codes), 0)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    @patch(MOD + ".require_any_permission")
    def test_returns_tuple(self, mock_perm, mock_frappe):
        from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
