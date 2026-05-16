# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

VALID_FREIGHT_PAYABLE_BY = frozenset({"PSP", "Vendor/Party"})


class prfcsolver(Document):
	pass


@frappe.whitelist()
def apply_freight_payable_by():
	"""Set custom_freight_payable_by on Purchase Receipts listed in the single DocType child table."""
	if not frappe.has_permission("Purchase Receipt", "write"):
		frappe.throw(_("Not permitted to update Purchase Receipt"), frappe.PermissionError)

	solver = frappe.get_single("pr fc solver")
	rows = solver.get("items") or []
	if not rows:
		frappe.throw(_("Add at least one Purchase Receipt row before applying."))

	updated = []
	skipped = []
	failed = []
	seen_prs = set()

	for row in rows:
		pr_name = row.purchase_receipt
		new_value = (row.freight_payable_by or "").strip()

		if not pr_name:
			failed.append({"purchase_receipt": pr_name, "reason": _("Purchase Receipt is required")})
			continue

		if pr_name in seen_prs:
			skipped.append({"purchase_receipt": pr_name, "reason": _("Duplicate row in table")})
			continue
		seen_prs.add(pr_name)

		if new_value not in VALID_FREIGHT_PAYABLE_BY:
			failed.append(
				{
					"purchase_receipt": pr_name,
					"reason": _("Freight Payable By must be PSP or Vendor/Party"),
				}
			)
			continue

		if not frappe.db.exists("Purchase Receipt", pr_name):
			failed.append({"purchase_receipt": pr_name, "reason": _("Purchase Receipt not found")})
			continue

		if not frappe.has_permission("Purchase Receipt", "write", pr_name):
			failed.append({"purchase_receipt": pr_name, "reason": _("No write permission on this document")})
			continue

		current_value = frappe.db.get_value("Purchase Receipt", pr_name, "custom_freight_payable_by") or ""
		if current_value == new_value:
			skipped.append(
				{
					"purchase_receipt": pr_name,
					"reason": _("Already set to {0}").format(new_value),
				}
			)
			continue

		frappe.db.set_value(
			"Purchase Receipt",
			pr_name,
			"custom_freight_payable_by",
			new_value,
			update_modified=True,
		)
		updated.append({"purchase_receipt": pr_name, "from": current_value, "to": new_value})

	frappe.db.commit()

	return {
		"updated": updated,
		"skipped": skipped,
		"failed": failed,
		"summary": _build_summary(updated, skipped, failed),
	}


def _build_summary(updated, skipped, failed):
	parts = []
	if updated:
		parts.append(_("Updated: {0}").format(len(updated)))
	if skipped:
		parts.append(_("Skipped: {0}").format(len(skipped)))
	if failed:
		parts.append(_("Failed: {0}").format(len(failed)))
	if not parts:
		return _("No rows processed.")
	return ", ".join(parts)
