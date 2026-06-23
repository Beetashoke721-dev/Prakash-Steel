# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


class IntegrationTestDeliveryDelayReasonMaster(IntegrationTestCase):
	"""
	Integration tests for DeliveryDelayReasonMaster.
	"""

	def setUp(self):
		frappe.db.delete("Delivery Delay Reason Master", {"name": ["like", "_Test%"]})

	def tearDown(self):
		frappe.db.delete("Delivery Delay Reason Master", {"name": ["like", "_Test%"]})

	def make_doc(self, delay_reason):
		doc = frappe.get_doc({
			"doctype": "Delivery Delay Reason Master",
			"delay_reason": delay_reason,
		})
		doc.insert()
		return doc

	def test_name_set_from_delay_reason(self):
		"""Document name must equal the delay_reason value."""
		doc = self.make_doc("_Test Traffic Jam")
		self.assertEqual(doc.name, "_Test Traffic Jam")

	def test_create_with_different_reasons(self):
		"""Multiple distinct reasons can be created without conflict."""
		reasons = ["_Test Weather", "_Test Strike", "_Test Customs"]
		for reason in reasons:
			doc = self.make_doc(reason)
			self.assertEqual(doc.name, reason)

	def test_duplicate_delay_reason_raises_error(self):
		"""Inserting a duplicate delay_reason must raise a duplicate-name error."""
		self.make_doc("_Test Duplicate Reason")
		with self.assertRaises(frappe.DuplicateEntryError):
			self.make_doc("_Test Duplicate Reason")

	def test_fetch_after_insert(self):
		"""Document inserted must be retrievable by its delay_reason as the ID."""
		self.make_doc("_Test Port Congestion")
		fetched = frappe.get_doc("Delivery Delay Reason Master", "_Test Port Congestion")
		self.assertEqual(fetched.delay_reason, "_Test Port Congestion")

	def test_delete(self):
		"""Deleted document must no longer exist in the database."""
		self.make_doc("_Test To Delete")
		frappe.delete_doc("Delivery Delay Reason Master", "_Test To Delete")
		self.assertFalse(frappe.db.exists("Delivery Delay Reason Master", "_Test To Delete"))
