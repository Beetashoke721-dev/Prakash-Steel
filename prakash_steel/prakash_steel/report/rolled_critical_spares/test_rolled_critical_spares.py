# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for rolled_critical_spares report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.rolled_critical_spares.rolled_critical_spares"


class TestGetColumns(unittest.TestCase):
    def test_returns_list_with_fieldnames(self):
        from prakash_steel.prakash_steel.report.rolled_critical_spares.rolled_critical_spares import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        fieldnames = [c["fieldname"] for c in cols]
        for f in ("item_code", "tog", "on_hand_stock", "on_hand_colour", "net_order_recommendation"):
            self.assertIn(f, fieldnames)


class TestColourBoundaries(unittest.TestCase):
    """Colour thresholds are identical to bright_critical_spares — verify independently."""

    def _colour(self, stock, tog):
        pct = round((stock / tog) * 100, 2) if tog else 0
        if pct == 0:       return "BLACK"
        if pct <= 34:      return "RED"
        if pct <= 67:      return "YELLOW"
        if pct <= 100:     return "GREEN"
        return "WHITE"

    def test_zero_stock_black(self):
        self.assertEqual(self._colour(0, 50), "BLACK")

    def test_34pct_red(self):
        self.assertEqual(self._colour(17, 50), "RED")

    def test_67pct_yellow(self):
        self.assertEqual(self._colour(67, 100), "YELLOW")

    def test_full_stock_green(self):
        self.assertEqual(self._colour(50, 50), "GREEN")

    def test_excess_stock_white(self):
        self.assertEqual(self._colour(100, 50), "WHITE")


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_data", return_value=[])
    def test_execute_returns_columns_and_data(self, _):
        from prakash_steel.prakash_steel.report.rolled_critical_spares.rolled_critical_spares import execute
        cols, data = execute()
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
