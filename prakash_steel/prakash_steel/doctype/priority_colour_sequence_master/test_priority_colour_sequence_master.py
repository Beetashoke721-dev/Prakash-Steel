# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestPriorityColourSequenceMaster(FrappeTestCase):
	"""Priority Colour Sequence Master is a Single doctype with a child table."""

	def test_get_single_doctype(self):
		doc = frappe.get_single("Priority Colour Sequence Master")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "Priority Colour Sequence Master")

	def test_doctype_is_single(self):
		meta = frappe.get_meta("Priority Colour Sequence Master")
		self.assertTrue(meta.issingle)

	def test_table_field_exists(self):
		meta = frappe.get_meta("Priority Colour Sequence Master")
		table_fields = [f for f in meta.fields if f.fieldtype == "Table"]
		self.assertTrue(len(table_fields) > 0)
