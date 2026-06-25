# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for po_snapshot_daily_view report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.po_recommendation_history.report.po_snapshot_daily_view.po_snapshot_daily_view"


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_list_with_fieldnames(self, mock_frappe):
        from prakash_steel.po_recommendation_history.report.po_snapshot_daily_view.po_snapshot_daily_view import get_columns
        cols = get_columns()
        self.assertIsInstance(cols, list)
        self.assertGreater(len(cols), 0)
        for col in cols:
            self.assertIn("fieldname", col)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.po_recommendation_history.report.po_snapshot_daily_view.po_snapshot_daily_view import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
