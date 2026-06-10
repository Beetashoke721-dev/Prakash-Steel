# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-GRADE-001", "_TEST-GRADE-002"]


class TestItemGrade(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Item Grade", name):
				frappe.delete_doc("Item Grade", name, ignore_permissions=True, force=True)

	def test_create_item_grade(self):
		doc = frappe.new_doc("Item Grade")
		doc.item_grade = "_TEST-GRADE-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Item Grade", "_TEST-GRADE-001"))

	def test_autoname_equals_item_grade(self):
		doc = frappe.get_doc({"doctype": "Item Grade", "item_grade": "_TEST-GRADE-001"}).insert(
			ignore_permissions=True
		)
		self.assertEqual(doc.name, doc.item_grade)

	def test_read_item_grade(self):
		frappe.get_doc({"doctype": "Item Grade", "item_grade": "_TEST-GRADE-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Item Grade", "_TEST-GRADE-002")
		self.assertEqual(fetched.item_grade, "_TEST-GRADE-002")
		self.assertEqual(fetched.doctype, "Item Grade")

	def test_delete_item_grade(self):
		doc = frappe.get_doc({"doctype": "Item Grade", "item_grade": "_TEST-GRADE-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("Item Grade", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Item Grade", "_TEST-GRADE-001"))
