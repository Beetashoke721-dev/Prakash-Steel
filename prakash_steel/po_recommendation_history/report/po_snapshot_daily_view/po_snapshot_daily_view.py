import frappe
from frappe import _
from frappe.utils import today


# The 4 standard combinations captured daily
COMBINATIONS = [
	{"purchase": 1, "sell": 0, "buffer_flag": 1, "label": "Purchase + Buffer"},
	{"purchase": 1, "sell": 0, "buffer_flag": 0, "label": "Purchase"},
	{"purchase": 0, "sell": 1, "buffer_flag": 1, "label": "Manufacture + Buffer"},
	{"purchase": 0, "sell": 1, "buffer_flag": 0, "label": "Manufacture"},
]


def execute(filters=None) -> tuple[list, list]:
	filters = frappe._dict(filters or {})
	if not filters.snapshot_date:
		filters.snapshot_date = today()

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"label": _("Combination"), "fieldname": "combination", "fieldtype": "Data", "width": 160},
		{"label": _("Snapshot Time"), "fieldname": "snapshot_time", "fieldtype": "Data", "width": 100},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("SKU Type"), "fieldname": "sku_type", "fieldtype": "Data", "width": 100},
		{"label": _("Requirement"), "fieldname": "requirement", "fieldtype": "Float", "width": 110},
		{"label": _("TOG"), "fieldname": "tog", "fieldtype": "Float", "width": 80},
		{"label": _("TOY"), "fieldname": "toy", "fieldtype": "Float", "width": 80},
		{"label": _("TOR"), "fieldname": "tor", "fieldtype": "Float", "width": 80},
		{"label": _("Open SO"), "fieldname": "open_so", "fieldtype": "Float", "width": 100},
		{"label": _("Total SO"), "fieldname": "total_so", "fieldtype": "Float", "width": 100},
		{"label": _("Open SO (Qualified)"), "fieldname": "open_so_qualified", "fieldtype": "Float", "width": 130},
		{"label": _("On Hand Stock"), "fieldname": "on_hand_stock", "fieldtype": "Float", "width": 120},
		{"label": _("WIP"), "fieldname": "wip", "fieldtype": "Float", "width": 80},
		{"label": _("Open PO"), "fieldname": "open_po", "fieldtype": "Float", "width": 100},
		{"label": _("Open Subcon PO"), "fieldname": "open_subcon_po", "fieldtype": "Float", "width": 130},
		{"label": _("Additional Demand"), "fieldname": "additional_demand", "fieldtype": "Float", "width": 130},
		{"label": _("Qualified Demand"), "fieldname": "qualified_demand", "fieldtype": "Float", "width": 130},
		{"label": _("On Hand Status"), "fieldname": "on_hand_status", "fieldtype": "Data", "width": 120},
		{"label": _("On Hand Colour"), "fieldname": "on_hand_colour", "fieldtype": "Data", "width": 120},
		{"label": _("Net Flow"), "fieldname": "net_flow", "fieldtype": "Float", "width": 100},
		{"label": _("Order Recommendation"), "fieldname": "order_recommendation", "fieldtype": "Float", "width": 170},
		{"label": _("MRQ"), "fieldname": "mrq", "fieldtype": "Float", "width": 80},
		{"label": _("Balance Order Recommendation"), "fieldname": "balance_order_recommendation", "fieldtype": "Float", "width": 200},
		{"label": _("Net Order Recommendation"), "fieldname": "net_order_recommendation", "fieldtype": "Float", "width": 180},
		{"label": _("MOQ"), "fieldname": "moq", "fieldtype": "Float", "width": 80},
		{"label": _("Order Multiple Qty"), "fieldname": "batch_size", "fieldtype": "Float", "width": 130},
		{"label": _("Prod Qty (Child Stock)"), "fieldname": "production_qty_based_on_child_stock", "fieldtype": "Float", "width": 160},
		{"label": _("Child Stock Full-Kit"), "fieldname": "child_full_kit_status", "fieldtype": "Data", "width": 140},
		{"label": _("Prod Qty (Child+WIP/PO)"), "fieldname": "production_qty_based_on_child_stock_wip_open_po", "fieldtype": "Float", "width": 180},
		{"label": _("Child+WIP/PO Full-Kit"), "fieldname": "child_wip_open_po_full_kit_status", "fieldtype": "Data", "width": 160},
		{"label": _("Child Item Code"), "fieldname": "child_item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Child Item Type"), "fieldname": "child_item_type", "fieldtype": "Data", "width": 120},
		{"label": _("Child SKU Type"), "fieldname": "child_sku_type", "fieldtype": "Data", "width": 120},
		{"label": _("Child Requirement"), "fieldname": "child_requirement", "fieldtype": "Float", "width": 130},
		{"label": _("Child Stock"), "fieldname": "child_stock", "fieldtype": "Float", "width": 100},
		{"label": _("Child Stock Soft Alloc"), "fieldname": "child_stock_soft_allocation_qty", "fieldtype": "Float", "width": 150},
		{"label": _("Child Stock Shortage"), "fieldname": "child_stock_shortage", "fieldtype": "Float", "width": 140},
		{"label": _("Child WIP/Open PO"), "fieldname": "child_wip_open_po", "fieldtype": "Float", "width": 130},
		{"label": _("Child WIP/PO Soft Alloc"), "fieldname": "child_wip_open_po_soft_allocation_qty", "fieldtype": "Float", "width": 170},
		{"label": _("Child WIP/PO Shortage"), "fieldname": "child_wip_open_po_shortage", "fieldtype": "Float", "width": 160},
	]


