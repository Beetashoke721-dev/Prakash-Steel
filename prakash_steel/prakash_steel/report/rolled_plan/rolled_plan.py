import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, nowdate

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_non_buffer_priority,
	calculate_net_order_recommendation,
	calculate_sku_type,
	calculate_spike_map,
	get_mrq_map,
	get_open_po_map,
	get_open_so_map_for_priority,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_stock_map,
	get_wip_map,
)


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def _buffer_colour(level, tog, qualified_demand):
	total = flt(tog) + flt(qualified_demand)
	if level == 0:
		return "Black"
	if total <= 0:
		return ""
	if level <= total / 3:
		return "Red"
	if level <= (2 * total) / 3:
		return "Yellow"
	if level <= total:
		return "Green"
	return "White"


_COLOUR_RANK = {"Black": 5, "Red": 4, "Yellow": 3, "Green": 2, "White": 1}
_RANK_COLOUR = {5: "Black", 4: "Red", 3: "Yellow", 2: "Green", 1: "White"}


def _compute_order_status(delivery_date, transaction_date):
	"""Mirror of Open SO Analysis order_status logic."""
	if not delivery_date:
		return None
	today = nowdate()
	remaining_days = date_diff(delivery_date, today)
	lead_time = date_diff(delivery_date, transaction_date) if transaction_date else None
	if lead_time:
		buffer_pct = (flt(remaining_days) / flt(lead_time)) * 100
	else:
		buffer_pct = flt(remaining_days) * 100
	numeric = math.ceil(buffer_pct)
	if numeric < 0:
		return "BLACK"
	if numeric <= 34:
		return "RED"
	if numeric <= 67:
		return "YELLOW"
	if numeric <= 100:
		return "GREEN"
	return "WHITE"


def get_rbmto_so_detail_map(item_codes):
	"""Returns {item_code: [{pending_qty, colour}, ...]} sorted delivery_date ASC for FIFO."""
	if not item_codes:
		return {}
	t = tuple(item_codes) if len(item_codes) > 1 else (next(iter(item_codes)),)
	rows = frappe.db.sql(
		"""
		SELECT soi.item_code, so.transaction_date, soi.delivery_date,
		       GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code IN %s
		  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
		ORDER BY soi.delivery_date ASC
		""",
		(t,),
		as_dict=True,
	)
	result = defaultdict(list)
	for r in rows:
		status = _compute_order_status(r.delivery_date, r.transaction_date)
		colour = status.capitalize() if status else ""
		result[r.item_code].append({"pending_qty": flt(r.pending_qty), "colour": colour})
	return result


def get_parent_bom_map(item_codes):
	"""Returns {child_item_code: [{parent_item, bom_qty, bom_quantity}, ...]} from default BOMs."""
	if not item_codes:
		return {}
	t = tuple(item_codes) if len(item_codes) > 1 else (next(iter(item_codes)),)
	rows = frappe.db.sql(
		"""
		SELECT b.item AS parent_item, bi.item_code AS child_item,
		       bi.qty AS bom_qty, b.quantity AS bom_quantity
		FROM `tabBOM Item` bi
		INNER JOIN `tabBOM` b ON b.name = bi.parent
		WHERE b.is_default = 1 AND b.docstatus = 1
		  AND bi.item_code IN %s
		""",
		(t,),
		as_dict=True,
	)
	result = defaultdict(list)
	for r in rows:
		result[r.child_item].append(
			{
				"parent_item": r.parent_item,
				"bom_qty": flt(r.bom_qty),
				"bom_quantity": flt(r.bom_quantity) or 1.0,
			}
		)
	return result


def _build_parent_batches(
	stock, wip, tog, qd, is_buffer, net_order_rec, batch_size, moq, priority_seq_map,
	item_code=None, open_so=0.0, so_map_for_priority=None,
):
	"""
	Generate production batch list for a parent BB item, mirroring bright_plan logic.
	Returns list of {batch_qty, level_before, colour, op_cp, priority_colour, priority_sequence}.
	"""
	if net_order_rec <= 0:
		return []

	if moq == 0 and batch_size > 0 and net_order_rec > batch_size:
		num_batches = round(net_order_rec / batch_size)
		qty_per_row = flt(batch_size)
	else:
		num_batches = 1
		qty_per_row = flt(net_order_rec)

	if qty_per_row <= 0:
		return []

	# BBMTA: display_open_so = qualified_demand; BBMTO: total open SO (same as bright_plan)
	display_open_so = flt(qd) if is_buffer else flt(open_so)
	remaining_so_for_op_cp = max(0.0, display_open_so - flt(stock) - flt(wip))
	accumulated = 0.0
	sku_type = "BBMTA" if is_buffer else "BBMTO"

	batches = []
	for _i in range(num_batches):
		level = flt(stock) + flt(wip) + accumulated
		if is_buffer:
			colour = _buffer_colour(level, tog, qd)
		else:
			colour = _non_buffer_priority(item_code, level, so_map_for_priority or {}) if item_code else ""
		op_cp = ""
		if is_buffer and qty_per_row > 0:
			op_cp = "OP" if remaining_so_for_op_cp > 0 else "CP"
		if colour:
			pc_str = ("MTA" + op_cp + colour.upper()) if sku_type == "BBMTA" else ("MTO" + colour.upper())
		else:
			pc_str = ""
		pri_seq = priority_seq_map.get(pc_str, 999999)
		batches.append(
			{
				"batch_qty": qty_per_row,
				"level_before": level,
				"colour": colour,
				"op_cp": op_cp,
				"priority_colour": pc_str,
				"priority_sequence": pri_seq,
			}
		)
		remaining_so_for_op_cp -= qty_per_row
		accumulated += qty_per_row
	return batches


_COLOUR_PRIORITY = {"Black": 5, "Red": 4, "Yellow": 3, "Green": 2, "White": 1}
_PRIORITY_TO_COLOUR = {5: "Black", 4: "Red", 3: "Yellow", 2: "Green", 1: "White"}


def _rbmto_on_hand_colour(level, own_so_list):
	"""
	RBMTO on-hand colour (mirrors po_recomendation _non_buffer_priority):
	FIFO-allocate `level` across own SOs sorted by delivery_date ASC.
	- If any SO has shortage → return worst colour of shortage SOs.
	- If no shortage → return worst colour of no-shortage SOs.
	"""
	if not own_so_list:
		return ""
	available = flt(level)
	worst_shortage = 0
	worst_no_shortage = 0
	for so in own_so_list:
		required = flt(so["pending_qty"])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		priority = _COLOUR_PRIORITY.get(so["colour"], 0)
		if shortage > 0:
			if priority > worst_shortage:
				worst_shortage = priority
		else:
			if priority > worst_no_shortage:
				worst_no_shortage = priority
	if worst_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_shortage, "")
	if worst_no_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_no_shortage, "")
	return ""


