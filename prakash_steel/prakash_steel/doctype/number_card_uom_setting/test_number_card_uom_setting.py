# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestNumberCardUOMSetting(FrappeTestCase):
	def test_mandatory_number_card_field(self):
		doc = frappe.new_doc("Number Card UOM Setting")
		doc.uom = "Nos"
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_uom_field(self):
		number_cards = frappe.get_all("Number Card", limit=1)
		if not number_cards:
			self.skipTest("No Number Card found in the system")
		doc = frappe.new_doc("Number Card UOM Setting")
		doc.number_card = number_cards[0].name
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_create_with_valid_data(self):
		number_cards = frappe.get_all("Number Card", limit=1)
		if not number_cards:
			self.skipTest("No Number Card found in the system")
		uom_name = "Nos"
		if not frappe.db.exists("UOM", uom_name):
			self.skipTest("UOM 'Nos' not found in the system")
		# Skip if already exists
		expected_name = f"{number_cards[0].name}-UOM"
		if frappe.db.exists("Number Card UOM Setting", expected_name):
			self.skipTest(f"Number Card UOM Setting {expected_name} already exists")
		doc = frappe.get_doc(
			{
				"doctype": "Number Card UOM Setting",
				"number_card": number_cards[0].name,
				"uom": uom_name,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(doc.name, expected_name)
		frappe.delete_doc("Number Card UOM Setting", doc.name, ignore_permissions=True, force=True)

	def test_doctype_has_required_fields(self):
		meta = frappe.get_meta("Number Card UOM Setting")
		field_names = [f.fieldname for f in meta.fields]
		self.assertIn("number_card", field_names)
		self.assertIn("uom", field_names)
