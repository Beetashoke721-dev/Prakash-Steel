# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

"""Unit tests for Billet Cutting Item doctype — no DB required."""

import json
import os
import unittest

from frappe.tests.utils import FrappeTestCase


class TestBilletCuttingItem(FrappeTestCase):
    def _load_json(self):
        json_path = os.path.join(os.path.dirname(__file__), "billet_cutting_item.json")
        with open(json_path) as f:
            return json.load(f)

    def test_doctype_is_child_table(self):
        meta = self._load_json()
        self.assertEqual(meta.get("istable"), 1)

    def test_required_fields_exist(self):
        meta = self._load_json()
        fieldnames = {f["fieldname"] for f in meta.get("fields", [])}
        required = {
            "billet_size",
            "billet_length",
            "billet_pcs",
            "billet_weight",
            "miss_billet_pcs",
            "miss_billet_weight",
            "total_billet_cutting_pcs",
            "ruffing_mill_status",
        }
        for field in required:
            self.assertIn(field, fieldnames, f"Missing field: {field}")

    def test_total_billet_cutting_pcs_is_int(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["total_billet_cutting_pcs"]["fieldtype"], "Int")

    def test_billet_size_is_link(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["billet_size"]["fieldtype"], "Link")

    def test_ruffing_mill_status_is_select(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["ruffing_mill_status"]["fieldtype"], "Select")

    def test_class_importable(self):
        from prakash_steel.prakash_steel.doctype.billet_cutting_item.billet_cutting_item import BilletCuttingItem
        self.assertTrue(callable(BilletCuttingItem))


if __name__ == "__main__":
    unittest.main()