def _rbmto_colour(level, own_so_list, parent_so_fifo_list):
	"""
	RBMTO colour:
	1. FIFO through own open SOs sorted by delivery_date ASC — stop at first shortage.
	2. FIFO remaining through parent SOs sorted by priority_sequence ASC — stop at first shortage.
	   Each parent SO entry has child_req = ceil(parent_pending_qty * bom_qty / bom_quantity).
	If no shortage anywhere → "".
	"""
	available = flt(level)

	# Step 1: own SO FIFO — stop and return colour at first SO with a shortage
	for so in own_so_list:
		required = flt(so["pending_qty"])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		if shortage > 0:
			return so["colour"] or ""

	# Step 2: parent batch FIFO (pre-sorted by priority_sequence ASC)
	# Allocate batch_qty (parent units) from available; child_req is for reference only
	for entry in parent_so_fifo_list:
		batch_qty = entry["batch_qty"]
		allocated = min(batch_qty, available)
		shortage = batch_qty - allocated
		available -= allocated
		if shortage > 0:
			return entry["colour"] or ""

	return ""


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Colour"),
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("On Hand Colour"),
			"fieldname": "on_hand_colour",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Net Order Recommendation"),
			"fieldname": "net_order_recommendation",
			"fieldtype": "Int",
			"width": 200,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Item Type"),
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Last Rolled Date"),
			"fieldname": "last_rolled_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": _("Last Rolled Qty"),
			"fieldname": "last_rolled_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Last 3 Months Sale"),
			"fieldname": "last_3_months_sale",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Last 3 Months Consumption"),
			"fieldname": "last_3_months_consumption",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Last 1 Month Sale"),
			"fieldname": "last_1_month_sale",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Last 1 Month Consumption"),
			"fieldname": "last_1_month_consumption",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("On Hand Stock"),
			"fieldname": "on_hand_stock",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{
			"label": _("TOG"),
			"fieldname": "tog",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("TOG Subgroup %"),
			"fieldname": "tog_subgroup_pct",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Net Qty"),
			"fieldname": "net_qty",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Sub Grp"),
			"fieldname": "sub_grp",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Grp"),
			"fieldname": "grp",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Shape"),
			"fieldname": "shape",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Subgrp+Shape"),
			"fieldname": "subgrp_shape",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Grp+Shape"),
			"fieldname": "grp_shape",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Grp Weightage Value"),
			"fieldname": "grp_weightage_value",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Subgrp Count"),
			"fieldname": "subgrp_count",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Subgroup Qty"),
			"fieldname": "subgroup_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Per Hour Qty"),
			"fieldname": "per_hour_qty",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Hrs Work"),
			"fieldname": "hrs_work",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Subgrp Hours+Setup"),
			"fieldname": "subgrp_hours_setup",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Subgrp Hours Shortage"),
			"fieldname": "subgrp_hours_shortage",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("Extra Hours"),
			"fieldname": "extra_hours",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Extra Qty"),
			"fieldname": "extra_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Excess Qty"),
			"fieldname": "excess_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Excess Qty/TOG"),
			"fieldname": "excess_qty_tog",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("TOG%"),
			"fieldname": "tog_pct",
			"fieldtype": "Float",
			"width": 90,
		},
		{
			"label": _("Allocated Hours"),
			"fieldname": "allocated_hours",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Total Allocated Qty"),
			"fieldname": "total_allocated_qty",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Final Allocated Qty"),
			"fieldname": "final_allocated_qty",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Calc Excess Qty"),
			"fieldname": "calc_excess_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Net Calc Excess Qty"),
			"fieldname": "net_calc_excess_qty",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Net Calc TOG%"),
			"fieldname": "net_calc_tog_pct",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("New Excess Qty"),
			"fieldname": "new_excess_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("New Excess/TOG"),
			"fieldname": "new_excess_tog",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Subgroup Weightage Value"),
			"fieldname": "subgroup_weightage_value",
			"fieldtype": "Float",
			"width": 190,
		},
		{
			"label": _("Group Count"),
			"fieldname": "group_count",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Weightage Value"),
			"fieldname": "weightage_value",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Prod Qty Based on Child Stock"),
			"fieldname": "prod_qty_based_on_child_stock",
			"fieldtype": "Float",
			"width": 200,
		},
		{
			"label": _("Prod Qty Based on Child Stock+WIP/Open PO"),
			"fieldname": "prod_qty_based_on_child_stock_wip_open_po",
			"fieldtype": "Float",
			"width": 260,
		},
		{
			"label": _("Child Item Code"),
			"fieldname": "child_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Child Requirement"),
			"fieldname": "child_requirement",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Child Stock"),
			"fieldname": "child_stock",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Child Stock Allocation"),
			"fieldname": "child_stock_allocation",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Child Shortage"),
			"fieldname": "child_shortage",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Child Item Open PO"),
			"fieldname": "child_item_open_po",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("First Parent Item"),
			"fieldname": "first_parent_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("First Parent Item Stock"),
			"fieldname": "first_parent_item_stock",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Second Parent Item"),
			"fieldname": "second_parent_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Second Parent Item Stock"),
			"fieldname": "second_parent_item_stock",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Third Parent Item"),
			"fieldname": "third_parent_item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Third Parent Item Stock"),
			"fieldname": "third_parent_item_stock",
			"fieldtype": "Float",
			"width": 180,
		},
	]


