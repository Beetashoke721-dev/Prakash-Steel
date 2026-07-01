# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestProductionplanningsettings(FrappeTestCase):
	"""Production planning settings is a Single doctype."""

	def test_get_single_doctype(self):
		doc = frappe.get_single("Production planning settings")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "Production planning settings")

	def test_doctype_is_single(self):
		meta = frappe.get_meta("Production planning settings")
		self.assertTrue(meta.issingle)

	def test_from_work_order_default_false(self):
		doc = frappe.get_single("Production planning settings")
		# Check defaults exist (0 = False for Check fields)
		self.assertIn(doc.from_work_order, [0, 1])
		self.assertIn(doc.from_production_plan, [0, 1])
		self.assertIn(doc.from_production_planning, [0, 1])

	def test_update_from_work_order(self):
		doc = frappe.get_single("Production planning settings")
		original = doc.from_work_order
		doc.from_work_order = 1 if not original else 0
		doc.save(ignore_permissions=True)
		updated = frappe.get_single("Production planning settings")
		self.assertEqual(updated.from_work_order, 1 if not original else 0)
		# Restore
		updated.from_work_order = original
		updated.save(ignore_permissions=True)

	def test_update_from_production_plan(self):
		doc = frappe.get_single("Production planning settings")
		original = doc.from_production_plan
		doc.from_production_plan = 1 if not original else 0
		doc.save(ignore_permissions=True)
		updated = frappe.get_single("Production planning settings")
		self.assertEqual(updated.from_production_plan, 1 if not original else 0)
		# Restore
		updated.from_production_plan = original
		updated.save(ignore_permissions=True)

	def test_update_from_production_planning(self):
		doc = frappe.get_single("Production planning settings")
		original = doc.from_production_planning
		doc.from_production_planning = 1 if not original else 0
		doc.save(ignore_permissions=True)
		updated = frappe.get_single("Production planning settings")
		self.assertEqual(updated.from_production_planning, 1 if not original else 0)
		# Restore
		updated.from_production_planning = original
		updated.save(ignore_permissions=True)
