# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for open_work_order_report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.open_work_order_report.open_work_order_report"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.open_work_order_report.open_work_order_report import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("work_order", "date", "item"):
            self.assertIn(f, fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    @patch(MOD + ".require_permission")
    def test_returns_tuple(self, mock_perm, mock_frappe):
        from prakash_steel.prakash_steel.report.open_work_order_report.open_work_order_report import execute
        mock_frappe.db.sql.return_value = []
        mock_frappe.db.get_all.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
