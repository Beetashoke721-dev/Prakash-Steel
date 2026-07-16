# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 100},
		{"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 100},
		{
			"label": "ID",
			"fieldname": "id",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 160,
		},
		{
			"label": "Sales Order",
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 160,
		},
		{
			"label": "Customer",
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{"label": "Place of Supply", "fieldname": "place_of_supply", "fieldtype": "Data", "width": 130},
		{"label": "Category Name", "fieldname": "category_name", "fieldtype": "Data", "width": 150},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 160,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 120},
		{
			"label": "Warehouse",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 180,
		},
	]


def get_data(filters) -> list[dict]:
	if not filters.get("from_date"):
		filters["from_date"] = frappe.utils.add_months(frappe.utils.today(), -1)
	if not filters.get("to_date"):
		filters["to_date"] = frappe.utils.today()

	conditions = """
		si.docstatus = 1
		AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND i.custom_item_type = 'BB'
	"""

	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"

	if filters.get("warehouse"):
		conditions += " AND sii.warehouse = %(warehouse)s"

	if filters.get("item_code"):
		conditions += " AND sii.item_code = %(item_code)s"

	if filters.get("category_name"):
		conditions += " AND i.custom_category_name = %(category_name)s"

	query = f"""
		SELECT
			DATE_FORMAT(si.posting_date, '%%b %%Y') AS month,
			si.posting_date AS date,
			si.name AS id,
			sii.sales_order,
			si.customer,
			si.place_of_supply,
			i.custom_category_name AS category_name,
			sii.item_code,
			sii.item_name,
			sii.qty,
			sii.rate,
			sii.warehouse

		FROM
			`tabSales Invoice` si
		LEFT JOIN
			`tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN
			`tabItem` i ON i.name = sii.item_code

		WHERE {conditions}

		ORDER BY si.posting_date ASC, si.name ASC
	"""

	return frappe.db.sql(query, filters, as_dict=True)
