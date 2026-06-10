# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_GRADE = "_TEST-IG-WCC"
TEST_CC_1 = "_TEST-CC-WCC1"
TEST_CC_2 = "_TEST-CC-WCC2"


class TestItemGradewiseColourCode(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item Grade", TEST_GRADE):
			frappe.get_doc({"doctype": "Item Grade", "item_grade": TEST_GRADE}).insert(
				ignore_permissions=True
			)
		for cc in [TEST_CC_1, TEST_CC_2]:
			if not frappe.db.exists("Colour Code", cc):
				frappe.get_doc({"doctype": "Colour Code", "colour_code": cc}).insert(
					ignore_permissions=True
				)

	@classmethod
	def tearDownClass(cls):
		for name in [f"{TEST_GRADE}-{TEST_CC_1}", f"{TEST_GRADE}-{TEST_CC_2}"]:
			if frappe.db.exists("Item Grade wise Colour Code", name):
				frappe.delete_doc(
					"Item Grade wise Colour Code", name, ignore_permissions=True, force=True
				)
		for cc in [TEST_CC_1, TEST_CC_2]:
			if frappe.db.exists("Colour Code", cc):
				frappe.delete_doc("Colour Code", cc, ignore_permissions=True, force=True)
		if frappe.db.exists("Item Grade", TEST_GRADE):
			frappe.delete_doc("Item Grade", TEST_GRADE, ignore_permissions=True, force=True)
		super().tearDownClass()

	def tearDown(self):
		for name in [f"{TEST_GRADE}-{TEST_CC_1}", f"{TEST_GRADE}-{TEST_CC_2}"]:
			if frappe.db.exists("Item Grade wise Colour Code", name):
				frappe.delete_doc(
					"Item Grade wise Colour Code", name, ignore_permissions=True, force=True
				)

	def test_create_item_grade_wise_colour_code(self):
		doc = frappe.get_doc(
			{
				"doctype": "Item Grade wise Colour Code",
				"item_grade": TEST_GRADE,
				"colour_code": TEST_CC_1,
			}
		).insert(ignore_permissions=True)
		expected_name = f"{TEST_GRADE}-{TEST_CC_1}"
		self.assertEqual(doc.name, expected_name)
		self.assertTrue(frappe.db.exists("Item Grade wise Colour Code", expected_name))

	def test_mandatory_item_grade_field(self):
		doc = frappe.new_doc("Item Grade wise Colour Code")
		doc.colour_code = TEST_CC_1
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_colour_code_field(self):
		doc = frappe.new_doc("Item Grade wise Colour Code")
		doc.item_grade = TEST_GRADE
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_item_grade_wise_colour_code(self):
		frappe.get_doc(
			{
				"doctype": "Item Grade wise Colour Code",
				"item_grade": TEST_GRADE,
				"colour_code": TEST_CC_2,
			}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Item Grade wise Colour Code", f"{TEST_GRADE}-{TEST_CC_2}")
		self.assertEqual(fetched.item_grade, TEST_GRADE)
		self.assertEqual(fetched.colour_code, TEST_CC_2)

	def test_delete_item_grade_wise_colour_code(self):
		doc = frappe.get_doc(
			{
				"doctype": "Item Grade wise Colour Code",
				"item_grade": TEST_GRADE,
				"colour_code": TEST_CC_1,
			}
		).insert(ignore_permissions=True)
		frappe.delete_doc(
			"Item Grade wise Colour Code", doc.name, ignore_permissions=True, force=True
		)
		self.assertFalse(frappe.db.exists("Item Grade wise Colour Code", doc.name))
