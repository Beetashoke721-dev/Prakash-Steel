# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

PROTECTED_ATTACHMENT_DOCTYPES = frozenset(
	{
		"Sales Invoice",
		"Purchase Receipt",
		"Stock Entry",
	}
)

ATTACHMENT_DELETE_GRACE_HOURS = 24
ATTACHMENT_DELETE_LOCKED_MESSAGE = _("Attachments cannot be deleted after 24 hours.")


def _is_system_context() -> bool:
	return bool(
		frappe.flags.in_migrate or frappe.flags.in_import or frappe.flags.in_test
	)


def is_material_transfer(doc) -> bool:
	stock_entry_type = doc.get("stock_entry_type") or doc.get("purpose")
	return stock_entry_type == "Material Transfer"


def sales_invoice_has_stock_items(doc) -> bool:
	"""Return True when the invoice includes at least one maintain-stock item."""
	item_codes = list(
		{d.get("item_code") for d in (doc.get("items") or []) if d.get("item_code")}
	)
	if not item_codes:
		return False

	return bool(
		frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes], "is_stock_item": 1},
			limit=1,
		)
	)


def requires_mandatory_attachment(doc) -> bool:
	if doc.doctype == "Sales Invoice":
		return sales_invoice_has_stock_items(doc)
	if doc.doctype == "Stock Entry":
		return is_material_transfer(doc)
	return doc.doctype == "Purchase Receipt"


def default_attachment_label(doc) -> str:
	if doc.doctype == "Sales Invoice":
		return _("Test Certificate")
	return _("Attachment")


def has_document_attachment(doc) -> bool:
	return bool(
		frappe.db.exists(
			"File",
			{"attached_to_doctype": doc.doctype, "attached_to_name": doc.name},
		)
	)


def validate_mandatory_attachment(doc, method=None, *, attachment_label: str | None = None) -> None:
	"""Require at least one file attached before submit.

	Enforced at submit (not at save) because Frappe can only attach files to a
	document that already exists, so a draft must be saved first.
	"""
	if _is_system_context() or not requires_mandatory_attachment(doc):
		return

	label = attachment_label or default_attachment_label(doc)
	if has_document_attachment(doc):
		return

	frappe.throw(
		_("{0} is required before submitting the {1}.").format(
			frappe.bold(label),
			doc.doctype,
		),
		title=_("Attachment Required"),
	)


def is_attachment_deletion_locked(file_doc) -> bool:
	if file_doc.attached_to_doctype not in PROTECTED_ATTACHMENT_DOCTYPES:
		return False

	if not file_doc.creation:
		return True

	created = get_datetime(file_doc.creation)
	delete_allowed_until = add_to_date(created, hours=ATTACHMENT_DELETE_GRACE_HOURS)
	return now_datetime() >= delete_allowed_until


@frappe.whitelist()
def can_delete_protected_attachment(file_id: str) -> bool:
	file_doc = frappe.get_doc("File", file_id)
	file_doc.check_permission("write")
	return not is_attachment_deletion_locked(file_doc)


def prevent_protected_attachment_deletion(doc, method=None) -> None:
	"""Block deletion of attachments on protected doctypes after 24 hours."""
	if _is_system_context():
		return

	if not is_attachment_deletion_locked(doc):
		return

	frappe.throw(
		ATTACHMENT_DELETE_LOCKED_MESSAGE,
		title=_("Attachment Deletion Not Allowed"),
	)
