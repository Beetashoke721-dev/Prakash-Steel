# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestItemwiseDailyOnHandColour(FrappeTestCase):
	TEST_DATE = "2099-01-01"

	def tearDown(self):
		if frappe.db.exists("Item wise Daily On Hand Colour", self.TEST_DATE):
			frappe.delete_doc(
				"Item wise Daily On Hand Colour",
				self.TEST_DATE,
				ignore_permissions=True,
				force=True,
			)

	def test_create_item_wise_daily_on_hand_colour(self):
		doc = frappe.get_doc(
			{"doctype": "Item wise Daily On Hand Colour", "posting_date": self.TEST_DATE}
		).insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Item wise Daily On Hand Colour", self.TEST_DATE))

	def test_autoname_from_posting_date(self):
		doc = frappe.get_doc(
			{"doctype": "Item wise Daily On Hand Colour", "posting_date": self.TEST_DATE}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, self.TEST_DATE)

	def test_read_item_wise_daily_on_hand_colour(self):
		frappe.get_doc(
			{"doctype": "Item wise Daily On Hand Colour", "posting_date": self.TEST_DATE}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Item wise Daily On Hand Colour", self.TEST_DATE)
		self.assertEqual(str(fetched.posting_date), self.TEST_DATE)

	def test_table_field_exists(self):
		meta = frappe.get_meta("Item wise Daily On Hand Colour")
		table_fields = [f for f in meta.fields if f.fieldtype == "Table"]
		self.assertTrue(len(table_fields) > 0)

	def test_delete_item_wise_daily_on_hand_colour(self):
		doc = frappe.get_doc(
			{"doctype": "Item wise Daily On Hand Colour", "posting_date": self.TEST_DATE}
		).insert(ignore_permissions=True)
		frappe.delete_doc(
			"Item wise Daily On Hand Colour", doc.name, ignore_permissions=True, force=True
		)
		self.assertFalse(frappe.db.exists("Item wise Daily On Hand Colour", self.TEST_DATE))
