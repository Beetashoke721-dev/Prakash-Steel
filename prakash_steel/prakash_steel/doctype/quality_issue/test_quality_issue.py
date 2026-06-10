# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_NAMES = ["_TEST-QI-001", "_TEST-QI-002"]


class TestQualityIssue(FrappeTestCase):
	def tearDown(self):
		for name in TEST_NAMES:
			if frappe.db.exists("Quality Issue", name):
				frappe.delete_doc("Quality Issue", name, ignore_permissions=True, force=True)

	def test_create_quality_issue(self):
		doc = frappe.new_doc("Quality Issue")
		doc.quality_issue_type = "_TEST-QI-001"
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Quality Issue", "_TEST-QI-001"))

	def test_autoname_equals_quality_issue_type(self):
		doc = frappe.get_doc(
			{"doctype": "Quality Issue", "quality_issue_type": "_TEST-QI-001"}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, doc.quality_issue_type)

	def test_mandatory_quality_issue_type_field(self):
		doc = frappe.new_doc("Quality Issue")
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_quality_issue(self):
		frappe.get_doc({"doctype": "Quality Issue", "quality_issue_type": "_TEST-QI-002"}).insert(
			ignore_permissions=True
		)
		fetched = frappe.get_doc("Quality Issue", "_TEST-QI-002")
		self.assertEqual(fetched.quality_issue_type, "_TEST-QI-002")

	def test_delete_quality_issue(self):
		doc = frappe.get_doc(
			{"doctype": "Quality Issue", "quality_issue_type": "_TEST-QI-001"}
		).insert(ignore_permissions=True)
		frappe.delete_doc("Quality Issue", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Quality Issue", "_TEST-QI-001"))
