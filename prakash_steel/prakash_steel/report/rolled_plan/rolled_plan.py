import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, nowdate

from prakash_steel.utils.whitelist_permissions import require_permission

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal import (
	compute_universe_net_order_recommendations,
	propagate_priority_through_bom_tree,
)
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_non_buffer_priority,
	buffer_order_recommendation_colour,
	_round_up_2dp,
	apply_spike_threshold,
	calculate_net_order_recommendation,
	calculate_sku_type,
	calculate_spike_map,
	get_draft_wo_map,
	get_mrq_map,
	get_open_po_map,
	get_open_subcon_po_map,
	get_open_so_map_for_priority,
	get_planning_stock_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_wip_map,
)


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def _buffer_colour(level, tog, qualified_demand) -> str:
	total = flt(tog) + flt(qualified_demand)
	if level == 0:
		return "BLACK"
	if total <= 0:
		return ""
	# Same round-UP-to-2dp coverage % as PO Recommendation for PSP's On Hand
	# Colour (_round_up_2dp) so Priority and On Hand Colour band an identical
	# percentage identically — no RED-vs-BLACK split on the same number.
	pct = _round_up_2dp((flt(level) / total) * 100)

	if pct == 0:
		return "BLACK"
	if pct <= 34:
		return "RED"
	if pct <= 67:
		return "YELLOW"
	if pct <= 100:
		return "GREEN"
	return "WHITE"


_COLOUR_RANK = {"Black": 5, "Red": 4, "Yellow": 3, "Green": 2, "White": 1}


def _pipeline_priority(row, wip, open_po, total_demand) -> str:
	"""Display-only priority with the req-plan rule (see req_plan_priority_colour).

	RBMTA: own pipeline (stock + WIP incl. draft WOs, as Bright Plan's level does,
	+ open PO + open subcon PO) against
	ceil(TOG) + total demand, in Bright Plan thirds. RBMTO: the row's existing
	Priority (FIFO open-SO allocation worsened by BOM ancestors). The "colour"
	column and the row ordering are left on their stock-only rule.
	"""
	if row.get("sku_type") != "RBMTA":
		return (row.get("colour") or "").upper()
	level = flt(row.get("on_hand_stock")) + flt(wip) + flt(open_po)
	total = math.ceil(flt(row.get("tog"))) + flt(total_demand)
	return buffer_order_recommendation_colour(level, total).upper()


def _compute_order_status(delivery_date, transaction_date) -> str | None:
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


def get_rbmto_so_detail_map(item_codes) -> dict:
	if not item_codes:
		return {}
	t = tuple(item_codes)
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


def get_parent_bom_map(item_codes) -> dict:
	if not item_codes:
		return {}
	t = tuple(item_codes)
	rows = frappe.db.sql(
		"""
		SELECT b.item AS parent_item, bi.item_code AS child_item,
		       bi.qty AS bom_qty, b.quantity AS bom_quantity, b.is_default AS is_default
		FROM `tabBOM Item` bi
		INNER JOIN `tabBOM` b ON b.name = bi.parent
		WHERE b.docstatus = 1 AND b.is_active = 1
		  AND bi.item_code IN %s
		""",
		(t,),
		as_dict=True,
	)
	best_by_pair: dict[tuple[str, str], dict] = {}
	for r in rows:
		key = (r.child_item, r.parent_item)
		existing = best_by_pair.get(key)
		if existing is None or (r.is_default and not existing["_is_default"]):
			best_by_pair[key] = {
				"parent_item": r.parent_item,
				"bom_qty": flt(r.bom_qty),
				"bom_quantity": flt(r.bom_quantity) or 1.0,
				"_is_default": bool(r.is_default),
			}
	result = defaultdict(list)
	for (child_item, _parent_item), entry in best_by_pair.items():
		entry = dict(entry)
		entry.pop("_is_default")
		result[child_item].append(entry)
	return result


