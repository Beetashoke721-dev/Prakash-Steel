# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for critical_spare_buffer_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.critical_spare_buffer_report.critical_spare_buffer_report"


class TestGetColumns(unittest.TestCase):
    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.critical_spare_buffer_report.critical_spare_buffer_report import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)

    def test_has_core_fields(self):
        from prakash_steel.prakash_steel.report.critical_spare_buffer_report.critical_spare_buffer_report import get_columns
        fieldnames = {c["fieldname"] for c in get_columns()}
        self.assertIn("item_code", fieldnames)
        self.assertIn("on_hand_stock", fieldnames)
        self.assertIn("order_recommendation", fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".get_data", return_value=[{"item_code": "CS-TEST"}])
    def test_returns_tuple(self, _):
        from prakash_steel.prakash_steel.report.critical_spare_buffer_report.critical_spare_buffer_report import execute
        result = execute()
        self.assertIsInstance(result, tuple)
        cols, data = result
        self.assertIsInstance(cols, list)
        self.assertEqual(data, [{"item_code": "CS-TEST"}])


if __name__ == "__main__":
    unittest.main()
