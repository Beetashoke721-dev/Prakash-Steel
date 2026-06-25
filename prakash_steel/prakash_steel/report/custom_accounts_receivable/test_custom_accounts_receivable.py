# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for custom_accounts_receivable — no DB required.

This report is a thin passthrough wrapper around ERPNext's built-in
accounts_receivable report. We just verify the module loads and the
re-export is callable.
"""

import unittest

import pytest


@pytest.mark.skip(reason="erpnext initializes frappe.db at class-load time — requires bench run-tests")
class TestCustomAccountsReceivable(unittest.TestCase):

    def test_module_is_importable(self):
        """Verify the report module itself can be imported."""
        import importlib
        mod = importlib.import_module(
            "prakash_steel.prakash_steel.report.custom_accounts_receivable.custom_accounts_receivable"
        )
        self.assertIsNotNone(mod)

    def test_execute_is_callable(self):
        from prakash_steel.prakash_steel.report.custom_accounts_receivable.custom_accounts_receivable import execute
        self.assertTrue(callable(execute))


if __name__ == "__main__":
    unittest.main()
