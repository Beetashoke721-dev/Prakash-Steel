# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for HBT Period Settings doctype — no DB required."""

import json
import os
import unittest

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestHBTPeriodSettings(IntegrationTestCase):
    """Integration tests for HBTPeriodSettings."""

    def _load_json(self):
        json_path = os.path.join(os.path.dirname(__file__), "hbt_period_settings.json")
        with open(json_path) as f:
            return json.load(f)

    def test_required_fields_exist(self):
        meta = self._load_json()
        fieldnames = {f["fieldname"] for f in meta.get("fields", []) if not f["fieldtype"].endswith("Break")}
        for field in ("fiscal_year", "from_month", "to_month"):
            self.assertIn(field, fieldnames, f"Missing field: {field}")

    def test_fiscal_year_is_link(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["fiscal_year"]["fieldtype"], "Link")

    def test_from_month_is_select(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["from_month"]["fieldtype"], "Select")

    def test_to_month_is_select(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["to_month"]["fieldtype"], "Select")

    def test_doctype_name(self):
        meta = self._load_json()
        self.assertEqual(meta.get("name"), "HBT Period Settings")

    def test_class_importable(self):
        from prakash_steel.prakash_steel.doctype.hbt_period_settings.hbt_period_settings import HBTPeriodSettings
        self.assertTrue(callable(HBTPeriodSettings))


if __name__ == "__main__":
    unittest.main()
