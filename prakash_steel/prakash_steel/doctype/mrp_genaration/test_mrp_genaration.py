# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMRPGenaration(FrappeTestCase):
	"""MRP Genaration is a Single doctype with only a button field."""

	def test_get_single_doctype(self):
		doc = frappe.get_single("MRP Genaration")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "MRP Genaration")

	def test_doctype_is_single(self):
		meta = frappe.get_meta("MRP Genaration")
		self.assertTrue(meta.issingle)
