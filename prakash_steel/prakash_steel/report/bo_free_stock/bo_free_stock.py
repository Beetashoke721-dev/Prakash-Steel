# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("On Hand Stock"),
			"fieldname": "on_hand_stock",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Bright Requirement"),
			"fieldname": "bright_requirement",
			"fieldtype": "Int",
			"width": 150,
		},
		{
			"label": _("Quantity Available to Sell"),
			"fieldname": "qty_available_to_sell",
			"fieldtype": "Int",
			"width": 190,
		},
		{
			"label": _("Open SO"),
			"fieldname": "open_so",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("Free Stock"),
			"fieldname": "free_stock",
			"fieldtype": "Int",
			"width": 130,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	filters = filters or {}

	conditions = ["i.disabled = 0", "i.custom_item_type = 'BO'"]
	params = []

	if filters.get("item_code"):
		conditions.append("i.name = %s")
		params.append(filters.get("item_code"))

	where_clause = " AND ".join(conditions)

	items = frappe.db.sql(
		f"""
		SELECT
			i.name AS item_code,
			i.item_name,
			i.custom_sku_type AS sku_type
		FROM `tabItem` i
		WHERE {where_clause}
		ORDER BY i.name
		""",
		tuple(params) if params else (),
		as_dict=True,
	)

	if not items:
		return []

	item_codes = [d.item_code for d in items]

	warehouses = _get_planning_engine_warehouses()
	stock_map = _get_stock_map(item_codes, warehouses)
	open_so_map = _get_open_so_map()
	bright_requirement_map = _get_bright_requirement_map()

	result = []
	for item in items:
		item_code = item.item_code
		on_hand_stock = flt(stock_map.get(item_code, 0))
		bright_requirement = flt(bright_requirement_map.get(item_code, 0))
		qty_available_to_sell = max(on_hand_stock - bright_requirement, 0)
		open_so = flt(open_so_map.get(item_code, 0))
		free_stock = max(qty_available_to_sell - open_so, 0)

		if not filters.get("include_zero_stock") and on_hand_stock == 0:
			continue

		result.append({
			"item_code": item_code,
			"item_name": item.item_name,
			"sku_type": item.sku_type,
			"on_hand_stock": math.ceil(on_hand_stock),
			"bright_requirement": math.ceil(bright_requirement),
			"qty_available_to_sell": math.ceil(qty_available_to_sell),
			"open_so": math.ceil(open_so),
			"free_stock": math.ceil(free_stock),
		})

	return result


def _get_planning_engine_warehouses() -> list[str]:
	doc = frappe.get_single("Planning Engine Warehouse Setup")
	warehouses = []
	for row in doc.table_cmgr:
		if row.warehouse:
			warehouses.append(row.warehouse)
	return warehouses


def _get_stock_map(item_codes: list[str], warehouses: list[str]) -> dict[str, float]:
	if not item_codes or not warehouses:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) AS stock
		FROM `tabBin`
		WHERE item_code IN %s
			AND warehouse IN %s
		GROUP BY item_code
		""",
		(tuple(item_codes), tuple(warehouses)),
		as_dict=True,
	)

	return {d.item_code: flt(d.stock) for d in rows}


def _get_open_so_map() -> dict[str, float]:
	rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) AS open_qty
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.custom_closed, 0) = 0
		GROUP BY soi.item_code
		""",
		as_dict=True,
	)

	return {d.item_code: flt(d.open_qty) for d in rows}


def _get_bright_plan_rows() -> list[dict]:
	from prakash_steel.prakash_steel.report.bright_plan.bright_plan import get_data as get_bright_plan_data

	return get_bright_plan_data()


def _get_bright_requirement_map() -> dict[str, float]:
	"""Bright Requirement for a BO item = sum of Child Stock Shortage across
	every Bright Plan row whose child_item_code matches it.

	A BO item can be a BOM component of multiple Bright Bar parents (and a
	single parent's demand can itself span multiple Bright Plan rows, one per
	MOQ/batch-size split) — every matching row's child_stock_shortage is
	summed, not just the first.
	"""
	bright_requirement_map: dict[str, float] = {}
	for row in _get_bright_plan_rows():
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue
		bright_requirement_map[child_item_code] = bright_requirement_map.get(
			child_item_code, 0
		) + flt(row.get("child_stock_shortage") or 0)

	return bright_requirement_map


@frappe.whitelist()
def get_bright_requirement_breakdown(item_code: str) -> dict:
	"""Step-by-step breakdown of how Bright Requirement is computed for a given
	BO item: every Bright Plan row whose child_item_code matches it (one row
	per Bright Bar parent / MOQ-batch split), each row's Child Stock Shortage,
	and the sum of those shortages that becomes this item's Bright Requirement
	— mirrors _get_bright_requirement_map exactly.
	"""
	if not frappe.has_permission("Item", "read"):
		frappe.throw(_("Not permitted to access Bright Requirement breakdowns."), frappe.PermissionError)

	item = frappe.db.get_value("Item", item_code, ["item_name", "custom_sku_type"], as_dict=True)
	if not item:
		frappe.throw(_("Item {0} not found").format(item_code))

	matching_rows = [row for row in _get_bright_plan_rows() if row.get("child_item_code") == item_code]

	if not matching_rows:
		return {
			"item_code": item_code,
			"item_name": item.item_name,
			"sku_type": item.custom_sku_type,
			"parents": [],
			"total_bright_requirement": 0,
			"no_parents": True,
		}

	parents = []
	total_bright_requirement = 0.0
	for row in matching_rows:
		shortage = flt(row.get("child_stock_shortage") or 0)
		total_bright_requirement += shortage
		parents.append({
			"parent_item": row.get("item_code"),
			"parent_item_name": row.get("item_name"),
			"machine": row.get("machine"),
			"sku_type": row.get("sku_type"),
			"production_qty": row.get("or_with_moq_batch_size"),
			"child_requirement": row.get("child_requirement"),
			"child_stock": row.get("child_stock"),
			"child_stock_soft_allocation_qty": row.get("child_stock_soft_allocation_qty"),
			"child_stock_shortage": math.ceil(shortage),
		})

	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"sku_type": item.custom_sku_type,
		"parents": parents,
		"total_bright_requirement": math.ceil(total_bright_requirement),
		"no_parents": False,
	}
