# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

"""Unit tests for Answer doctype — no DB required."""

import json
import os
import unittest

from frappe.tests.utils import FrappeTestCase


class TestAnswer(FrappeTestCase):
    def _load_json(self):
        json_path = os.path.join(os.path.dirname(__file__), "answer.json")
        with open(json_path) as f:
            return json.load(f)

    def test_has_option_field(self):
        meta = self._load_json()
        fieldnames = {f["fieldname"] for f in meta.get("fields", [])}
        self.assertIn("option", fieldnames)

    def test_option_is_data_type(self):
        meta = self._load_json()
        field_map = {f["fieldname"]: f for f in meta.get("fields", [])}
        self.assertEqual(field_map["option"]["fieldtype"], "Data")

    def test_autoname_uses_option_field(self):
        meta = self._load_json()
        self.assertEqual(meta.get("autoname"), "field:option")

    def test_class_importable(self):
        from prakash_steel.prakash_steel.doctype.answer.answer import Answer
        self.assertTrue(callable(Answer))

    def test_doctype_name(self):
        meta = self._load_json()
        self.assertEqual(meta.get("name"), "Answer")


if __name__ == "__main__":
    unittest.main()
