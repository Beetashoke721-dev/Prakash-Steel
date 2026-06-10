# Copyright (c) 2025, beetashoke chakraborty and Contributors
# See license.txt

import datetime

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


class TestHourlyProduction(FrappeTestCase):
	"""
	Hourly Production tracks rolling mill output per hour window.
	Requires: time_from, time_to, production_date, finish_item (Link->Item),
	          furnace_temparature, no_of_passes
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.item_code = None
		items = frappe.get_all("Item", limit=1)
		if items:
			cls.item_code = items[0].name

	def _make_doc(self, **overrides):
		data = {
			"doctype": "Hourly Production",
			"production_date": today(),
			"time_from": "08:00:00",
			"time_to": "09:00:00",
			"finish_item": self.item_code,
			"finish_item_pcs": 50,
			"furnace_temparature": 1200,
			"no_of_passes": 3,
		}
		data.update(overrides)
		return frappe.get_doc(data)

	def tearDown(self):
		test_docs = frappe.get_all(
			"Hourly Production",
			filters={"production_date": today(), "time_from": "08:00:00"},
			pluck="name",
		)
		for name in test_docs:
			try:
				d = frappe.get_doc("Hourly Production", name)
				if d.docstatus == 1:
					d.cancel()
				frappe.delete_doc("Hourly Production", name, ignore_permissions=True, force=True)
			except Exception:
				pass

	def test_create_hourly_production(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = self._make_doc().insert(ignore_permissions=True, ignore_links=True)
		self.assertIsNotNone(doc.name)
		self.assertTrue(frappe.db.exists("Hourly Production", doc.name))

	def test_mandatory_finish_item_field(self):
		doc = self._make_doc(finish_item=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_furnace_temparature_field(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = self._make_doc(furnace_temparature=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_no_of_passes_field(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = self._make_doc(no_of_passes=None)
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_hourly_production(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = self._make_doc().insert(ignore_permissions=True, ignore_links=True)
		fetched = frappe.get_doc("Hourly Production", doc.name)
		# Time fields are returned as datetime.timedelta from DB
		self.assertEqual(fetched.time_from, datetime.timedelta(hours=8))
		self.assertEqual(fetched.time_to, datetime.timedelta(hours=9))
		self.assertEqual(fetched.furnace_temparature, 1200)
		self.assertEqual(fetched.no_of_passes, 3)

	def test_update_hourly_production(self):
		if not self.item_code:
			self.skipTest("No items found in the system")
		doc = self._make_doc().insert(ignore_permissions=True, ignore_links=True)
		doc.furnace_temparature = 1250
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Hourly Production", doc.name)
		self.assertEqual(updated.furnace_temparature, 1250)

	def test_doctype_is_submittable(self):
		meta = frappe.get_meta("Hourly Production")
		self.assertTrue(meta.is_submittable)
