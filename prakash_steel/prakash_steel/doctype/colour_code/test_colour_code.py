# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-CC-001", "_TEST-CC-002"]


class TestColourCode(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Colour Code", name):
				frappe.delete_doc("Colour Code", name, ignore_permissions=True, force=True)

	def test_create_colour_code(self):
		doc = frappe.new_doc("Colour Code")
		doc.colour_code = "_TEST-CC-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Colour Code", "_TEST-CC-001"))

	def test_autoname_equals_colour_code(self):
		doc = frappe.get_doc({"doctype": "Colour Code", "colour_code": "_TEST-CC-001"}).insert(
			ignore_permissions=True
		)
		self.assertEqual(doc.name, doc.colour_code)

	def test_mandatory_colour_code_field(self):
		doc = frappe.new_doc("Colour Code")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_colour_code(self):
		frappe.get_doc({"doctype": "Colour Code", "colour_code": "_TEST-CC-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Colour Code", "_TEST-CC-002")
		self.assertEqual(fetched.colour_code, "_TEST-CC-002")

	def test_delete_colour_code(self):
		doc = frappe.get_doc({"doctype": "Colour Code", "colour_code": "_TEST-CC-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("Colour Code", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Colour Code", "_TEST-CC-001"))