def _build_parent_batches(
	stock,
	wip,
	tog,
	qd,
	is_buffer,
	net_order_rec,
	batch_size,
	moq,
	priority_seq_map,
	item_code=None,
	open_so=0.0,
	so_map_for_priority=None,
) -> list:
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


def _worst_fifo_colour(level, entries, qty_key, colour_key="colour") -> str:
	if not entries:
		return ""
	available = flt(level)
	worst_shortage_rank, worst_shortage_colour = 0, ""
	worst_no_shortage_rank, worst_no_shortage_colour = 0, ""
	for entry in entries:
		required = flt(entry[qty_key])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		colour = entry.get(colour_key) or ""
		rank = _COLOUR_RANK.get(colour.capitalize(), 0) if colour else 0
		if shortage > 0:
			if rank > worst_shortage_rank:
				worst_shortage_rank, worst_shortage_colour = rank, colour
		else:
			if rank > worst_no_shortage_rank:
				worst_no_shortage_rank, worst_no_shortage_colour = rank, colour
	if worst_shortage_rank > 0:
		return worst_shortage_colour
	if worst_no_shortage_rank > 0:
		return worst_no_shortage_colour
	return ""


def _rbmto_colour(level, own_so_list, parent_so_fifo_list) -> str:
	if own_so_list:
		return _worst_fifo_colour(level, own_so_list, "pending_qty")
	return _worst_fifo_colour(level, parent_so_fifo_list, "batch_qty")


def get_columns() -> list[dict]:
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
		# {
		# 	"label": _("P Priority"),
		# 	"fieldname": "colour",
		# 	"fieldtype": "Data",
		# 	"width": 100,
		# },
		{
			"label": _("Priority"),
			"fieldname": "pipeline_priority",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("On Hand Colour"),
			"fieldname": "on_hand_colour",
			"fieldtype": "Data",
			"width": 130,
			"hidden":1,
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
			"fieldname": "tog_subgroup_pct_all",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"label": _("Subgrp+Shape"),
			"fieldname": "subgrp_shape",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Shape"),
			"fieldname": "shape",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Grp"),
			"fieldname": "grp",
			"fieldtype": "Data",
			"width": 100,
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
			"label": _("Sub Grp"),
			"fieldname": "sub_grp",
			"fieldtype": "Data",
			"width": 120,
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
			"label": _("Subgroup TOG %"),
			"fieldname": "tog_subgroup_pct",
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
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
			"hidden":1,
		},
		{
			"label": _("TOG%"),
			"fieldname": "tog_pct",
			"fieldtype": "Float",
			"width": 90,
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
			"hidden":1,
		},
		{
			"label": _("Net Qty"),
			"fieldname": "net_qty",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Subgroup Weightage Value"),
			"fieldname": "subgroup_weightage_value",
			"fieldtype": "Float",
			"width": 190,
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
		{
			"label": _("PBCNB121FLAG"),
			"fieldname": "pbcnb121flag",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Actual / Planned Qty%"),
			"fieldname": "actual_planned_qty_pct",
			"fieldtype": "Float",
			"precision": 2,
			"width": 170,
		},
	]


