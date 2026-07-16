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
		{
			"label": "Invoice Date",
			"fieldname": "invoice_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "Invoice Number",
			"fieldname": "invoice_number",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 170,
		},
		{
			"label": "Sales Order Number",
			"fieldname": "sales_order_number",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 170,
			"align": "left",
		},
		{
			"label": "Customer Name",
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": "Customer Group Name",
			"fieldname": "customer_group_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Place of Supply",
			"fieldname": "place_of_supply",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": "Category Name",
			"fieldname": "category_name",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 220,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": "Quantity",
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 110,
			"align": "left",
		},
		{
			"label": "Item Price",
			"fieldname": "item_price",
			"fieldtype": "Currency",
			"width": 120,
			"align": "left",
		},
	]


def get_data(filters) -> list[dict]:
	conditions = ["si.docstatus = 1"]

	if filters.get("company"):
		conditions.append("si.company = %(company)s")

	if filters.get("sales_invoice"):
		conditions.append("si.name = %(sales_invoice)s")

	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")

	if filters.get("customer_group_name"):
		conditions.append("cust.custom_customer_group_name = %(customer_group_name)s")

	if filters.get("sales_order"):
		conditions.append("sii.sales_order = %(sales_order)s")

	if filters.get("item_code"):
		conditions.append("sii.item_code = %(item_code)s")

	if filters.get("category_name"):
		conditions.append("i.custom_category_name = %(category_name)s")

	if filters.get("place_of_supply"):
		conditions.append("si.place_of_supply = %(place_of_supply)s")

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")

	query = f"""
		SELECT
			si.posting_date AS invoice_date,
			si.name AS invoice_number,
			sii.sales_order AS sales_order_number,
			si.customer_name AS customer_name,
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), '') AS customer_group_name,
			si.place_of_supply,
			i.custom_category_name AS category_name,
			sii.item_code,
			sii.item_name,
			ROUND(sii.qty, 0) AS qty,
			sii.rate AS item_price
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN `tabCustomer` cust ON cust.name = si.customer
		LEFT JOIN `tabItem` i ON i.name = sii.item_code
		WHERE {" AND ".join(conditions)}
		ORDER BY si.posting_date ASC, si.name ASC, sii.idx ASC
	"""

	return frappe.db.sql(query, filters, as_dict=True)
