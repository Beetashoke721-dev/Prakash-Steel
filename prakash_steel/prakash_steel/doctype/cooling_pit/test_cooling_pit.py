# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

TEST_MATERIAL_IN_TIME = "2099-01-01 08:00:00"


class TestCoolingPIT(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.item_code = None
		items = frappe.get_all("Item", limit=1)
		if items:
			cls.item_code = items[0].name

	def tearDown(self):
		if self.item_code:
			name = f"{self.item_code} - {TEST_MATERIAL_IN_TIME}"
			if frappe.db.exists("Cooling PIT", name):
				frappe.db.set_value("Cooling PIT", name, "docstatus", 2)
				frappe.delete_doc("Cooling PIT", name, ignore_permissions=True, force=True)
		# Cleanup any test Cooling PIT docs
		test_docs = frappe.get_all(
			"Cooling PIT",
			filters={"material_in_time": TEST_MATERIAL_IN_TIME},
			pluck="name",
		)
		for doc_name in test_docs:
			frappe.db.set_value("Cooling PIT", doc_name, "docstatus", 2)
			frappe.delete_doc("Cooling PIT", doc_name, ignore_permissions=True, force=True)

	def test_create_cooling_pit(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Cooling PIT",
				"item_code": self.item_code,
				"material_in_time": TEST_MATERIAL_IN_TIME,
			}
		).insert(ignore_permissions=True)
		self.assertIsNotNone(doc.name)
		self.assertTrue(frappe.db.exists("Cooling PIT", doc.name))

	def test_mandatory_item_code_field(self):
		doc = frappe.new_doc("Cooling PIT")
		doc.material_in_time = TEST_MATERIAL_IN_TIME
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_material_in_time_field(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.new_doc("Cooling PIT")
		doc.item_code = self.item_code
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_cooling_pit(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Cooling PIT",
				"item_code": self.item_code,
				"material_in_time": TEST_MATERIAL_IN_TIME,
			}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Cooling PIT", doc.name)
		self.assertEqual(fetched.item_code, self.item_code)

	def test_doctype_is_submittable(self):
		meta = frappe.get_meta("Cooling PIT")
		self.assertTrue(meta.is_submittable)

	def test_submit_cooling_pit(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Cooling PIT",
				"item_code": self.item_code,
				"material_in_time": TEST_MATERIAL_IN_TIME,
			}
		).insert(ignore_permissions=True)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		doc.cancel()
		self.assertEqual(doc.docstatus, 2)
