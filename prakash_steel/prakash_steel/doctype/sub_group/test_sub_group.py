# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSubGroup(FrappeTestCase):
	TEST_SUB_GROUP_ID_1 = "_TSG-001"
	TEST_SUB_GROUP_ID_2 = "_TSG-002"

	def tearDown(self):
		for sg_id in [self.TEST_SUB_GROUP_ID_1, self.TEST_SUB_GROUP_ID_2]:
			if frappe.db.exists("Sub Group", sg_id):
				frappe.delete_doc("Sub Group", sg_id, ignore_permissions=True, force=True)

	def test_create_sub_group(self):
		doc = frappe.new_doc("Sub Group")
		doc.sub_group_id = self.TEST_SUB_GROUP_ID_1
		doc.sub_group_name = "Test Sub Group One"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Sub Group", self.TEST_SUB_GROUP_ID_1))

	def test_mandatory_sub_group_name_field(self):
		doc = frappe.new_doc("Sub Group")
		doc.sub_group_id = self.TEST_SUB_GROUP_ID_1
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_sub_group(self):
		frappe.get_doc(
			{
				"doctype": "Sub Group",
				"sub_group_id": self.TEST_SUB_GROUP_ID_2,
				"sub_group_name": "Test Sub Group Two",
			}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Sub Group", self.TEST_SUB_GROUP_ID_2)
		self.assertEqual(fetched.sub_group_name, "Test Sub Group Two")
		self.assertEqual(fetched.sub_group_id, self.TEST_SUB_GROUP_ID_2)

	def test_update_sub_group(self):
		doc = frappe.get_doc(
			{
				"doctype": "Sub Group",
				"sub_group_id": self.TEST_SUB_GROUP_ID_1,
				"sub_group_name": "Test Sub Group One",
			}
		).insert(ignore_permissions=True)
		doc.sub_group_name = "Updated Sub Group Name"
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Sub Group", self.TEST_SUB_GROUP_ID_1)
		self.assertEqual(updated.sub_group_name, "Updated Sub Group Name")

	def test_delete_sub_group(self):
		doc = frappe.get_doc(
			{
				"doctype": "Sub Group",
				"sub_group_id": self.TEST_SUB_GROUP_ID_1,
				"sub_group_name": "Test Sub Group One",
			}
		).insert(ignore_permissions=True)
		frappe.delete_doc("Sub Group", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Sub Group", self.TEST_SUB_GROUP_ID_1))
