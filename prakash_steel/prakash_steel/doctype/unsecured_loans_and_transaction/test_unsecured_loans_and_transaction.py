# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

LOAN_NAME = "Promoter Loan"


class TestUnsecuredLoansandTransaction(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.fiscal_year = None
		fiscal_years = frappe.get_all("Fiscal Year", order_by="year_start_date desc", limit=1)
		if fiscal_years:
			cls.fiscal_year = fiscal_years[0].name

	def tearDown(self):
		if self.fiscal_year:
			name = f"{LOAN_NAME} / {self.fiscal_year}"
			if frappe.db.exists("Unsecured Loans and Transaction", name):
				frappe.delete_doc(
					"Unsecured Loans and Transaction", name, ignore_permissions=True, force=True
				)

	def test_create_unsecured_loan_transaction(self):
		if not self.fiscal_year:
			self.skipTest("No Fiscal Year found in the system")
		doc = frappe.get_doc(
			{
				"doctype": "Unsecured Loans and Transaction",
				"unsecured_loan": LOAN_NAME,
				"financial_year": self.fiscal_year,
				"interest_percent": 12.5,
			}
		).insert(ignore_permissions=True)
		expected_name = f"{LOAN_NAME} / {self.fiscal_year}"
		self.assertEqual(doc.name, expected_name)
		self.assertTrue(frappe.db.exists("Unsecured Loans and Transaction", expected_name))

	def test_mandatory_unsecured_loan_field(self):
		if not self.fiscal_year:
			self.skipTest("No Fiscal Year found in the system")
		doc = frappe.new_doc("Unsecured Loans and Transaction")
		doc.financial_year = self.fiscal_year
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_financial_year_field(self):
		doc = frappe.new_doc("Unsecured Loans and Transaction")
		doc.unsecured_loan = LOAN_NAME
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_unsecured_loan_transaction(self):
		if not self.fiscal_year:
			self.skipTest("No Fiscal Year found in the system")
		frappe.get_doc(
			{
				"doctype": "Unsecured Loans and Transaction",
				"unsecured_loan": LOAN_NAME,
				"financial_year": self.fiscal_year,
				"interest_percent": 10.0,
			}
		).insert(ignore_permissions=True)
		expected_name = f"{LOAN_NAME} / {self.fiscal_year}"
		fetched = frappe.get_doc("Unsecured Loans and Transaction", expected_name)
		self.assertEqual(fetched.unsecured_loan, LOAN_NAME)
		self.assertEqual(fetched.financial_year, self.fiscal_year)
		self.assertEqual(fetched.interest_percent, 10.0)

	def test_update_interest_percent(self):
		if not self.fiscal_year:
			self.skipTest("No Fiscal Year found in the system")
		frappe.get_doc(
			{
				"doctype": "Unsecured Loans and Transaction",
				"unsecured_loan": LOAN_NAME,
				"financial_year": self.fiscal_year,
				"interest_percent": 10.0,
			}
		).insert(ignore_permissions=True)
		expected_name = f"{LOAN_NAME} / {self.fiscal_year}"
		doc = frappe.get_doc("Unsecured Loans and Transaction", expected_name)
		doc.interest_percent = 15.5
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Unsecured Loans and Transaction", expected_name)
		self.assertAlmostEqual(updated.interest_percent, 15.5, places=2)
