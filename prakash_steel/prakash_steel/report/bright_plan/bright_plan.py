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
	get_stock_map,
	get_wip_map,
)
from prakash_steel.utils.lead_time import get_default_bom


@frappe.whitelist()
def get_item_breakdown(item_code):
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
	mrq = flt(mrq_map.get(item_code, 0))

	qualified_demand, _till_today, _spike = get_qualified_demand_for_item(
		item_code, till_today_map, spike_map, item_buffer_map, item_tog_map, item_type_map, spike_master_map
	)
	qualified_demand = flt(qualified_demand)

	if is_buffer:
		base_order_rec = max(0, tog + qualified_demand - stock - wip - mrq)
	else:
		base_order_rec = max(0, qualified_demand - stock - wip - mrq)

	net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

	if moq == 0 and batch_size > 0 and net_order_rec > batch_size:
		num_batches = round(net_order_rec / batch_size)
		qty_per_row = batch_size
	else:
		num_batches = 1
		qty_per_row = net_order_rec

	item_open_so = flt(open_so_qty_map.get(item_code, 0))
	# Buffer: display/OP-CP uses qualified_demand (delivery_date <= today + spike)
	# Non-buffer: display/OP-CP uses all-time open SO
	display_open_so = qualified_demand if is_buffer else item_open_so
	remaining_so_for_op_cp = max(0, display_open_so - stock - wip)
	accumulated_batch_qty = 0.0

	rows = []
	for i in range(num_batches):
		level = stock + wip + accumulated_batch_qty

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

		if qty_per_row == 0:
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


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Machine"),
			"fieldname": "machine",
			"fieldtype": "Data",
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
			"label": _("OP/CP"),
			"fieldname": "op_cp",
			"fieldtype": "Data",
			"width": 80,
			"hidden": 1,
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
			"label": _("Child SKU Type"),
			"fieldname": "child_sku_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Per Hour Production"),
			"fieldname": "per_hour_production",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Process Time"),
			"fieldname": "process_time",
			"fieldtype": "Float",
			"width": 130,
		},
	]


def get_data(filters=None):
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

	# Build base rows
	data = []
	child_stock_map = {}
	child_wip_open_po_map = {}

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
		open_po = flt(open_po_map.get(item_code, 0))

		qualified_demand, till_today, spike = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map,
			item_tog_map,
			item_type_map,
			spike_master_map,
		)
		qualified_demand = flt(qualified_demand)

		# Calculate order recommendation
		if is_buffer:
			base_order_rec = max(0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0, qualified_demand - stock - wip - mrq)

		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		# Determine row splitting: split into multiple rows of batch_size each
		# only when batch_size is set (no MOQ) and net_order_rec > batch_size
		if moq == 0 and batch_size > 0 and net_order_rec > batch_size:
			num_batches = round(net_order_rec / batch_size)
			qty_per_row = batch_size
		else:
			num_batches = 1
			qty_per_row = net_order_rec

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
						child_doc = frappe.get_doc("Item", child_item_code)
						child_item_type = child_doc.get("custom_item_type")
						child_buffer_flag = child_doc.get("custom_buffer_flag") or "Non-Buffer"
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

		item_open_so = flt(open_so_qty_map.get(item_code, 0))
		# Buffer: open SO for display/OP-CP = qualified_demand (delivery_date <= today + spike)
		# Non-buffer: open SO for display/OP-CP = all-time open SO (no date filter)
		display_open_so = qualified_demand if is_buffer else item_open_so
		remaining_so_for_op_cp = max(0, display_open_so - stock - wip)
		accumulated_batch_qty = 0.0

		for _i in range(num_batches):
			# Colour: level = stock + wip + qty already produced in previous batches
			# Mirrors open_mr_for_manufacture logic (prev_mr_qty = accumulated batches)
			level = stock + wip + accumulated_batch_qty
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

			if qty_per_row == 0:
				op_cp = ""
			elif remaining_so_for_op_cp > 0:
				op_cp = "OP"
			else:
				op_cp = "CP"
			remaining_so_for_op_cp -= qty_per_row

			base_row = {
				"machine": None,
				"item_code": item_code,
				"item_name": item_name_map[item_code],
				"sku_type": sku_type,
				"open_so": math.ceil(display_open_so),
				"on_hand_stock": math.ceil(stock),
				"on_hand_colour_priority": on_hand_colour_priority,
				"op_cp": op_cp,
				"priority_colour": (
					("MTA" + (op_cp or "") + on_hand_colour_priority.upper())
					if sku_type == "BBMTA"
					else ("MTO" + on_hand_colour_priority.upper())
				)
				if on_hand_colour_priority
				else "",
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
				"per_hour_production": None,
				"process_time": None,
			}

			if child_items:
				for child_info in child_items:
					child_bom_qty = child_info["bom_qty"]
					child_bom_quantity = child_info["bom_quantity"] or 1.0
					normalized_qty = child_bom_qty / child_bom_quantity if child_bom_quantity else 0
					child_requirement = math.ceil(net_order_rec * normalized_qty)

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

	# Sort by on_hand_colour_priority severity (BLACK first, then RED, YELLOW, GREEN, WHITE, empty)
	_colour_order = {"BLACK": 0, "RED": 1, "YELLOW": 2, "GREEN": 3, "WHITE": 4, "": 5}
	data.sort(key=lambda r: _colour_order.get((r.get("on_hand_colour_priority") or "").upper(), 5))

	# Per-item allocation: each parent item independently allocates from actual child stock.
	# All batch rows of the same item show the same item-level values (cached per pair).
	allocation_cache = {}  # (item_code, child_item_code) -> computed allocation dict

	for row in data:
		child_item_code = row.get("child_item_code")
		item_code = row.get("item_code")
		if not child_item_code:
			continue

		pair = (item_code, child_item_code)

		if pair in allocation_cache:
			row.update(allocation_cache[pair])
			continue

		child_requirement = flt(row.get("child_requirement", 0))
		# Use actual child stock — no cross-item depletion
		actual_child_stock = flt(child_stock_map.get(child_item_code, 0))
		actual_child_wip_open_po = flt(child_wip_open_po_map.get(child_item_code, 0))

		stock_allocated = min(child_requirement, actual_child_stock)
		stock_shortage = child_requirement - stock_allocated
		wip_open_po_allocated = min(stock_shortage, actual_child_wip_open_po)
		total_allocated = stock_allocated + wip_open_po_allocated

		child_bom_qty = flt(row.get("child_bom_qty", 0))
		child_bom_quantity = flt(row.get("child_bom_quantity", 1.0)) or 1.0
		parent_per_child = (child_bom_quantity / child_bom_qty) if child_bom_qty else 0

		cached = {
			"child_stock_soft_allocation_qty": math.ceil(stock_allocated),
			"child_stock_shortage": math.ceil(stock_shortage),
			"production_qty_based_on_child_stock": math.ceil(stock_allocated * parent_per_child),
			"production_qty_based_on_child_stock_wip_open_po": math.ceil(total_allocated * parent_per_child),
		}
		allocation_cache[pair] = cached
		row.update(cached)

	return data