def get_data(filters=None):
	if not filters:
		filters = {}

	# Fetch all RB items
	rb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.item_name,
			i.custom_item_type as item_type,
			i.custom_buffer_flag as buffer_flag,
			i.safety_stock as tog,
			i.min_order_qty as moq,
			i.custom_batch_size as batch_size,
			i.custom_sub_group_new_name as sub_grp,
			i.custom_shape as shape,
			i.custom_group_for_sub_assemblies as grp
		FROM `tabItem` i
		WHERE i.custom_item_type = 'RB'
		""",
		as_dict=True,
	)

	if not rb_items:
		return []

	item_codes = set(item.item_code for item in rb_items)
	item_codes_tuple = tuple(item_codes) if len(item_codes) > 1 else (next(iter(item_codes)),)

	# Build lookup maps
	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	item_info_map = {}
	for item in rb_items:
		item_buffer_map[item.item_code] = item.buffer_flag or "Non-Buffer"
		item_type_map[item.item_code] = item.item_type
		item_tog_map[item.item_code] = flt(item.tog or 0)
		item_info_map[item.item_code] = item

	# Per hour qty and final planned hrs from Rolling Algo
	rolling_algo_rows = frappe.db.get_all(
		"Rolling Algo",
		fields=["item_code", "per_hour_planned_qty", "final_planned_hrs"],
	)
	per_hour_qty_map = {r.item_code: flt(r.per_hour_planned_qty) for r in rolling_algo_rows}
	final_planned_hrs_map = {r.item_code: flt(r.final_planned_hrs) for r in rolling_algo_rows}

	stock_map = get_stock_map(item_codes)
	mrq_map = get_mrq_map()

	# Last rolled date and qty from most recent submitted Finish Weight doc per item
	last_rolled_rows = frappe.db.sql(
		"""
		SELECT fw.item_code, fw.posting_date, fw.finish_weight
		FROM `tabFinish Weight` fw
		INNER JOIN (
			SELECT item_code, MAX(posting_date) AS max_date
			FROM `tabFinish Weight`
			WHERE docstatus = 1 AND item_code IN %s
			GROUP BY item_code
		) latest ON fw.item_code = latest.item_code AND fw.posting_date = latest.max_date
		WHERE fw.docstatus = 1
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_rolled_map = {}
	for r in last_rolled_rows:
		existing = last_rolled_map.get(r.item_code)
		if not existing or r.posting_date > existing["last_rolled_date"]:
			last_rolled_map[r.item_code] = {
				"last_rolled_date": r.posting_date,
				"last_rolled_qty": flt(r.finish_weight),
			}
	open_po_map = get_open_po_map()
	so_qty_map = get_sales_order_qty_map(filters)

	# Last 3 months consumption (90 days) from Bright Bar Production
	last_3month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			bbp.raw_material AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND bbp.raw_material IN %s
		GROUP BY bbp.raw_material
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_3month_consumption_map = {r.item_code: flt(r.consumption_qty) for r in last_3month_consumption_rows}

	# Last 1 month consumption (30 days) from Bright Bar Production
	last_1month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			bbp.raw_material AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND bbp.raw_material IN %s
		GROUP BY bbp.raw_material
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_1month_consumption_map = {r.item_code: flt(r.consumption_qty) for r in last_1month_consumption_rows}

	# Last 3 months sale (90 days) — same logic as bright_plan
	last_3month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(sii.qty) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND sii.item_code IN %s
		GROUP BY sii.item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_3month_sale_map = {r.item_code: flt(r.sale_qty) for r in last_3month_rows}

	# Last 1 month sale (30 days) — same query, shorter interval
	last_1month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(sii.qty) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND sii.item_code IN %s
		GROUP BY sii.item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_1month_sale_map = {r.item_code: flt(r.sale_qty) for r in last_1month_rows}

	till_today_map, spike_map_base = get_qualified_demand_map()
	calculated_spike_map = calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map)
	spike_map_base.update(calculated_spike_map)

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}

	qualified_demand_map = {}
	for item_code in item_codes:
		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map_base,
			item_buffer_map,
			item_tog_map,
			item_type_map,
			spike_master_map,
		)
		qualified_demand_map[item_code] = qualified_demand

	# Build RBMTO colour data — own SO FIFO + parent BOM FIFO
	rbmto_codes = {ic for ic in item_codes if item_buffer_map.get(ic) != "Buffer"}
	rbmto_so_detail_map = {}
	parent_bom_map = {}
	parent_data_map = {}
	child_parent_so_fifo = defaultdict(list)
	rbmto_eligible_parent_map = {}

	if rbmto_codes:
		rbmto_so_detail_map = get_rbmto_so_detail_map(rbmto_codes)
		parent_bom_map = get_parent_bom_map(rbmto_codes)

		all_parent_codes = {p["parent_item"] for plist in parent_bom_map.values() for p in plist}
		if all_parent_codes:
			parent_tuple = (
				tuple(all_parent_codes) if len(all_parent_codes) > 1 else (next(iter(all_parent_codes)),)
			)

			# Parent item master
			parent_master_rows = frappe.db.sql(
				"""
				SELECT name AS item_code,
				       custom_buffer_flag AS buffer_flag,
				       custom_item_type AS item_type,
				       safety_stock AS tog,
				       min_order_qty AS moq,
				       custom_batch_size AS batch_size
				FROM `tabItem`
				WHERE name IN %s
				""",
				(parent_tuple,),
				as_dict=True,
			)
			p_master_map = {r.item_code: r for r in parent_master_rows}
			p_buffer_map = {r.item_code: r.buffer_flag or "Non-Buffer" for r in parent_master_rows}
			p_type_map = {r.item_code: r.item_type or "" for r in parent_master_rows}
			p_tog_map = {r.item_code: flt(r.tog or 0) for r in parent_master_rows}

			# Spike for BB parent items
			bb_spike_map = calculate_spike_map(all_parent_codes, p_buffer_map, p_type_map, p_tog_map)
			parent_spike_map = dict(spike_map_base)
			parent_spike_map.update(bb_spike_map)

			# Parent stock and WIP
			parent_stock_map = get_stock_map(all_parent_codes)
			parent_wip_map = get_wip_map()

			# Open SO for BBMTO parents (all open SOs, no date filter — same as bright_plan)
			parent_open_so_qty_map = get_sales_order_qty_map({})
			parent_so_for_priority_map = get_open_so_map_for_priority(list(all_parent_codes))

			# Priority sequence master
			priority_seq_rows = frappe.db.sql(
				"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
				as_dict=True,
			)
			priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

			for ic in all_parent_codes:
				master = p_master_map.get(ic)
				if not master:
					continue
				is_buf = p_buffer_map[ic] == "Buffer"
				tog_p = p_tog_map[ic]
				stock_p = flt(parent_stock_map.get(ic, 0))
				wip_p = flt(parent_wip_map.get(ic, 0))
				mrq_p = flt(mrq_map.get(ic, 0))
				moq_p = flt(master.moq or 0)
				bs_p = flt(master.batch_size or 0)

				qd_p, _, _ = get_qualified_demand_for_item(
					ic,
					till_today_map,
					parent_spike_map,
					p_buffer_map,
					p_tog_map,
					p_type_map,
					spike_master_map,
				)
				qd_p = flt(qd_p)
				open_so_p = flt(parent_open_so_qty_map.get(ic, 0)) if not is_buf else 0.0

				if is_buf:
					base_rec = max(0, tog_p + qd_p - stock_p - wip_p - mrq_p)
				else:
					base_rec = max(0, open_so_p - stock_p - wip_p - mrq_p)
				net_rec = calculate_net_order_recommendation(base_rec, moq_p, bs_p)

				parent_data_map[ic] = {
					"net_order_rec": net_rec,
					"stock": stock_p,
					"wip": wip_p,
					"tog": tog_p,
					"qd": qd_p,
					"open_so": open_so_p,
					"is_buffer": is_buf,
					"batch_size": bs_p,
					"moq": moq_p,
				}

		# RBMTO items eligible for BBMTA parent allocation logic:
		# exactly one parent AND that parent is BBMTA (BB + Buffer)
		for child_ic in rbmto_codes:
			parents = parent_bom_map.get(child_ic, [])
			if len(parents) == 1:
				parent_ic = parents[0]["parent_item"]
				if p_type_map.get(parent_ic) == "BB" and p_buffer_map.get(parent_ic) == "Buffer":
					rbmto_eligible_parent_map[child_ic] = parent_ic

		# Build per-child-item flat batch FIFO list using bright_plan incremental logic
		for child_ic in rbmto_codes:
			flat = []
			for p in parent_bom_map.get(child_ic, []):
				parent_item = p["parent_item"]
				pd = parent_data_map.get(parent_item)
				if not pd:
					continue
				bom_ratio = p["bom_qty"] / (p["bom_quantity"] or 1.0)
				batches = _build_parent_batches(
					pd["stock"],
					pd["wip"],
					pd["tog"],
					pd["qd"],
					pd["is_buffer"],
					pd["net_order_rec"],
					pd["batch_size"],
					pd["moq"],
					priority_seq_map,
					item_code=parent_item,
					open_so=pd.get("open_so", 0),
					so_map_for_priority=parent_so_for_priority_map,
				)
				for batch in batches:
					child_req = math.ceil(batch["batch_qty"] * bom_ratio)
					flat.append(
						{
							"parent_item": parent_item,
							"batch_qty": batch["batch_qty"],
							"level_before": batch["level_before"],
							"child_req": child_req,
							"colour": batch["colour"],
							"priority_colour": batch["priority_colour"],
							"priority_sequence": batch["priority_sequence"],
							"op_cp": batch["op_cp"],
							"tog": pd["tog"],
						}
					)
			flat.sort(key=lambda x: (x["priority_sequence"], -flt(x["tog"])))
			child_parent_so_fifo[child_ic] = flat

	# Fetch colour weightage map from Single DocType
	colour_weightage_rows = frappe.get_all(
		"Colour Weightage Master Table",
		filters={"parent": "Colour Weightage Master"},
		fields=["colour", "weightage"],
	)
	colour_weightage_map = {r.colour: flt(r.weightage) for r in colour_weightage_rows}

	data = []
	for item_code in sorted(item_codes):
		item = item_info_map[item_code]
		buffer_flag = item_buffer_map[item_code]
		sku_type = calculate_sku_type(buffer_flag, item_type_map[item_code])

		# Only include RBMTA and RBMTO
		if sku_type not in ("RBMTA", "RBMTO"):
			continue

		is_buffer = buffer_flag == "Buffer"
		tog = item_tog_map[item_code]
		stock = flt(stock_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		moq = flt(item.moq or 0)
		batch_size = flt(item.batch_size or 0)

		# WIP is excluded for RBMTA and RBMTO

		if is_buffer:
			# RBMTA: TOG + qualified_demand - stock - MRQ
			qualified_demand = flt(qualified_demand_map.get(item_code, 0))
			base_order_rec = tog + qualified_demand - stock - mrq
		else:
			# RBMTO: open_so - stock - MRQ
			open_so = flt(so_qty_map.get(item_code, 0))
			base_order_rec = open_so - stock - mrq

		base_order_rec = max(0, base_order_rec)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		# if net_order_rec <= 0:
		# 	continue

		# Colour — level = stock only (MRQ excluded)
		level = stock
		if is_buffer:
			colour = _buffer_colour(level, tog, flt(qualified_demand_map.get(item_code, 0)))
		else:
			colour = _rbmto_colour(
				level,
				rbmto_so_detail_map.get(item_code, []),
				child_parent_so_fifo.get(item_code, []),
			)

		# For eligible RBMTO: use parent BBMTA's tog, per_hour_qty, final_planned_hrs
		effective_tog = tog
		effective_per_hour_qty = per_hour_qty_map.get(item_code) or None
		if item_code in rbmto_eligible_parent_map:
			parent_ic = rbmto_eligible_parent_map[item_code]
			pd = parent_data_map.get(parent_ic, {})
			if flt(pd.get("tog") or 0) > 0:
				effective_tog = flt(pd.get("tog") or 0)
			if not effective_per_hour_qty:
				effective_per_hour_qty = per_hour_qty_map.get(parent_ic) or None

		data.append(
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"colour": colour,
				"on_hand_colour": None,
				"net_order_recommendation": math.ceil(flt(net_order_rec)),
				"sku_type": sku_type,
				"item_type": item_type_map[item_code],
				"tog": math.ceil(flt(effective_tog)),
				"tog_subgroup_pct": None,
				"last_rolled_date": last_rolled_map.get(item_code, {}).get("last_rolled_date"),
				"last_rolled_qty": last_rolled_map.get(item_code, {}).get("last_rolled_qty"),
				"last_3_months_sale": last_3month_sale_map.get(item_code, 0),
				"last_3_months_consumption": last_3month_consumption_map.get(item_code, 0),
				"last_1_month_sale": last_1month_sale_map.get(item_code, 0),
				"last_1_month_consumption": last_1month_consumption_map.get(item_code, 0),
				"on_hand_stock": flt(stock),
				"net_qty": None,
				"sub_grp": item.sub_grp or "",
				"grp": item.grp or "",
				"shape": item.shape or "",
				"subgrp_shape": " ".join(filter(None, [item.sub_grp, item.shape])),
				"grp_shape": " ".join(filter(None, [item.grp, item.shape])),
				"grp_weightage_value": None,
				"subgrp_count": None,
				"subgroup_qty": None,
				"per_hour_qty": effective_per_hour_qty,
				"hrs_work": (flt(net_order_rec) / effective_per_hour_qty) if effective_per_hour_qty else None,
				"subgrp_hours_setup": None,
				"subgrp_hours_shortage": None,
				"extra_hours": None,
				"extra_qty": None,
				"excess_qty": None,
				"excess_qty_tog": None,
				"tog_pct": None,
				"allocated_hours": None,
				"total_allocated_qty": None,
				"final_allocated_qty": None,
				"calc_excess_qty": None,
				"net_calc_excess_qty": None,
				"net_calc_tog_pct": None,
				"new_excess_qty": None,
				"new_excess_tog": None,
				"subgroup_weightage_value": None,
				"group_count": None,
				"weightage_value": math.ceil(flt(net_order_rec)) * colour_weightage_map.get(colour, 0),
				"prod_qty_based_on_child_stock": None,
				"prod_qty_based_on_child_stock_wip_open_po": None,
				"child_item_code": None,
				"child_requirement": None,
				"child_stock": None,
				"child_stock_allocation": None,
				"child_shortage": None,
				"child_item_open_po": None,
				"first_parent_item": None,
				"first_parent_item_stock": None,
				"second_parent_item": None,
				"second_parent_item_stock": None,
				"third_parent_item": None,
				"third_parent_item_stock": None,
			}
		)

	# --- TOG Subgroup % ---
	subgrp_tog_sum = defaultdict(float)
	for row in data:
		subgrp_tog_sum[row["subgrp_shape"]] += flt(row["tog"])
	for row in data:
		group_sum = subgrp_tog_sum.get(row["subgrp_shape"], 0)
		tog_pct_val = round((flt(row["tog"]) / group_sum) * 100, 2) if group_sum else None
		row["tog_subgroup_pct"] = tog_pct_val
		row["tog_pct"] = tog_pct_val

	# --- Weightage Value aggregations ---
	subgrp_wv_sum = defaultdict(float)
	grp_wv_sum = defaultdict(float)
	subgrp_qty_sum = defaultdict(float)
	subgrp_count_map = defaultdict(int)
	grp_count_map = defaultdict(int)
	subgrp_hrs_sum = defaultdict(float)
	subgrp_final_hrs_sum = defaultdict(float)
	for row in data:
		subgrp_wv_sum[row["subgrp_shape"]] += flt(row["weightage_value"])
		grp_wv_sum[row["grp_shape"]] += flt(row["weightage_value"])
		subgrp_qty_sum[row["subgrp_shape"]] += flt(row.get("net_order_recommendation", 0))
		subgrp_count_map[row["subgrp_shape"]] += 1
		grp_count_map[row["grp_shape"]] += 1
		subgrp_hrs_sum[row["sub_grp"]] += flt(row.get("hrs_work") or 0)
		subgrp_final_hrs_sum[row["sub_grp"]] += flt(final_planned_hrs_map.get(row["item_code"]) or 0)
	for row in data:
		row["subgroup_weightage_value"] = subgrp_wv_sum.get(row["subgrp_shape"], 0) or None
		row["grp_weightage_value"] = grp_wv_sum.get(row["grp_shape"], 0) or None
		row["subgroup_qty"] = subgrp_qty_sum.get(row["subgrp_shape"], 0) or None
		row["subgrp_count"] = subgrp_count_map.get(row["subgrp_shape"], 0)
		row["group_count"] = grp_count_map.get(row["grp_shape"], 0)
		row["subgrp_hours_setup"] = subgrp_hrs_sum.get(row["sub_grp"]) or None
		final_hrs = subgrp_final_hrs_sum.get(row["sub_grp"], 0)
		setup_hrs = subgrp_hrs_sum.get(row["sub_grp"], 0)
		shortage = max(0, final_hrs - setup_hrs)
		row["subgrp_hours_shortage"] = shortage
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map

		if row.get("sku_type") == "RBMTA" or is_eligible_rbmto:
			tog_pct = flt(row.get("tog_subgroup_pct") or 0)
			extra_hrs = round((tog_pct * shortage) / 100, 3)
			row["extra_hours"] = extra_hrs
			per_hr = flt(row.get("per_hour_qty") or 0)
			row["extra_qty"] = round(extra_hrs * per_hr, 3) if per_hr else None
		else:
			row["extra_hours"] = 0
			row["extra_qty"] = 0

		# On-hand colour and excess qty
		on_hand_stock = flt(row.get("on_hand_stock") or 0)
		tog_val = flt(row.get("tog") or 0)
		qd_val = flt(qualified_demand_map.get(ic) or 0)
		on_hand_colour = None

		if row.get("sku_type") == "RBMTA":
			denominator = tog_val + qd_val
			if denominator > 0:
				pct = (on_hand_stock / denominator) * 100
				if pct == 0:
					on_hand_colour = "BLACK"
				elif pct <= 34:
					on_hand_colour = "RED"
				elif pct <= 67:
					on_hand_colour = "YELLOW"
				elif pct <= 100:
					on_hand_colour = "GREEN"
				else:
					on_hand_colour = "WHITE"
		elif is_eligible_rbmto:
			# Use parent BBMTA item's stock/tog/qd for buffer-style on_hand_colour
			parent_ic = rbmto_eligible_parent_map[ic]
			pd = parent_data_map.get(parent_ic, {})
			p_stock = flt(pd.get("stock") or 0)
			p_tog = flt(pd.get("tog") or 0)
			p_qd = flt(pd.get("qd") or 0)
			denominator = p_tog + p_qd
			if denominator > 0:
				pct = (p_stock / denominator) * 100
				if pct == 0:
					on_hand_colour = "BLACK"
				elif pct <= 34:
					on_hand_colour = "RED"
				elif pct <= 67:
					on_hand_colour = "YELLOW"
				elif pct <= 100:
					on_hand_colour = "GREEN"
				else:
					on_hand_colour = "WHITE"
			# For excess_qty use parent values
			tog_val = p_tog
			qd_val = p_qd
			on_hand_stock = p_stock
		elif row.get("sku_type") == "RBMTO":
			on_hand_colour = _rbmto_on_hand_colour(
				flt(row.get("on_hand_stock") or 0), rbmto_so_detail_map.get(ic, [])
			)

		row["on_hand_colour"] = on_hand_colour
		if on_hand_colour == "WHITE":
			row["excess_qty"] = on_hand_stock - tog_val - qd_val
		else:
			row["excess_qty"] = flt(row.get("extra_qty") or 0)
		excess = flt(row["excess_qty"])
		row["excess_qty_tog"] = round((excess / tog_val) * 100, 3) if tog_val else None

	# --- Allocated Hours ---
	subgrp_extra_hrs_sum = defaultdict(float)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if row.get("sku_type") == "RBMTA" or is_eligible_rbmto:
			subgrp_extra_hrs_sum[row["subgrp_shape"]] += flt(row.get("extra_hours") or 0)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if row.get("sku_type") == "RBMTA" or is_eligible_rbmto:
			total_extra = subgrp_extra_hrs_sum.get(row["subgrp_shape"], 0)
			tog_pct_val = flt(row.get("tog_pct") or 0)
			alloc_hrs = round(total_extra * tog_pct_val / 100, 3)
			row["allocated_hours"] = alloc_hrs
			per_hr = flt(row.get("per_hour_qty") or 0)
			total_alloc_qty = round(alloc_hrs * per_hr, 3) if per_hr else None
			row["total_allocated_qty"] = total_alloc_qty
			if row.get("on_hand_colour") == "WHITE":
				row["final_allocated_qty"] = max(0, flt(total_alloc_qty) - flt(row.get("excess_qty") or 0))
			else:
				row["final_allocated_qty"] = total_alloc_qty
		else:
			row["allocated_hours"] = 0
			row["total_allocated_qty"] = 0
			row["final_allocated_qty"] = 0

	# --- Redistribute lost hours from WHITE items to eligible items ---
	# Step 1: sum lost_hours per subgrp_shape from WHITE items (RBMTA + eligible RBMTO)
	subgrp_lost_hrs = defaultdict(float)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if (row.get("sku_type") == "RBMTA" or is_eligible_rbmto) and row.get("on_hand_colour") == "WHITE":
			per_hr = flt(row.get("per_hour_qty") or 0)
			lost_qty = flt(row.get("total_allocated_qty") or 0) - flt(row.get("final_allocated_qty") or 0)
			if per_hr > 0 and lost_qty > 0:
				subgrp_lost_hrs[row["subgrp_shape"]] += lost_qty / per_hr

	# Step 2: sum tog_pct of eligible items per subgrp_shape (non-WHITE, final_allocated_qty > 0)
	subgrp_eligible_tog_sum = defaultdict(float)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if (
			(row.get("sku_type") == "RBMTA" or is_eligible_rbmto)
			and row.get("on_hand_colour") != "WHITE"
			and flt(row.get("final_allocated_qty") or 0) > 0
		):
			subgrp_eligible_tog_sum[row["subgrp_shape"]] += flt(row.get("tog_pct") or 0)

	# Step 3: distribute to eligible items (RBMTA + eligible RBMTO)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if (
			(row.get("sku_type") == "RBMTA" or is_eligible_rbmto)
			and row.get("on_hand_colour") != "WHITE"
			and flt(row.get("final_allocated_qty") or 0) > 0
		):
			lost_hrs = subgrp_lost_hrs.get(row["subgrp_shape"], 0)
			if lost_hrs > 0:
				eligible_tog_sum = subgrp_eligible_tog_sum.get(row["subgrp_shape"], 0)
				per_hr = flt(row.get("per_hour_qty") or 0)
				if eligible_tog_sum > 0 and per_hr > 0:
					norm_pct = flt(row.get("tog_pct") or 0) / eligible_tog_sum
					additional_qty = round(lost_hrs * norm_pct * per_hr, 3)
					row["final_allocated_qty"] = flt(row.get("final_allocated_qty") or 0) + additional_qty

	# --- Calc Excess Qty: sum of excess_qty per subgrp_shape ---
	subgrp_excess_sum = defaultdict(float)
	for row in data:
		subgrp_excess_sum[row["subgrp_shape"]] += flt(row.get("excess_qty") or 0)
	for row in data:
		calc_excess = subgrp_excess_sum.get(row["subgrp_shape"], 0)
		row["calc_excess_qty"] = calc_excess or None
		# Net Calc Excess Qty
		if row.get("sku_type") == "RBMTA" and row.get("on_hand_colour") == "WHITE":
			row["net_calc_excess_qty"] = max(calc_excess - flt(row.get("excess_qty") or 0), 0) or None
		else:
			row["net_calc_excess_qty"] = calc_excess or None

	# --- Net Calc TOG%: (tog / sum of net_calc_excess_qty > 0 per subgrp_shape) * 100 ---
	subgrp_net_calc_excess_sum = defaultdict(float)
	for row in data:
		val = flt(row.get("net_calc_excess_qty") or 0)
		if val > 0:
			subgrp_net_calc_excess_sum[row["subgrp_shape"]] += val
	for row in data:
		denom = subgrp_net_calc_excess_sum.get(row["subgrp_shape"], 0)
		tog_val = flt(row.get("tog") or 0)
		row["net_calc_tog_pct"] = round((tog_val / denom) * 100, 2) if denom else None

	# --- New Excess Qty: sum_of_extra_qty_per_subgrp_shape * (net_calc_tog_pct / 100) ---
	subgrp_extra_qty_sum = defaultdict(float)
	for row in data:
		subgrp_extra_qty_sum[row["subgrp_shape"]] += flt(row.get("extra_qty") or 0)
	for row in data:
		net_calc_tog = flt(row.get("net_calc_tog_pct") or 0)
		total_extra_qty = subgrp_extra_qty_sum.get(row["subgrp_shape"], 0)
		new_excess = round(total_extra_qty * net_calc_tog / 100, 3) if net_calc_tog else None
		row["new_excess_qty"] = new_excess
		tog_val = flt(row.get("tog") or 0)
		row["new_excess_tog"] = round(flt(new_excess) / tog_val, 3) if tog_val and new_excess else None
		net_order = flt(row.get("net_order_recommendation") or 0)
		row["net_qty"] = round(flt(new_excess or 0) + net_order, 3) if (new_excess or net_order) else None

	# --- Top-3 parent items per RB item (any item that uses this RB item in their BOM) ---
	rb_item_codes_in_data = [r["item_code"] for r in data]
	rb_top3_parents_map = {}
	rb_parent_stock_map = {}
	if rb_item_codes_in_data:
		rb_tuple = (
			tuple(rb_item_codes_in_data) if len(rb_item_codes_in_data) > 1 else (rb_item_codes_in_data[0],)
		)
		rb_parent_rows = frappe.db.sql(
			"""
			SELECT bi.item_code AS child_item, b.item AS parent_item,
			       b.is_default, b.creation
			FROM `tabBOM Item` bi
			INNER JOIN `tabBOM` b ON b.name = bi.parent
			WHERE bi.item_code IN %s AND b.docstatus = 1
			ORDER BY bi.item_code, b.is_default DESC, b.creation ASC
			""",
			(rb_tuple,),
			as_dict=True,
		)
		for r in rb_parent_rows:
			lst = rb_top3_parents_map.setdefault(r.child_item, [])
			if len(lst) < 3:
				lst.append(r.parent_item)
		all_rb_parent_codes = {p for lst in rb_top3_parents_map.values() for p in lst}
		if all_rb_parent_codes:
			rp_tuple = (
				tuple(all_rb_parent_codes)
				if len(all_rb_parent_codes) > 1
				else (next(iter(all_rb_parent_codes)),)
			)
			rp_stock_rows = frappe.db.sql(
				"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
				(rp_tuple,),
				as_dict=True,
			)
			rb_parent_stock_map = {r.item_code: flt(r.stock) for r in rp_stock_rows}

	# --- Child BOM expansion with FIFO allocation ---

	# Fetch default BOMs for items with net_order_recommendation > 0
	bom_children_map = {}  # {item_code: [{item_code, bom_qty, bom_quantity}, ...]}
	items_with_rec = [r["item_code"] for r in data if r.get("net_order_recommendation", 0) > 0]
	if items_with_rec:
		bom_parent_tuple = tuple(items_with_rec) if len(items_with_rec) > 1 else (items_with_rec[0],)
		bom_rows = frappe.db.sql(
			"""
			SELECT b.item AS parent_item, bi.item_code AS child_item,
			       bi.qty AS bom_qty, b.quantity AS bom_quantity
			FROM `tabBOM Item` bi
			INNER JOIN `tabBOM` b ON b.name = bi.parent
			WHERE b.is_default = 1 AND b.docstatus = 1
			  AND b.item IN %s
			""",
			(bom_parent_tuple,),
			as_dict=True,
		)
		for r in bom_rows:
			bom_children_map.setdefault(r.parent_item, []).append(
				{
					"item_code": r.child_item,
					"bom_qty": flt(r.bom_qty),
					"bom_quantity": flt(r.bom_quantity) or 1.0,
				}
			)

	# Gather all unique child item codes
	all_child_codes = {c["item_code"] for children in bom_children_map.values() for c in children}

	child_stock_map_bom = {}
	child_item_sku_map = {}
	if all_child_codes:
		child_tuple = tuple(all_child_codes) if len(all_child_codes) > 1 else (next(iter(all_child_codes)),)

		# Child stock
		child_stock_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(child_tuple,),
			as_dict=True,
		)
		child_stock_map_bom = {r.item_code: math.ceil(flt(r.stock)) for r in child_stock_rows}

		# Child SKU types (to determine WIP eligibility)
		child_item_rows = frappe.db.sql(
			"SELECT name AS item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE name IN %s",
			(child_tuple,),
			as_dict=True,
		)
		for r in child_item_rows:
			child_item_sku_map[r.item_code] = calculate_sku_type(
				r.custom_buffer_flag or "Non-Buffer", r.custom_item_type
			)

	child_wip_map = get_wip_map()

	# Sort by colour priority descending (Black first = most urgent → allocated first)
	data.sort(key=lambda r: _COLOUR_RANK.get(r.get("colour", ""), 0), reverse=True)

	# FIFO pools
	remaining_child_stock_fifo = {ic: flt(child_stock_map_bom.get(ic, 0)) for ic in all_child_codes}
	remaining_child_wip_open_po_fifo = {}

	expanded_data = []
	for row in data:
		item_code = row["item_code"]
		children = bom_children_map.get(item_code, [])
		net_or = flt(row.get("net_order_recommendation", 0))

		if not children:
			top3 = rb_top3_parents_map.get(item_code, [])
			keys = [
				("first_parent_item", "first_parent_item_stock"),
				("second_parent_item", "second_parent_item_stock"),
				("third_parent_item", "third_parent_item_stock"),
			]
			for i, (pk, sk) in enumerate(keys):
				if i < len(top3):
					row[pk] = top3[i]
					row[sk] = rb_parent_stock_map.get(top3[i], 0)
				else:
					row[pk] = None
					row[sk] = None
			expanded_data.append(row)
			continue

		for child_info in children:
			child_ic = child_info["item_code"]
			bom_qty = child_info["bom_qty"]
			bom_quantity = child_info["bom_quantity"]

			child_requirement = math.ceil(net_or * (bom_qty / bom_quantity))
			child_stock_val = child_stock_map_bom.get(child_ic, 0)
			child_open_po = flt(open_po_map.get(child_ic, 0))

			child_sku = child_item_sku_map.get(child_ic, "")
			child_wip = 0 if child_sku in ("RBMTA", "RBMTO") else flt(child_wip_map.get(child_ic, 0))
			child_wip_open_po = math.ceil(child_wip + child_open_po)

			# FIFO: stock allocation
			available_stock = flt(remaining_child_stock_fifo.get(child_ic, 0))
			stock_allocated = min(child_requirement, available_stock)
			stock_shortage = child_requirement - stock_allocated
			remaining_child_stock_fifo[child_ic] = available_stock - stock_allocated

			# FIFO: WIP + Open PO allocation on remaining shortage
			if child_ic not in remaining_child_wip_open_po_fifo:
				remaining_child_wip_open_po_fifo[child_ic] = flt(child_wip_open_po)
			available_wip_open_po = remaining_child_wip_open_po_fifo[child_ic]
			wip_open_po_allocated = min(stock_shortage, available_wip_open_po)
			remaining_child_wip_open_po_fifo[child_ic] = available_wip_open_po - wip_open_po_allocated

			parent_per_child_factor = (bom_quantity / bom_qty) if bom_qty else 0
			total_allocated = stock_allocated + wip_open_po_allocated

			prod_qty_stock = min(math.ceil(flt(stock_allocated) * parent_per_child_factor), math.ceil(net_or))
			prod_qty_wip = min(math.ceil(flt(total_allocated) * parent_per_child_factor), math.ceil(net_or))

			new_row = row.copy()
			new_row["child_item_code"] = child_ic
			new_row["child_requirement"] = child_requirement
			new_row["child_stock"] = child_stock_val
			new_row["child_stock_allocation"] = math.ceil(stock_allocated)
			new_row["child_shortage"] = math.ceil(stock_shortage)
			new_row["child_item_open_po"] = math.ceil(child_open_po)
			new_row["prod_qty_based_on_child_stock"] = prod_qty_stock
			new_row["prod_qty_based_on_child_stock_wip_open_po"] = prod_qty_wip

			# Top-3 parent items for this RB item (any item that uses it in their BOM)
			top3 = rb_top3_parents_map.get(item_code, [])
			keys = [
				("first_parent_item", "first_parent_item_stock"),
				("second_parent_item", "second_parent_item_stock"),
				("third_parent_item", "third_parent_item_stock"),
			]
			for i, (pk, sk) in enumerate(keys):
				if i < len(top3):
					new_row[pk] = top3[i]
					new_row[sk] = rb_parent_stock_map.get(top3[i], 0)
				else:
					new_row[pk] = None
					new_row[sk] = None

			expanded_data.append(new_row)

	return expanded_data


