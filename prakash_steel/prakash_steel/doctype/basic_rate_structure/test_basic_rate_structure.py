# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class IntegrationTestBasicRateStructure(IntegrationTestCase):
	"""
	Integration tests for BasicRateStructure.
	Use this class for testing interactions between multiple components.
	"""

	def make_doc(self, payment_terms):
		return frappe.get_doc(
			{
				"doctype": "Basic Rate Structure",
				"date": frappe.utils.today(),
				"billet_basic_ms": 50,
				"rolling_charges": 10,
				"payment_terms": payment_terms,
				"ms_square": 2,
				"c4_round": 3,
				"c4_flat_square": 4,
				"round_bright_c4_difference": 1.5,
				"bright_round_basic_difference": 2,
				"bright_flat_basic_difference": 0.5,
			}
		)

	def test_rate_chain_15_days(self):
		doc = self.make_doc(payment_terms=15)
		doc.validate()

		self.assertEqual(doc.ms_round_basic_rate, 60.5)  # 50 + 10 + 0.5
		self.assertEqual(doc.ms_square_rate, 62.5)  # 60.5 + 2
		self.assertEqual(doc.c4_round_rate, 63.5)  # 3 + 60.5
		self.assertEqual(doc.c4_flat_square_rate, 67.5)  # 4 + 63.5
		self.assertEqual(doc.round_bright_c4_rate, 65.0)  # 63.5 + 1.5
		self.assertEqual(doc.bright_round_basic, 60.5)  # 50 + 8.5 + 2
		self.assertEqual(doc.bright_flat_basic, 66.0)  # 60.5 + 5 + 0.5

	def test_surcharge_30_days(self):
		doc = self.make_doc(payment_terms=30)
		doc.validate()
		self.assertEqual(doc.ms_round_basic_rate, 61.0)  # 50 + 10 + 1

	def test_surcharge_other_days(self):
		doc = self.make_doc(payment_terms=45)
		doc.validate()
		self.assertEqual(doc.ms_round_basic_rate, 60.0)  # 50 + 10 + 0
