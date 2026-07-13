# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

"""Unit tests for Billet Cutting table doctype — no DB required."""

import json
import os
import unittest

from frappe.tests.utils import FrappeTestCase


class TestBilletCuttingtable(FrappeTestCase):
    def _load_json(self):
        json_path = os.path.join(os.path.dirname(__file__), "billet_cutting_table.json")
        with open(json_path) as f:
            return json.load(f)

    def test_doctype_is_not_child_table(self):
        meta = self._load_json()
        self.assertNotEqual(meta.get("istable"), 1)

    def test_has_posting_date_field(self):
        meta = self._load_json()
        fieldnames = {f["fieldname"] for f in meta.get("fields", [])}
        self.assertIn("posting_date", fieldnames)

    def test_has_items_table_field(self):
        meta = self._load_json()
        table_fields = [f for f in meta.get("fields", []) if f["fieldtype"] == "Table"]
        self.assertTrue(len(table_fields) >= 1, "Expected at least one Table field")

    def test_posting_date_is_date_type(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["posting_date"]["fieldtype"], "Date")

    def test_class_importable(self):
        from prakash_steel.prakash_steel.doctype.billet_cutting_table.billet_cutting_table import BilletCuttingtable
        self.assertTrue(callable(BilletCuttingtable))


if __name__ == "__main__":
    unittest.main()
