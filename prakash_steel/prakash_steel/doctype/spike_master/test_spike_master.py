# Copyright (c) 2026, beetashoke chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

TEST_ITEM_TYPE = "_TEST-IT-SPIKE"


class TestSpikeMaster(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Item Type", TEST_ITEM_TYPE):
			frappe.get_doc({"doctype": "Item Type", "item_type": TEST_ITEM_TYPE}).insert(
				ignore_permissions=True
			)

	@classmethod
	def tearDownClass(cls):
		if frappe.db.exists("Spike Master", TEST_ITEM_TYPE):
			frappe.delete_doc("Spike Master", TEST_ITEM_TYPE, ignore_permissions=True, force=True)
		if frappe.db.exists("Item Type", TEST_ITEM_TYPE):
			frappe.delete_doc("Item Type", TEST_ITEM_TYPE, ignore_permissions=True, force=True)
		super().tearDownClass()

	def tearDown(self):
		if frappe.db.exists("Spike Master", TEST_ITEM_TYPE):
			frappe.delete_doc("Spike Master", TEST_ITEM_TYPE, ignore_permissions=True, force=True)

	def test_create_spike_master(self):
		doc = frappe.get_doc(
			{
				"doctype": "Spike Master",
				"item_type": TEST_ITEM_TYPE,
				"demand_horizon": 13,
				"spike_threshold": 50,
			}
		).insert(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Spike Master", TEST_ITEM_TYPE))
		self.assertEqual(doc.name, TEST_ITEM_TYPE)

	def test_mandatory_item_type_field(self):
		doc = frappe.new_doc("Spike Master")
		doc.demand_horizon = 13
		doc.spike_threshold = 50
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_demand_horizon_field(self):
		doc = frappe.new_doc("Spike Master")
		doc.item_type = TEST_ITEM_TYPE
		doc.spike_threshold = 50
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_mandatory_spike_threshold_field(self):
		doc = frappe.new_doc("Spike Master")
		doc.item_type = TEST_ITEM_TYPE
		doc.demand_horizon = 13
		self.assertRaises(frappe.exceptions.MandatoryError, doc.insert)

	def test_read_spike_master(self):
		frappe.get_doc(
			{
				"doctype": "Spike Master",
				"item_type": TEST_ITEM_TYPE,
				"demand_horizon": 26,
				"spike_threshold": 75,
			}
		).insert(ignore_permissions=True)
		fetched = frappe.get_doc("Spike Master", TEST_ITEM_TYPE)
		self.assertEqual(fetched.item_type, TEST_ITEM_TYPE)
		self.assertEqual(fetched.demand_horizon, 26)
		self.assertEqual(fetched.spike_threshold, 75)

	def test_update_spike_master(self):
		frappe.get_doc(
			{
				"doctype": "Spike Master",
				"item_type": TEST_ITEM_TYPE,
				"demand_horizon": 13,
				"spike_threshold": 50,
			}
		).insert(ignore_permissions=True)
		doc = frappe.get_doc("Spike Master", TEST_ITEM_TYPE)
		doc.demand_horizon = 52
		doc.save(ignore_permissions=True)
		updated = frappe.get_doc("Spike Master", TEST_ITEM_TYPE)
		self.assertEqual(updated.demand_horizon, 52)
