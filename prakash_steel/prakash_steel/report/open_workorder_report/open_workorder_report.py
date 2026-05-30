# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Date"),
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Item"),
			"fieldname": "item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": _("Colour"),
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Item SKU Type"),
			"fieldname": "item_sku_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Child Item Code"),
			"fieldname": "child_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": _("Child Item Qty"),
			"fieldname": "child_item_qty",
			"fieldtype": "Float",
			"precision": 2,
			"width": 120,
		},
		{
			"label": _("Child SKU Type"),
			"fieldname": "child_sku_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Machine"),
			"fieldname": "machine",
			"fieldtype": "Data",
			"width": 130,
		},
	]


def _calculate_sku_type(buffer_flag, item_type):
	is_buffer = (buffer_flag or "") == "Buffer"
	mapping = {
		"BB": ("BBMTA", "BBMTO"),
		"RB": ("RBMTA", "RBMTO"),
		"BO": ("BOTA", "BOTO"),
		"RM": ("PTA", "PTO"),
		"Traded": ("TRMTA", "TRMTO"),
	}
	pair = mapping.get(item_type)
	if not pair:
		return ""
	return pair[0] if is_buffer else pair[1]


def get_data(filters=None):
	work_orders = frappe.db.sql(
		"""
		SELECT
			wo.name AS work_order,
			wo.planned_start_date AS date,
			wo.production_item AS item,
			ROUND(wo.qty) AS qty
		FROM `tabWork Order` wo
		WHERE wo.docstatus = 1
			AND wo.status NOT IN ('Completed', 'Stopped', 'Cancelled','Closed')
		ORDER BY wo.planned_start_date ASC, wo.name
		""",
		as_dict=True,
	)

	if not work_orders:
		return []

	# Collect all parent item codes for item master lookup
	parent_item_codes = list({wo.item for wo in work_orders})

	item_master_rows = frappe.db.sql(
		"""
		SELECT name, custom_item_type, custom_buffer_flag
		FROM `tabItem`
		WHERE name IN %s
		""",
		(parent_item_codes,),
		as_dict=True,
	)
	item_master_map = {
		r.name: {
			"item_type": r.custom_item_type or "",
			"buffer_flag": r.custom_buffer_flag or "Non-Buffer",
		}
		for r in item_master_rows
	}

	# Fetch child items for all work orders at once
	wo_names = [wo.work_order for wo in work_orders]
	child_rows = frappe.db.sql(
		"""
		SELECT
			woi.parent AS work_order,
			woi.item_code AS child_item_code,
			woi.required_qty AS child_item_qty
		FROM `tabWork Order Item` woi
		WHERE woi.parent IN %s
		ORDER BY woi.idx ASC
		""",
		(wo_names,),
		as_dict=True,
	)

	# Collect all child item codes for item master lookup
	child_item_codes = list({r.child_item_code for r in child_rows})
	child_master_map = {}
	if child_item_codes:
		child_master_rows = frappe.db.sql(
			"""
			SELECT name, custom_item_type, custom_buffer_flag
			FROM `tabItem`
			WHERE name IN %s
			""",
			(child_item_codes,),
			as_dict=True,
		)
		child_master_map = {
			r.name: {
				"item_type": r.custom_item_type or "",
				"buffer_flag": r.custom_buffer_flag or "Non-Buffer",
			}
			for r in child_master_rows
		}

	# Group child rows by work order
	children_by_wo = {}
	for cr in child_rows:
		children_by_wo.setdefault(cr.work_order, []).append(cr)

	data = []
	for wo in work_orders:
		parent_master = item_master_map.get(wo.item, {})
		item_sku_type = _calculate_sku_type(parent_master.get("buffer_flag"), parent_master.get("item_type"))

		base = {
			"date": wo.date,
			"item": wo.item,
			"qty": wo.qty,
			"colour": "",  # logic TBD
			"item_sku_type": item_sku_type,
			"machine": "",  # logic TBD
		}

		children = children_by_wo.get(wo.work_order, [])
		if children:
			for child in children:
				child_master = child_master_map.get(child.child_item_code, {})
				child_sku_type = _calculate_sku_type(
					child_master.get("buffer_flag"), child_master.get("item_type")
				)
				row = base.copy()
				row["child_item_code"] = child.child_item_code
				row["child_item_qty"] = flt(child.child_item_qty)
				row["child_sku_type"] = child_sku_type
				data.append(row)
		else:
			row = base.copy()
			row["child_item_code"] = None
			row["child_item_qty"] = None
			row["child_sku_type"] = None
			data.append(row)

	return data
