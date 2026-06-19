# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_overview_data(from_date, to_date, supplier=None) -> list[dict]:
	"""
	Return accurate overview counts for the Procurement Tracker Dashboard.

	Each count queries its own doctype directly so the values are
	independent of the MR → PO → PR → PI join chain used by the
	procurement tracker report.

	All counts consider only submitted documents (docstatus = 1).
	Date ranges are applied to the native date field of each doctype.
	"""
	if not frappe.has_permission("Material Request", "read") and not frappe.has_permission(
		"Purchase Order", "read"
	) and not frappe.has_permission("Purchase Receipt", "read") and not frappe.has_permission(
		"Purchase Invoice", "read"
	):
		frappe.throw(_("Not permitted to access procurement dashboard data."), frappe.PermissionError)

	filters_mr = {
		"from_date": from_date,
		"to_date": to_date,
	}
	filters_po = dict(filters_mr)
	filters_pr = dict(filters_mr)
	filters_pi = dict(filters_mr)

	# ── Material Requests ──────────────────────────────────────────
	mr_cond = "mr.docstatus = 1 AND mr.transaction_date BETWEEN %(from_date)s AND %(to_date)s"
	mr_count = 0
	if frappe.has_permission("Material Request", "read"):
		mr_count = frappe.db.sql(
			f"SELECT COUNT(DISTINCT mr.name) FROM `tabMaterial Request` mr WHERE {mr_cond}",
			filters_mr,
		)[0][0] or 0

	# ── Purchase Orders ────────────────────────────────────────────
	po_cond = (
		"po.docstatus = 1"
		" AND po.transaction_date BETWEEN %(from_date)s AND %(to_date)s"
	)
	if supplier:
		po_cond += " AND po.supplier = %(supplier)s"
		filters_po["supplier"] = supplier
	po_count = 0
	if frappe.has_permission("Purchase Order", "read"):
		po_count = frappe.db.sql(
			f"SELECT COUNT(DISTINCT po.name) FROM `tabPurchase Order` po WHERE {po_cond}",
			filters_po,
		)[0][0] or 0

	# ── Purchase Receipts ──────────────────────────────────────────
	pr_cond = (
		"pr.docstatus = 1"
		" AND pr.posting_date BETWEEN %(from_date)s AND %(to_date)s"
	)
	if supplier:
		pr_cond += " AND pr.supplier = %(supplier)s"
		filters_pr["supplier"] = supplier
	pr_count = 0
	if frappe.has_permission("Purchase Receipt", "read"):
		pr_count = frappe.db.sql(
			f"SELECT COUNT(DISTINCT pr.name) FROM `tabPurchase Receipt` pr WHERE {pr_cond}",
			filters_pr,
		)[0][0] or 0

	# ── Purchase Invoices ──────────────────────────────────────────
	pi_cond = (
		"pi.docstatus = 1"
		" AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s"
	)
	if supplier:
		pi_cond += " AND pi.supplier = %(supplier)s"
		filters_pi["supplier"] = supplier
	pi_count = 0
	if frappe.has_permission("Purchase Invoice", "read"):
		pi_count = frappe.db.sql(
			f"SELECT COUNT(DISTINCT pi.name) FROM `tabPurchase Invoice` pi WHERE {pi_cond}",
			filters_pi,
		)[0][0] or 0

	return {
		"total_material_requests": mr_count,
		"total_purchase_orders": po_count,
		"total_purchase_receipts": pr_count,
		"total_purchase_invoices": pi_count,
	}
