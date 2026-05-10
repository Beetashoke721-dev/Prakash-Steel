# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	calculate_net_order_recommendation,
	calculate_spike_map,
	get_mrq_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_stock_map,
	get_wip_map,
)


@frappe.whitelist()
def get_machine_load_colours():
	"""Return colour rules from Machine Load Colour Master."""
	rows = frappe.get_all(
		"Machine Load Colour Table",
		filters={"parent": "Machine Load Colour Master"},
		fields=["colour", "from_days", "to_days"],
		order_by="from_days asc",
	)
	return [{"colour": r.colour, "from_days": flt(r.from_days), "to_days": flt(r.to_days)} for r in rows]


@frappe.whitelist()
def get_machine_breakdown(machine_group_name):
	"""Return per-item calculation detail for a given machine (for the debug dialog)."""
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
		SELECT bmm.item_code
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1 AND bmmt.machine_group_name = %s
		""",
		(machine_group_name,),
		as_dict=True,
	)
	item_codes_for_machine = [r.item_code for r in machine_rows]
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

	item_codes = set(item.item_code for item in bb_items)
	item_buffer_map, item_type_map, item_tog_map, moq_map, batch_size_map = {}, {}, {}, {}, {}
	for item in bb_items:
		ic = item.item_code
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic] = item.item_type
		item_tog_map[ic] = flt(item.tog or 0)
		moq_map[ic] = flt(item.moq or 0)
		batch_size_map[ic] = flt(item.batch_size or 0)

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

	item_rows = []
	total_prod_req = 0.0
	total_order_req = 0.0

	for item_code in sorted(item_codes):
		is_buffer = item_buffer_map[item_code] == "Buffer"
		stock = flt(stock_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]

		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code, till_today_map, spike_map, item_buffer_map, item_tog_map, item_type_map, spike_master_map
		)
		qualified_demand = flt(qualified_demand)

		if is_buffer:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0.0, qualified_demand - stock - wip - mrq)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		display_open_so = qualified_demand if is_buffer else flt(open_so_qty_map.get(item_code, 0))
		order_req = max(0.0, display_open_so - stock)

		total_prod_req += net_order_rec
		total_order_req += order_req

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
		})

	net_prod_load = round((total_prod_req / effective_runtime) / no_of_machines, 2) if effective_runtime and no_of_machines else 0
	net_order_load = round((total_order_req / effective_runtime) / no_of_machines, 2) if effective_runtime and no_of_machines else 0

	return {
		"machine": machine_group_name,
		"no_of_machines": no_of_machines,
		"oee": oee,
		"runtime": runtime,
		"effective_runtime": round(effective_runtime, 2),
		"items": item_rows,
		"total_prod_req": round(total_prod_req),
		"total_order_req": round(total_order_req),
		"net_prod_load": net_prod_load,
		"net_order_load": net_order_load,
	}


def execute(filters=None):
	columns = get_columns()
	data = get_data()
	return columns, data


def get_columns():
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
		},
		{
			"label": "Net Prod Load (Days)",
			"fieldname": "net_prod_load",
			"fieldtype": "Float",
			"precision": 2,
			"width": 180,
		},
		{
			"label": "Net Order Load (Days)",
			"fieldname": "net_order_load",
			"fieldtype": "Float",
			"precision": 2,
			"width": 180,
		},
	]


def get_data():
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
		SELECT bmm.item_code, bmmt.machine_group_name
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1
		""",
		as_dict=True,
	)
	# item_code -> machine_group_name
	item_machine_map = {r.item_code: r.machine_group_name for r in machine_rows}

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

	item_codes = set(item.item_code for item in bb_items)
	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	moq_map = {}
	batch_size_map = {}

	for item in bb_items:
		ic = item.item_code
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic] = item.item_type
		item_tog_map[ic] = flt(item.tog or 0)
		moq_map[ic] = flt(item.moq or 0)
		batch_size_map[ic] = flt(item.batch_size or 0)

	# 5. Fetch shared maps (same as bright_plan)
	stock_map = get_stock_map(item_codes)
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

	# 6. For each item, compute net_order_rec (prod load) and open_so - stock (order load)
	machine_net_req_map = {m.machine_group_name: 0.0 for m in machines}
	machine_order_load_map = {m.machine_group_name: 0.0 for m in machines}

	for item_code in item_codes:
		machine_group = item_machine_map.get(item_code)
		if not machine_group or machine_group not in machine_net_req_map:
			continue

		is_buffer = item_buffer_map[item_code] == "Buffer"
		stock = flt(stock_map.get(item_code, 0))
		wip = flt(wip_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]

		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code, till_today_map, spike_map, item_buffer_map, item_tog_map, item_type_map, spike_master_map
		)
		qualified_demand = flt(qualified_demand)

		# Net prod load: uses production order recommendation (wip/mrq/moq factored in)
		if is_buffer:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip - mrq)
		else:
			base_order_rec = max(0.0, qualified_demand - stock - wip - mrq)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
		machine_net_req_map[machine_group] += net_order_rec

		# Net order load: open_so - stock (buffer uses qualified_demand as open_so)
		display_open_so = qualified_demand if is_buffer else flt(open_so_qty_map.get(item_code, 0))
		machine_order_load_map[machine_group] += max(0.0, display_open_so - stock)

	# 7. Build output rows
	data = []
	for m in machines:
		mgn = m.machine_group_name
		detail = machine_detail_map[mgn]
		no_of_machines = detail["no_of_machines"]
		oee = detail["oee"]
		runtime = detail["runtime"]
		total_net_req = machine_net_req_map.get(mgn, 0.0)

		# effective hours per machine per day = runtime * (oee / 100)
		effective_runtime = runtime * (oee / 100.0) if oee else 0

		total_order_req = machine_order_load_map.get(mgn, 0.0)

		if effective_runtime and no_of_machines:
			net_prod_load = round((total_net_req / effective_runtime) / no_of_machines, 2)
			net_order_load = round((total_order_req / effective_runtime) / no_of_machines, 2)
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


def _build_zero_rows(machines):
	return [
		{
			"machine_name": m.machine_group_name,
			"no_of_machines": m.no_of_machines,
			"net_prod_load": 0,
			"net_order_load": 0,
		}
		for m in machines
	]
