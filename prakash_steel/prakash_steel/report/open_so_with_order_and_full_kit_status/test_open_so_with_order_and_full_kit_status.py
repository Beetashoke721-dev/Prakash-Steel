# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for open_so_with_order_and_full_kit_status report — no DB required."""

import unittest
from unittest.mock import patch

MOD = "prakash_steel.prakash_steel.report.open_so_with_order_and_full_kit_status.open_so_with_order_and_full_kit_status"


class TestValidateFilters(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_throws_when_to_before_from(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_so_with_order_and_full_kit_status.open_so_with_order_and_full_kit_status import validate_filters
        mock_frappe.throw.side_effect = Exception("date error")
        with self.assertRaises(Exception):
            validate_filters({"from_date": "2026-06-01", "to_date": "2026-05-01"})


class TestGetAllowedCustomers(unittest.TestCase):
    @patch(MOD + ".frappe")
    def test_admin_has_no_restriction(self, mock_frappe):
        from prakash_steel.prakash_steel.report.open_so_with_order_and_full_kit_status.open_so_with_order_and_full_kit_status import get_allowed_customers_for_user
        mock_frappe.session.user = "Administrator"
        result = get_allowed_customers_for_user()
        # Administrator should return None (no restriction)
        self.assertIsNone(result)


class TestExecute(unittest.TestCase):
    def test_no_filters_returns_empty(self):
        from prakash_steel.prakash_steel.report.open_so_with_order_and_full_kit_status.open_so_with_order_and_full_kit_status import execute
        result = execute(None)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0], [])


if __name__ == "__main__":
    unittest.main()
