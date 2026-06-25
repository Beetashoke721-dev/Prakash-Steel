# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for warehouse_wise_stock_qty report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.warehouse_wise_stock_qty.warehouse_wise_stock_qty"


class TestGetColumns(unittest.TestCase):
    def test_has_warehouse_and_stock_qty(self):
        from prakash_steel.prakash_steel.report.warehouse_wise_stock_qty.warehouse_wise_stock_qty import get_columns
        cols = get_columns()
        fieldnames = [c["fieldname"] for c in cols]
        self.assertIn("warehouse", fieldnames)
        self.assertIn("stock_qty", fieldnames)


class TestExecute(unittest.TestCase):

    @patch(MOD + ".frappe")
    def test_returns_columns_and_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.warehouse_wise_stock_qty.warehouse_wise_stock_qty import execute
        mock_frappe.db.sql.return_value = [{"warehouse": "Main WH", "stock_qty": 500.0}]
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["warehouse"], "Main WH")

    @patch(MOD + ".frappe")
    def test_empty_returns_empty_list(self, mock_frappe):
        from prakash_steel.prakash_steel.report.warehouse_wise_stock_qty.warehouse_wise_stock_qty import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertEqual(data, [])

    @patch(MOD + ".frappe")
    def test_stock_qty_cast_to_float(self, mock_frappe):
        from prakash_steel.prakash_steel.report.warehouse_wise_stock_qty.warehouse_wise_stock_qty import execute
        mock_frappe.db.sql.return_value = [{"warehouse": "WH-01", "stock_qty": None}]
        _, data = execute({})
        self.assertEqual(data[0]["stock_qty"], 0.0)


if __name__ == "__main__":
    unittest.main()
