import frappe
from frappe import _


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None, ignore_permissions=False) -> object:
	# if ignore_permissions and "System Manager" not in frappe.get_roles():
	# 	frappe.throw(_("Not permitted to bypass permissions when creating Sales Invoice."), frappe.PermissionError)

	if not frappe.has_permission("Sales Order", "read") and not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("Not permitted to create Sales Invoice."), frappe.PermissionError)

	if not frappe.has_permission("Sales Invoice", "create") and not frappe.has_permission("Sales Invoice", "write"):
		frappe.throw(_("Not permitted to create Sales Invoice."), frappe.PermissionError)

	# Only System Manager can request ignore_permissions=True (server-side bypass).
	ignore_permissions = bool(ignore_permissions) and "System Manager" in frappe.get_roles()

	from erpnext.selling.doctype.sales_order.sales_order import (
		make_sales_invoice as _make_sales_invoice,
	)

	doc = _make_sales_invoice(
		source_name,
		target_doc,
		ignore_permissions=ignore_permissions,
	)

	if not (doc and doc.items):
		return doc

	original_count = len(doc.items)

	doc.items = [
		item
		for item in doc.items
		if not (
			item.get("so_detail") and frappe.db.get_value("Sales Order Item", item.so_detail, "custom_closed")
		)
	]

	# Re-index after filtering
	for idx, item in enumerate(doc.items, 1):
		item.idx = idx

	closed_count = original_count - len(doc.items)
	if closed_count:
		frappe.msgprint(
			_("{0} closed item(s) were excluded from the Sales Invoice.").format(closed_count),
			indicator="orange",
			alert=True,
		)

	return doc