def get_data(filters=None) -> list[dict]:
	if not filters:
		filters = {}

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
	item_codes_tuple = tuple(item_codes)

	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	item_info_map = {}
	for item in rb_items:
		item_buffer_map[item.item_code] = item.buffer_flag or "Non-Buffer"
		item_type_map[item.item_code] = item.item_type
		item_tog_map[item.item_code] = flt(item.tog or 0)
		item_info_map[item.item_code] = item

	rolling_algo_rows = frappe.db.get_all(
		"Rolling Algo",
		fields=["item_code", "per_hour_planned_qty"],
	)
	per_hour_qty_map = {r.item_code: flt(r.per_hour_planned_qty) for r in rolling_algo_rows}

	rolling_subgroup_setup_rows = frappe.db.get_all(
		"Rolling Subgroup Setup",
		fields=["subgroup_name", "shape", "planned_hrs"],
	)
	subgroup_setup_hrs_map = {
		((r.subgroup_name or "").strip(), (r.shape or "").strip()): flt(r.planned_hrs)
		for r in rolling_subgroup_setup_rows
	}

	stock_map = get_planning_stock_map(item_codes)
	mrq_map = get_mrq_map()

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
	open_subcon_po_map = get_open_subcon_po_map()

	last_3month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(bbp.raw_material, ''), bbp.material) AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND (bbp.raw_material IN %s OR bbp.material IN %s)
		GROUP BY COALESCE(NULLIF(bbp.raw_material, ''), bbp.material)
		""",
		(item_codes_tuple, item_codes_tuple),
		as_dict=True,
	)
	last_3month_consumption_map = {
		r.item_code: flt(r.consumption_qty) for r in last_3month_consumption_rows if r.item_code
	}

	last_1month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(bbp.raw_material, ''), bbp.material) AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND (bbp.raw_material IN %s OR bbp.material IN %s)
		GROUP BY COALESCE(NULLIF(bbp.raw_material, ''), bbp.material)
		""",
		(item_codes_tuple, item_codes_tuple),
		as_dict=True,
	)
	last_1month_consumption_map = {
		r.item_code: flt(r.consumption_qty) for r in last_1month_consumption_rows if r.item_code
	}

	wo_last_rolled_rows = frappe.db.sql(
		"""
		SELECT wo.production_item AS item_code, wo.actual_start_date, wo.produced_qty
		FROM `tabWork Order` wo
		INNER JOIN (
			SELECT production_item, MAX(actual_start_date) AS max_date
			FROM `tabWork Order`
			WHERE docstatus = 1 AND production_item IN %s AND actual_start_date IS NOT NULL
			GROUP BY production_item
		) latest ON wo.production_item = latest.production_item AND wo.actual_start_date = latest.max_date
		WHERE wo.docstatus = 1
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	wo_last_rolled_map = {}
	for r in wo_last_rolled_rows:
		existing = wo_last_rolled_map.get(r.item_code)
		if not existing or r.actual_start_date > existing["_dt"]:
			wo_last_rolled_map[r.item_code] = {
				"last_rolled_date": r.actual_start_date.date(),
				"last_rolled_qty": flt(r.produced_qty),
				"_dt": r.actual_start_date,
			}

	rb_parent_bom_map = get_parent_bom_map(item_codes)
	rb_parent_item_codes = {p["parent_item"] for plist in rb_parent_bom_map.values() for p in plist}

	wo_3month_consumption_map = defaultdict(float)
	wo_1month_consumption_map = defaultdict(float)
	if rb_parent_item_codes:
		wo_consumption_rows = frappe.db.sql(
			"""
			SELECT wo.production_item AS parent_item, woi.item_code AS child_item,
			       wo.actual_start_date AS actual_start_date, woi.consumed_qty AS consumed_qty
			FROM `tabWork Order` wo
			INNER JOIN `tabWork Order Item` woi ON woi.parent = wo.name
			WHERE wo.docstatus = 1
			  AND wo.production_item IN %s
			  AND woi.item_code IN %s
			  AND wo.actual_start_date IS NOT NULL
			  AND DATE(wo.actual_start_date) >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			""",
			(tuple(rb_parent_item_codes), item_codes_tuple),
			as_dict=True,
		)
		today_date = nowdate()
		for r in wo_consumption_rows:
			qty = flt(r.consumed_qty)
			if not qty:
				continue
			wo_3month_consumption_map[r.child_item] += qty
			if date_diff(today_date, r.actual_start_date.date()) <= 29:
				wo_1month_consumption_map[r.child_item] += qty

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
		)
		qualified_demand = flt(qualified_demand)
		if item_buffer_map.get(item_code) == "Buffer":
			qualified_demand = apply_spike_threshold(
				qualified_demand,
				item_tog_map.get(item_code, 0),
				item_type_map.get(item_code),
				spike_master_map,
			)
		qualified_demand_map[item_code] = qualified_demand

	psp_net_order_map, psp_total_demand_map = compute_universe_net_order_recommendations()

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
			parent_tuple = tuple(all_parent_codes)

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

			bb_spike_map = calculate_spike_map(all_parent_codes, p_buffer_map, p_type_map, p_tog_map)
			parent_spike_map = dict(spike_map_base)
			parent_spike_map.update(bb_spike_map)

			parent_stock_map = get_planning_stock_map(all_parent_codes)
			parent_wip_map = get_wip_map()

			parent_open_so_qty_map = get_sales_order_qty_map({})
			parent_so_for_priority_map = get_open_so_map_for_priority(list(all_parent_codes))

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
				open_po_p = flt(open_po_map.get(ic, 0))
				open_subcon_po_p = flt(open_subcon_po_map.get(ic, 0))
				mrq_p = flt(mrq_map.get(ic, 0))
				moq_p = flt(master.moq or 0)
				bs_p = flt(master.batch_size or 0)

				qd_p, _, _ = get_qualified_demand_for_item(
					ic,
					till_today_map,
					parent_spike_map,
					p_buffer_map,
				)
				qd_p = flt(qd_p)
				if is_buf:
					qd_p = apply_spike_threshold(qd_p, tog_p, p_type_map.get(ic), spike_master_map)
				open_so_p = flt(parent_open_so_qty_map.get(ic, 0)) if not is_buf else 0.0

				# All SKU types net off Open PO, Open Subcon PO and WIP the same way.
				if is_buf:
					base_rec = max(0, tog_p + qd_p - stock_p - wip_p - open_po_p - open_subcon_po_p - mrq_p)
				else:
					base_rec = max(0, open_so_p - stock_p - wip_p - open_po_p - open_subcon_po_p - mrq_p)
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

		for child_ic in rbmto_codes:
			if flt(psp_net_order_map.get(child_ic, 0)) <= 0:
				continue
			parents = parent_bom_map.get(child_ic, [])
			if len(parents) == 1:
				parent_ic = parents[0]["parent_item"]
				if p_buffer_map.get(parent_ic) == "Buffer":
					rbmto_eligible_parent_map[child_ic] = parent_ic

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

		if sku_type not in ("RBMTA", "RBMTO"):
			continue

		is_buffer = buffer_flag == "Buffer"
		tog = item_tog_map[item_code]
		stock = flt(stock_map.get(item_code, 0))

		net_order_rec = flt(psp_net_order_map.get(item_code, 0))

		level = stock
		if is_buffer:
			# math.ceil(tog) — the same TOG value shown in the TOG column and used
			# as the On Hand Colour denominator, so both colours divide by the
			# identical number.
			colour = _buffer_colour(level, math.ceil(flt(tog)), flt(psp_total_demand_map.get(item_code, 0)))
		else:
			colour = _rbmto_colour(
				level,
				rbmto_so_detail_map.get(item_code, []),
				child_parent_so_fifo.get(item_code, []),
			)

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
				"buffer_flag": buffer_flag,
				"priority": None,
				"net_order_recommendation": math.ceil(flt(net_order_rec)),
				"sku_type": sku_type,
				"item_type": item_type_map[item_code],
				"tog": math.ceil(flt(effective_tog)),
				"tog_subgroup_pct": None,
				"tog_subgroup_pct_all": None,
				"last_rolled_date": (
					wo_last_rolled_map.get(item_code, {}).get("last_rolled_date")
					or last_rolled_map.get(item_code, {}).get("last_rolled_date")
				),
				"last_rolled_qty": (
					wo_last_rolled_map.get(item_code, {}).get("last_rolled_qty")
					if item_code in wo_last_rolled_map
					else last_rolled_map.get(item_code, {}).get("last_rolled_qty")
				),
				"last_3_months_sale": last_3month_sale_map.get(item_code, 0),
				"last_3_months_consumption": (
					last_3month_consumption_map.get(item_code, 0) + wo_3month_consumption_map.get(item_code, 0)
				),
				"last_1_month_sale": last_1month_sale_map.get(item_code, 0),
				"last_1_month_consumption": (
					last_1month_consumption_map.get(item_code, 0) + wo_1month_consumption_map.get(item_code, 0)
				),
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
				"hrs_work": round(flt(net_order_rec) / effective_per_hour_qty, 2) if effective_per_hour_qty else None,
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
				"pbcnb121flag": 1 if item_code in rbmto_eligible_parent_map else 0,
				"actual_planned_qty_pct": None,
			}
		)

	wip_map_rb = get_wip_map()
	draft_wo_map_rb = get_draft_wo_map()

	own_so_map_for_priority = get_open_so_map_for_priority(list(item_codes))
	for row in data:
		ic = row["item_code"]
		level = flt(row.get("on_hand_stock") or 0) + flt(wip_map_rb.get(ic, 0))
		row["priority"] = _non_buffer_priority(ic, level, own_so_map_for_priority)
	propagate_priority_through_bom_tree(data, wip_map_rb, open_po_map)

	subgrp_tog_sum_all = defaultdict(float)
	for row in data:
		subgrp_tog_sum_all[row["subgrp_shape"]] += flt(row["tog"])
	for row in data:
		group_sum_all = subgrp_tog_sum_all.get(row["subgrp_shape"], 0)
		row["tog_subgroup_pct_all"] = (
			round((flt(row["tog"]) / group_sum_all) * 100, 2) if group_sum_all else None
		)

	subgrp_tog_sum = defaultdict(float)
	for row in data:
		if flt(row.get("net_order_recommendation") or 0) > 0:
			subgrp_tog_sum[row["subgrp_shape"]] += flt(row["tog"])
	for row in data:
		if flt(row.get("net_order_recommendation") or 0) > 0:
			group_sum = subgrp_tog_sum.get(row["subgrp_shape"], 0)
			tog_pct_val = round((flt(row["tog"]) / group_sum) * 100, 2) if group_sum else None
		else:
			tog_pct_val = None
		row["tog_subgroup_pct"] = tog_pct_val
		row["tog_pct"] = row["tog_subgroup_pct_all"]

	subgrp_wv_sum = defaultdict(float)
	grp_wv_sum = defaultdict(float)
	subgrp_qty_sum = defaultdict(float)
	subgrp_count_map = defaultdict(int)
	grp_count_map = defaultdict(int)
	subgrp_hrs_sum = defaultdict(float)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		subgrp_wv_sum[row["subgrp_shape"]] += flt(row["weightage_value"])
		grp_wv_sum[row["grp_shape"]] += flt(row["weightage_value"])
		subgrp_qty_sum[row["subgrp_shape"]] += flt(row.get("net_order_recommendation", 0))
		subgrp_count_map[row["subgrp_shape"]] += 1
		grp_count_map[row["grp_shape"]] += 1
		subgrp_hrs_sum[row["subgrp_shape"]] += flt(row.get("hrs_work") or 0)
	for row in data:
		row["subgroup_weightage_value"] = subgrp_wv_sum.get(row["subgrp_shape"], 0) or None
		row["grp_weightage_value"] = grp_wv_sum.get(row["grp_shape"], 0) or None
		row["subgroup_qty"] = subgrp_qty_sum.get(row["subgrp_shape"], 0) or None
		row["subgrp_count"] = subgrp_count_map.get(row["subgrp_shape"], 0)
		row["group_count"] = grp_count_map.get(row["grp_shape"], 0)
		final_hrs = subgroup_setup_hrs_map.get(((row["sub_grp"] or "").strip(), (row["shape"] or "").strip()), 0)
		setup_hrs = round(subgrp_hrs_sum.get(row["subgrp_shape"], 0), 2)
		shortage = round(max(0, final_hrs - setup_hrs), 2)
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		row["subgrp_hours_setup"] = setup_hrs
		row["subgrp_hours_shortage"] = shortage

		if row.get("sku_type") == "RBMTA" or is_eligible_rbmto:
			tog_pct = flt(row.get("tog_subgroup_pct") or 0)
			extra_hrs = round((tog_pct * shortage) / 100, 2)
			row["extra_hours"] = extra_hrs
			per_hr = flt(row.get("per_hour_qty") or 0)
			row["extra_qty"] = round(extra_hrs * per_hr, 3) if per_hr else None
		else:
			row["extra_hours"] = 0
			row["extra_qty"] = 0

		on_hand_stock = flt(row.get("on_hand_stock") or 0)
		wip_val = flt(wip_map_rb.get(ic, 0))
		tog_val = flt(row.get("tog") or 0)
		qd_val = flt(qualified_demand_map.get(ic) or 0)
		on_hand_colour = None

		if row.get("sku_type") == "RBMTA":
			total_demand = flt(psp_total_demand_map.get(ic, 0))
			denominator = tog_val + total_demand
			if denominator > 0:
				pct = _round_up_2dp((on_hand_stock / denominator) * 100)
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
			parent_ic = rbmto_eligible_parent_map[ic]
			pd = parent_data_map.get(parent_ic, {})
			p_stock = flt(pd.get("stock") or 0)
			p_wip = flt(pd.get("wip") or 0)
			p_tog = flt(pd.get("tog") or 0)
			p_qd = flt(pd.get("qd") or 0)
			denominator = p_tog + p_qd
			if denominator > 0:
				pct = _round_up_2dp((p_stock / denominator) * 100)
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
			wip_val = p_wip
			tog_val = p_tog
			qd_val = p_qd
			on_hand_stock = p_stock
		elif row.get("sku_type") == "RBMTO":
			on_hand_colour = row.get("priority") or ""

		row["on_hand_colour"] = on_hand_colour
		if row.get("sku_type") == "RBMTO":
			row["colour"] = row.get("priority") or ""
		row["pipeline_priority"] = _pipeline_priority(
			row,
			flt(wip_map_rb.get(ic, 0)) + flt(draft_wo_map_rb.get(ic, 0)),
			flt(open_po_map.get(ic, 0)) + flt(open_subcon_po_map.get(ic, 0)),
			flt(psp_total_demand_map.get(ic, 0)),
		)
		if on_hand_colour == "WHITE":
			row["extra_hours"] = None
			row["extra_qty"] = None
			row["excess_qty"] = on_hand_stock + wip_val - tog_val - qd_val
		else:
			row["excess_qty"] = flt(row.get("extra_qty") or 0)
		excess = flt(row["excess_qty"])
		row["excess_qty_tog"] = round((excess / tog_val) * 100, 3) if tog_val else None

		if row.get("sku_type") == "RBMTO":
			for fieldname in ("extra_hours", "extra_qty", "excess_qty", "tog_pct"):
				if flt(row.get(fieldname) or 0) == 0:
					row[fieldname] = None

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

	subgrp_lost_hrs = defaultdict(float)
	for row in data:
		ic = row["item_code"]
		is_eligible_rbmto = row.get("sku_type") == "RBMTO" and ic in rbmto_eligible_parent_map
		if (row.get("sku_type") == "RBMTA" or is_eligible_rbmto) and row.get("on_hand_colour") == "WHITE":
			per_hr = flt(row.get("per_hour_qty") or 0)
			lost_qty = flt(row.get("total_allocated_qty") or 0) - flt(row.get("final_allocated_qty") or 0)
			if per_hr > 0 and lost_qty > 0:
				subgrp_lost_hrs[row["subgrp_shape"]] += lost_qty / per_hr

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

	subgrp_extra_qty_sum = defaultdict(float)
	for row in data:
		subgrp_extra_qty_sum[row["subgrp_shape"]] += flt(row.get("extra_qty") or 0)

	for row in data:
		total_extra_qty = subgrp_extra_qty_sum.get(row["subgrp_shape"], 0)
		tog_pct_own = flt(row.get("tog_pct") or 0)
		calc_excess = round(total_extra_qty * tog_pct_own / 100, 3) if tog_pct_own else 0
		row["calc_excess_qty"] = calc_excess or None
		if row.get("sku_type") == "RBMTA" and row.get("on_hand_colour") == "WHITE":
			row["net_calc_excess_qty"] = max(calc_excess - flt(row.get("excess_qty") or 0), 0) or None
		else:
			row["net_calc_excess_qty"] = calc_excess or None

	subgrp_net_calc_tog_sum = defaultdict(float)
	for row in data:
		if flt(row.get("net_calc_excess_qty") or 0) > 0:
			subgrp_net_calc_tog_sum[row["subgrp_shape"]] += flt(row.get("tog") or 0)
	for row in data:
		if flt(row.get("net_calc_excess_qty") or 0) > 0:
			denom = subgrp_net_calc_tog_sum.get(row["subgrp_shape"], 0)
			tog_val = flt(row.get("tog") or 0)
			row["net_calc_tog_pct"] = round((tog_val / denom) * 100, 2) if denom else None
		else:
			row["net_calc_tog_pct"] = None

	for row in data:
		net_calc_tog = flt(row.get("net_calc_tog_pct") or 0)
		total_extra_qty = subgrp_extra_qty_sum.get(row["subgrp_shape"], 0)
		new_excess = round(total_extra_qty * net_calc_tog / 100, 3) if net_calc_tog else None
		row["new_excess_qty"] = new_excess
		tog_val = flt(row.get("tog") or 0)
		row["new_excess_tog"] = round(flt(new_excess) / tog_val, 3) if tog_val and new_excess else None
		net_order = flt(row.get("net_order_recommendation") or 0)
		row["net_qty"] = math.ceil(flt(new_excess or 0) + net_order) if (new_excess or net_order) else None

	subgrp_net_order_sum = defaultdict(float)
	subgrp_net_qty_sum = defaultdict(float)
	for row in data:
		subgrp_net_order_sum[row["subgrp_shape"]] += flt(row.get("net_order_recommendation") or 0)
		subgrp_net_qty_sum[row["subgrp_shape"]] += flt(row.get("net_qty") or 0)
	for row in data:
		subgrp_net_order_total = subgrp_net_order_sum.get(row["subgrp_shape"], 0)
		subgrp_net_qty_total = subgrp_net_qty_sum.get(row["subgrp_shape"], 0)
		row["actual_planned_qty_pct"] = (
			round((subgrp_net_order_total / subgrp_net_qty_total) * 100, 2) if subgrp_net_qty_total else None
		)

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
			WHERE bi.item_code IN %s AND b.docstatus = 1 AND b.is_active = 1
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
			rb_parent_stock_map = get_planning_stock_map(all_rb_parent_codes)

	bom_children_map = {}
	items_with_rec = [r["item_code"] for r in data if r.get("net_order_recommendation", 0) > 0]
	if items_with_rec:
		bom_parent_tuple = tuple(items_with_rec) if len(items_with_rec) > 1 else (items_with_rec[0],)
		bom_rows = frappe.db.sql(
			"""
			SELECT b.item AS parent_item, bi.item_code AS child_item,
			       bi.qty AS bom_qty, b.quantity AS bom_quantity
			FROM `tabBOM Item` bi
			INNER JOIN `tabBOM` b ON b.name = bi.parent
			WHERE b.is_default = 1 AND b.docstatus = 1 AND b.is_active = 1
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

	all_child_codes = {c["item_code"] for children in bom_children_map.values() for c in children}

	child_stock_map_bom = {}
	if all_child_codes:
		child_stock_map_bom = {
			ic: math.ceil(v) for ic, v in get_planning_stock_map(all_child_codes).items()
		}

	child_wip_map = get_wip_map()

	data.sort(key=lambda r: _COLOUR_RANK.get((r.get("colour") or "").capitalize(), 0), reverse=True)

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

			child_wip = flt(child_wip_map.get(child_ic, 0))
			child_wip_open_po = math.ceil(child_wip + child_open_po)

			available_stock = flt(remaining_child_stock_fifo.get(child_ic, 0))
			stock_allocated = min(child_requirement, available_stock)
			stock_shortage = child_requirement - stock_allocated
			remaining_child_stock_fifo[child_ic] = available_stock - stock_allocated

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


@frappe.whitelist()
def get_item_colour_breakdown(item_code) -> dict | list:
	require_permission("Item", "report")

	data = get_data()
	item_row = next((r for r in data if r.get("item_code") == item_code), None)
	if not item_row:
		frappe.throw(f"Item {item_code} not found in Rolled Plan (not an RB item, or excluded).")

	sku_type = item_row.get("sku_type")
	is_buffer = sku_type == "RBMTA"
	level = flt(item_row.get("on_hand_stock") or 0)
	tog = flt(item_row.get("tog") or 0)

	result = {
		"item_code": item_code,
		"item_name": item_row.get("item_name"),
		"sku_type": sku_type,
		"buffer_flag": "Buffer" if is_buffer else "Non-Buffer",
		"stock": level,
		"level": level,
		"tog": tog,
		"colour": item_row.get("colour"),
		"on_hand_colour": item_row.get("on_hand_colour"),
	}

	if is_buffer:
		_, total_demand_map = compute_universe_net_order_recommendations()
		total_demand = flt(total_demand_map.get(item_code, 0))
		total = tog + total_demand
		pct = _round_up_2dp((level / total) * 100) if total > 0 else None
		result.update(
			{
				"detail_type": "buffer",
				"total_demand": total_demand,
				"total": total,
				"pct": pct,
			}
		)
	else:
		mrq_map_all = get_mrq_map()
		till_today_map, spike_map_base = get_qualified_demand_map()
		spike_master_records = frappe.get_all(
			"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
		)
		spike_master_map = {
			sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
			for sm in spike_master_records
		}

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

		parent_bom_list = get_parent_bom_map({item_code}).get(item_code, [])
		parent_fifo = []

		if parent_bom_list:
			all_parent_codes = {p["parent_item"] for p in parent_bom_list}
			parent_tuple = tuple(all_parent_codes)

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

			p_stock_map = get_planning_stock_map(all_parent_codes)
			p_wip_map = get_wip_map()
			p_open_po_map = get_open_po_map()
			p_open_subcon_po_map = get_open_subcon_po_map()

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
				open_po_p = flt(p_open_po_map.get(ic, 0))
				open_subcon_po_p = flt(p_open_subcon_po_map.get(ic, 0))
				mrq_p = flt(mrq_map_all.get(ic, 0))
				moq_p = flt(master.moq or 0)
				bs_p = flt(master.batch_size or 0)

				qd_p, _, _ = get_qualified_demand_for_item(
					ic,
					till_today_map,
					parent_spike_map,
					p_buffer_map,
				)
				qd_p = flt(qd_p)
				if is_buf:
					qd_p = apply_spike_threshold(qd_p, tog_p, p_type_map.get(ic), spike_master_map)
				open_so_p = flt(p_open_so_qty_map.get(ic, 0)) if not is_buf else 0.0

				# All SKU types net off Open PO, Open Subcon PO and WIP the same way.
				if is_buf:
					base_rec = max(0, tog_p + qd_p - stock_p - wip_p - open_po_p - open_subcon_po_p - mrq_p)
				else:
					base_rec = max(0, open_so_p - stock_p - wip_p - open_po_p - open_subcon_po_p - mrq_p)
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

		own_so_map_for_priority = get_open_so_map_for_priority([item_code])
		own_priority_seed = _non_buffer_priority(item_code, level, own_so_map_for_priority)
		final_priority = item_row.get("priority") or ""
		propagated_from_ancestor = bool(final_priority) and final_priority != own_priority_seed

		result.update(
			{
				"detail_type": "non_buffer",
				"own_so_fifo": own_so_fifo,
				"parent_fifo": parent_fifo,
				"own_priority_seed": own_priority_seed,
				"propagated_from_ancestor": propagated_from_ancestor,
				"direct_parents": sorted({p["parent_item"] for p in parent_bom_list}),
			}
		)

	return result
