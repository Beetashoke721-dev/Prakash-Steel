# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission

from prakash_steel.prakash_steel.report.open_mr_for_manufacture.open_mr_for_manufacture import (
	_PRIORITY_TO_COLOUR,
	_STATUS_PRIORITY,
	_buffer_colour,
	_non_buffer_colour,
	calculate_sku_type,
	get_item_master_map,
	get_open_so_map,
	get_qualified_demand_map,
	get_stock_map,
)


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("WO No"),
			"fieldname": "work_order",
			"fieldtype": "Link",
			"options": "Work Order",
			"width": 160,
		},
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Colour"),
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Priority"),
			"fieldname": "priority",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Priority Sequence"),
			"fieldname": "priority_sequence",
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"label": _("Item SKU Type"),
			"fieldname": "item_sku_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Child Item Code"),
			"fieldname": "child_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Child Item Qty"),
			"fieldname": "child_item_qty",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Child SKU Type"),
			"fieldname": "child_sku_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Machine"),
			"fieldname": "machine",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def get_data(filters=None):
	work_orders = frappe.db.sql(
		"""
		SELECT
			wo.name AS work_order,
			wo.creation AS wo_creation,
			wo.planned_start_date AS date,
			wo.production_item AS item,
			ROUND(wo.qty) AS qty,
			wo.custom_machine_name AS machine
		FROM `tabWork Order` wo
		WHERE wo.docstatus = 0
		ORDER BY wo.planned_start_date ASC, wo.name
		""",
		as_dict=True,
	)

	if not work_orders:
		return []

	parent_item_codes = list({wo.item for wo in work_orders})

	item_master_map = get_item_master_map(parent_item_codes)
	stock_map = get_stock_map(parent_item_codes)
	wip_map = get_submitted_wo_map(parent_item_codes)
	qd_map = get_qualified_demand_map(parent_item_codes, item_master_map)
	so_map = get_open_so_map(parent_item_codes)
	prev_wo_qty_map = get_previous_wo_qty_map(work_orders)
	op_cp_map = get_op_cp_map(work_orders, stock_map, wip_map, qd_map, item_master_map)

	priority_seq_rows = frappe.db.sql(
		"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
		as_dict=True,
	)
	priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

	# Fetch child items for all work orders at once
	wo_names = [wo.work_order for wo in work_orders]
	child_rows = frappe.db.sql(
		"""
		SELECT
			woi.parent AS work_order,
			woi.item_code AS child_item_code,
			woi.required_qty AS child_item_qty
		FROM `tabWork Order Item` woi
		WHERE woi.parent IN %s
		ORDER BY woi.idx ASC
		""",
		(wo_names,),
		as_dict=True,
	)

	child_item_codes = list({r.child_item_code for r in child_rows})
	child_master_map = {}
	if child_item_codes:
		child_master_rows = frappe.db.sql(
			"""
			SELECT name, custom_item_type, custom_buffer_flag
			FROM `tabItem`
			WHERE name IN %s
			""",
			(child_item_codes,),
			as_dict=True,
		)
		child_master_map = {
			r.name: {
				"item_type": r.custom_item_type or "",
				"buffer_flag": r.custom_buffer_flag or "Non-Buffer",
			}
			for r in child_master_rows
		}

	children_by_wo = {}
	for cr in child_rows:
		children_by_wo.setdefault(cr.work_order, []).append(cr)

	data = []
	for wo in work_orders:
		master = item_master_map.get(wo.item, {"tog": 0.0, "buffer_flag": "Non-Buffer", "item_type": ""})
		item_sku_type = calculate_sku_type(master["buffer_flag"], master["item_type"])

		level = (
			flt(stock_map.get(wo.item, 0))
			+ flt(wip_map.get(wo.item, 0))
			+ flt(prev_wo_qty_map.get((wo.work_order, wo.item), 0))
		)

		if master["buffer_flag"] == "Buffer":
			colour = _buffer_colour(level, master["tog"], qd_map.get(wo.item, 0))
		else:
			colour = _non_buffer_colour(wo.item, level, so_map)

		op_cp = op_cp_map.get(wo.work_order, "")
		if colour:
			if item_sku_type == "BBMTA":
				priority = "MTA" + op_cp + colour.upper()
			else:
				priority = "MTO" + colour.upper()
		else:
			priority = ""

		priority_sequence = priority_seq_map.get(priority) if priority else None

		base = {
			"work_order": wo.work_order,
			"date": wo.date,
			"item": wo.item,
			"qty": wo.qty,
			"colour": colour,
			"priority": priority,
			"priority_sequence": priority_sequence,
			"item_sku_type": item_sku_type,
			"machine": wo.machine or "",
		}

		children = children_by_wo.get(wo.work_order, [])
		if children:
			for child in children:
				child_master = child_master_map.get(child.child_item_code, {})
				child_sku_type = calculate_sku_type(
					child_master.get("buffer_flag", "Non-Buffer"),
					child_master.get("item_type", ""),
				)
				row = base.copy()
				row["child_item_code"] = child.child_item_code
				row["child_item_qty"] = flt(child.child_item_qty)
				row["child_sku_type"] = child_sku_type
				data.append(row)
		else:
			row = base.copy()
			row["child_item_code"] = None
			row["child_item_qty"] = None
			row["child_sku_type"] = None
			data.append(row)

	# Sort ascending by priority_sequence; rows with no sequence go last
	data.sort(key=lambda r: r.get("priority_sequence") if r.get("priority_sequence") is not None else 999999)

	return data


