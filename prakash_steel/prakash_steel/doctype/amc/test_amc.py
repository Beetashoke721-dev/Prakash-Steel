# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for AMC doctype business logic — no DB / no site required.

The module-level `frappe` reference is stubbed via `patch.object(MOD, "frappe")`
and documents are built with `object.__new__` so `Document.__init__` (which
needs a bound site) is skipped.
"""

import unittest
from unittest.mock import patch

from prakash_steel.prakash_steel.doctype.amc import amc as MOD


def make_amc(**attrs):
	doc = object.__new__(MOD.AMC)
	doc.__dict__.update(
		{
			"name": "AMC-0001",
			"total_services_available": 4,
			"services_availed": None,
			"services_remaining": None,
		}
	)
	doc.__dict__.update(attrs)
	return doc


class TestSetServiceCounts(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_remaining_equals_total_when_no_visits(self, mock_frappe):
		mock_frappe.db.count.return_value = 0
		doc = make_amc(total_services_available=4)

		doc.validate()

		self.assertEqual(doc.services_availed, 0)
		self.assertEqual(doc.services_remaining, 4)

	@patch.object(MOD, "frappe")
	def test_reflects_submitted_visits(self, mock_frappe):
		mock_frappe.db.count.return_value = 1
		doc = make_amc(total_services_available=4)

		doc.validate()

		self.assertEqual(doc.services_availed, 1)
		self.assertEqual(doc.services_remaining, 3)

	@patch.object(MOD, "frappe")
	def test_missing_total_treated_as_zero(self, mock_frappe):
		mock_frappe.db.count.return_value = 0
		doc = make_amc(total_services_available=None)

		doc.validate()

		self.assertEqual(doc.services_availed, 0)
		self.assertEqual(doc.services_remaining, 0)

	@patch.object(MOD, "frappe")
	def test_remaining_goes_negative_when_over_availed(self, mock_frappe):
		mock_frappe.db.count.return_value = 5
		doc = make_amc(total_services_available=4)

		doc.validate()

		self.assertEqual(doc.services_remaining, -1)


class TestGetServicesAvailed(unittest.TestCase):
	def test_returns_zero_without_amc_no(self):
		self.assertEqual(MOD.get_services_availed(None), 0)

	@patch.object(MOD, "frappe")
	def test_counts_submitted_visits_only(self, mock_frappe):
		mock_frappe.db.count.return_value = 3

		result = MOD.get_services_availed("AMC-0001")

		self.assertEqual(result, 3)
		mock_frappe.db.count.assert_called_once_with(
			"AMC Service Visit", {"amc_no": "AMC-0001", "docstatus": 1}
		)


class TestRecalculateAmcServices(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_noop_without_amc_no(self, mock_frappe):
		MOD.recalculate_amc_services(None)
		mock_frappe.db.set_value.assert_not_called()

	@patch.object(MOD, "frappe")
	def test_writes_availed_and_remaining(self, mock_frappe):
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 1

		MOD.recalculate_amc_services("AMC-0001")

		mock_frappe.db.set_value.assert_called_once_with(
			"AMC",
			"AMC-0001",
			{"services_availed": 1, "services_remaining": 3},
		)

	@patch.object(MOD, "frappe")
	def test_missing_total_treated_as_zero(self, mock_frappe):
		mock_frappe.db.get_value.return_value = None
		mock_frappe.db.count.return_value = 2

		MOD.recalculate_amc_services("AMC-0001")

		mock_frappe.db.set_value.assert_called_once_with(
			"AMC",
			"AMC-0001",
			{"services_availed": 2, "services_remaining": -2},
		)


if __name__ == "__main__":
	unittest.main()