def _get_latest_snapshot(snapshot_date, purchase, sell, buffer_flag):
	"""Return the name and snapshot_time of the latest successful snapshot for a given combination on a date."""
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


def _parse_multiselect(value) -> list[str]:
	"""MultiSelectList sends a list or newline-joined string; normalise to a Python list."""
	if not value:
		return []
	if isinstance(value, list):
		return [v for v in value if v]
	return [v.strip() for v in str(value).split("\n") if v.strip()]


def get_data(filters) -> list[dict]:
	snapshot_date = filters.snapshot_date
	sku_types = _parse_multiselect(filters.get("sku_type"))
	item_code_filter = filters.get("item_code")

	data = []

	for combo in COMBINATIONS:
		snap = _get_latest_snapshot(
			snapshot_date,
			combo["purchase"],
			combo["sell"],
			combo["buffer_flag"],
		)
		if not snap:
			continue

		item_filters = {"parent": snap.name}
		if sku_types:
			item_filters["sku_type"] = ["in", sku_types]
		if item_code_filter:
			item_filters["item_code"] = item_code_filter

		rows = frappe.get_all(
			"PO Recommendation Snapshot Item",
			filters=item_filters,
			fields=[
				"item_code", "sku_type", "requirement",
				"tog", "toy", "tor",
				"open_so", "total_so", "open_so_qualified",
				"on_hand_stock", "wip", "open_po", "open_subcon_po",
				"additional_demand", "qualified_demand",
				"on_hand_status", "on_hand_colour", "net_flow",
				"order_recommendation", "mrq",
				"balance_order_recommendation", "net_order_recommendation",
				"moq", "batch_size",
				"production_qty_based_on_child_stock", "child_full_kit_status",
				"production_qty_based_on_child_stock_wip_open_po", "child_wip_open_po_full_kit_status",
				"child_item_code", "child_item_type", "child_sku_type",
				"child_requirement", "child_stock", "child_stock_soft_allocation_qty",
				"child_stock_shortage", "child_wip_open_po",
				"child_wip_open_po_soft_allocation_qty", "child_wip_open_po_shortage",
			],
			order_by="item_code asc",
		)

		snap_time = str(snap.snapshot_time)[:8] if snap.snapshot_time else ""

		for row in rows:
			row["combination"] = combo["label"]
			row["snapshot_time"] = snap_time
			data.append(row)

	return data
