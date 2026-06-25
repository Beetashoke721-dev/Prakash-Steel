# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for item_wise_stock_balance report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("item_code", "item_name", "item_group"):
            self.assertIn(f, fieldnames)

    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_item_group_filter_applied(self, mock_frappe):
        from prakash_steel.prakash_steel.report.item_wise_stock_balance.item_wise_stock_balance import get_data
        mock_frappe.db.sql.return_value = []
        get_data({"item_group": "Finished Goods"})
        mock_frappe.db.sql.assert_called_once()


if __name__ == "__main__":
    unittest.main()
