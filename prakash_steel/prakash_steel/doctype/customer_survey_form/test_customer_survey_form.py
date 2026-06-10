# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCustomerSurveyForm(FrappeTestCase):
	def tearDown(self):
		for doc in frappe.get_all(
			"Customer Survey Form",
			filters={"customer_name": ["like", "_TEST-%"]},
			pluck="name",
		):
			frappe.delete_doc("Customer Survey Form", doc, ignore_permissions=True, force=True)

	def _make_doc(self, **overrides):
		data = {
			"doctype": "Customer Survey Form",
			"customer_name": "_TEST-CUSTOMER",
			"rating": "8",
			"reason": "Good quality products",
			"satisfaction_rating": "Which of the following aspects of our steel bars need significant improvement?",
			"future_support": "Better delivery timelines",
		}
		data.update(overrides)
		return frappe.get_doc(data)

	def test_create_customer_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		self.assertIsNotNone(doc.name)
		self.assertTrue(doc.name.startswith("CS-"))
		self.assertTrue(frappe.db.exists("Customer Survey Form", doc.name))

	def test_mandatory_customer_name_field(self):
		doc = self._make_doc(customer_name=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_rating_field(self):
		doc = self._make_doc(rating=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_reason_field(self):
		doc = self._make_doc(reason=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_future_support_field(self):
		doc = self._make_doc(future_support=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_customer_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		fetched = frappe.get_doc("Customer Survey Form", doc.name)
		self.assertEqual(fetched.customer_name, "_TEST-CUSTOMER")
		self.assertEqual(fetched.rating, "8")

	def test_update_customer_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		doc.rating = "9"
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Customer Survey Form", doc.name)
		self.assertEqual(updated.rating, "9")

	def test_checklist_fields_default_to_false(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		self.assertEqual(doc.dimensional_accuracy_size_straightness, 0)
		self.assertEqual(doc.surface_finish_of_the_bars, 0)
		self.assertEqual(doc.consistency_of_material_across_batches, 0)

	def test_checklist_fields_can_be_set(self):
		doc = self._make_doc(
			dimensional_accuracy_size_straightness=1,
			surface_finish_of_the_bars=1,
		)
		doc.insert(ignore_permissions=True)
		fetched = frappe.get_doc("Customer Survey Form", doc.name)
		self.assertEqual(fetched.dimensional_accuracy_size_straightness, 1)
		self.assertEqual(fetched.surface_finish_of_the_bars, 1)

	def test_delete_customer_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		frappe.delete_doc("Customer Survey Form", doc.name, ignore_permissions=True, force=True)
		self.assertFalse(frappe.db.exists("Customer Survey Form", doc.name))
