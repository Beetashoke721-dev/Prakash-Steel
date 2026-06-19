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
			"label": "Sales Invoice",
			"fieldname": "sales_invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 150,
		},
		{"label": "Posting Date", "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": "Due Date", "fieldname": "due_date", "fieldtype": "Date", "width": 100},
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
		{
			"label": "Outstanding Amount",
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
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
        si.docstatus != 2
        AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
    """

	if filters.get("customer"):
		conditions += " AND si.customer = %(customer)s"

	if filters.get("status"):
		conditions += " AND si.status = %(status)s"

	if filters.get("item_code"):
		conditions += " AND sii.item_code = %(item_code)s"

	query = f"""
        SELECT
            si.name AS sales_invoice,
            si.posting_date,
            si.due_date,
            si.status,
            si.customer,
            si.grand_total,
            si.outstanding_amount,
            si.territory,

            sii.item_code,
            sii.item_name,
            sii.qty,
            sii.uom,
            sii.rate,
            sii.amount

        FROM
            `tabSales Invoice` si
        LEFT JOIN
            `tabSales Invoice Item` sii ON sii.parent = si.name

        WHERE {conditions}

        ORDER BY si.posting_date DESC, si.name
    """

	return frappe.db.sql(query, filters, as_dict=True)