# ---------------------------------------------------------------------------
# Whitelist API — Item Colour Breakdown
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_final_allocated_qty_breakdown(item_code):
	"""
	Returns step-by-step breakdown of how final_allocated_qty is computed for an RB item.
	Runs the full report and extracts the item's row + subgroup context.
	"""
	data = get_data()
	if not data:
		return None

	# Find the item's row
	item_row = next((r for r in data if r.get("item_code") == item_code), None)
	if not item_row:
		return {"error": f"Item {item_code} not found in report (no net order recommendation?)"}

	subgrp = item_row.get("subgrp_shape", "")
	sub_grp = item_row.get("sub_grp", "")

	# All rows in same subgrp_shape
	subgrp_rows = [r for r in data if r.get("subgrp_shape") == subgrp]

	# Eligible items (non-WHITE, final_allocated_qty > 0)
	eligible_rows = [
		r
		for r in subgrp_rows
		if r.get("on_hand_colour") != "WHITE" and flt(r.get("final_allocated_qty") or 0) > 0
	]

	return {
		"item_code": item_code,
		"item_name": item_row.get("item_name"),
		"sku_type": item_row.get("sku_type"),
		"subgrp_shape": subgrp,
		"sub_grp": sub_grp,
		# Step 1: Item base values
		"tog": item_row.get("tog"),
		"per_hour_qty": item_row.get("per_hour_qty"),
		"net_order_rec": item_row.get("net_order_recommendation"),
		"hrs_work": item_row.get("hrs_work"),
		"tog_pct": item_row.get("tog_pct"),
		# Step 2: Subgroup hours shortage
		"subgrp_hrs_setup": item_row.get("subgrp_hours_setup"),
		"subgrp_hours_shortage": item_row.get("subgrp_hours_shortage"),
		# Step 3: Extra hours & qty
		"extra_hours": item_row.get("extra_hours"),
		"extra_qty": item_row.get("extra_qty"),
		# Step 4: On hand colour & excess qty
		"on_hand_colour": item_row.get("on_hand_colour"),
		"on_hand_stock": item_row.get("on_hand_stock"),
		"excess_qty": item_row.get("excess_qty"),
		"excess_qty_tog": item_row.get("excess_qty_tog"),
		# Step 5: Allocated hours
		"subgrp_extra_hrs_sum": sum(flt(r.get("extra_hours") or 0) for r in subgrp_rows),
		"allocated_hours": item_row.get("allocated_hours"),
		"total_allocated_qty": item_row.get("total_allocated_qty"),
		# Step 6: Final allocated qty
		"final_allocated_qty": item_row.get("final_allocated_qty"),
		# Subgroup context for white deduction & redistribution
		"white_items": [
			{
				"item_code": r.get("item_code"),
				"total_allocated_qty": r.get("total_allocated_qty"),
				"excess_qty": r.get("excess_qty"),
				"final_allocated_qty": r.get("final_allocated_qty"),
				"per_hour_qty": r.get("per_hour_qty"),
				"lost_qty": flt(r.get("total_allocated_qty") or 0) - flt(r.get("final_allocated_qty") or 0),
			}
			for r in subgrp_rows
			if r.get("on_hand_colour") == "WHITE"
		],
		"eligible_tog_sum": sum(flt(r.get("tog_pct") or 0) for r in eligible_rows),
		"subgrp_lost_hrs": sum(
			(flt(r.get("total_allocated_qty") or 0) - flt(r.get("final_allocated_qty") or 0))
			/ flt(r.get("per_hour_qty") or 1)
			for r in subgrp_rows
			if r.get("on_hand_colour") == "WHITE"
			and flt(r.get("per_hour_qty") or 0) > 0
			and flt(r.get("total_allocated_qty") or 0) > flt(r.get("final_allocated_qty") or 0)
		),
		# All rows in subgrp for context table
		"subgrp_rows": [
			{
				"item_code": r.get("item_code"),
				"tog_pct": r.get("tog_pct"),
				"extra_hours": r.get("extra_hours"),
				"on_hand_colour": r.get("on_hand_colour"),
				"excess_qty": r.get("excess_qty"),
				"allocated_hours": r.get("allocated_hours"),
				"total_allocated_qty": r.get("total_allocated_qty"),
				"final_allocated_qty": r.get("final_allocated_qty"),
			}
			for r in subgrp_rows
		],
	}


