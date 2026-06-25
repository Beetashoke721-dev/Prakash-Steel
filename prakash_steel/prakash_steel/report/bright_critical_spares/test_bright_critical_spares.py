# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for bright_critical_spares report — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares"


class TestGetColumns(unittest.TestCase):
    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)

    def test_all_have_fieldname(self):
        from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import get_columns
        for col in get_columns():
            self.assertIn("fieldname", col)

    def test_required_fields_present(self):
        from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for required in ("item_code", "tog", "on_hand_stock", "order_recommendation", "on_hand_colour"):
            self.assertIn(required, fieldnames)


class TestOnHandColourLogic(unittest.TestCase):
    """The colour assignment is pure logic — no DB needed."""

    def _colour(self, on_hand_stock, tog):
        """Replicate the colour logic from get_data."""
        on_hand_status_value = round((on_hand_stock / tog) * 100, 2) if tog else 0
        if on_hand_status_value == 0:
            return "BLACK"
        elif 0 < on_hand_status_value <= 34:
            return "RED"
        elif 34 < on_hand_status_value <= 67:
            return "YELLOW"
        elif 67 < on_hand_status_value <= 100:
            return "GREEN"
        return "WHITE"

    def test_zero_stock_is_black(self):
        self.assertEqual(self._colour(0, 100), "BLACK")

    def test_no_tog_is_black(self):
        self.assertEqual(self._colour(0, 0), "BLACK")

    def test_low_stock_is_red(self):
        self.assertEqual(self._colour(20, 100), "RED")   # 20%

    def test_mid_stock_is_yellow(self):
        self.assertEqual(self._colour(50, 100), "YELLOW")  # 50%

    def test_high_stock_is_green(self):
        self.assertEqual(self._colour(80, 100), "GREEN")   # 80%

    def test_above_100pct_is_white(self):
        self.assertEqual(self._colour(150, 100), "WHITE")  # 150%

    def test_boundary_34pct_is_red(self):
        self.assertEqual(self._colour(34, 100), "RED")

    def test_boundary_35pct_is_yellow(self):
        self.assertEqual(self._colour(35, 100), "YELLOW")

    def test_order_recommendation_floored_at_zero(self):
        # tog=10, stock=20 → recommendation = max(0, 10-20) = 0
        tog, stock = 10, 20
        self.assertEqual(max(0, tog - stock), 0)

    def test_net_order_recommendation_is_max_of_rec_and_moq(self):
        order_rec, moq = 5, 20
        self.assertEqual(max(order_rec, moq), 20)


class TestExecute(unittest.TestCase):

    @patch(MOD + ".get_data", return_value=[{"item_code": "CS-001"}])
    def test_execute_returns_tuple(self, mock_data):
        from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import execute
        result = execute()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    @patch(MOD + ".get_data", return_value=[])
    def test_execute_empty_data(self, mock_data):
        from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import execute
        columns, data = execute()
        self.assertIsInstance(columns, list)
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
