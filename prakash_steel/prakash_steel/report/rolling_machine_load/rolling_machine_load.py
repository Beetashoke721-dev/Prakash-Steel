# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import _round_half_up
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.bom_traversal import (
	compute_universe_net_order_recommendations,
)
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	apply_spike_threshold,
	calculate_spike_map,
	calculate_sku_type,
	get_planning_stock_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
)
from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import get_parent_bom_map
from prakash_steel.utils.whitelist_permissions import require_any_permission

DEFAULT_MACHINE_NAME = "Rolling Machine"
NO_OF_MACHINES = 1  # only one rolling mill


def get_machine() -> dict:
	"""Machine name, OEE and runtime from the Rolling Machine single."""
	doc = frappe.get_cached_doc("Rolling Machine")
	oee = flt(doc.oee)
	runtime = flt(doc.runtime)
	return {
		"machine_name": doc.machine_name or DEFAULT_MACHINE_NAME,
		"no_of_machines": NO_OF_MACHINES,
		"oee": oee,
		"runtime": runtime,
		# effective hours per day = runtime * (oee / 100)
		"effective_runtime": runtime * (oee / 100.0) if oee else 0,
	}


def _load_days(total_hours, effective_runtime) -> float:
	if not effective_runtime or not NO_OF_MACHINES:
		return 0
	return _round_half_up((total_hours / effective_runtime) / NO_OF_MACHINES, 1)


def get_item_rows() -> list[dict]:
	"""Per RB item prod / order hours on the rolling machine.

	Prod hours  = Net Order Rec (same value as Rolled Plan, BOM-propagated) / per hour qty
	Order hours = (Open SO - Stock) / per hour qty  (buffer: Open SO = qualified demand
	              before spike threshold, same as Bright Machine Load)
	Per hour qty comes from Rolling Algo; an RBMTO item without its own falls back to
	its single Buffer parent's, same as Rolled Plan.
	"""
	rb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.custom_buffer_flag as buffer_flag,
			i.custom_item_type as item_type,
			i.safety_stock as tog
		FROM `tabItem` i
		WHERE i.custom_item_type = 'RB'
		""",
		as_dict=True,
	)
	if not rb_items:
		return []

	item_codes = set()
	item_buffer_map, item_type_map, item_tog_map = {}, {}, {}
	for item in rb_items:
		ic = item.item_code
		item_codes.add(ic)
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic] = item.item_type
		item_tog_map[ic] = flt(item.tog or 0)

	per_hour_qty_map = {
		r.item_code: flt(r.per_hour_planned_qty)
		for r in frappe.db.get_all("Rolling Algo", fields=["item_code", "per_hour_planned_qty"])
	}

	psp_net_order_map, _ = compute_universe_net_order_recommendations()
	stock_map = get_planning_stock_map(item_codes)
	till_today_map, spike_map = get_qualified_demand_map()

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}
	spike_map.update(calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map))

	open_so_qty_map = get_sales_order_qty_map({})

	# RBMTO per-hour fallback: single parent which is a Buffer item (as in Rolled Plan)
	fallback_candidates = [
		ic
		for ic in item_codes
		if item_buffer_map[ic] != "Buffer"
		and not per_hour_qty_map.get(ic)
		and flt(psp_net_order_map.get(ic, 0)) > 0
	]
	parent_bom_map = get_parent_bom_map(fallback_candidates)
	parent_codes = {p["parent_item"] for parents in parent_bom_map.values() for p in parents}
	parent_buffer_map = {}
	if parent_codes:
		parent_buffer_map = {
			r.name: r.custom_buffer_flag
			for r in frappe.get_all(
				"Item", filters={"name": ["in", list(parent_codes)]}, fields=["name", "custom_buffer_flag"]
			)
		}

	rows = []
	for item_code in sorted(item_codes):
		is_buffer = item_buffer_map[item_code] == "Buffer"
		sku_type = calculate_sku_type(item_buffer_map[item_code], item_type_map[item_code])
		if sku_type not in ("RBMTA", "RBMTO"):
			continue

		net_order_rec = flt(psp_net_order_map.get(item_code, 0))

		per_hour_qty = per_hour_qty_map.get(item_code) or 0.0
		if not per_hour_qty and item_code in fallback_candidates:
			parents = parent_bom_map.get(item_code, [])
			if len(parents) == 1 and parent_buffer_map.get(parents[0]["parent_item"]) == "Buffer":
				per_hour_qty = per_hour_qty_map.get(parents[0]["parent_item"]) or 0.0

		stock = flt(stock_map.get(item_code, 0))
		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code, till_today_map, spike_map, item_buffer_map
		)
		raw_qualified_demand = flt(qualified_demand)
		if is_buffer:
			qualified_demand = apply_spike_threshold(
				raw_qualified_demand, item_tog_map[item_code], item_type_map.get(item_code), spike_master_map
			)

		display_open_so = raw_qualified_demand if is_buffer else flt(open_so_qty_map.get(item_code, 0))
		order_req = max(0.0, display_open_so - stock)

		prod_hours = net_order_rec / per_hour_qty if per_hour_qty else 0
		order_hours = order_req / per_hour_qty if per_hour_qty else 0

		rows.append({
			"item_code": item_code,
			"sku_type": sku_type,
			"open_so": round(display_open_so),
			"stock": round(stock),
			"tog": round(item_tog_map[item_code]),
			"qualified_demand": round(flt(qualified_demand)),
			"net_order_rec": round(net_order_rec),
			"order_req": round(order_req),
			"per_hour_qty": per_hour_qty,
			"prod_hours": prod_hours,
			"order_hours": order_hours,
		})

	return rows


def execute(filters=None) -> tuple[list, list]:
	return get_columns(), get_data()


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
	machine = get_machine()
	rows = get_item_rows()
	return [{
		"machine_name": machine["machine_name"],
		"no_of_machines": NO_OF_MACHINES,
		"net_prod_load": _load_days(sum(r["prod_hours"] for r in rows), machine["effective_runtime"]),
		"net_order_load": _load_days(sum(r["order_hours"] for r in rows), machine["effective_runtime"]),
	}]


@frappe.whitelist()
def get_machine_breakdown() -> dict:
	"""Return per-item calculation detail for the rolling machine (for the debug dialog)."""
	require_any_permission([("Rolling Machine", "read"), ("Item", "read")])
	machine = get_machine()
	rows = get_item_rows()
	total_prod_hours = sum(r["prod_hours"] for r in rows)
	total_order_hours = sum(r["order_hours"] for r in rows)
	for r in rows:
		r["prod_hours"] = round(r["prod_hours"], 2)
		r["order_hours"] = round(r["order_hours"], 2)

	return {
		"machine": machine["machine_name"],
		"no_of_machines": NO_OF_MACHINES,
		"oee": machine["oee"],
		"runtime": machine["runtime"],
		"effective_runtime": round(machine["effective_runtime"], 2),
		"items": rows,
		"total_prod_hours": round(total_prod_hours, 2),
		"total_order_hours": round(total_order_hours, 2),
		"net_prod_load": _load_days(total_prod_hours, machine["effective_runtime"]),
		"net_order_load": _load_days(total_order_hours, machine["effective_runtime"]),
	}
