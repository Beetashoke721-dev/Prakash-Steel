# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import unittest
from unittest.mock import MagicMock, patch


def _make_doc(**kwargs):
	doc = MagicMock()
	for key, value in kwargs.items():
		setattr(doc, key, value)
	doc.get = lambda field, default=None: kwargs.get(field, default)
	return doc


def _make_item(item_code="ITEM-1"):
	item = MagicMock()
	item.item_code = item_code
	item.get = lambda field, default=None: item_code if field == "item_code" else default
	return item


class TestAttachmentValidation(unittest.TestCase):
	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_requires_mandatory_attachment_for_sales_invoice_with_stock_items(self, mock_frappe):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		mock_frappe.get_all.return_value = [{"name": "ITEM-1"}]
		doc = _make_doc(doctype="Sales Invoice", items=[_make_item()])
		self.assertTrue(requires_mandatory_attachment(doc))

	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_skips_sales_invoice_without_stock_items(self, mock_frappe):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		mock_frappe.get_all.return_value = []
		doc = _make_doc(doctype="Sales Invoice", items=[_make_item()])
		self.assertFalse(requires_mandatory_attachment(doc))

	def test_skips_sales_invoice_without_items(self):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		doc = _make_doc(doctype="Sales Invoice", items=[])
		self.assertFalse(requires_mandatory_attachment(doc))

	def test_requires_mandatory_attachment_for_purchase_receipt(self):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		doc = _make_doc(doctype="Purchase Receipt")
		self.assertTrue(requires_mandatory_attachment(doc))

	def test_requires_mandatory_attachment_for_material_transfer_stock_entry(self):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		doc = _make_doc(doctype="Stock Entry", purpose="Material Transfer")
		self.assertTrue(requires_mandatory_attachment(doc))

	def test_skips_non_material_transfer_stock_entry(self):
		from prakash_steel.utils.attachment_validation import requires_mandatory_attachment

		doc = _make_doc(doctype="Stock Entry", purpose="Material Issue")
		self.assertFalse(requires_mandatory_attachment(doc))

	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_validate_mandatory_attachment_throws_when_missing(self, mock_frappe):
		from prakash_steel.utils.attachment_validation import validate_mandatory_attachment

		mock_frappe.flags.in_migrate = False
		mock_frappe.flags.in_import = False
		mock_frappe.flags.in_test = False
		mock_frappe.db.exists.return_value = None
		mock_frappe.bold.side_effect = lambda value: value
		mock_frappe.throw.side_effect = Exception("attachment required")

		doc = _make_doc(doctype="Purchase Receipt", name="PR-0001")
		with self.assertRaises(Exception):
			validate_mandatory_attachment(doc)

	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_validate_mandatory_attachment_skips_system_context(self, mock_frappe):
		from prakash_steel.utils.attachment_validation import validate_mandatory_attachment

		mock_frappe.flags.in_migrate = True
		doc = _make_doc(doctype="Purchase Receipt", name="PR-0001")
		validate_mandatory_attachment(doc)
		mock_frappe.throw.assert_not_called()

	@patch("prakash_steel.utils.attachment_validation.now_datetime")
	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_prevent_protected_attachment_deletion_blocks_after_grace_period(
		self, mock_frappe, mock_now_datetime
	):
		from prakash_steel.utils.attachment_validation import (
			prevent_protected_attachment_deletion,
		)
		from frappe.utils import add_to_date, get_datetime

		mock_frappe.flags.in_migrate = False
		mock_frappe.flags.in_import = False
		mock_frappe.flags.in_test = False
		mock_frappe.throw.side_effect = Exception("delete blocked")

		created = get_datetime("2026-08-30 10:00:00")
		mock_now_datetime.return_value = add_to_date(created, hours=25)

		doc = _make_doc(
			attached_to_doctype="Sales Invoice",
			attached_to_name="SINV-0001",
			creation=created,
		)
		with self.assertRaises(Exception):
			prevent_protected_attachment_deletion(doc)

	@patch("prakash_steel.utils.attachment_validation.now_datetime")
	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_prevent_protected_attachment_deletion_allows_within_grace_period(
		self, mock_frappe, mock_now_datetime
	):
		from prakash_steel.utils.attachment_validation import (
			prevent_protected_attachment_deletion,
		)
		from frappe.utils import add_to_date, get_datetime

		mock_frappe.flags.in_migrate = False
		mock_frappe.flags.in_import = False
		mock_frappe.flags.in_test = False

		created = get_datetime("2026-08-30 10:00:00")
		mock_now_datetime.return_value = add_to_date(created, hours=12)

		doc = _make_doc(
			attached_to_doctype="Sales Invoice",
			attached_to_name="SINV-0001",
			creation=created,
		)
		prevent_protected_attachment_deletion(doc)
		mock_frappe.throw.assert_not_called()

	@patch("prakash_steel.utils.attachment_validation.frappe")
	def test_prevent_protected_attachment_deletion_ignores_other_doctypes(self, mock_frappe):
		from prakash_steel.utils.attachment_validation import (
			prevent_protected_attachment_deletion,
		)

		doc = _make_doc(attached_to_doctype="Purchase Invoice", attached_to_name="PINV-0001")
		prevent_protected_attachment_deletion(doc)
		mock_frappe.throw.assert_not_called()


if __name__ == "__main__":
	unittest.main()
