import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission

SKU_COMBO = {
	"PTA": {"purchase": 1, "sell": 0, "buffer_flag": 1},
	"BOTA": {"purchase": 1, "sell": 0, "buffer_flag": 1},
	"TRMTA": {"purchase": 1, "sell": 0, "buffer_flag": 1},
	"PTO": {"purchase": 1, "sell": 0, "buffer_flag": 0},
	"BOTO": {"purchase": 1, "sell": 0, "buffer_flag": 0},
	"TRMTO": {"purchase": 1, "sell": 0, "buffer_flag": 0},
	"BBMTA": {"purchase": 0, "sell": 1, "buffer_flag": 1},
	"RBMTA": {"purchase": 0, "sell": 1, "buffer_flag": 1},
	"BBMTO": {"purchase": 0, "sell": 1, "buffer_flag": 0},
	"RBMTO": {"purchase": 0, "sell": 1, "buffer_flag": 0},
}

BUFFER_SKUS = {"PTA", "BOTA", "TRMTA", "BBMTA", "RBMTA"}
CHILD_SKUS = {"BBMTA", "RBMTA", "BBMTO", "RBMTO"}  # SKUs that show child columns


def get_columns(sku_type) -> list[dict]:
	is_buffer = sku_type in BUFFER_SKUS
	cols = [
		{"label": _("Snapshot Time"), "fieldname": "snapshot_time", "fieldtype": "Data", "width": 100},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
	]

	if is_buffer:
		cols += [
			{"label": _("Machine Name"), "fieldname": "machine_name", "fieldtype": "Data", "width": 140},
			{"label": _("TOG"), "fieldname": "tog", "fieldtype": "Float", "width": 80},
			{"label": _("TOY"), "fieldname": "toy", "fieldtype": "Float", "width": 80},
			{"label": _("TOR"), "fieldname": "tor", "fieldtype": "Float", "width": 80},
			{"label": _("Open SO"), "fieldname": "open_so", "fieldtype": "Float", "width": 100},
			{"label": _("On Hand Stock"), "fieldname": "on_hand_stock", "fieldtype": "Float", "width": 120},
			{"label": _("WIP"), "fieldname": "wip", "fieldtype": "Float", "width": 80},
			{"label": _("Open PO"), "fieldname": "open_po", "fieldtype": "Float", "width": 100},
			{"label": _("Open Subcon PO"), "fieldname": "open_subcon_po", "fieldtype": "Float", "width": 130},
			{
				"label": _("Qualified Demand"),
				"fieldname": "qualified_demand",
				"fieldtype": "Float",
				"width": 130,
			},
			{"label": _("On Hand Status"), "fieldname": "on_hand_status", "fieldtype": "Data", "width": 120},
			{"label": _("On Hand Colour"), "fieldname": "on_hand_colour", "fieldtype": "Data", "width": 120},
			{"label": _("Net Flow"), "fieldname": "net_flow", "fieldtype": "Float", "width": 100},
		]
	else:
		cols += [
			{"label": _("Priority"), "fieldname": "priority", "fieldtype": "Data", "width": 110},
			{"label": _("Requirement"), "fieldname": "requirement", "fieldtype": "Float", "width": 110},
			{"label": _("Total SO"), "fieldname": "total_so", "fieldtype": "Float", "width": 100},
			{"label": _("Open SO"), "fieldname": "open_so", "fieldtype": "Float", "width": 100},
			{"label": _("On Hand Stock"), "fieldname": "on_hand_stock", "fieldtype": "Float", "width": 120},
			{"label": _("WIP"), "fieldname": "wip", "fieldtype": "Float", "width": 80},
			{"label": _("Open PO"), "fieldname": "open_po", "fieldtype": "Float", "width": 100},
			{"label": _("Open Subcon PO"), "fieldname": "open_subcon_po", "fieldtype": "Float", "width": 130},
		]

	cols += [
		{
			"label": _("Order Recommendation"),
			"fieldname": "order_recommendation",
			"fieldtype": "Float",
			"width": 170,
		},
		{"label": _("MRQ"), "fieldname": "mrq", "fieldtype": "Float", "width": 80},
		{
			"label": _("Balance Order Rec"),
			"fieldname": "balance_order_recommendation",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Net Order Recommendation"),
			"fieldname": "net_order_recommendation",
			"fieldtype": "Float",
			"width": 180,
		},
		{"label": _("MOQ"), "fieldname": "moq", "fieldtype": "Float", "width": 80},
		{"label": _("Order Multiple Qty"), "fieldname": "batch_size", "fieldtype": "Float", "width": 130},
	]

	if sku_type in CHILD_SKUS:
		cols += [
			{
				"label": _("Prod Qty (Child Stock)"),
				"fieldname": "production_qty_based_on_child_stock",
				"fieldtype": "Float",
				"width": 170,
			},
			{
				"label": _("Child Full Kit Status"),
				"fieldname": "child_full_kit_status",
				"fieldtype": "Data",
				"width": 150,
			},
			{
				"label": _("Prod Qty (Child Stock+WIP+PO)"),
				"fieldname": "production_qty_based_on_child_stock_wip_open_po",
				"fieldtype": "Float",
				"width": 200,
			},
			{
				"label": _("Child WIP+PO Full Kit Status"),
				"fieldname": "child_wip_open_po_full_kit_status",
				"fieldtype": "Data",
				"width": 180,
			},
			{
				"label": _("Child Item Code"),
				"fieldname": "child_item_code",
				"fieldtype": "Link",
				"options": "Item",
				"width": 150,
			},
			{
				"label": _("Child Item Type"),
				"fieldname": "child_item_type",
				"fieldtype": "Data",
				"width": 120,
			},
			{"label": _("Child SKU Type"), "fieldname": "child_sku_type", "fieldtype": "Data", "width": 110},
			{
				"label": _("Child Requirement"),
				"fieldname": "child_requirement",
				"fieldtype": "Float",
				"width": 130,
			},
			{"label": _("Child Stock"), "fieldname": "child_stock", "fieldtype": "Float", "width": 100},
			{
				"label": _("Child Stock Soft Alloc"),
				"fieldname": "child_stock_soft_allocation_qty",
				"fieldtype": "Float",
				"width": 150,
			},
			{
				"label": _("Child Stock Shortage"),
				"fieldname": "child_stock_shortage",
				"fieldtype": "Float",
				"width": 140,
			},
			{
				"label": _("Child WIP+Open PO"),
				"fieldname": "child_wip_open_po",
				"fieldtype": "Float",
				"width": 130,
			},
			{
				"label": _("Child WIP+PO Soft Alloc"),
				"fieldname": "child_wip_open_po_soft_allocation_qty",
				"fieldtype": "Float",
				"width": 160,
			},
			{
				"label": _("Child WIP+PO Shortage"),
				"fieldname": "child_wip_open_po_shortage",
				"fieldtype": "Float",
				"width": 150,
			},
		]

	return cols


