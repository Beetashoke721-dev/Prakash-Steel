# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "Parent Item", "fieldname": "parent_item", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "BOM ID", "fieldname": "bom_id", "fieldtype": "Link", "options": "BOM", "width": 160},
		{"label": "BOM Qty", "fieldname": "bom_qty", "fieldtype": "Float", "width": 90},
		{"label": "Default", "fieldname": "is_default", "fieldtype": "Check", "width": 80},
		{"label": "Active", "fieldname": "is_active", "fieldtype": "Check", "width": 80},
		{"label": "Child Item Code", "fieldname": "child_item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "Child Qty", "fieldname": "child_qty", "fieldtype": "Float", "width": 90},
	]


def get_data(filters):
	conditions = []
	values = {}

	if filters.get("item"):
		conditions.append("bom.item = %(item)s")
		values["item"] = filters["item"]

	if filters.get("is_default"):
		conditions.append("bom.is_default = %(is_default)s")
		values["is_default"] = 1 if filters["is_default"] == "Yes" else 0

	if filters.get("is_active"):
		conditions.append("bom.is_active = %(is_active)s")
		values["is_active"] = 1 if filters["is_active"] == "Yes" else 0

	where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

	return frappe.db.sql(f"""
		SELECT
			bom.item        AS parent_item,
			bom.name        AS bom_id,
			bom.quantity    AS bom_qty,
			bom.is_default,
			bom.is_active,
			bi.item_code    AS child_item_code,
			bi.qty          AS child_qty
		FROM `tabBOM` bom
		LEFT JOIN `tabBOM Item` bi ON bi.parent = bom.name
		{where}
		ORDER BY bom.item, bom.name, bi.idx
	""", values, as_dict=True)
