# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-ITEM-TYPE-001", "_TEST-ITEM-TYPE-002"]


class TestItemType(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Item Type", name):
				frappe.delete_doc("Item Type", name, ignore_permissions=True, force=True)

	def test_create_item_type(self):
		doc = frappe.new_doc("Item Type")
		doc.item_type = "_TEST-ITEM-TYPE-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Item Type", "_TEST-ITEM-TYPE-001"))

	def test_autoname_equals_item_type(self):
		doc = frappe.get_doc({"doctype": "Item Type", "item_type": "_TEST-ITEM-TYPE-001"}).insert(
			ignore_permissions=True
		)
		self.assertEqual(doc.name, doc.item_type)

	def test_mandatory_item_type_field(self):
		doc = frappe.new_doc("Item Type")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_item_type(self):
		frappe.get_doc({"doctype": "Item Type", "item_type": "_TEST-ITEM-TYPE-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Item Type", "_TEST-ITEM-TYPE-002")
		self.assertEqual(fetched.item_type, "_TEST-ITEM-TYPE-002")

	def test_delete_item_type(self):
		doc = frappe.get_doc({"doctype": "Item Type", "item_type": "_TEST-ITEM-TYPE-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("Item Type", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Item Type", "_TEST-ITEM-TYPE-001"))
