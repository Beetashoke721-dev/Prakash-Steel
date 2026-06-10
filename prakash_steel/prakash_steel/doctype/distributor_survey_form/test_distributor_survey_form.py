# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDistributorSurveyForm(FrappeTestCase):
	def tearDown(self):
		for doc in frappe.get_all(
			"Distributor Survey Form",
			filters={"distributor_name": ["like", "_TEST-%"]},
			pluck="name",
		):
			frappe.delete_doc(
				"Distributor Survey Form", doc, ignore_permissions=True, force=True
			)

	def _make_doc(self, **overrides):
		data = {
			"doctype": "Distributor Survey Form",
			"distributor_name": "_TEST-DISTRIBUTOR",
			"recommendation": "9",
			"primary_reason": "Reliable supply and good quality",
			"future_support": "Stronger after-sales support",
			"future_aspect": "Improved credit terms and faster dispatch",
		}
		data.update(overrides)
		return frappe.get_doc(data)

	def test_create_distributor_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		self.assertIsNotNone(doc.name)
		self.assertTrue(doc.name.startswith("DS-"))
		self.assertTrue(frappe.db.exists("Distributor Survey Form", doc.name))

	def test_mandatory_distributor_name_field(self):
		doc = self._make_doc(distributor_name=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_recommendation_field(self):
		doc = self._make_doc(recommendation=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_primary_reason_field(self):
		doc = self._make_doc(primary_reason=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_future_aspect_field(self):
		doc = self._make_doc(future_aspect=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_distributor_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		fetched = frappe.get_doc("Distributor Survey Form", doc.name)
		self.assertEqual(fetched.distributor_name, "_TEST-DISTRIBUTOR")
		self.assertEqual(fetched.recommendation, "9")

	def test_update_distributor_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		doc.recommendation = "10"
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Distributor Survey Form", doc.name)
		self.assertEqual(updated.recommendation, "10")

	def test_delete_distributor_survey_form(self):
		doc = self._make_doc().insert(ignore_permissions=True)
		frappe.delete_doc(
			"Distributor Survey Form", doc.name, ignore_permissions=True, force=True
		)
		self.assertFalse(frappe.db.exists("Distributor Survey Form", doc.name))
