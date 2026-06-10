# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-CAT-001", "_TEST-CAT-002"]


class TestItemCategory(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Item Category", name):
				frappe.delete_doc("Item Category", name, ignore_permissions=True, force=True)

	def test_create_item_category(self):
		doc = frappe.new_doc("Item Category")
		doc.category_name = "_TEST-CAT-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Item Category", "_TEST-CAT-001"))

	def test_autoname_equals_category_name(self):
		doc = frappe.get_doc(
			{"doctype": "Item Category", "category_name": "_TEST-CAT-001"}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, doc.category_name)

	def test_mandatory_category_name_field(self):
		doc = frappe.new_doc("Item Category")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_item_category(self):
		frappe.get_doc({"doctype": "Item Category", "category_name": "_TEST-CAT-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Item Category", "_TEST-CAT-002")
		self.assertEqual(fetched.category_name, "_TEST-CAT-002")

	def test_delete_item_category(self):
		doc = frappe.get_doc({"doctype": "Item Category", "category_name": "_TEST-CAT-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("Item Category", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Item Category", "_TEST-CAT-001"))
