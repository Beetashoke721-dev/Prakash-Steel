# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math
import frappe
from frappe import _
from frappe.utils import flt
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_STATUS_PRIORITY,
	_PRIORITY_TO_COLOUR,
	_non_buffer_priority,
	calculate_net_order_recommendation,
	calculate_spike_map,
	calculate_sku_type,
	get_mrq_map,
	get_open_po_map,
	get_open_so_map_for_priority,
	get_sales_order_qty_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	apply_spike_threshold,
	get_stock_map,
	get_wip_map,
)
from prakash_steel.utils.lead_time import get_default_bom
from prakash_steel.utils.whitelist_permissions import require_permission


def get_draft_wo_map() -> dict:
	"""Returns {item_code: draft_wo_qty} — sum of qty from draft (docstatus=0) Work Orders."""
	rows = frappe.db.sql(
		"""
		SELECT production_item AS item_code, SUM(qty) AS draft_wo_qty
		FROM `tabWork Order`
		WHERE docstatus = 0
		GROUP BY production_item
		""",
		as_dict=True,
	)
	return {r.item_code: flt(r.draft_wo_qty) for r in rows}


@frappe.whitelist()
def get_item_breakdown(item_code) -> list[dict]:
	require_permission("Item", "report")
	item = frappe.db.get_value(
		"Item",
		item_code,
		["custom_buffer_flag", "custom_item_type", "safety_stock", "min_order_qty", "custom_batch_size"],
		as_dict=True,
	)
	if not item or item.custom_item_type != "BB":
		return []

	buffer_flag = item.custom_buffer_flag or "Non-Buffer"
	is_buffer = buffer_flag == "Buffer"
	sku_type = calculate_sku_type(buffer_flag, "BB")
	tog = flt(item.safety_stock or 0)
	moq = flt(item.min_order_qty or 0)
	batch_size = flt(item.custom_batch_size or 0)

	item_codes = {item_code}
	item_buffer_map = {item_code: buffer_flag}
	item_type_map = {item_code: "BB"}
	item_tog_map = {item_code: tog}

	stock_map = get_stock_map(item_codes)
	wip_map = get_wip_map()
	draft_wo_map = get_draft_wo_map()
	mrq_map = get_mrq_map()
	till_today_map, spike_map = get_qualified_demand_map()

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}
	calculated_spike_map = calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map)
	spike_map.update(calculated_spike_map)

	open_so_qty_map = get_sales_order_qty_map({})
	so_map_for_priority = get_open_so_map_for_priority(list(item_codes))

	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))
	draft_wo = flt(draft_wo_map.get(item_code, 0))
	mrq = flt(mrq_map.get(item_code, 0))

	qualified_demand, _till_today, _spike = get_qualified_demand_for_item(
		item_code, till_today_map, spike_map, item_buffer_map
	)
	qualified_demand = flt(qualified_demand)
	if is_buffer:
		qualified_demand = apply_spike_threshold(
			qualified_demand, tog, item_type_map.get(item_code), spike_master_map
		)

	item_open_so = flt(open_so_qty_map.get(item_code, 0))
	if is_buffer:
		base_order_rec = max(0, tog + qualified_demand - stock - wip - mrq)
	else:
		base_order_rec = max(0, item_open_so - stock - wip - mrq)

	net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

	if moq == 0 and batch_size > 0 and net_order_rec > batch_size:
		num_batches = round(net_order_rec / batch_size)
		qty_per_row = batch_size
	else:
		num_batches = 1
		qty_per_row = net_order_rec

	# Buffer: display/OP-CP uses qualified_demand (delivery_date <= today + spike)
	# Non-buffer: display/OP-CP uses all-time open SO
	display_open_so = qualified_demand if is_buffer else item_open_so
	remaining_so_for_op_cp = max(0, display_open_so - stock - wip - draft_wo)
	accumulated_batch_qty = 0.0

	rows = []
	for i in range(num_batches):
		level = stock + wip + draft_wo + accumulated_batch_qty

		if is_buffer:
			total = tog + qualified_demand
			if level == 0:
				colour = "Black"
				reason = "Level is 0 -> Black"
			elif total <= 0:
				colour = ""
				reason = f"TOG+Demand = {total:.0f} <= 0 -> no colour"
			elif level <= total / 3:
				colour = "Red"
				reason = f"Level {level:.0f} <= Total/3 ({total / 3:.0f}) -> Red"
			elif level <= (2 * total) / 3:
				colour = "Yellow"
				reason = f"Level {level:.0f} <= 2xTotal/3 ({(2 * total) / 3:.0f}) -> Yellow"
			elif level <= total:
				colour = "Green"
				reason = f"Level {level:.0f} <= Total ({total:.0f}) -> Green"
			else:
				colour = "White"
				reason = f"Level {level:.0f} > Total ({total:.0f}) -> White"
			total_val = math.ceil(total)
		else:
			colour = _non_buffer_priority(item_code, level, so_map_for_priority)
			reason = f"Non-buffer FIFO SO allocation at level {level:.0f}"
			total_val = None

		if not is_buffer:
			op_cp = ""
		elif qty_per_row == 0:
			op_cp = ""
		elif remaining_so_for_op_cp > 0:
			op_cp = "OP"
		else:
			op_cp = "CP"

		if colour:
			if sku_type == "BBMTA":
				priority_colour = "MTA" + (op_cp or "") + colour.upper()
			else:
				priority_colour = "MTO" + colour.upper()
		else:
			priority_colour = ""

		rows.append(
			{
				"batch_no": i + 1,
				"qty_per_row": math.ceil(qty_per_row),
				"stock": math.ceil(stock),
				"wip": math.ceil(wip),
				"draft_wo": math.ceil(draft_wo),
				"mrq": math.ceil(mrq),
				"accumulated_batch_qty": math.ceil(accumulated_batch_qty),
				"level": math.ceil(level),
				"tog": math.ceil(tog),
				"qualified_demand": math.ceil(qualified_demand),
				"total": total_val,
				"on_hand_colour": colour,
				"colour_reason": reason,
				"remaining_so_before": math.ceil(max(0, remaining_so_for_op_cp)),
				"op_cp": op_cp,
				"priority_colour": priority_colour,
				"open_so": math.ceil(display_open_so),
				"sku_type": sku_type,
				"is_buffer": is_buffer,
				"net_order_rec": math.ceil(net_order_rec),
				"num_batches": num_batches,
				"moq": math.ceil(moq),
				"batch_size": math.ceil(batch_size),
			}
		)

		remaining_so_for_op_cp -= qty_per_row
		accumulated_batch_qty += qty_per_row

	return rows


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Machine"),
			"fieldname": "machine",
			"fieldtype": "Link",
			"options": "Bright Machine",
			"width": 130,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Open SO"),
			"fieldname": "open_so",
			"fieldtype": "Int",
			"width": 120,
		},
		# {
		# 	"label": _("Last 3 Month Sale"),
		# 	"fieldname": "last_3month_sale",
		# 	"fieldtype": "Int",
		# 	"width": 150,
		# },
		{
			"label": _("On Hand Stock"),
			"fieldname": "on_hand_stock",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Order Recommendation Colour"),
			"fieldname": "on_hand_colour_priority",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Production Order Recommendation"),
			"fieldname": "or_with_moq_batch_size",
			"fieldtype": "Int",
			"width": 220,
		},
		{
			"label": _("Priority"),
			"fieldname": "priority_colour",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Priority Sequence"),
			"fieldname": "priority_sequence",
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"label": _("OP/CP"),
			"fieldname": "op_cp",
			"fieldtype": "Data",
			"width": 80,
			"hidden": 0,
		},
		{
			"label": _("MOQ"),
			"fieldname": "moq",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Order Multiple Qty"),
			"fieldname": "batch_size",
			"fieldtype": "Int",
			"width": 150,
		},
		{
			"label": _("Prod Qty based on Child Stock"),
			"fieldname": "production_qty_based_on_child_stock",
			"fieldtype": "Int",
			"width": 220,
		},
		{
			"label": _("Process Time based on Child Stock"),
			"fieldname": "process_time_based_on_child_stock",
			"fieldtype": "Float",
			"precision": 2,
			"width": 220,
		},
		{
			"label": _("Prod Qty based on Child Stock+WIP/Open PO"),
			"fieldname": "production_qty_based_on_child_stock_wip_open_po",
			"fieldtype": "Int",
			"width": 280,
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
			"fieldtype": "Int",
			"width": 150,
		},
		{
			"label": _("Child Stock"),
			"fieldname": "child_stock",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Child Stock Soft Allocation"),
			"fieldname": "child_stock_soft_allocation_qty",
			"fieldtype": "Int",
			"width": 200,
		},
		{
			"label": _("Child Stock Shortage"),
			"fieldname": "child_stock_shortage",
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"label": _("Child WIP/Open PO"),
			"fieldname": "child_wip_open_po",
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"label": _("Child SKU Type"),
			"fieldname": "child_sku_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Per Hour Production"),
			"fieldname": "per_hour_production",
			"fieldtype": "Float",
			"precision": 2,
			"width": 160,
		},
		{
			"label": _("Process Time"),
			"fieldname": "process_time",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
	]


