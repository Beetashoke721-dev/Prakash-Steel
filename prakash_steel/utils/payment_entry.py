import frappe
from frappe import _
from frappe.utils import now_datetime

from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_reference_details as _erpnext_get_reference_details,
)

INVOICE_DOCTYPES = ("Sales Invoice", "Purchase Invoice")


@frappe.whitelist()
def get_reference_details(
	reference_doctype, reference_name, party_account_currency, party_type=None, party=None
) -> dict:
	"""Wrapper around ERPNext's `get_reference_details` that also returns the
	invoice's `posting_date` under the key `custom_invoice_date`.

	The Payment Entry form's `reference_name` handler iterates over every key
	in the response and applies it to the row via `frappe.model.set_value`,
	which is exactly how `due_date` gets populated client-side. By including
	`custom_invoice_date` here, our field is set at the same instant as
	`due_date` (no separate round-trip, no race condition with the grid
	refresh).
	"""
	if reference_doctype not in INVOICE_DOCTYPES:
		frappe.throw(_("Invalid reference doctype."), frappe.PermissionError)

	ref_details = _erpnext_get_reference_details(
		reference_doctype, reference_name, party_account_currency, party_type, party
	)

	# Plain dict so JSON response always includes keys added below (same payload ERPNext
	# sends for due_date / outstanding_amount, etc.).
	ref_details = dict(ref_details)

	if reference_doctype in INVOICE_DOCTYPES:
		ref_details["custom_invoice_date"] = frappe.db.get_value(
			reference_doctype, reference_name, "posting_date"
		)

	return ref_details


def set_submitted_time(doc, method=None) -> None:
	"""Store submit time in custom_submitted_time on submit."""
	if doc.get("custom_submitted_time"):
		return

	# If fixture is not yet migrated, avoid blocking submission.
	if not frappe.db.has_column(doc.doctype, "custom_submitted_time"):
		return

	doc.db_set("custom_submitted_time", now_datetime(), update_modified=False)


def set_invoice_date_on_references(doc, method=None) -> None:
	"""Populate `custom_invoice_date` on each Payment Entry Reference row from
	the linked Sales/Purchase Invoice's `posting_date`.

	Mirrors how ERPNext auto-fetches `due_date` via `set_missing_ref_details`,
	but targets our custom field. Runs on validate so it covers rows added
	programmatically (e.g. Get Outstanding Invoices, API, imports) where the
	client-side handler in `public/js/payment_entry.js` would not fire.
	"""
	if not frappe.db.has_column("Payment Entry Reference", "custom_invoice_date"):
		return

	# Cache invoice lookups within a single save to avoid duplicate DB hits
	# when the same invoice is referenced multiple times.
	posting_date_cache: dict[tuple[str, str], object] = {}

	for row in doc.get("references") or []:
		if not row.reference_doctype or not row.reference_name:
			row.custom_invoice_date = None
			continue

		if row.reference_doctype not in INVOICE_DOCTYPES:
			row.custom_invoice_date = None
			continue

		key = (row.reference_doctype, row.reference_name)
		if key not in posting_date_cache:
			posting_date_cache[key] = frappe.db.get_value(
				row.reference_doctype, row.reference_name, "posting_date"
			)

		row.custom_invoice_date = posting_date_cache[key]
