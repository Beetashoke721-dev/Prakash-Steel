# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.py

"""Tests for rolled_plan report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.rolled_plan.rolled_plan"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_list_with_fieldnames(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)


class TestPipelinePriority(unittest.TestCase):
    def _fn(self, row, wip=0, open_po=0, total_demand=0):
        from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import _pipeline_priority
        return _pipeline_priority(row, wip, open_po, total_demand)

    def test_rbmta_bands_stock_plus_wip_plus_po_in_thirds(self):
        # total = TOG 60 + demand 30 = 90 -> thirds at 30 / 60 / 90
        row = {"sku_type": "RBMTA", "tog": 60, "on_hand_stock": 10}
        self.assertEqual(self._fn({**row, "on_hand_stock": 0}, total_demand=30), "BLACK")
        self.assertEqual(self._fn(row, total_demand=30), "RED")
        self.assertEqual(self._fn(row, wip=30, total_demand=30), "YELLOW")
        self.assertEqual(self._fn(row, wip=30, open_po=40, total_demand=30), "GREEN")
        self.assertEqual(self._fn(row, wip=81, total_demand=30), "WHITE")

    def test_rbmta_rounds_tog_up_like_the_tog_column(self):
        row = {"sku_type": "RBMTA", "tog": 89.2, "on_hand_stock": 60}
        self.assertEqual(self._fn(row), "YELLOW")  # 60 <= 2/3 of ceil(89.2)=90

    def test_rbmto_mirrors_existing_priority(self):
        self.assertEqual(self._fn({"sku_type": "RBMTO", "colour": "Red"}, wip=999), "RED")
        self.assertEqual(self._fn({"sku_type": "RBMTO", "colour": None}), "")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
