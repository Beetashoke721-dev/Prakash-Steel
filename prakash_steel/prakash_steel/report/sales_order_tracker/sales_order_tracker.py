# Copyright (c) 2025, beetashoke chakraborty and contributors
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
			"label": "Sales Order",
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 150,
		},
		{"label": "Date", "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
		{
			"label": "Customer",
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 150,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 120},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 80},
		{"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 120},
		{"label": "Amount", "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 150},
		{"label": "Delivery Date", "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
		{
			"label": "Territory",
			"fieldname": "territory",
			"fieldtype": "Link",
			"options": "Territory",
			"width": 120,
		},
	]


def get_data(filters) -> list[dict]:
	# Set default date range if not provided (1 month span)
	if not filters.get("from_date"):
		filters["from_date"] = frappe.utils.add_months(frappe.utils.today(), -1)
	if not filters.get("to_date"):
		filters["to_date"] = frappe.utils.today()

	conditions = """
        so.docstatus != 2
        AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
    """

	if filters.get("customer"):
		conditions += " AND so.customer = %(customer)s"

	if filters.get("status"):
		conditions += " AND so.status = %(status)s"

	if filters.get("item_code"):
		conditions += " AND soi.item_code = %(item_code)s"

	query = f"""
        SELECT
            so.name AS sales_order,
            so.transaction_date,
            so.status,
            so.customer,
            so.grand_total,
            so.delivery_date,
            so.territory,

            soi.item_code,
            soi.item_name,
            soi.qty,
            soi.uom,
            soi.rate,
            soi.amount

        FROM
            `tabSales Order` so
        LEFT JOIN
            `tabSales Order Item` soi ON soi.parent = so.name

        WHERE {conditions}

        ORDER BY so.transaction_date DESC, so.name
    """

	return frappe.db.sql(query, filters, as_dict=True)
