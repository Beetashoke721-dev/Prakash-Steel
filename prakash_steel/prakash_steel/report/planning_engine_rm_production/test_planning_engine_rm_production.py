# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for planning_engine_rm_production report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.planning_engine_rm_production.planning_engine_rm_production"


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        from prakash_steel.prakash_steel.report.planning_engine_rm_production.planning_engine_rm_production import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("production_date", "item_name", "actual_qty"):
            self.assertIn(f, fieldnames)

    def test_returns_list(self):
        from prakash_steel.prakash_steel.report.planning_engine_rm_production.planning_engine_rm_production import get_columns
        self.assertIsInstance(get_columns(), list)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from prakash_steel.prakash_steel.report.planning_engine_rm_production.planning_engine_rm_production import execute
        mock_frappe.db.sql.return_value = []
        cols, data = execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)

    @patch(MOD + ".frappe")
    def test_empty_data(self, mock_frappe):
        from prakash_steel.prakash_steel.report.planning_engine_rm_production.planning_engine_rm_production import execute
        mock_frappe.db.sql.return_value = []
        _, data = execute({})
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
