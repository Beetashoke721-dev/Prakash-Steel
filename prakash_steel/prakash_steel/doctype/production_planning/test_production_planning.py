# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestProductionPlanning(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = (
			frappe.defaults.get_global_default("company")
			or (frappe.get_all("Company", limit=1) or [{"name": None}])[0]["name"]
		)

	def _make_production_planning(self, naming_series="Rolled Plan - .{posting_date}.-.####"):
		return frappe.get_doc(
			{
				"doctype": "Production Planning",
				"naming_series": naming_series,
				"posting_date": today(),
				"company": self.company,
				"shift_type": "Day",
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		for doc in frappe.get_all(
			"Production Planning",
			filters={"posting_date": today(), "company": self.company or ""},
		):
			try:
				d = frappe.get_doc("Production Planning", doc.name)
				if d.docstatus == 1:
					d.cancel()
				frappe.delete_doc(
					"Production Planning", doc.name, ignore_permissions=True, force=True
				)
			except Exception:
				pass

	def test_create_production_planning(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = self._make_production_planning()
		self.assertIsNotNone(doc.name)
		self.assertTrue(frappe.db.exists("Production Planning", doc.name))

	def test_mandatory_posting_date_field(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = frappe.new_doc("Production Planning")
		doc.naming_series = "Rolled Plan - .{posting_date}.-.####"
		doc.company = self.company
		doc.shift_type = "Day"
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_shift_type_field(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = frappe.new_doc("Production Planning")
		doc.naming_series = "Rolled Plan - .{posting_date}.-.####"
		doc.posting_date = today()
		doc.company = self.company
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_naming_series_field(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = frappe.new_doc("Production Planning")
		doc.posting_date = today()
		doc.company = self.company
		doc.shift_type = "Day"
		inserted = doc.insert(ignore_permissions=True)
		self.assertIsNotNone(inserted.name)
		frappe.delete_doc("Production Planning", inserted.name, ignore_permissions=True, force=True)

	def test_read_production_planning(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = self._make_production_planning("Bright Plan - .{posting_date}.-.####")
		fetched = frappe.get_doc("Production Planning", doc.name)
		self.assertEqual(fetched.company, self.company)
		self.assertEqual(fetched.shift_type, "Day")

	def test_doctype_is_submittable(self):
		meta = frappe.get_meta("Production Planning")
		self.assertTrue(meta.is_submittable)

	def test_submit_and_cancel_production_planning(self):
		if not self.company:
			self.skipTest("No company found in the system")
		doc = self._make_production_planning()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		doc.cancel()
		self.assertEqual(doc.docstatus, 2)
