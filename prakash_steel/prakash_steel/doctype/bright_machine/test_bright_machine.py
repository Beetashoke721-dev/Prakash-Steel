# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-BM-001", "_TEST-BM-002"]


class TestBrightMachine(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Bright Machine", name):
				frappe.delete_doc("Bright Machine", name, ignore_permissions=True, force=True)

	def _make_bright_machine(self, name):
		return frappe.get_doc(
			{
				"doctype": "Bright Machine",
				"machine_group_name": name,
				"no_of_machines": 2,
				"oee": 85.0,
				"runtime": 8.5,
			}
		).insert(ignore_permissions=True)

	def test_create_bright_machine(self):
		doc = self._make_bright_machine("_TEST-BM-001")
		self.assertTrue(frappe.db.exists("Bright Machine", "_TEST-BM-001"))

	def test_autoname_equals_machine_group_name(self):
		doc = self._make_bright_machine("_TEST-BM-001")
		self.assertEqual(doc.name, doc.machine_group_name)

	def test_mandatory_fields(self):
		# missing machine_group_name
		doc = frappe.new_doc("Bright Machine")
		doc.no_of_machines = 2
		doc.oee = 85.0
		doc.runtime = 8.0
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_no_of_machines(self):
		doc = frappe.new_doc("Bright Machine")
		doc.machine_group_name = "_TEST-BM-001"
		doc.oee = 85.0
		doc.runtime = 8.0
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_bright_machine(self):
		self._make_bright_machine("_TEST-BM-002")
		fetched = frappe.get_doc("Bright Machine", "_TEST-BM-002")
		self.assertEqual(fetched.machine_group_name, "_TEST-BM-002")
		self.assertEqual(fetched.no_of_machines, 2)
		self.assertEqual(fetched.oee, 85.0)
		self.assertEqual(fetched.runtime, 8.5)

	def test_update_bright_machine(self):
		doc = self._make_bright_machine("_TEST-BM-001")
		doc.no_of_machines = 4
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Bright Machine", "_TEST-BM-001")
		self.assertEqual(updated.no_of_machines, 4)

	def test_delete_bright_machine(self):
		doc = self._make_bright_machine("_TEST-BM-001")
		frappe.delete_doc("Bright Machine", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Bright Machine", "_TEST-BM-001"))
