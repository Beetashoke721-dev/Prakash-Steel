# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None) -> tuple[list, list]:
	columns = [
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 180
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220
		},
		{
			"label": "Item Type",
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 100
		}
	]

	items = frappe.db.sql("""
		SELECT
			i.item_code,
			i.item_name,
			i.custom_item_type AS item_type
		FROM `tabItem` i
		WHERE
			i.custom_item_type IN ('BB', 'RB')
			AND i.disabled = 0
			AND NOT EXISTS (
				SELECT 1 FROM `tabBOM`
				WHERE item = i.item_code
				AND is_active = 1
				AND docstatus = 1
			)
		ORDER BY i.custom_item_type, i.item_code
	""", as_dict=1)

	return columns, items