def get_data(filters=None) -> list[dict]:
	# Fetch all BB items (both buffer BBMTA and non-buffer BBMTO)
	bb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.item_name,
			i.custom_buffer_flag as buffer_flag,
			i.custom_item_type as item_type,
			i.safety_stock as tog,
			i.min_order_qty as moq,
			i.custom_batch_size as batch_size
		FROM `tabItem` i
		WHERE i.custom_item_type = 'BB'
		""",
		as_dict=True,
	)

	if not bb_items:
		return []

	item_codes = set(item.item_code for item in bb_items)

	# Build lookup maps
	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	moq_map = {}
	batch_size_map = {}
	item_name_map = {}

	for item in bb_items:
		ic = item.item_code
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic] = item.item_type
		item_tog_map[ic] = flt(item.tog or 0)
		moq_map[ic] = flt(item.moq or 0)
		batch_size_map[ic] = flt(item.batch_size or 0)
		item_name_map[ic] = item.item_name or ic

	# Fetch shared data maps
	stock_map = get_stock_map(item_codes)
	wip_map = get_wip_map()
	draft_wo_map = get_draft_wo_map()
	open_po_map = get_open_po_map()
	mrq_map = get_mrq_map()
	till_today_map, spike_map = get_qualified_demand_map()

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}
		for sm in spike_master_records
	}

	calculated_spike_map = calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map)
	spike_map.update(calculated_spike_map)

	# Open SO qty map (all open SOs, not just till today)
	open_so_qty_map = get_sales_order_qty_map({})

	# For BBMTO priority calculation
	so_map_for_priority = get_open_so_map_for_priority(list(item_codes))

	# Build machine map: item_code -> {machine, per_hour_production} from default row
	machine_rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.machine_group_name, bmmt.mt_per_hour_production
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1
		""",
		as_dict=True,
	)
	machine_map = {
		r.item_code: {
			"machine": r.machine_group_name,
			"per_hour_production": flt(r.mt_per_hour_production),
		}
		for r in machine_rows
	}

	# Build priority sequence map: priority_colour value -> sequence number
	priority_seq_rows = frappe.db.sql(
		"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
		as_dict=True,
	)
	priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

	# Last 3 month sale map: item_code -> sum of (qty - delivered_qty) from submitted Sales Invoices
	last_3month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(GREATEST(0, sii.qty - IFNULL(sii.delivered_qty, 0))) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
		GROUP BY sii.item_code
		""",
		as_dict=True,
	)
	last_3month_sale_map = {r.item_code: math.ceil(flt(r.sale_qty)) for r in last_3month_rows}

	# Build base rows
	data = []
	child_stock_map = {}
	child_wip_open_po_map = {}
	child_item_detail_map = {}  # cache: item_code -> (custom_item_type, custom_buffer_flag)

	for item_code in sorted(item_codes):
		buffer_flag = item_buffer_map[item_code]
		is_buffer = buffer_flag == "Buffer"
		sku_type = calculate_sku_type(buffer_flag, "BB")  # BBMTA or BBMTO

		stock = flt(stock_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]
		mrq = flt(mrq_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		draft_wo = flt(draft_wo_map.get(item_code, 0))
		open_po = flt(open_po_map.get(item_code, 0))

		qualified_demand, till_today, spike = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map,
		)
		qualified_demand = flt(qualified_demand)
		if is_buffer:
			qualified_demand = apply_spike_threshold(
				qualified_demand, tog, item_type_map.get(item_code), spike_master_map
			)
		item_open_so = flt(open_so_qty_map.get(item_code, 0))

		# Calculate order recommendation
		if is_buffer:
			base_order_rec = max(0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0, item_open_so - stock - wip - mrq)

		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		# Determine row splitting: split into multiple rows of batch_size each
		# only when batch_size is set (no MOQ) and net_order_rec > batch_size
		if moq == 0 and batch_size > 0 and net_order_rec > batch_size:
			num_batches = round(net_order_rec / batch_size)
			qty_per_row = batch_size
		else:
			num_batches = 1
			qty_per_row = net_order_rec

		if net_order_rec == 0:
			continue

		# Get BOM child items (fetched once per parent item)
		bom = get_default_bom(item_code)
		child_items = []

		if bom:
			try:
				bom_doc = frappe.get_doc("BOM", bom)
				bom_quantity = flt(bom_doc.quantity) or 1.0
				for bom_item in bom_doc.items:
					child_item_code = bom_item.item_code
					child_bom_qty = flt(bom_item.qty)

					# Fetch child item details once
					child_item_type = None
					child_sku_type = None
					child_stock = 0
					child_wip_open_po = 0

					try:
						if child_item_code not in child_item_detail_map:
							child_item_detail_map[child_item_code] = (
								frappe.db.get_value(
									"Item",
									child_item_code,
									["custom_item_type", "custom_buffer_flag"],
									as_dict=True,
								)
								or {}
							)
						child_detail = child_item_detail_map[child_item_code]
						child_item_type = child_detail.get("custom_item_type")
						child_buffer_flag = child_detail.get("custom_buffer_flag") or "Non-Buffer"
						child_sku_type = calculate_sku_type(child_buffer_flag, child_item_type)

						if child_item_code not in child_stock_map:
							stock_data = frappe.db.sql(
								"SELECT SUM(actual_qty) as stock FROM `tabBin` WHERE item_code = %s",
								(child_item_code,),
								as_dict=True,
							)
							child_stock_map[child_item_code] = math.ceil(
								flt(stock_data[0].stock if stock_data and stock_data[0].stock else 0)
							)

						child_stock = child_stock_map[child_item_code]

						child_wip = (
							0
							if child_sku_type in ["RBMTA", "RBMTO"]
							else flt(wip_map.get(child_item_code, 0))
						)
						child_open_po = flt(open_po_map.get(child_item_code, 0))
						child_wip_open_po = math.ceil(child_wip + child_open_po)

						if child_item_code not in child_wip_open_po_map:
							child_wip_open_po_map[child_item_code] = child_wip_open_po
					except Exception:
						pass

					child_items.append(
						{
							"item_code": child_item_code,
							"bom_qty": child_bom_qty,
							"bom_quantity": bom_quantity,
							"child_item_type": child_item_type,
							"child_sku_type": child_sku_type,
							"child_stock": child_stock,
							"child_wip_open_po": child_wip_open_po,
						}
					)
			except Exception:
				pass

		# Buffer: open SO for display/OP-CP = qualified_demand (delivery_date <= today + spike)
		# Non-buffer: open SO for display/OP-CP = all-time open SO (no date filter)
		display_open_so = qualified_demand if is_buffer else item_open_so
		remaining_so_for_op_cp = max(0, display_open_so - stock - wip - draft_wo)
		accumulated_batch_qty = 0.0

		for _i in range(num_batches):
			# Colour: level = stock + submitted_wo + draft_wo + qty already produced in previous batches
			level = stock + wip + draft_wo + accumulated_batch_qty
			if is_buffer:
				total = tog + qualified_demand
				if level == 0:
					on_hand_colour_priority = "Black"
				elif total <= 0:
					on_hand_colour_priority = ""
				elif level <= total / 3:
					on_hand_colour_priority = "Red"
				elif level <= (2 * total) / 3:
					on_hand_colour_priority = "Yellow"
				elif level <= total:
					on_hand_colour_priority = "Green"
				else:
					on_hand_colour_priority = "White"
			else:
				on_hand_colour_priority = _non_buffer_priority(item_code, level, so_map_for_priority)

			if not is_buffer:
				op_cp = ""
			elif qty_per_row == 0:
				op_cp = ""
			elif remaining_so_for_op_cp > 0:
				op_cp = "OP"
			else:
				op_cp = "CP"
			remaining_so_for_op_cp -= qty_per_row

			machine_info = machine_map.get(item_code) or {}
			machine_name = machine_info.get("machine")
			per_hour = machine_info.get("per_hour_production")
			priority_colour = (
				(("MTA" + (op_cp or "") + on_hand_colour_priority.upper())
				if sku_type == "BBMTA"
				else ("MTO" + on_hand_colour_priority.upper()))
				if on_hand_colour_priority else ""
			)

			base_row = {
				"machine": machine_name,
				"per_hour_production": per_hour,
				"process_time": round(qty_per_row / flt(per_hour), 2) if per_hour else None,
				"item_code": item_code,
				"item_name": item_name_map[item_code],
				"sku_type": sku_type,
				"open_so": math.ceil(display_open_so),
				"last_3month_sale": last_3month_sale_map.get(item_code, 0),
				"on_hand_stock": math.ceil(stock),
				"on_hand_colour_priority": on_hand_colour_priority,
				"op_cp": op_cp,
				"priority_colour": priority_colour,
				"priority_sequence": priority_seq_map.get(priority_colour) if priority_colour else None,
				"or_with_moq_batch_size": math.ceil(qty_per_row),
				"moq": math.ceil(moq),
				"batch_size": math.ceil(batch_size),
				"production_qty_based_on_child_stock": None,
				"process_time_based_on_child_stock": None,
				"production_qty_based_on_child_stock_wip_open_po": None,
				"child_item_code": None,
				"child_requirement": None,
				"child_stock": None,
				"child_stock_soft_allocation_qty": None,
				"child_stock_shortage": None,
				"child_sku_type": None,
				"child_bom_qty": None,
				"child_bom_quantity": None,
				"child_wip_open_po": None,
			}

			if child_items:
				for child_info in child_items:
					child_bom_qty = child_info["bom_qty"]
					child_bom_quantity = child_info["bom_quantity"] or 1.0
					normalized_qty = child_bom_qty / child_bom_quantity if child_bom_quantity else 0
					child_requirement = math.ceil(qty_per_row * normalized_qty)

					row = base_row.copy()
					row["child_item_code"] = child_info["item_code"]
					row["child_sku_type"] = child_info["child_sku_type"]
					row["child_requirement"] = child_requirement
					row["child_stock"] = child_info["child_stock"]
					row["child_wip_open_po"] = child_info["child_wip_open_po"]
					row["child_bom_qty"] = child_bom_qty
					row["child_bom_quantity"] = child_bom_quantity
					row["child_stock_soft_allocation_qty"] = None

					data.append(row)
			else:
				data.append(base_row)

			accumulated_batch_qty += qty_per_row

	# Sort by machine (grouped), then by priority_sequence (user-defined order from Priority Colour Sequence Master)
	# Rows with no machine go last; rows with no sequence go last within their machine group
	data.sort(
		key=lambda r: (
			r.get("machine") or "\xff",
			r.get("priority_sequence") if r.get("priority_sequence") is not None else 999999,
		)
	)

	# FIFO child stock allocation: deplete stock row by row in sorted order.
	# Each row sees the remaining child stock after all previous rows have consumed their share.
	remaining_child_stock = {k: flt(v) for k, v in child_stock_map.items()}
	remaining_child_wip_open_po = {k: flt(v) for k, v in child_wip_open_po_map.items()}

	for row in data:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue

		child_requirement = flt(row.get("child_requirement", 0))
		available_child_stock = flt(remaining_child_stock.get(child_item_code, 0))
		available_child_wip_open_po = flt(remaining_child_wip_open_po.get(child_item_code, 0))

		stock_allocated = min(child_requirement, available_child_stock)
		stock_shortage = child_requirement - stock_allocated
		wip_open_po_allocated = min(stock_shortage, available_child_wip_open_po)
		total_allocated = stock_allocated + wip_open_po_allocated

		# Deplete for subsequent rows
		remaining_child_stock[child_item_code] = available_child_stock - stock_allocated
		remaining_child_wip_open_po[child_item_code] = available_child_wip_open_po - wip_open_po_allocated

		child_bom_qty = flt(row.get("child_bom_qty", 0))
		child_bom_quantity = flt(row.get("child_bom_quantity", 1.0)) or 1.0
		parent_per_child = (child_bom_quantity / child_bom_qty) if child_bom_qty else 0

		net_order_recommendation = math.ceil(flt(row.get("or_with_moq_batch_size", 0)))
		per_hour = flt(row.get("per_hour_production") or 0)

		prod_qty_child_stock = math.ceil(stock_allocated * parent_per_child)
		# Cap at net order recommendation — can't produce more than what's actually needed
		prod_qty_child_stock = min(prod_qty_child_stock, net_order_recommendation)

		prod_qty_child_stock_wip = math.ceil(total_allocated * parent_per_child)
		# Cap at net order recommendation — can't produce more than what's actually needed
		prod_qty_child_stock_wip = min(prod_qty_child_stock_wip, net_order_recommendation)

		row["child_stock"] = math.ceil(flt(child_stock_map.get(child_item_code, 0)))
		row["child_stock_soft_allocation_qty"] = math.ceil(stock_allocated)
		row["child_stock_shortage"] = math.ceil(stock_shortage)
		row["production_qty_based_on_child_stock"] = prod_qty_child_stock
		row["process_time_based_on_child_stock"] = round(prod_qty_child_stock / per_hour, 2) if per_hour else None
		row["production_qty_based_on_child_stock_wip_open_po"] = prod_qty_child_stock_wip

	return data
