# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-MM-001", "_TEST-MM-002"]


class TestMachineMaster(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Machine Master", name):
				frappe.delete_doc("Machine Master", name, ignore_permissions=True, force=True)

	def test_create_machine_master(self):
		doc = frappe.new_doc("Machine Master")
		doc.machine_name = "_TEST-MM-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Machine Master", "_TEST-MM-001"))

	def test_autoname_equals_machine_name(self):
		doc = frappe.get_doc(
			{"doctype": "Machine Master", "machine_name": "_TEST-MM-001"}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, doc.machine_name)

	def test_mandatory_machine_name_field(self):
		doc = frappe.new_doc("Machine Master")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_machine_master(self):
		frappe.get_doc({"doctype": "Machine Master", "machine_name": "_TEST-MM-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Machine Master", "_TEST-MM-002")
		self.assertEqual(fetched.machine_name, "_TEST-MM-002")

	def test_update_machine_master(self):
		doc = frappe.get_doc({"doctype": "Machine Master", "machine_name": "_TEST-MM-001"}).insert(
			ignore_permissions=True
		)
		doc.machine_name = "_TEST-MM-001-UPDATED"
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Machine Master", doc.name)
		self.assertEqual(updated.machine_name, "_TEST-MM-001-UPDATED")

	def test_delete_machine_master(self):
		doc = frappe.get_doc({"doctype": "Machine Master", "machine_name": "_TEST-MM-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("Machine Master", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Machine Master", "_TEST-MM-001"))
