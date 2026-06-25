# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	get_mrq_map,
	get_open_po_map,
	get_stock_map,
)


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data()
	return columns, data


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
		{
			"label": _("TOG"),
			"fieldname": "tog",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("On Hand Stock"),
			"fieldname": "on_hand_stock",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("On Order"),
			"fieldname": "on_order",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("MRQ"),
			"fieldname": "mrq",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Order Recommendation"),
			"fieldname": "order_recommendation",
			"fieldtype": "Int",
			"width": 160,
		},
		{
			"label": _("On Hand Status"),
			"fieldname": "on_hand_status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("On Hand Colour"),
			"fieldname": "on_hand_colour",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("MOQ"),
			"fieldname": "moq",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Net Order Recommendation"),
			"fieldname": "net_order_recommendation",
			"fieldtype": "Int",
			"width": 180,
		},
	]


def get_cs_tog_map(item_codes: set[str]) -> dict[str, float]:
	if not item_codes:
		return {}

	rows = frappe.db.get_all(
		"CS Tog table",
		filters=[
			["warehouse", "=", "Bright Bar Unit - PSPL"],
			["parenttype", "=", "Item"],
			["parentfield", "=", "custom_cs_tog_table"],
		],
		fields=["parent as item_code", "top_of_green"],
	)

	return {row.item_code: flt(row.top_of_green) for row in rows}


def get_stock_map_by_warehouse(item_codes: set[str], warehouse: str) -> dict[str, float]:
	if not item_codes:
		return {}

	rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) AS stock
		FROM `tabBin`
		WHERE item_code IN %s
		AND warehouse = %s
		GROUP BY item_code
		""",
		(tuple(item_codes), warehouse),
		as_dict=True,
	)

	return {row.item_code: flt(row.stock) for row in rows}


def get_data() -> list[dict]:
	items = frappe.db.get_all(
		"Item",
		filters={"custom_item_type": "CS", "custom_buffer_flag": "Buffer", "disabled": 0},
		fields=["name as item_code", "item_name", "safety_stock as tog", "min_order_qty as moq"],
	)

	if not items:
		return []

	item_codes = {d.item_code for d in items}
	stock_map = get_stock_map_by_warehouse(item_codes, "Bright Bar Unit - PSPL")
	open_po_map = get_open_po_map()
	mrq_map = get_mrq_map()
	cs_tog_map = get_cs_tog_map(item_codes)

	data = []
	for item in items:
		item_code = item.item_code
		tog = int(flt(cs_tog_map.get(item_code, 0)))
		on_hand_stock = int(flt(stock_map.get(item_code, 0)))
		on_order = int(flt(open_po_map.get(item_code, 0)))
		mrq = int(flt(mrq_map.get(item_code, 0)))
		order_recommendation = max(0, tog - on_hand_stock - on_order - mrq)
		on_hand_status_value = round((on_hand_stock / tog) * 100, 2) if tog else 0
		on_hand_status = f"{on_hand_status_value:.2f}%"
		moq = int(flt(item.moq))
		net_order_recommendation = max(order_recommendation, moq)

		if on_hand_status_value == 0:
			on_hand_colour = "BLACK"
		elif 0 < on_hand_status_value <= 34:
			on_hand_colour = "RED"
		elif 34 < on_hand_status_value <= 67:
			on_hand_colour = "YELLOW"
		elif 67 < on_hand_status_value <= 100:
			on_hand_colour = "GREEN"
		else:
			on_hand_colour = "WHITE"

		data.append(
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"tog": tog,
				"on_hand_stock": on_hand_stock,
				"mrq": mrq,
				"on_order": on_order,
				"order_recommendation": order_recommendation,
				"on_hand_status": on_hand_status,
				"on_hand_colour": on_hand_colour,
				"moq": moq,
				"net_order_recommendation": net_order_recommendation,
			}
		)

	data.sort(key=lambda x: float(x["on_hand_status"].rstrip("%")))
	return data
