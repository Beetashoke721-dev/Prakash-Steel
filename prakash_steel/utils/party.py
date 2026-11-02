# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def warn_if_party_details_missing(doc, method=None) -> None:
	"""
	Show a non-blocking warning when creating Customer/Supplier with missing details.

	Does not raise — save must still succeed if the user dismisses the message.
	"""
	if doc.doctype not in ("Customer", "Supplier"):
		return

	if not doc.is_new():
		return

	warnings = []

	if doc.doctype == "Supplier":
		accounts = doc.get("accounts") or []
		if not any(row.get("account") for row in accounts):
			warnings.append(_("Please set Default Accounts in Accounting section."))

	if not (doc.get("mobile_no") or "").strip():
		warnings.append(_("Please enter Mobile No."))

	if not (doc.get("email_id") or "").strip():
		warnings.append(_("Please enter Email ID."))

	if not warnings:
		return

	frappe.msgprint(
		"<br>".join(warnings),
		title=_("Missing Information"),
		indicator="orange",
	)


def warn_if_default_accounts_missing(doc, method=None) -> None:
	"""Backward-compatible alias for older hook references."""
	warn_if_party_details_missing(doc, method=method)
