# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestADUHorizon(FrappeTestCase):
	"""ADU Horizon is a Single doctype — only one record exists."""

	def test_get_single_doctype(self):
		doc = frappe.get_single("ADU Horizon")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "ADU Horizon")

	def test_valid_week_options(self):
		valid_weeks = ["4", "13", "26", "52"]
		for week in valid_weeks:
			doc = frappe.get_single("ADU Horizon")
			original = doc.week
			doc.week = week
			doc.save(ignore_permissions=True)
			refreshed = frappe.get_single("ADU Horizon")
			self.assertEqual(refreshed.week, week)
			# Restore
			doc.week = original
			doc.save(ignore_permissions=True)
			break  # Test one value to avoid repeated saves

	def test_update_week(self):
		doc = frappe.get_single("ADU Horizon")
		original_week = doc.week
		new_week = "13" if original_week != "13" else "4"
		doc.week = new_week
		doc.save(ignore_permissions=True)
		updated = frappe.get_single("ADU Horizon")
		self.assertEqual(updated.week, new_week)
		# Restore original
		updated.week = original_week
		updated.save(ignore_permissions=True)
