import frappe

from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_delay_reasons():
	require_permission("Sales Order", "read")
	return frappe.get_all(
		"Delivery Delay Reason Master",
		fields=["name", "delay_reason"],
		order_by="delay_reason asc",
	)


@frappe.whitelist()
def save_delay_info(rows):
	require_permission("Sales Order", "write")
	if isinstance(rows, str):
		import json
		rows = json.loads(rows)

	if not rows:
		return

	for row in rows:
		soi_name = row.get("soi_name")
		if not soi_name:
			continue

		frappe.db.set_value(
			"Sales Order Item",
			soi_name,
			{
				"custom_delay_reasons": row.get("delay_reason") or None,
				"custom_delay_remarks": row.get("delay_remarks") or None,
			},
			update_modified=False,
		)

	frappe.db.commit()
	return {"status": "ok", "updated": len(rows)}


# Column layout for each tab — mirrors COLS_ANALYSIS / COLS_DISPATCH in open_so_page.js
# (the "__pad" spacer column is dropped, and the delay editors map to their stored fields).
_EXPORT_COLUMNS = {
	"analysis": [
		("date", "SO Date"),
		("customer", "Customer Name"),
		("item_code", "Item Code"),
		("qty", "Order Qty"),
		("rate", "Rate"),
		("payment_terms_template", "Payment Terms"),
		("lead_time", "Lead Time"),
		("special_condition", "Special Cond."),
		("status", "Status"),
		("sales_order", "Sales Order"),
		("delivered_qty", "Delivered Qty"),
		("delivery_date", "Delivery Date"),
		("pending_qty", "Qty to Deliver"),
		("item_type", "Item Type"),
		("sku_type", "SKU Type"),
		("remaining_days", "Remaining Days"),
		("buffer_status", "Buffer Status"),
		("order_status", "Order Status"),
		("stock", "Stock"),
		("stock_allocation", "Stock Alloc."),
		("shortage", "Shortage"),
		("reducing_stock", "Reducing Stock"),
		("line_fullkit", "Line Fullkit"),
		("order_fullkit", "Order Fullkit"),
		("amount", "Amount"),
		("pending_amount", "Pending Amount"),
		("delay_reasons", "Delay Reason"),
		("delay_remarks", "Delay Remarks"),
	],
	"dispatch": [
		("order_status", "Order Status"),
		("date", "Sales Order Date"),
		("delivery_date", "Delivery Date"),
		("sales_order", "Sales Order"),
		("customer", "Customer Name"),
		("order_fullkit", "Order Fullkit"),
		("item_code", "Item Code"),
		("line_fullkit", "Line Fullkit"),
		("qty", "Order Qty"),
		("pending_qty", "Qty to Deliver"),
		("stock_allocation", "Stock Allocation"),
		("delay_reasons", "Delay Reason"),
		("delay_remarks", "Delay Remarks"),
	],
}

_EXPORT_SHEET_NAME = {"analysis": "Open SO Analysis", "dispatch": "Ready to Dispatch"}
_EXPORT_DATE_FIELDS = {"date", "delivery_date"}


@frappe.whitelist()
def export_so_tab_xlsx(tab=None, filters=None, order_status=None, line_fullkit=None):
	"""Download the currently selected tab of the Open SO page as an .xlsx.

	Re-runs the Open SO Analysis report with the page filters, then applies the
	same tab / colour / line-full-kit narrowing the page shows on screen.
	"""
	import json

	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Sales Order", "read")

	tab = tab if tab in _EXPORT_COLUMNS else "analysis"

	if isinstance(filters, str):
		filters = json.loads(filters or "{}")
	filters = filters or {}

	if isinstance(line_fullkit, str):
		try:
			line_fullkit = json.loads(line_fullkit)
		except ValueError:
			line_fullkit = [line_fullkit] if line_fullkit else None

	from prakash_steel.prakash_steel.report.open_so_analysis.open_so_analysis import (
		execute as run_open_so_analysis,
	)

	# The page keeps every kit state in the report itself and narrows Ready to
	# Dispatch client-side, so mirror that here.
	filters.setdefault("line_fullkit_status", ["Partial", "Full-kit", "Pending"])
	data = run_open_so_analysis(frappe._dict(filters))[1] or []

	if order_status and order_status.upper() != "ALL":
		wanted = order_status.upper()
		data = [r for r in data if (r.get("order_status") or "").upper() == wanted]

	if tab == "dispatch":
		lf = line_fullkit or ["Partial", "Full-kit"]
		data = [r for r in data if r.get("line_fullkit") in lf]

	columns = _EXPORT_COLUMNS[tab]

	def _fmt(fieldname, value):
		if value is None:
			return ""
		if fieldname in _EXPORT_DATE_FIELDS:
			parts = str(value).split(" ")[0].split("-")
			if len(parts) == 3:
				return f"{parts[2]}-{parts[1]}-{parts[0]}"
		return value

	rows = [[label for _fieldname, label in columns]]
	for row in data:
		rows.append([_fmt(fieldname, row.get(fieldname)) for fieldname, _label in columns])

	sheet_name = _EXPORT_SHEET_NAME[tab]
	xlsx_file = make_xlsx(rows, sheet_name)
	frappe.response["filename"] = f"{sheet_name}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
