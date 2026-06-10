# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestColourWeightageMaster(FrappeTestCase):
	"""Colour Weightage Master is a Single doctype with a child table."""

	def test_get_single_doctype(self):
		doc = frappe.get_single("Colour Weightage Master")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "Colour Weightage Master")

	def test_doctype_is_single(self):
		meta = frappe.get_meta("Colour Weightage Master")
		self.assertTrue(meta.issingle)

	def test_table_field_exists(self):
		meta = frappe.get_meta("Colour Weightage Master")
		table_fields = [f for f in meta.fields if f.fieldtype == "Table"]
		self.assertTrue(len(table_fields) > 0)
