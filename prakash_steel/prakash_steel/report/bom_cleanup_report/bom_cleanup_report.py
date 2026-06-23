# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"label": "Parent Item", "fieldname": "parent_item", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": "BOM ID", "fieldname": "bom_id", "fieldtype": "Link", "options": "BOM", "width": 200},
		{"label": "Default", "fieldname": "is_default", "fieldtype": "Check", "width": 80},
		{"label": "Active", "fieldname": "is_active", "fieldtype": "Check", "width": 80},
		{"label": "Common Child Item Code", "fieldname": "child_item_code", "fieldtype": "Link", "options": "Item", "width": 200},
		{"label": "Child Item Name", "fieldname": "child_item_name", "fieldtype": "Data", "width": 200},
	]


def get_data(filters) -> list[dict]:
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

	# Only flag duplicates where the same child appears in more than one *active* BOM
	conditions.append("bom.is_active = 1")
	conditions.append("""
		(bom.item, bi.item_code) IN (
			SELECT bom2.item, bi2.item_code
			FROM `tabBOM` bom2
			JOIN `tabBOM Item` bi2 ON bi2.parent = bom2.name
			WHERE bom2.is_active = 1
			GROUP BY bom2.item, bi2.item_code
			HAVING COUNT(DISTINCT bom2.name) > 1
		)
	""")

	where = "WHERE " + " AND ".join(conditions)

	# Find (parent_item, child_item_code) pairs that appear in more than 1 BOM,
	# then return each individual BOM row for those pairs.
	return frappe.db.sql(f"""
		SELECT
			bom.item        AS parent_item,
			bom.name        AS bom_id,
			bom.is_default,
			bom.is_active,
			bi.item_code    AS child_item_code,
			bi.item_name    AS child_item_name
		FROM `tabBOM` bom
		JOIN `tabBOM Item` bi ON bi.parent = bom.name
		{where}
		ORDER BY bom.item, bi.item_code, bom.name
	""", values, as_dict=True)
