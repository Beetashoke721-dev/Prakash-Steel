# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from decimal import ROUND_HALF_UP, Decimal

import frappe
from frappe.utils import flt


def _round_half_up(value, decimals=1) -> float:
	"""Round to `decimals` places, rounding .5 away from zero (e.g. 5.25 -> 5.3)."""
	quant = Decimal("1." + "0" * decimals) if decimals else Decimal("1")
	return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	apply_spike_threshold,
	calculate_net_order_recommendation,
	calculate_spike_map,
	get_mrq_map,
	get_planning_stock_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_wip_map,
)
from prakash_steel.utils.whitelist_permissions import require_any_permission


def _build_item_maps(items) -> tuple:
	"""Build lookup dicts from a list of item rows (output of Item SQL query).
	Returns: (item_codes, buffer_map, type_map, tog_map, moq_map, batch_size_map)
	"""
	item_codes = set()
	item_buffer_map, item_type_map, item_tog_map, moq_map, batch_size_map = {}, {}, {}, {}, {}
	for item in items:
		ic = item.item_code
		item_codes.add(ic)
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic]   = item.item_type
		item_tog_map[ic]    = flt(item.tog or 0)
		moq_map[ic]         = flt(item.moq or 0)
		batch_size_map[ic]  = flt(item.batch_size or 0)
	return item_codes, item_buffer_map, item_type_map, item_tog_map, moq_map, batch_size_map


@frappe.whitelist()
def get_machine_load_colours() -> list | dict:
	"""Return colour rules from Machine Load Colour Master."""
	require_any_permission([("Bright Machine", "read"), ("Machine Load Colour Master", "read")])
	rows = frappe.get_all(
		"Machine Load Colour Table",
		filters={"parent": "Machine Load Colour Master"},
		fields=["colour", "from_days", "to_days"],
		order_by="from_days asc",
	)
	return [{"colour": r.colour, "from_days": flt(r.from_days), "to_days": flt(r.to_days)} for r in rows]


