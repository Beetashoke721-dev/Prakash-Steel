# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

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
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Open SO"),
			"fieldname": "open_so",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Free Stock"),
			"fieldname": "free_stock",
			"fieldtype": "Float",
			"width": 130,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	filters = filters or {}

	conditions = ["i.disabled = 0", "i.custom_item_type = 'Traded'"]
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

	result = []
	for item in items:
		item_code = item.item_code
		on_hand_stock = flt(stock_map.get(item_code, 0))
		open_so = flt(open_so_map.get(item_code, 0))
		free_stock = max(on_hand_stock - open_so, 0)

		if not filters.get("include_zero_stock") and on_hand_stock == 0:
			continue

		result.append({
			"item_code": item_code,
			"item_name": item.item_name,
			"sku_type": item.sku_type,
			"on_hand_stock": on_hand_stock,
			"open_so": open_so,
			"free_stock": free_stock,
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
