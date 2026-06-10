# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestRollingAlgo(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.item_code = None
		items = frappe.get_all("Item", filters={"custom_item_type": ["!=", "BB"]}, limit=1)
		if items:
			cls.item_code = items[0].name
		else:
			items = frappe.get_all("Item", limit=1)
			if items:
				cls.item_code = items[0].name

	def tearDown(self):
		# Rolling Algo autoname uses spaces around colon so name != item_code
		# Clean up by item_code field value instead
		if self.item_code:
			for name in frappe.get_all(
				"Rolling Algo", filters={"item_code": self.item_code}, pluck="name"
			):
				frappe.delete_doc("Rolling Algo", name, ignore_permissions=True, force=True)

	def test_create_rolling_algo(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Rolling Algo",
				"item_code": self.item_code,
				"no_of_guide_setups": 2,
				"per_hour_planned_qty": 500,
			}
		).insert(ignore_permissions=True)
		self.assertIsNotNone(doc.name)
		self.assertTrue(
			frappe.db.exists("Rolling Algo", {"item_code": self.item_code})
		)

	def test_mandatory_item_code_field(self):
		doc = frappe.new_doc("Rolling Algo")
		doc.no_of_guide_setups = 2
		doc.per_hour_planned_qty = 500
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_no_of_guide_setups(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.new_doc("Rolling Algo")
		doc.item_code = self.item_code
		doc.per_hour_planned_qty = 500
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_per_hour_planned_qty(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.new_doc("Rolling Algo")
		doc.item_code = self.item_code
		doc.no_of_guide_setups = 2
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_rolling_algo(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Rolling Algo",
				"item_code": self.item_code,
				"no_of_guide_setups": 3,
				"per_hour_planned_qty": 750,
			}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Rolling Algo", doc.name)
		self.assertEqual(fetched.item_code, self.item_code)
		self.assertEqual(fetched.no_of_guide_setups, 3)
		self.assertEqual(fetched.per_hour_planned_qty, 750)

	def test_update_rolling_algo(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Rolling Algo",
				"item_code": self.item_code,
				"no_of_guide_setups": 2,
				"per_hour_planned_qty": 500,
			}
		).insert(ignore_permissions=True)
		doc.per_hour_planned_qty = 1000
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Rolling Algo", doc.name)
		self.assertEqual(updated.per_hour_planned_qty, 1000)
