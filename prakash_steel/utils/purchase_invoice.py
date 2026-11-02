# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe


def set_weight_slip_qty_from_purchase_receipt(doc) -> None:
	"""
	Copy Purchase Receipt Item custom_party_billing_qty into
	Purchase Invoice Item custom_weight_slip_qty (via pr_detail).
	"""
	items = doc.get("items") or []
	pr_details = [row.pr_detail for row in items if row.get("pr_detail")]
	if not pr_details:
		return

	qty_map = {
		row.name: row.custom_party_billing_qty
		for row in frappe.get_all(
			"Purchase Receipt Item",
			filters={"name": ["in", pr_details]},
			fields=["name", "custom_party_billing_qty"],
		)
	}
	for row in items:
		if row.get("pr_detail") and row.pr_detail in qty_map:
			row.custom_weight_slip_qty = qty_map[row.pr_detail]


@frappe.whitelist()
def make_purchase_invoice(source_name, target_doc=None, args=None) -> object:
	"""Create Purchase Invoice from Purchase Receipt and map weight slip qty."""
	from erpnext.stock.doctype.purchase_receipt.purchase_receipt import (
		make_purchase_invoice as _make_purchase_invoice,
	)

	doc = _make_purchase_invoice(source_name, target_doc, args)
	set_weight_slip_qty_from_purchase_receipt(doc)
	return doc
