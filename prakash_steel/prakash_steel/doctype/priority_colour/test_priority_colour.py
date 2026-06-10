# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-PC-001", "_TEST-PC-002"]


class TestPriorityColour(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Priority Colour", name):
				frappe.delete_doc("Priority Colour", name, ignore_permissions=True, force=True)

	def test_create_priority_colour(self):
		doc = frappe.new_doc("Priority Colour")
		doc.priotrity_colour = "_TEST-PC-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Priority Colour", "_TEST-PC-001"))

	def test_autoname_equals_priotrity_colour(self):
		doc = frappe.get_doc(
			{"doctype": "Priority Colour", "priotrity_colour": "_TEST-PC-001"}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, doc.priotrity_colour)

	def test_mandatory_priotrity_colour_field(self):
		doc = frappe.new_doc("Priority Colour")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_priority_colour(self):
		frappe.get_doc({"doctype": "Priority Colour", "priotrity_colour": "_TEST-PC-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Priority Colour", "_TEST-PC-002")
		self.assertEqual(fetched.priotrity_colour, "_TEST-PC-002")

	def test_delete_priority_colour(self):
		doc = frappe.get_doc(
			{"doctype": "Priority Colour", "priotrity_colour": "_TEST-PC-001"}
		).insert(ignore_permissions=True)
		frappe.delete_doc("Priority Colour", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Priority Colour", "_TEST-PC-001"))