def _get_latest_snapshot(snapshot_date, purchase, sell, buffer_flag):
	results = frappe.get_all(
		"PO Recommendation Snapshot",
		filters={
			"snapshot_date": snapshot_date,
			"purchase": purchase,
			"sell": sell,
			"buffer_flag": buffer_flag,
			"status": "Success",
			"sku_type_filter": "",
			"item_code_filter": "",
		},
		fields=["name", "snapshot_time"],
		order_by="snapshot_time desc",
		limit=1,
	)
	return results[0] if results else None


@frappe.whitelist()
def get_sku_data(sku_type, snapshot_date, item_code=None) -> list[dict]:
	require_permission("PO Recommendation Snapshot", "read")
	combo = SKU_COMBO.get(sku_type)
	if not combo:
		frappe.throw(_(f"Unknown SKU type: {sku_type}"))

	columns = get_columns(sku_type)
	snap = _get_latest_snapshot(snapshot_date, combo["purchase"], combo["sell"], combo["buffer_flag"])
	if not snap:
		return {"columns": columns, "data": []}

	is_buffer = sku_type in BUFFER_SKUS

	item_filters = {"parent": snap.name, "sku_type": sku_type}
	if item_code:
		item_filters["item_code"] = item_code

	base_fields = [
		"item_code",
		"machine_name",
		"priority",
		"requirement",
		"tog",
		"toy",
		"tor",
		"open_so",
		"total_so",
		"open_so_qualified",
		"on_hand_stock",
		"wip",
		"open_po",
		"open_subcon_po",
		"qualified_demand",
		"additional_demand",
		"net_flow",
		"on_hand_status",
		"on_hand_colour",
		"order_recommendation",
		"mrq",
		"balance_order_recommendation",
		"net_order_recommendation",
		"moq",
		"batch_size",
	]

	buffer_extra_fields = [
		"production_qty_based_on_child_stock",
		"child_full_kit_status",
		"production_qty_based_on_child_stock_wip_open_po",
		"child_wip_open_po_full_kit_status",
		"child_item_code",
		"child_item_type",
		"child_sku_type",
		"child_requirement",
		"child_stock",
		"child_stock_soft_allocation_qty",
		"child_stock_shortage",
		"child_wip_open_po",
		"child_wip_open_po_soft_allocation_qty",
		"child_wip_open_po_shortage",
	]

	fields = base_fields + (buffer_extra_fields if sku_type in CHILD_SKUS else [])

	rows = frappe.get_all(
		"PO Recommendation Snapshot Item",
		filters=item_filters,
		fields=fields,
		order_by="item_code asc",
	)

	COLOUR_ORDER = {"BLACK": 0, "RED": 1, "YELLOW": 2, "GREEN": 3, "WHITE": 4}

	snap_time = str(snap.snapshot_time)[:8] if snap.snapshot_time else ""
	data = []
	for row in rows:
		row = dict(row)
		row["snapshot_time"] = snap_time
		data.append(row)

	if is_buffer:
		data.sort(key=lambda r: COLOUR_ORDER.get(r.get("on_hand_colour") or "", 99))

	return {"columns": columns, "data": data}


