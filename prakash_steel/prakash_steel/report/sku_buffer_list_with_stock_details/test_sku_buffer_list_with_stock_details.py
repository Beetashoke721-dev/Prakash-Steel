# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for sku_buffer_list_with_stock_details — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.sku_buffer_list_with_stock_details.sku_buffer_list_with_stock_details"


class TestCalculateSkuType(unittest.TestCase):
    def _run(self, buffer_flag, item_type):
        from prakash_steel.prakash_steel.report.sku_buffer_list_with_stock_details.sku_buffer_list_with_stock_details import calculate_sku_type
        return calculate_sku_type(buffer_flag, item_type)

    def test_bb_buffer(self):       self.assertEqual(self._run("Buffer", "BB"), "BBMTA")
    def test_rb_non_buffer(self):   self.assertEqual(self._run("Non-Buffer", "RB"), "RBMTO")
    def test_traded_buffer(self):   self.assertEqual(self._run("Buffer", "Traded"), "TRMTA")
    def test_none_returns_none(self): self.assertIsNone(self._run("Buffer", None))
    def test_unknown_returns_none(self): self.assertIsNone(self._run("Non-Buffer", "CS"))


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_execute_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.sku_buffer_list_with_stock_details.sku_buffer_list_with_stock_details import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        mock_frappe._dict.side_effect = dict
        result = execute({})
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
