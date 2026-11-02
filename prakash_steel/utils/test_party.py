# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

"""Unit tests for utils/party.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.party"


def _make_doc(doctype, **fields):
	doc = MagicMock()
	doc.doctype = doctype
	doc.is_new.return_value = True
	doc.get = lambda field, default=None: fields.get(field, default)
	return doc


class TestWarnIfPartyDetailsMissing(unittest.TestCase):
	@patch(f"{MOD}.frappe")
	def test_skips_existing_documents(self, mock_frappe):
		from prakash_steel.utils.party import warn_if_party_details_missing

		doc = _make_doc("Supplier")
		doc.is_new.return_value = False
		warn_if_party_details_missing(doc)
		mock_frappe.msgprint.assert_not_called()

	@patch(f"{MOD}.frappe")
	def test_skips_other_doctypes(self, mock_frappe):
		from prakash_steel.utils.party import warn_if_party_details_missing

		warn_if_party_details_missing(_make_doc("Sales Invoice"))
		mock_frappe.msgprint.assert_not_called()

	@patch(f"{MOD}._", side_effect=lambda msg: msg)
	@patch(f"{MOD}.frappe")
	def test_warns_for_missing_supplier_details(self, mock_frappe, _mock_translate):
		from prakash_steel.utils.party import warn_if_party_details_missing

		doc = _make_doc("Supplier", accounts=[])
		warn_if_party_details_missing(doc)

		mock_frappe.msgprint.assert_called_once()
		message = mock_frappe.msgprint.call_args[0][0]
		self.assertIn("Default Accounts", message)
		self.assertIn("Mobile No", message)
		self.assertIn("Email ID", message)
		self.assertEqual(mock_frappe.msgprint.call_args.kwargs.get("title"), "Missing Information")

	@patch(f"{MOD}._", side_effect=lambda msg: msg)
	@patch(f"{MOD}.frappe")
	def test_warns_for_missing_customer_contact_fields_only(self, mock_frappe, _mock_translate):
		from prakash_steel.utils.party import warn_if_party_details_missing

		doc = _make_doc("Customer", accounts=[])
		warn_if_party_details_missing(doc)

		mock_frappe.msgprint.assert_called_once()
		message = mock_frappe.msgprint.call_args[0][0]
		self.assertNotIn("Default Accounts", message)
		self.assertIn("Mobile No", message)
		self.assertIn("Email ID", message)

	@patch(f"{MOD}.frappe")
	def test_no_warning_when_all_details_present(self, mock_frappe):
		from prakash_steel.utils.party import warn_if_party_details_missing

		doc = _make_doc(
			"Supplier",
			accounts=[{"account": "Creditors - P"}],
			mobile_no="9876543210",
			email_id="supplier@example.com",
		)
		warn_if_party_details_missing(doc)
		mock_frappe.msgprint.assert_not_called()

	@patch(f"{MOD}.frappe")
	def test_warns_only_for_missing_fields(self, mock_frappe):
		from prakash_steel.utils.party import warn_if_party_details_missing

		doc = _make_doc(
			"Customer",
			mobile_no="9876543210",
			email_id="customer@example.com",
		)
		warn_if_party_details_missing(doc)
		mock_frappe.msgprint.assert_not_called()
