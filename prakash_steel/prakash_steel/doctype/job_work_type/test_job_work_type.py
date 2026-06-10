# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-JWT-001", "_TEST-JWT-002"]


class TestJOBWorkType(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("JOB Work Type", name):
				frappe.delete_doc("JOB Work Type", name, ignore_permissions=True, force=True)

	def test_create_job_work_type(self):
		doc = frappe.new_doc("JOB Work Type")
		doc.job_work_type = "_TEST-JWT-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("JOB Work Type", "_TEST-JWT-001"))

	def test_mandatory_job_work_type_field(self):
		doc = frappe.new_doc("JOB Work Type")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_job_work_type(self):
		frappe.get_doc({"doctype": "JOB Work Type", "job_work_type": "_TEST-JWT-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("JOB Work Type", "_TEST-JWT-002")
		self.assertEqual(fetched.job_work_type, "_TEST-JWT-002")

	def test_update_job_work_type(self):
		doc = frappe.get_doc({"doctype": "JOB Work Type", "job_work_type": "_TEST-JWT-001"}).insert(
			ignore_permissions=True
		)
		doc.job_work_type = "_TEST-JWT-001-UPDATED"
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("JOB Work Type", doc.name)
		self.assertEqual(updated.job_work_type, "_TEST-JWT-001-UPDATED")

	def test_delete_job_work_type(self):
		doc = frappe.get_doc({"doctype": "JOB Work Type", "job_work_type": "_TEST-JWT-001"}).insert(
			ignore_permissions=True
		)
		frappe.delete_doc("JOB Work Type", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("JOB Work Type", "_TEST-JWT-001"))
