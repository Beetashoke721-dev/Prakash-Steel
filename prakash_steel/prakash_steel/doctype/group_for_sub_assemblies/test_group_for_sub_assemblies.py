# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-GROUP-001", "_TEST-GROUP-002"]


class TestGroupforSubAssemblies(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Group for Sub Assemblies", name):
				frappe.delete_doc("Group for Sub Assemblies", name, ignore_permissions=True, force=True)

	def test_create_group(self):
		doc = frappe.new_doc("Group for Sub Assemblies")
		doc.group_name = "_TEST-GROUP-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Group for Sub Assemblies", "_TEST-GROUP-001"))

	def test_autoname_equals_group_name(self):
		doc = frappe.get_doc(
			{"doctype": "Group for Sub Assemblies", "group_name": "_TEST-GROUP-001"}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, doc.group_name)

	def test_mandatory_group_name_field(self):
		doc = frappe.new_doc("Group for Sub Assemblies")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_group(self):
		frappe.get_doc(
			{"doctype": "Group for Sub Assemblies", "group_name": "_TEST-GROUP-002"}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Group for Sub Assemblies", "_TEST-GROUP-002")
		self.assertEqual(fetched.group_name, "_TEST-GROUP-002")

	def test_delete_group(self):
		doc = frappe.get_doc(
			{"doctype": "Group for Sub Assemblies", "group_name": "_TEST-GROUP-001"}
		).insert(ignore_permissions=True)
		frappe.delete_doc("Group for Sub Assemblies", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Group for Sub Assemblies", "_TEST-GROUP-001"))