@frappe.whitelist()
def get_item_colour_breakdown(item_code):
	"""
	Returns full colour computation detail for an RB item.
	RBMTA → buffer_colour breakdown.
	RBMTO → own SO FIFO detail + parent BOM FIFO detail.
	"""
	item_doc = frappe.db.get_value(
		"Item",
		item_code,
		[
			"name",
			"item_name",
			"custom_item_type",
			"custom_buffer_flag",
			"safety_stock",
			"min_order_qty",
			"custom_batch_size",
		],
		as_dict=True,
	)
	if not item_doc or item_doc.custom_item_type != "RB":
		frappe.throw(f"Item {item_code} is not an RB item.")

	buffer_flag = item_doc.custom_buffer_flag or "Non-Buffer"
	item_type = item_doc.custom_item_type
	is_buffer = buffer_flag == "Buffer"
	tog = flt(item_doc.safety_stock or 0)
	sku_type = calculate_sku_type(buffer_flag, item_type)

	stock_data = frappe.db.sql(
		"SELECT SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code = %s",
		(item_code,),
		as_dict=True,
	)
	stock = flt(stock_data[0].stock if stock_data else 0)
	mrq_map_all = get_mrq_map()
	mrq = flt(mrq_map_all.get(item_code, 0))
	level = stock

	item_buffer_map = {item_code: buffer_flag}
	item_type_map = {item_code: item_type}
	item_tog_map = {item_code: tog}

	till_today_map, spike_map_base = get_qualified_demand_map()
	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}
	calculated_spike = calculate_spike_map({item_code}, item_buffer_map, item_type_map, item_tog_map)
	spike_map_base.update(calculated_spike)

	qualified_demand, till_today, spike = get_qualified_demand_for_item(
		item_code,
		till_today_map,
		spike_map_base,
		item_buffer_map,
		item_tog_map,
		item_type_map,
		spike_master_map,
	)
	qualified_demand = flt(qualified_demand)

	result = {
		"item_code": item_code,
		"item_name": item_doc.item_name,
		"sku_type": sku_type,
		"buffer_flag": buffer_flag,
		"stock": stock,
		"mrq": mrq,
		"level": level,
		"tog": tog,
	}

	if is_buffer:
		colour = _buffer_colour(level, tog, qualified_demand)
		total = tog + qualified_demand
		result.update(
			{
				"detail_type": "buffer",
				"qualified_demand": qualified_demand,
				"till_today": flt(till_today),
				"spike": flt(spike),
				"total": total,
				"colour": colour,
			}
		)
	else:
		# Fetch own SOs with delivery_date for display
		own_so_rows = frappe.db.sql(
			"""
			SELECT soi.delivery_date, so.transaction_date,
			       GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
			FROM `tabSales Order Item` soi
			INNER JOIN `tabSales Order` so ON so.name = soi.parent
			WHERE so.docstatus = 1
			  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			  AND IFNULL(soi.custom_closed, 0) = 0
			  AND soi.item_code = %s
			  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
			ORDER BY soi.delivery_date ASC
			""",
			(item_code,),
			as_dict=True,
		)

		available = level
		own_so_fifo = []
		for r in own_so_rows:
			required = flt(r.pending_qty)
			allocated = min(required, available)
			so_shortage = required - allocated
			available -= allocated
			status = _compute_order_status(r.delivery_date, r.transaction_date)
			colour_so = status.capitalize() if status else ""
			own_so_fifo.append(
				{
					"delivery_date": str(r.delivery_date) if r.delivery_date else "",
					"pending_qty": required,
					"allocated": allocated,
					"shortage": so_shortage,
					"available_after": available,
					"order_status": colour_so,
				}
			)

		# Parent BOM FIFO — production batch iteration (same logic as bright_plan)
		parent_bom_list = get_parent_bom_map({item_code}).get(item_code, [])
		parent_fifo = []

		if parent_bom_list:
			all_parent_codes = {p["parent_item"] for p in parent_bom_list}
			parent_tuple = (
				tuple(all_parent_codes) if len(all_parent_codes) > 1 else (next(iter(all_parent_codes)),)
			)

			parent_rows = frappe.db.sql(
				"""SELECT name AS item_code, custom_buffer_flag AS buffer_flag,
				          custom_item_type AS item_type, safety_stock AS tog,
				          min_order_qty AS moq, custom_batch_size AS batch_size
				   FROM `tabItem` WHERE name IN %s""",
				(parent_tuple,),
				as_dict=True,
			)
			p_master_map = {r.item_code: r for r in parent_rows}
			p_buffer_map = {r.item_code: r.buffer_flag or "Non-Buffer" for r in parent_rows}
			p_type_map = {r.item_code: r.item_type or "" for r in parent_rows}
			p_tog_map = {r.item_code: flt(r.tog or 0) for r in parent_rows}

			bb_spike = calculate_spike_map(all_parent_codes, p_buffer_map, p_type_map, p_tog_map)
			parent_spike_map = dict(spike_map_base)
			parent_spike_map.update(bb_spike)

			p_stock_rows = frappe.db.sql(
				"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
				(parent_tuple,),
				as_dict=True,
			)
			p_stock_map = {r.item_code: flt(r.stock) for r in p_stock_rows}
			p_wip_map = get_wip_map()

			# Open SO for BBMTO parents (all open SOs, no date filter — same as bright_plan)
			p_open_so_qty_map = get_sales_order_qty_map({})
			p_so_for_priority_map = get_open_so_map_for_priority(list(all_parent_codes))

			priority_seq_rows = frappe.db.sql(
				"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
				as_dict=True,
			)
			priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

			p_data = {}
			for ic in all_parent_codes:
				master = p_master_map.get(ic)
				if not master:
					continue
				is_buf = p_buffer_map[ic] == "Buffer"
				tog_p = p_tog_map[ic]
				stock_p = flt(p_stock_map.get(ic, 0))
				wip_p = flt(p_wip_map.get(ic, 0))
				mrq_p = flt(mrq_map_all.get(ic, 0))
				moq_p = flt(master.moq or 0)
				bs_p = flt(master.batch_size or 0)

				qd_p, _, _ = get_qualified_demand_for_item(
					ic,
					till_today_map,
					parent_spike_map,
					p_buffer_map,
					p_tog_map,
					p_type_map,
					spike_master_map,
				)
				qd_p = flt(qd_p)
				open_so_p = flt(p_open_so_qty_map.get(ic, 0)) if not is_buf else 0.0

				if is_buf:
					base_rec = max(0, tog_p + qd_p - stock_p - wip_p - mrq_p)
				else:
					base_rec = max(0, open_so_p - stock_p - wip_p - mrq_p)
				net_rec = calculate_net_order_recommendation(base_rec, moq_p, bs_p)

				p_data[ic] = {
					"stock": stock_p,
					"wip": wip_p,
					"tog": tog_p,
					"qd": qd_p,
					"open_so": open_so_p,
					"is_buffer": is_buf,
					"net_order_rec": net_rec,
					"batch_size": bs_p,
					"moq": moq_p,
				}

			# Build flat batch list (same logic as bright_plan) and run FIFO
			flat = []
			for p in parent_bom_list:
				parent_item = p["parent_item"]
				pd = p_data.get(parent_item)
				if not pd:
					continue
				bom_ratio = p["bom_qty"] / (p["bom_quantity"] or 1.0)
				batches = _build_parent_batches(
					pd["stock"],
					pd["wip"],
					pd["tog"],
					pd["qd"],
					pd["is_buffer"],
					pd["net_order_rec"],
					pd["batch_size"],
					pd["moq"],
					priority_seq_map,
					item_code=parent_item,
					open_so=pd.get("open_so", 0),
					so_map_for_priority=p_so_for_priority_map,
				)
				for batch in batches:
					child_req = math.ceil(batch["batch_qty"] * bom_ratio)
					flat.append(
						{
							"parent_item": parent_item,
							"batch_qty": batch["batch_qty"],
							"level_before": batch["level_before"],
							"priority_colour": batch["priority_colour"],
							"priority_sequence": batch["priority_sequence"],
							"op_cp": batch["op_cp"],
							"colour": batch["colour"],
							"child_req": child_req,
							"tog": pd["tog"],
						}
					)
			flat.sort(key=lambda x: (x["priority_sequence"], -flt(x["tog"])))

			for entry in flat:
				batch_qty = entry["batch_qty"]
				allocated = min(batch_qty, available)
				shortage = batch_qty - allocated
				available -= allocated
				parent_fifo.append(
					{
						"parent_item": entry["parent_item"],
						"priority_sequence": entry["priority_sequence"],
						"priority_colour": entry["priority_colour"],
						"op_cp": entry["op_cp"],
						"level_before": math.ceil(entry["level_before"]),
						"batch_qty": math.ceil(entry["batch_qty"]),
						"child_req": math.ceil(entry["child_req"]),
						"allocated": math.ceil(allocated),
						"shortage": math.ceil(shortage),
						"available_after": math.ceil(available),
						"order_status": entry["colour"],
					}
				)

		# Determine final colour: first shortage in own SOs, then first shortage in parent SOs
		final_colour = ""
		for entry in own_so_fifo:
			if entry["shortage"] > 0:
				final_colour = entry["order_status"]
				break
		if not final_colour:
			for entry in parent_fifo:
				if entry["shortage"] > 0:
					final_colour = entry["order_status"]
					break

		result.update(
			{
				"detail_type": "non_buffer",
				"colour": final_colour,
				"own_so_fifo": own_so_fifo,
				"parent_fifo": parent_fifo,
			}
		)

	return result
