import frappe
from frappe.utils import cint, flt

from erpnext.stock.dashboard.item_dashboard import get_data as _original_get_data


@frappe.whitelist()
def get_data(
	item_code=None, warehouse=None, item_group=None, start=0, sort_by="actual_qty", sort_order="desc"
) -> list[dict]:
	"""Return item dashboard data, excluding qty from custom_closed Sales Order items."""
	if not frappe.has_permission("Item", "read"):
		frappe.throw("Not permitted to access item dashboard data.", frappe.PermissionError)

	items = _original_get_data(
		item_code=item_code,
		warehouse=warehouse,
		item_group=item_group,
		start=start,
		sort_by=sort_by,
		sort_order=sort_order,
	)

	if not items:
		return items

	precision = cint(frappe.db.get_single_value("System Settings", "float_precision"))

	for item in items:
		# Sum qty still pending (qty - delivered_qty) from custom_closed SO items
		result = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(soi.qty - soi.delivered_qty), 0) AS closed_qty
			FROM `tabSales Order Item` soi
			INNER JOIN `tabSales Order` so ON so.name = soi.parent
			WHERE soi.item_code = %s
			  AND soi.warehouse = %s
			  AND so.docstatus = 1
			  AND so.status NOT IN ('Closed', 'Completed', 'Cancelled')
			  AND soi.custom_closed = 1
			  AND soi.qty > soi.delivered_qty
			""",
			(item.item_code, item.warehouse),
		)

		closed_qty = flt(result[0][0] if result else 0, precision)

		if closed_qty > 0:
			item["reserved_qty"] = flt(item.get("reserved_qty", 0) - closed_qty, precision)
			item["projected_qty"] = flt(item.get("projected_qty", 0) + closed_qty, precision)

		# Sum qty still pending (qty - received_qty) from custom_closed PO items
		po_result = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(poi.qty - poi.received_qty), 0) AS closed_qty
			FROM `tabPurchase Order Item` poi
			INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
			WHERE poi.item_code = %s
			  AND poi.warehouse = %s
			  AND po.docstatus = 1
			  AND po.status NOT IN ('Closed', 'Completed', 'Cancelled')
			  AND poi.custom_closed = 1
			  AND poi.qty > poi.received_qty
			""",
			(item.item_code, item.warehouse),
		)

		po_closed_qty = flt(po_result[0][0] if po_result else 0, precision)

		if po_closed_qty > 0:
			item["ordered_qty"] = flt(item.get("ordered_qty", 0) - po_closed_qty, precision)
			item["projected_qty"] = flt(item.get("projected_qty", 0) + po_closed_qty, precision)

	return items