def _fill_missing_fg_item(data, order_field, child_doctype) -> None:
	"""Backfill fg_item for snapshot rows captured before fg_item was stored.

	Older snapshots don't keep the order line id, so match on (order, item_code, qty),
	falling back to (order, item_code); when several lines still match, list every FG.
	"""
	missing = [r for r in data if not r.get("fg_item") and r.get(order_field)]
	if not missing:
		return

	lines = frappe.get_all(
		child_doctype,
		filters={"parent": ["in", list({r[order_field] for r in missing})], "fg_item": ["is", "set"]},
		fields=["parent", "item_code", "qty", "fg_item"],
		order_by="parent asc, idx asc",
	)
	by_item, by_qty = {}, {}
	for line in lines:
		for fg_map, key in (
			(by_item, (line.parent, line.item_code)),
			(by_qty, (line.parent, line.item_code, flt(line.qty))),
		):
			fgs = fg_map.setdefault(key, [])
			if line.fg_item not in fgs:
				fgs.append(line.fg_item)

	for row in missing:
		key = (row[order_field], row.get("item_code"))
		fgs = by_qty.get((*key, flt(row.get("qty")))) or by_item.get(key)
		if fgs:
			row["fg_item"] = ", ".join(fgs)


SO_COLUMNS = [
	{"label": "SO Date", "fieldname": "so_date", "fieldtype": "Date", "width": 100},
	{"label": "Customer", "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
	{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
	{"label": "Finished Good", "fieldname": "fg_item", "fieldtype": "Link", "options": "Item", "width": 160},
	{"label": "Order Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
	{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 90},
	{"label": "Payment Terms", "fieldname": "payment_terms_template", "fieldtype": "Data", "width": 140},
	{"label": "Lead Time", "fieldname": "lead_time", "fieldtype": "Int", "width": 90},
	{"label": "Special Condition", "fieldname": "special_condition", "fieldtype": "Data", "width": 140},
	{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
	{
		"label": "Sales Order",
		"fieldname": "sales_order",
		"fieldtype": "Link",
		"options": "Sales Order",
		"width": 160,
	},
	{"label": "Delivered Qty", "fieldname": "delivered_qty", "fieldtype": "Float", "width": 110},
	{"label": "Delivery Date", "fieldname": "delivery_date", "fieldtype": "Date", "width": 110},
	{"label": "Qty to Deliver", "fieldname": "pending_qty", "fieldtype": "Float", "width": 110},
	{"label": "Item Type", "fieldname": "item_type", "fieldtype": "Data", "width": 100},
	{"label": "SKU Type", "fieldname": "sku_type", "fieldtype": "Data", "width": 90},
	{"label": "Remaining Days", "fieldname": "remaining_days", "fieldtype": "Int", "width": 120},
	{"label": "Buffer Status (%)", "fieldname": "buffer_status", "fieldtype": "Data", "width": 130},
	{"label": "Order Status", "fieldname": "order_status", "fieldtype": "Data", "width": 120},
	{"label": "Stock", "fieldname": "stock", "fieldtype": "Float", "width": 80},
	{"label": "Stock Allocation", "fieldname": "stock_allocation", "fieldtype": "Float", "width": 130},
	{"label": "Shortage", "fieldname": "shortage", "fieldtype": "Float", "width": 90},
	{"label": "Line Fullkit", "fieldname": "line_fullkit", "fieldtype": "Data", "width": 110},
	{"label": "Order Fullkit", "fieldname": "order_fullkit", "fieldtype": "Data", "width": 110},
	{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 110},
	{"label": "Pending Amount", "fieldname": "pending_amount", "fieldtype": "Currency", "width": 130},
]

SO_FIELDS = [c["fieldname"] for c in SO_COLUMNS]


@frappe.whitelist()
def get_so_data(snapshot_date, item_code=None) -> list[dict]:
	require_permission("SO Recommendation Snapshot", "read")
	snap = frappe.get_all(
		"SO Recommendation Snapshot",
		filters={"snapshot_date": snapshot_date, "status": "Success"},
		fields=["name", "snapshot_time"],
		order_by="snapshot_time desc",
		limit=1,
	)
	if not snap:
		return {"columns": SO_COLUMNS, "data": []}

	snap = snap[0]
	item_filters = {"parent": snap.name}
	if item_code:
		item_filters["item_code"] = item_code

	rows = frappe.get_all(
		"SO Recommendation Snapshot Item",
		filters=item_filters,
		fields=SO_FIELDS,
		order_by="sales_order asc, item_code asc",
	)

	data = [dict(r) for r in rows]
	_fill_missing_fg_item(data, "sales_order", "Sales Order Item")
	return {"columns": SO_COLUMNS, "data": data}


@frappe.whitelist()
def export_sku_xlsx(sku_type, snapshot_date, item_code=None) -> dict:
	require_permission("PO Recommendation Snapshot", "read")
	import base64
	from frappe.utils.xlsxutils import make_xlsx

	result = get_sku_data(sku_type, snapshot_date, item_code)
	columns = result["columns"]
	data = result["data"]

	# Header row + data rows
	rows = [[col["label"] for col in columns]]
	for row in data:
		rows.append([row.get(col["fieldname"], "") for col in columns])

	xlsx_file = make_xlsx(rows, sku_type)
	return {
		"filename": f"{sku_type}_Snapshot_{snapshot_date}.xlsx",
		"content": base64.b64encode(xlsx_file.getvalue()).decode("utf-8"),
	}


@frappe.whitelist()
def export_so_xlsx(snapshot_date, item_code=None) -> dict:
	require_permission("SO Recommendation Snapshot", "read")
	import base64
	from frappe.utils.xlsxutils import make_xlsx

	result = get_so_data(snapshot_date, item_code)
	columns = result["columns"]
	data = result["data"]

	rows = [[col["label"] for col in columns]]
	date_fields = {col["fieldname"] for col in columns if col.get("fieldtype") == "Date"}
	for row in data:
		row_values = []
		for col in columns:
			val = row.get(col["fieldname"], "")
			if val and col["fieldname"] in date_fields:
				from datetime import date, datetime
				if isinstance(val, (date, datetime)):
					val = val.strftime("%d-%m-%Y")
				else:
					parts = str(val)[:10].split("-")
					val = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else str(val)[:10]
			row_values.append(val)
		rows.append(row_values)

	xlsx_file = make_xlsx(rows, "Open SO Report")
	return {
		"filename": f"Open_SO_Report_{snapshot_date}.xlsx",
		"content": base64.b64encode(xlsx_file.getvalue()).decode("utf-8"),
	}


OPEN_PO_COLUMNS = [
	{"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 100},
	{"label": "Supplier", "fieldname": "supplier", "fieldtype": "Link", "options": "Supplier", "width": 160},
	{"label": "Item Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
	{"label": "Finished Good", "fieldname": "fg_item", "fieldtype": "Link", "options": "Item", "width": 160},
	{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
	{"label": "Order Qty", "fieldname": "qty", "fieldtype": "Float", "width": 90},
	{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 100},
	{"label": "Lead Time", "fieldname": "cf_lead_time", "fieldtype": "Int", "width": 90},
	{"label": "Payment Terms", "fieldname": "payment_terms_template", "fieldtype": "Data", "width": 140},
	{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 110},
	{
		"label": "Purchase Order",
		"fieldname": "purchase_order",
		"fieldtype": "Link",
		"options": "Purchase Order",
		"width": 170,
	},
]

OPEN_PO_FIELDS = [c["fieldname"] for c in OPEN_PO_COLUMNS]


@frappe.whitelist()
def get_open_po_data(snapshot_date, item_code=None) -> list[dict]:
	require_permission("Purchase Order Recommendation Snapshot", "read")
	snap = frappe.get_all(
		"Purchase Order Recommendation Snapshot",
		filters={"snapshot_date": snapshot_date, "status": "Success"},
		fields=["name", "snapshot_time"],
		order_by="snapshot_time desc",
		limit=1,
	)
	if not snap:
		return {"columns": OPEN_PO_COLUMNS, "data": []}

	snap = snap[0]
	item_filters = {"parent": snap.name}
	if item_code:
		item_filters["item_code"] = item_code

	# Fetch snapshot fields (excluding payment_terms_template which lives on PO itself)
	snap_fields = [f for f in OPEN_PO_FIELDS if f != "payment_terms_template"]
	rows = frappe.get_all(
		"Purchase Order Recommendation Snapshot Item",
		filters=item_filters,
		fields=snap_fields,
		order_by="purchase_order asc, item_code asc",
	)

	# Filter out closed/completed/cancelled rows at snapshot level
	EXCLUDED_STATUSES = {"Closed", "Completed", "Cancelled", "To Bill"}
	data = [dict(r) for r in rows if (r.get("status") or "") not in EXCLUDED_STATUSES]

	# Fetch payment_terms_template from Purchase Order (parent)
	po_names = list({r["purchase_order"] for r in data if r.get("purchase_order")})
	if po_names:
		po_parents = frappe.get_all(
			"Purchase Order",
			filters={"name": ["in", po_names]},
			fields=["name", "payment_terms_template"],
		)
		terms_map = {p["name"]: p.get("payment_terms_template") or "" for p in po_parents}

		# Fetch custom_closed from Purchase Order Item (child table) — keyed by (parent, item_code)
		poi_rows = frappe.get_all(
			"Purchase Order Item",
			filters={"parent": ["in", po_names], "custom_closed": 1},
			fields=["parent", "item_code"],
		)
		closed_items = {(r["parent"], r["item_code"]) for r in poi_rows}

		# Filter out custom_closed items and map payment terms
		data = [row for row in data if (row.get("purchase_order"), row.get("item_code")) not in closed_items]
		for row in data:
			row["payment_terms_template"] = terms_map.get(row.get("purchase_order"), "")

	_fill_missing_fg_item(data, "purchase_order", "Purchase Order Item")
	return {"columns": OPEN_PO_COLUMNS, "data": data}


@frappe.whitelist()
def export_open_po_xlsx(snapshot_date, item_code=None) -> dict:
	require_permission("Purchase Order Recommendation Snapshot", "read")
	import base64
	from frappe.utils.xlsxutils import make_xlsx

	result = get_open_po_data(snapshot_date, item_code)
	columns = result["columns"]
	data = result["data"]

	rows = [[col["label"] for col in columns]]
	date_fields = {col["fieldname"] for col in columns if col.get("fieldtype") == "Date"}
	for row in data:
		row_values = []
		for col in columns:
			val = row.get(col["fieldname"], "")
			if val and col["fieldname"] in date_fields:
				from datetime import date, datetime
				if isinstance(val, (date, datetime)):
					val = val.strftime("%d-%m-%Y")
				else:
					parts = str(val)[:10].split("-")
					val = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else str(val)[:10]
			row_values.append(val)
		rows.append(row_values)

	xlsx_file = make_xlsx(rows, "Open PO Report")
	return {
		"filename": f"Open_PO_Report_{snapshot_date}.xlsx",
		"content": base64.b64encode(xlsx_file.getvalue()).decode("utf-8"),
	}


STOCK_BALANCE_COLUMNS = [
	{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 170},
	{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
	# {"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 140},
	{"label": "Category Name", "fieldname": "category_name", "fieldtype": "Data", "width": 140},
	# {"label": "Stock UOM", "fieldname": "stock_uom", "fieldtype": "Link", "options": "UOM", "width": 100},
	{"label": "Balance Qty", "fieldname": "balance_qty", "fieldtype": "Float", "width": 120},
]

STOCK_BALANCE_FIELDS = [c["fieldname"] for c in STOCK_BALANCE_COLUMNS]


@frappe.whitelist()
def get_stock_balance_data(snapshot_date, item_code=None) -> list[dict]:
	require_permission("Stock Balance Snapshot", "read")
	snap = frappe.get_all(
		"Stock Balance Snapshot",
		filters={"snapshot_date": snapshot_date, "status": "Success"},
		fields=["name", "snapshot_time"],
		order_by="snapshot_time desc",
		limit=1,
	)
	if not snap:
		return {"columns": STOCK_BALANCE_COLUMNS, "data": []}

	snap = snap[0]
	item_filters = {"parent": snap.name}
	if item_code:
		item_filters["item_code"] = item_code

	rows = frappe.get_all(
		"Stock Balance Snapshot Item",
		filters=item_filters,
		fields=STOCK_BALANCE_FIELDS,
		order_by="item_code asc",
	)

	data = [dict(r) for r in rows]
	return {"columns": STOCK_BALANCE_COLUMNS, "data": data}


@frappe.whitelist()
def export_stock_balance_xlsx(snapshot_date, item_code=None) -> dict:
	require_permission("Stock Balance Snapshot", "read")
	import base64
	from frappe.utils.xlsxutils import make_xlsx

	result = get_stock_balance_data(snapshot_date, item_code)
	columns = result["columns"]
	data = result["data"]

	rows = [[col["label"] for col in columns]]
	for row in data:
		rows.append([row.get(col["fieldname"], "") for col in columns])

	xlsx_file = make_xlsx(rows, "Stock Balance Report")
	return {
		"filename": f"Stock_Balance_Report_{snapshot_date}.xlsx",
		"content": base64.b64encode(xlsx_file.getvalue()).decode("utf-8"),
	}
