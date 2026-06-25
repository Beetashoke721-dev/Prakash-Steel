# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for day_book_entries report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.day_book_entries.day_book_entries"


class TestNormalizeFilterValue(unittest.TestCase):
    def _run(self, value):
        from prakash_steel.prakash_steel.report.day_book_entries.day_book_entries import _normalize_filter_value
        return _normalize_filter_value(value)

    def test_string_returned_as_is(self):
        self.assertEqual(self._run("CUST-001"), "CUST-001")

    def test_list_returns_first_truthy(self):
        self.assertEqual(self._run([None, "CUST-001", "CUST-002"]), "CUST-001")

    def test_empty_list_returns_empty_string(self):
        self.assertEqual(self._run([None, None]), "")

    def test_none_returns_empty_string(self):
        self.assertEqual(self._run(None), "")

    def test_tuple_returns_first_truthy(self):
        self.assertEqual(self._run((None, "JV-001")), "JV-001")


class TestGetColumns(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_has_required_fields(self, mock_frappe):
        from prakash_steel.prakash_steel.report.day_book_entries.day_book_entries import get_columns
        fieldnames = [c["fieldname"] for c in get_columns()]
        for f in ("date", "vch_type", "vch_no", "debit_amount", "credit_amount"):
            self.assertIn(f, fieldnames)


class TestExecute(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_returns_tuple(self, mock_frappe):
        from frappe import _dict
        from prakash_steel.prakash_steel.report.day_book_entries.day_book_entries import execute
        mock_frappe._dict.side_effect = _dict
        mock_frappe.db.sql.return_value = []
        mock_frappe.has_permission.return_value = True
        cols, data = execute({"date": "2026-06-25"})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
