# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestESSLBiometricSettings(FrappeTestCase):
	"""ESSL Biometric Settings is a Single doctype for biometric device configuration."""

	def setUp(self):
		self._original = {
			"api_url": frappe.db.get_single_value("ESSL Biometric Settings", "api_url"),
			"username": frappe.db.get_single_value("ESSL Biometric Settings", "username"),
		}

	def tearDown(self):
		doc = frappe.get_single("ESSL Biometric Settings")
		doc.api_url = self._original["api_url"] or ""
		doc.username = self._original["username"] or ""
		doc.save(ignore_permissions=True)

	def test_get_single_doctype(self):
		doc = frappe.get_single("ESSL Biometric Settings")
		self.assertIsNotNone(doc)
		self.assertEqual(doc.doctype, "ESSL Biometric Settings")

	def test_doctype_is_single(self):
		meta = frappe.get_meta("ESSL Biometric Settings")
		self.assertTrue(meta.issingle)

	def test_required_fields_exist(self):
		meta = frappe.get_meta("ESSL Biometric Settings")
		field_names = [f.fieldname for f in meta.fields]
		self.assertIn("api_url", field_names)
		self.assertIn("username", field_names)
		self.assertIn("password", field_names)
		self.assertIn("devices", field_names)

	def test_update_api_url(self):
		doc = frappe.get_single("ESSL Biometric Settings")
		doc.api_url = "http://test-essl-server.example.com/api"
		doc.username = "testuser"
		doc.password = "testpassword"
		doc.save(ignore_permissions=True)
		updated = frappe.get_single("ESSL Biometric Settings")
		self.assertEqual(updated.api_url, "http://test-essl-server.example.com/api")
		self.assertEqual(updated.username, "testuser")

	def test_devices_is_table_field(self):
		meta = frappe.get_meta("ESSL Biometric Settings")
		devices_field = next((f for f in meta.fields if f.fieldname == "devices"), None)
		self.assertIsNotNone(devices_field)
		self.assertEqual(devices_field.fieldtype, "Table")
