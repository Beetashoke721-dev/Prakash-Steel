# Copyright (c) 2026, Beetashoke Chakraborty and Contributors
# See license.txt

"""Unit tests for AMC Service Visit doctype business logic — no DB / no site.

The module-level `frappe` reference is stubbed via `patch.object(MOD, "frappe")`
and documents are built with `object.__new__` so `Document.__init__` (which
needs a bound site) is skipped. `frappe.throw` is wired to raise a real
`ValidationError` so guard clauses can be asserted.
"""

import unittest
from unittest.mock import patch

import frappe

from prakash_steel.prakash_steel.doctype.amc_service_visit import (
	amc_service_visit as MOD,
)


def make_visit(**attrs):
	doc = object.__new__(MOD.AMCServiceVisit)
	doc.__dict__.update({"name": "SER-0001", "amc_no": "AMC-0001"})
	doc.__dict__.update(attrs)
	return doc


def wire_throw(mock_frappe):
	mock_frappe.throw.side_effect = frappe.ValidationError
	mock_frappe.bold.side_effect = lambda v: str(v)


class TestValidateServicesRemaining(unittest.TestCase):
	@patch.object(MOD, "frappe")
	def test_noop_when_amc_no_missing(self, mock_frappe):
		make_visit(amc_no=None).validate_services_remaining()

		mock_frappe.db.get_value.assert_not_called()
		mock_frappe.db.count.assert_not_called()

	@patch.object(MOD, "frappe")
	def test_passes_when_services_remain(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 1  # 1 availed, 3 remain

		make_visit().validate_services_remaining()  # must not raise
		mock_frappe.throw.assert_not_called()

	@patch.object(MOD, "frappe")
	def test_passes_on_last_available_service(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 3  # this visit is the 4th

		make_visit().validate_services_remaining()  # must not raise
		mock_frappe.throw.assert_not_called()

	@patch.object(MOD, "frappe")
	def test_throws_when_all_services_availed(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 4

		with self.assertRaises(frappe.ValidationError):
			make_visit().validate_services_remaining()

	@patch.object(MOD, "frappe")
	def test_throws_when_over_availed(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 5

		with self.assertRaises(frappe.ValidationError):
			make_visit().validate_services_remaining()

	@patch.object(MOD, "frappe")
	def test_throws_when_total_is_zero(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 0
		mock_frappe.db.count.return_value = 0

		with self.assertRaises(frappe.ValidationError):
			make_visit().validate_services_remaining()

	@patch.object(MOD, "frappe")
	def test_count_excludes_current_doc_and_drafts(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 0

		make_visit(name="SER-0009").validate_services_remaining()

		doctype, filters = mock_frappe.db.count.call_args[0]
		self.assertEqual(doctype, "AMC Service Visit")
		self.assertEqual(filters["amc_no"], "AMC-0001")
		self.assertEqual(filters["docstatus"], 1)
		self.assertEqual(filters["name"], ("!=", "SER-0009"))

	@patch.object(MOD, "frappe")
	def test_validate_dispatches_to_services_check(self, mock_frappe):
		wire_throw(mock_frappe)
		mock_frappe.db.get_value.return_value = 4
		mock_frappe.db.count.return_value = 4

		with self.assertRaises(frappe.ValidationError):
			make_visit().validate()


class TestSubmitCancelHooks(unittest.TestCase):
	def test_on_submit_recalculates_amc(self):
		with patch.object(MOD, "recalculate_amc_services") as mock_recalc:
			make_visit().on_submit()
			mock_recalc.assert_called_once_with("AMC-0001")

	def test_on_cancel_recalculates_amc(self):
		with patch.object(MOD, "recalculate_amc_services") as mock_recalc:
			make_visit().on_cancel()
			mock_recalc.assert_called_once_with("AMC-0001")


if __name__ == "__main__":
	unittest.main()