# ---------------------------------------------------------------------------
# OP / CP assignment per Work Order
# ---------------------------------------------------------------------------


def get_op_cp_map(work_orders, stock_map, wip_map, qd_map, item_master_map):
	"""
	For Buffer items: assign OP if remaining qualified demand (after stock+wip) is not yet
	covered by earlier WOs, else CP. Non-buffer items always get "".
	WOs for the same item are processed in creation order (oldest first).
	"""
	item_wo_groups = defaultdict(list)
	for wo in work_orders:
		item_wo_groups[wo.item].append(wo)

	op_cp_map = {}

	for item_code, wos in item_wo_groups.items():
		master = item_master_map.get(item_code, {})
		if master.get("buffer_flag") != "Buffer":
			for wo in wos:
				op_cp_map[wo.work_order] = ""
			continue

		stock = flt(stock_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		qualified_demand = flt(qd_map.get(item_code, 0))
		remaining = max(0.0, qualified_demand - stock - wip)

		for wo in sorted(wos, key=lambda w: w.wo_creation):
			op_cp_map[wo.work_order] = "OP" if remaining > 0 else "CP"
			remaining -= flt(wo.qty)

	return op_cp_map


# ---------------------------------------------------------------------------
# Previous Work Order pending qty
# ---------------------------------------------------------------------------


def get_previous_wo_qty_map(work_orders):
	"""
	Returns {(work_order, item_code): previous_pending_qty}.
	For each WO, sums qty of all draft WOs for the same item
	that were created before this WO's creation.
	"""
	item_codes = list({wo.item for wo in work_orders})
	if not item_codes:
		return {}

	all_open = frappe.db.sql(
		"""
		SELECT
			wo.name AS work_order,
			wo.creation,
			wo.production_item AS item_code,
			wo.qty AS pending_qty
		FROM `tabWork Order` wo
		WHERE wo.docstatus = 0
		  AND wo.production_item IN %s
		""",
		(item_codes,),
		as_dict=True,
	)

	item_wo_map = defaultdict(list)
	for p in all_open:
		item_wo_map[p.item_code].append(p)

	result_map = {}
	for wo in work_orders:
		key = (wo.work_order, wo.item)
		result_map[key] = flt(
			sum(
				p.pending_qty
				for p in item_wo_map[wo.item]
				if p.creation < wo.wo_creation
			)
		)
	return result_map


# ---------------------------------------------------------------------------
# Submitted WO pending qty (used as WIP for draft WO level calculation)
# ---------------------------------------------------------------------------


def get_submitted_wo_map(item_codes):
	"""
	Returns {item_code: total_pending_qty} from submitted (docstatus=1) Work Orders
	that are not Completed/Stopped/Cancelled/Closed.
	This represents actual in-progress production (WIP) for the item.
	"""
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT
			wo.production_item AS item_code,
			SUM(GREATEST(0, wo.qty - IFNULL(wo.produced_qty, 0))) AS pending_qty
		FROM `tabWork Order` wo
		WHERE wo.docstatus = 1
		  AND wo.status NOT IN ('Completed', 'Stopped', 'Cancelled', 'Closed')
		  AND wo.production_item IN %s
		GROUP BY wo.production_item
		""",
		(item_codes,),
		as_dict=True,
	)
	return {r.item_code: flt(r.pending_qty) for r in rows}


# ---------------------------------------------------------------------------
# Debug API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_wo_item_breakdown(wo_name):
	"""
	Returns per-item breakdown for the given draft Work Order:
	  buffer items  → stock, wip, tog, qualified_demand, previous_wo_qty, level, colour
	  non-buffer    → stock, wip, previous_wo_qty, level, SO-level FIFO detail, colour
	"""
	require_permission("Work Order", "read")
	wo = frappe.db.get_value(
		"Work Order",
		wo_name,
		["name", "creation", "production_item", "qty", "docstatus"],
		as_dict=True,
	)
	if not wo:
		frappe.throw(f"Work Order {wo_name} not found.")

	item_code = wo.production_item
	item_codes = [item_code]

	item_master_map = get_item_master_map(item_codes)
	stock_map = get_stock_map(item_codes)
	wip_map = get_submitted_wo_map(item_codes)
	qd_map = get_qualified_demand_map(item_codes, item_master_map)
	so_map = get_open_so_map(item_codes)

	# Previous draft WO qty relative to this WO
	all_open = frappe.db.sql(
		"""
		SELECT
			wo2.name AS work_order,
			wo2.creation,
			wo2.production_item AS item_code,
			wo2.qty AS pending_qty
		FROM `tabWork Order` wo2
		WHERE wo2.docstatus = 0
		  AND wo2.production_item = %s
		""",
		(item_code,),
		as_dict=True,
	)
	prev_qty = flt(sum(p.pending_qty for p in all_open if p.creation < wo.creation))

	master = item_master_map.get(item_code, {"tog": 0.0, "buffer_flag": "Non-Buffer", "item_type": ""})
	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))
	level = stock + wip + prev_qty
	is_buffer = master["buffer_flag"] == "Buffer"

	entry = {
		"item_code": item_code,
		"buffer_flag": master["buffer_flag"],
		"sku_type": calculate_sku_type(master["buffer_flag"], master["item_type"]),
		"stock": stock,
		"wip": wip,
		"previous_wo_qty": prev_qty,
		"level": level,
	}

	if is_buffer:
		tog = master["tog"]
		qd = flt(qd_map.get(item_code, 0))
		entry["tog"] = tog
		entry["qualified_demand"] = qd
		entry["colour"] = _buffer_colour(level, tog, qd)
		entry["so_fifo_detail"] = []
	else:
		entry["tog"] = "N/A"
		entry["qualified_demand"] = "N/A"
		sos = so_map.get(item_code, [])
		available = level
		fifo_rows = []
		worst_priority = 0

		for so in sos:
			required = flt(so["pending_qty"])
			allocated = min(required, available)
			shortage = required - allocated
			available -= allocated
			status = so["order_status"] or ""

			if shortage > 0:
				priority = _STATUS_PRIORITY.get(status, 0)
				if priority > worst_priority:
					worst_priority = priority

			fifo_rows.append(
				{
					"delivery_date": str(so["delivery_date"]) if so["delivery_date"] else "",
					"pending_qty": required,
					"allocated": allocated,
					"shortage": shortage,
					"order_status": status,
				}
			)

		colour = (
			"Green"
			if worst_priority == 0 and sos
			else (_PRIORITY_TO_COLOUR.get(worst_priority, "") if worst_priority else "")
		)
		entry["colour"] = colour
		entry["so_fifo_detail"] = fifo_rows

	return [entry]
