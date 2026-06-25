# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Tests for open_mr_(wo)_report — no DB required."""

import importlib.util
import os
import unittest
from unittest.mock import patch

_REPORT_DIR = os.path.join(os.path.dirname(__file__))
_SOURCE_FILE = os.path.join(_REPORT_DIR, "open_mr_(wo)_report.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("open_mr_wo_report", _SOURCE_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestGetColumns(unittest.TestCase):
    def test_has_required_fields(self):
        mod = _load_module()
        fieldnames = [c["fieldname"] for c in mod.get_columns()]
        self.assertGreater(len(fieldnames), 0)
        for col in mod.get_columns():
            self.assertIn("fieldname", col)


class TestExecute(unittest.TestCase):
    def test_returns_tuple(self):
        mod = _load_module()
        with patch.object(mod, "frappe") as mock_frappe, \
             patch.object(mod, "require_permission", return_value=None):
            mock_frappe.db.sql.return_value = []
            mock_frappe.db.get_all.return_value = []
            cols, data = mod.execute({})
        self.assertIsInstance(cols, list)
        self.assertIsInstance(data, list)


if __name__ == "__main__":
    unittest.main()
