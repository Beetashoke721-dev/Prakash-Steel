# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

"""Unit tests for utils/journal_entry.py — no DB required."""

import unittest
from unittest.mock import MagicMock, patch

MOD = "prakash_steel.utils.journal_entry"


def _make_row(idx, account):
	row = MagicMock()
	row.idx = idx
	row.account = account
	return row


def _make_doc(rows):
	doc = MagicMock()
	doc.get = lambda k, d=None: rows if k == "accounts" else d
	return doc


class TestValidateNoIncomeAccounts(unittest.TestCase):
	@patch(f"{MOD}.frappe")
	def test_passes_when_no_income_accounts(self, mock_frappe):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		mock_frappe.get_all.return_value = []
		doc = _make_doc([_make_row(1, "Cash - P"), _make_row(2, "Creditors - P")])
		validate_no_income_accounts(doc)
		mock_frappe.throw.assert_not_called()

	@patch(f"{MOD}._", side_effect=lambda msg: msg)
	@patch(f"{MOD}.frappe")
	def test_throws_for_single_income_account(self, mock_frappe, _mock_translate):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		mock_frappe.get_all.return_value = ["Sales - P"]
		mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
		mock_frappe.throw.side_effect = Exception("income blocked")
		doc = _make_doc([_make_row(1, "Sales - P"), _make_row(2, "Debtors - P")])
		with self.assertRaises(Exception):
			validate_no_income_accounts(doc)
		mock_frappe.throw.assert_called_once()
		message = mock_frappe.throw.call_args[0][0]
		self.assertIn("Row 1", message)
		self.assertIn("Sales - P", message)
		self.assertNotIn("Sales Invoice", message)
		self.assertEqual(
			mock_frappe.throw.call_args.kwargs.get("title"),
			"Income Account Not Allowed",
		)

	@patch(f"{MOD}._", side_effect=lambda msg: msg)
	@patch(f"{MOD}.frappe")
	def test_throws_for_multiple_income_accounts(self, mock_frappe, _mock_translate):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		mock_frappe.get_all.return_value = ["Sales - P", "Other Income - P"]
		mock_frappe.bold.side_effect = lambda x: f"<b>{x}</b>"
		mock_frappe.throw.side_effect = Exception("income blocked")
		doc = _make_doc(
			[
				_make_row(1, "Sales - P"),
				_make_row(2, "Cash - P"),
				_make_row(3, "Other Income - P"),
			]
		)
		with self.assertRaises(Exception):
			validate_no_income_accounts(doc)
		message = mock_frappe.throw.call_args[0][0]
		self.assertIn("Row 1", message)
		self.assertIn("Row 3", message)

	@patch(f"{MOD}.frappe")
	def test_passes_with_empty_accounts(self, mock_frappe):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		doc = _make_doc([])
		validate_no_income_accounts(doc)
		mock_frappe.throw.assert_not_called()
		mock_frappe.get_all.assert_not_called()

	@patch(f"{MOD}.frappe")
	def test_passes_when_account_blank(self, mock_frappe):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		doc = _make_doc([_make_row(1, None), _make_row(2, "")])
		validate_no_income_accounts(doc)
		mock_frappe.throw.assert_not_called()
		mock_frappe.get_all.assert_not_called()

	@patch(f"{MOD}.frappe")
	def test_get_all_filters_income_root_type(self, mock_frappe):
		from prakash_steel.utils.journal_entry import validate_no_income_accounts

		mock_frappe.get_all.return_value = []
		doc = _make_doc([_make_row(1, "Sales - P"), _make_row(2, "Cash - P")])
		validate_no_income_accounts(doc)
		kwargs = mock_frappe.get_all.call_args.kwargs
		self.assertEqual(kwargs["filters"]["root_type"], "Income")
		self.assertEqual(kwargs["pluck"], "name")
