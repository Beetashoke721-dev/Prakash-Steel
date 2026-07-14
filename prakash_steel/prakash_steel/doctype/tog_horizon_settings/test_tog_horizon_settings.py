# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for TOG Horizon Settings doctype — no DB required."""

import json
import os
import unittest

from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestTOGHorizonSettings(IntegrationTestCase):
    """Integration tests for TOGHorizonSettings."""

    def _load_json(self):
        json_path = os.path.join(os.path.dirname(__file__), "tog_horizon_settings.json")
        with open(json_path) as f:
            return json.load(f)

    def test_required_fields_exist(self):
        meta = self._load_json()
        fieldnames = {f["fieldname"] for f in meta.get("fields", []) if not f["fieldtype"].endswith("Break")}
        for field in ("from_month", "to_month"):
            self.assertIn(field, fieldnames, f"Missing field: {field}")

    def test_from_month_is_date(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["from_month"]["fieldtype"], "Date")

    def test_to_month_is_date(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["to_month"]["fieldtype"], "Date")

    def test_doctype_name(self):
        meta = self._load_json()
        self.assertEqual(meta.get("name"), "TOG Horizon Settings")

    def test_class_importable(self):
        from prakash_steel.prakash_steel.doctype.tog_horizon_settings.tog_horizon_settings import TOGHorizonSettings
        self.assertTrue(callable(TOGHorizonSettings))


if __name__ == "__main__":
    unittest.main()
