# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRootCauseAnalysis(FrappeTestCase):
	def test_create_root_cause_analysis(self):
		doc = frappe.get_doc(
			{
				"doctype": "Root Cause Analysis",
				"issue_date": "2026-09-03",
				"status": "Not Started",
			}
		).insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Root Cause Analysis", doc.name))
		frappe.delete_doc("Root Cause Analysis", doc.name, ignore_permissions=True, force=True)

	def test_can_insert_without_fields(self):
		doc = frappe.new_doc("Root Cause Analysis")
		doc.insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Root Cause Analysis", doc.name))
		frappe.delete_doc("Root Cause Analysis", doc.name, ignore_permissions=True, force=True)
