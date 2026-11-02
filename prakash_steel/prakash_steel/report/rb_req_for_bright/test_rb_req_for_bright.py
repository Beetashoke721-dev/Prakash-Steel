# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for rb_req_for_bright report — no DB required.

The Bright Plan's ``get_data`` is patched on the module object so the RB
roll-up (filter to RB children, sum Child Stock Shortage per item) can be
exercised without a database.
"""

import importlib
import unittest
from unittest.mock import patch

MOD = importlib.import_module(
    "prakash_steel.prakash_steel.report.rb_req_for_bright.rb_req_for_bright"
)


def bright_row(child_item_code, child_sku_type, child_stock_shortage):
    return {
        "child_item_code": child_item_code,
        "child_sku_type": child_sku_type,
        "child_stock_shortage": child_stock_shortage,
    }


class TestGetColumns(unittest.TestCase):
    def test_returns_item_code_and_rb_shortage(self):
        self.assertEqual(
            [c["fieldname"] for c in MOD.get_columns()],
            ["item_code", "rb_shortage"],
        )


class TestGetData(unittest.TestCase):
    @patch.object(MOD, "get_bright_plan_data")
    def test_sums_shortage_across_rows_for_the_same_child(self, mock_data):
        mock_data.return_value = [
            bright_row("RB-1", "RBMTA", 10),
            bright_row("RB-1", "RBMTA", 5),
            bright_row("RB-1", "RBMTA", 3),
        ]
        self.assertEqual(MOD.get_data({}), [{"item_code": "RB-1", "rb_shortage": 18}])

    @patch.object(MOD, "get_bright_plan_data")
    def test_keeps_only_rb_children(self, mock_data):
        mock_data.return_value = [
            bright_row("RB-1", "RBMTA", 10),
            bright_row("RB-2", "RBMTO", 7),
            bright_row("BLT-1", "PTA", 100),
            bright_row("BO-1", "BOTO", 50),
            bright_row("NONE-1", None, 20),
        ]
        self.assertEqual(
            MOD.get_data({}),
            [
                {"item_code": "RB-1", "rb_shortage": 10},
                {"item_code": "RB-2", "rb_shortage": 7},
            ],
        )

    @patch.object(MOD, "get_bright_plan_data")
    def test_skips_rows_without_child_item_code(self, mock_data):
        mock_data.return_value = [
            {"child_item_code": None, "child_sku_type": "RBMTA", "child_stock_shortage": 10},
        ]
        self.assertEqual(MOD.get_data({}), [])

    @patch.object(MOD, "get_bright_plan_data")
    def test_rounds_summed_shortage_up(self, mock_data):
        mock_data.return_value = [
            bright_row("RB-1", "RBMTA", 1.2),
            bright_row("RB-1", "RBMTA", 0.1),
        ]
        self.assertEqual(MOD.get_data({}), [{"item_code": "RB-1", "rb_shortage": 2}])

    @patch.object(MOD, "get_bright_plan_data")
    def test_drops_items_whose_summed_shortage_is_zero(self, mock_data):
        mock_data.return_value = [
            {"child_item_code": "RB-1", "child_sku_type": "RBMTA"},
            bright_row("RB-2", "RBMTA", 4),
            bright_row("RB-2", "RBMTA", -4),
            bright_row("RB-3", "RBMTO", 5),
        ]
        self.assertEqual(MOD.get_data({}), [{"item_code": "RB-3", "rb_shortage": 5}])

    @patch.object(MOD, "get_bright_plan_data")
    def test_results_sorted_by_shortage_high_to_low(self, mock_data):
        mock_data.return_value = [
            bright_row("RB-9", "RBMTA", 5),
            bright_row("RB-2", "RBMTO", 100),
            bright_row("RB-5", "RBMTA", 40),
        ]
        self.assertEqual(
            [r["item_code"] for r in MOD.get_data({})],
            ["RB-2", "RB-5", "RB-9"],
        )

    @patch.object(MOD, "get_bright_plan_data")
    def test_equal_shortages_break_ties_on_item_code(self, mock_data):
        mock_data.return_value = [
            bright_row("RB-9", "RBMTA", 7),
            bright_row("RB-2", "RBMTO", 7),
        ]
        self.assertEqual(
            [r["item_code"] for r in MOD.get_data({})],
            ["RB-2", "RB-9"],
        )


class TestExecute(unittest.TestCase):
    @patch.object(MOD, "get_bright_plan_data", return_value=[])
    def test_execute_returns_columns_and_data(self, _):
        cols, data = MOD.execute({})
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