@frappe.whitelist()
def get_machine_breakdown(machine_group_name) -> list | dict:
	"""Return per-item calculation detail for a given machine (for the debug dialog)."""
	require_any_permission([("Bright Machine", "read"), ("Item", "read")])
	machine = frappe.db.get_value(
		"Bright Machine",
		machine_group_name,
		["machine_group_name", "no_of_machines", "oee", "runtime"],
		as_dict=True,
	)
	if not machine:
		return {}

	no_of_machines = flt(machine.no_of_machines) or 1
	oee = flt(machine.oee) or 0
	runtime = flt(machine.runtime) or 0
	effective_runtime = runtime * (oee / 100.0) if oee else 0

	# Items mapped to this machine (default row)
	machine_rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.mt_per_hour_production
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1 AND bmmt.machine_group_name = %s
		""",
		(machine_group_name,),
		as_dict=True,
	)
	item_codes_for_machine = [r.item_code for r in machine_rows]
	item_kg_per_hour_map = {r.item_code: flt(r.mt_per_hour_production) for r in machine_rows}
	if not item_codes_for_machine:
		return {
			"machine": machine_group_name,
			"no_of_machines": no_of_machines,
			"oee": oee,
			"runtime": runtime,
			"effective_runtime": effective_runtime,
			"items": [],
			"total_prod_req": 0,
			"total_order_req": 0,
			"net_prod_load": 0,
			"net_order_load": 0,
		}

	# Fetch item details for only these items
	placeholders = ", ".join(["%s"] * len(item_codes_for_machine))
	bb_items = frappe.db.sql(
		f"""
		SELECT
			i.name as item_code,
			i.custom_buffer_flag as buffer_flag,
			i.custom_item_type as item_type,
			i.safety_stock as tog,
			i.min_order_qty as moq,
			i.custom_batch_size as batch_size
		FROM `tabItem` i
		WHERE i.name IN ({placeholders})
		""",
		item_codes_for_machine,
		as_dict=True,
	)

	item_codes, item_buffer_map, item_type_map, item_tog_map, moq_map, batch_size_map = _build_item_maps(bb_items)

	stock_map = get_planning_stock_map(item_codes)
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

	item_rows = []
	total_prod_hours = 0.0
	total_order_hours = 0.0

	for item_code in sorted(item_codes):
		kg_per_hour = item_kg_per_hour_map.get(item_code, 0.0)
		is_buffer = item_buffer_map[item_code] == "Buffer"
		stock = flt(stock_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]

		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code, till_today_map, spike_map, item_buffer_map
		)
		raw_qualified_demand = flt(qualified_demand)
		qualified_demand = raw_qualified_demand
		if is_buffer:
			qualified_demand = apply_spike_threshold(
				raw_qualified_demand, tog, item_type_map.get(item_code), spike_master_map
			)

		if is_buffer:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0.0, flt(open_so_qty_map.get(item_code, 0)) - stock - wip - mrq)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		# Buffer: Open SO is qualified demand before the spike threshold, same as
		# PO Recommendation / Manual Bright Plan.
		display_open_so = raw_qualified_demand if is_buffer else flt(open_so_qty_map.get(item_code, 0))
		order_req = max(0.0, display_open_so - stock)

		prod_hours = round(net_order_rec / kg_per_hour, 4) if kg_per_hour else 0
		order_hours = round(order_req / kg_per_hour, 4) if kg_per_hour else 0

		total_prod_hours += prod_hours
		total_order_hours += order_hours

		item_rows.append({
			"item_code": item_code,
			"sku_type": "BBMTA" if is_buffer else "BBMTO",
			"open_so": round(display_open_so),
			"stock": round(stock),
			"wip": round(wip),
			"mrq": round(mrq),
			"tog": round(tog),
			"qualified_demand": round(qualified_demand),
			"moq": round(moq),
			"batch_size": round(batch_size),
			"base_order_rec": round(base_order_rec),
			"net_order_rec": round(net_order_rec),
			"order_req": round(order_req),
			"kg_per_hour": kg_per_hour,
			"prod_hours": round(prod_hours, 2),
			"order_hours": round(order_hours, 2),
		})

	net_prod_load = round((total_prod_hours / effective_runtime) / no_of_machines, 2) if effective_runtime and no_of_machines else 0
	net_order_load = round((total_order_hours / effective_runtime) / no_of_machines, 2) if effective_runtime and no_of_machines else 0

	return {
		"machine": machine_group_name,
		"no_of_machines": no_of_machines,
		"oee": oee,
		"runtime": runtime,
		"effective_runtime": round(effective_runtime, 2),
		"items": item_rows,
		"total_prod_hours": round(total_prod_hours, 2),
		"total_order_hours": round(total_order_hours, 2),
		"net_prod_load": net_prod_load,
		"net_order_load": net_order_load,
	}


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data()
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Machine Name",
			"fieldname": "machine_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "No of Machines",
			"fieldname": "no_of_machines",
			"fieldtype": "Int",
			"width": 150,
			"align": "center",
		},
		{
			"label": "Net Prod Load (Days)",
			"fieldname": "net_prod_load",
			"fieldtype": "Float",
			"precision": 1,
			"width": 180,
		},
		{
			"label": "Net Order Load (Days)",
			"fieldname": "net_order_load",
			"fieldtype": "Float",
			"precision": 1,
			"width": 180,
		},
	]


def get_data() -> list[dict]:
	# 1. Fetch all Bright Machine records
	machines = frappe.get_all(
		"Bright Machine",
		fields=["machine_group_name", "no_of_machines", "oee", "runtime"],
		order_by="machine_group_name asc",
	)
	if not machines:
		return []

	# 2. Build machine details map keyed by machine_group_name
	machine_detail_map = {
		m.machine_group_name: {
			"no_of_machines": flt(m.no_of_machines) or 1,
			"oee": flt(m.oee) or 0,
			"runtime": flt(m.runtime) or 0,
		}
		for m in machines
	}

	# 3. Get item -> machine mapping from Bright Machine Master (default row only)
	machine_rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.machine_group_name, bmmt.mt_per_hour_production
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1
		""",
		as_dict=True,
	)
	item_machine_map = {r.item_code: r.machine_group_name for r in machine_rows}
	item_kg_per_hour_map = {r.item_code: flt(r.mt_per_hour_production) for r in machine_rows}

	# 4. Fetch all BB items
	bb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
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
		return _build_zero_rows(machines)

	item_codes, item_buffer_map, item_type_map, item_tog_map, moq_map, batch_size_map = _build_item_maps(bb_items)

	# 5. Fetch shared maps (same as bright_plan)
	stock_map = get_planning_stock_map(item_codes)
	wip_map = get_wip_map()
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

	open_so_qty_map = get_sales_order_qty_map({})

	# 6. For each item, compute process hours per machine
	# prod hours = net_order_rec / kg_per_hour  (production order rec based; non-buffer uses all open SO, as in bright_plan)
	# order hours = (open_so - stock) / kg_per_hour  (open so based)
	machine_prod_hours_map = {m.machine_group_name: 0.0 for m in machines}
	machine_order_hours_map = {m.machine_group_name: 0.0 for m in machines}

	for item_code in item_codes:
		machine_group = item_machine_map.get(item_code)
		if not machine_group or machine_group not in machine_prod_hours_map:
			continue

		kg_per_hour = item_kg_per_hour_map.get(item_code, 0.0)
		if not kg_per_hour:
			continue

		is_buffer = item_buffer_map[item_code] == "Buffer"
		stock = flt(stock_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]

		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code, till_today_map, spike_map, item_buffer_map
		)
		raw_qualified_demand = flt(qualified_demand)
		qualified_demand = raw_qualified_demand
		if is_buffer:
			qualified_demand = apply_spike_threshold(
				raw_qualified_demand, tog, item_type_map.get(item_code), spike_master_map
			)

		# Prod hours: net order rec / kg_per_hour
		if is_buffer:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0.0, flt(open_so_qty_map.get(item_code, 0)) - stock - wip - mrq)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
		machine_prod_hours_map[machine_group] += net_order_rec / kg_per_hour

		# Order hours: (open_so - stock) / kg_per_hour
		# Buffer: Open SO is qualified demand before the spike threshold, same as
		# PO Recommendation / Manual Bright Plan.
		display_open_so = raw_qualified_demand if is_buffer else flt(open_so_qty_map.get(item_code, 0))
		order_req = max(0.0, display_open_so - stock)
		machine_order_hours_map[machine_group] += order_req / kg_per_hour

	# 7. Build output rows
	data = []
	for m in machines:
		mgn = m.machine_group_name
		detail = machine_detail_map[mgn]
		no_of_machines = detail["no_of_machines"]
		oee = detail["oee"]
		runtime = detail["runtime"]
		total_prod_hours = machine_prod_hours_map.get(mgn, 0.0)
		total_order_hours = machine_order_hours_map.get(mgn, 0.0)

		# effective hours per machine per day = runtime * (oee / 100)
		effective_runtime = runtime * (oee / 100.0) if oee else 0

		if effective_runtime and no_of_machines:
			net_prod_load = _round_half_up((total_prod_hours / effective_runtime) / no_of_machines, 1)
			net_order_load = _round_half_up((total_order_hours / effective_runtime) / no_of_machines, 1)
		else:
			net_prod_load = 0
			net_order_load = 0

		data.append({
			"machine_name": mgn,
			"no_of_machines": int(no_of_machines),
			"net_prod_load": net_prod_load,
			"net_order_load": net_order_load,
		})

	return data


def _build_zero_rows(machines) -> list[dict]:
	return [
		{
			"machine_name": m.machine_group_name,
			"no_of_machines": m.no_of_machines,
			"net_prod_load": 0,
			"net_order_load": 0,
		}
		for m in machines
	]
