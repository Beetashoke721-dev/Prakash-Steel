# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBrightMachineMaster(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.item_code = None
		items = frappe.get_all("Item", limit=1)
		if items:
			cls.item_code = items[0].name
		# Find a Bright Machine to use as machine_group_name in table rows
		cls.bright_machine = None
		bm = frappe.get_all("Bright Machine", limit=1)
		if bm:
			cls.bright_machine = bm[0].name

	def tearDown(self):
		if self.item_code and frappe.db.exists("Bright Machine Master", self.item_code):
			frappe.delete_doc(
				"Bright Machine Master", self.item_code, ignore_permissions=True, force=True
			)

	def _make_doc(self):
		"""Create a valid Bright Machine Master with one default machine row."""
		machine_row = {
			"doctype": "Bright Machine Master Table",
			"machine_group_name": self.bright_machine,
			"mt_per_hour_production": 100.0,
			"is_default": 1,
		}
		return frappe.get_doc(
			{
				"doctype": "Bright Machine Master",
				"item_code": self.item_code,
				"machine_details": [machine_row] if self.bright_machine else [],
			}
		)

	def test_create_bright_machine_master(self):
		if not self.item_code or not self.bright_machine:
			self.skipTest("No items or Bright Machines found in the system")
		doc = self._make_doc().insert(ignore_permissions=True)
		self.assertEqual(doc.name, self.item_code)
		self.assertTrue(frappe.db.exists("Bright Machine Master", self.item_code))

	def test_mandatory_item_code_field(self):
		doc = frappe.new_doc("Bright Machine Master")
		self.assertRaises(frappe.exceptions.MandatoryError, lambda: doc.insert(ignore_permissions=True))

	def test_read_bright_machine_master(self):
		if not self.item_code or not self.bright_machine:
			self.skipTest("No items or Bright Machines found in the system")
		self._make_doc().insert(ignore_permissions=True)
		fetched = frappe.get_doc("Bright Machine Master", self.item_code)
		self.assertEqual(fetched.item_code, self.item_code)

	def test_machine_details_table_field_exists(self):
		meta = frappe.get_meta("Bright Machine Master")
		table_fields = [f for f in meta.fields if f.fieldtype == "Table"]
		self.assertTrue(len(table_fields) > 0)
		self.assertEqual(table_fields[0].options, "Bright Machine Master Table")

	def test_delete_bright_machine_master(self):
		if not self.item_code or not self.bright_machine:
			self.skipTest("No items or Bright Machines found in the system")
		doc = self._make_doc().insert(ignore_permissions=True)
		frappe.delete_doc(
			"Bright Machine Master", doc.name, ignore_permissions=True, force=True
		)
		self.assertFalse(frappe.db.exists("Bright Machine Master", self.item_code))
