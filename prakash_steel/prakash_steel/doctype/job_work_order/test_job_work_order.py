# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestJOBWorkOrder(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.customer = None
		customers = frappe.get_all("Customer", limit=1)
		if customers:
			cls.customer = customers[0].name

	def _make_job_work_order(self, job_work_type="Sale-Purchase"):
		return frappe.get_doc(
			{
				"doctype": "JOB Work Order",
				"job_work_type": job_work_type,
				"job_work_date": today(),
				"customer": self.customer,
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		for doc in frappe.get_all("JOB Work Order", filters={"customer": self.customer or ""}):
			try:
				d = frappe.get_doc("JOB Work Order", doc.name)
				if d.docstatus == 1:
					d.cancel()
				frappe.delete_doc("JOB Work Order", doc.name, ignore_permissions=True, force=True)
			except Exception:
				pass

	def test_create_job_work_order(self):
		if not self.customer:
			self.skipTest("No customer found in the system")
		doc = self._make_job_work_order()
		self.assertIsNotNone(doc.name)
		self.assertTrue(frappe.db.exists("JOB Work Order", doc.name))

	def test_mandatory_job_work_type_field(self):
		if not self.customer:
			self.skipTest("No customer found in the system")
		doc = frappe.new_doc("JOB Work Order")
		doc.job_work_date = today()
		doc.customer = self.customer
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_job_work_date_field(self):
		if not self.customer:
			self.skipTest("No customer found in the system")
		doc = frappe.new_doc("JOB Work Order")
		doc.job_work_type = "Sale-Purchase"
		doc.customer = self.customer
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_customer_field(self):
		doc = frappe.new_doc("JOB Work Order")
		doc.job_work_type = "Sale-Purchase"
		doc.job_work_date = today()
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_job_work_order(self):
		if not self.customer:
			self.skipTest("No customer found in the system")
		doc = self._make_job_work_order("Subcontracting")
		fetched = frappe.get_doc("JOB Work Order", doc.name)
		self.assertEqual(fetched.job_work_type, "Subcontracting")
		self.assertEqual(fetched.customer, self.customer)

	def test_doctype_is_submittable(self):
		meta = frappe.get_meta("JOB Work Order")
		self.assertTrue(meta.is_submittable)

	def test_submit_and_cancel_job_work_order(self):
		if not self.customer:
			self.skipTest("No customer found in the system")
		doc = self._make_job_work_order()
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		doc.cancel()
		self.assertEqual(doc.docstatus, 2)
