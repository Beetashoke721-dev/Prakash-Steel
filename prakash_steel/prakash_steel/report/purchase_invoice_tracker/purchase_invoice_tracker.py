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
			"label": "Purchase Invoice ID",
			"fieldname": "purchase_invoice_id",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 150,
		},
		{
			"label": "Status",
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Quantity",
			"fieldname": "quantity",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Date",
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "Supplier",
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150,
		},
		{
			"label": "Grand Total",
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def get_data(filters) -> list[dict]:
	# Set default date range if not provided
	if not filters.get("from_date"):
		filters["from_date"] = "2020-01-01"
	if not filters.get("to_date"):
		filters["to_date"] = "2030-12-31"

	conditions = """
		pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
	"""

	if filters.get("supplier"):
		conditions += " AND pi.supplier = %(supplier)s"

	# Add workflow status filter if specified
	if filters.get("workflow_status"):
		conditions += " AND pi.workflow_state = %(workflow_status)s"

	# Simple query to get Purchase Invoice data
	query = f"""
		SELECT
			pi.name AS purchase_invoice_id,
			pi.status AS status,
			COALESCE(SUM(pii.qty), 0) AS quantity,
			pi.posting_date AS date,
			pi.supplier,
			pi.grand_total

		FROM
			`tabPurchase Invoice` pi
		LEFT JOIN
			`tabPurchase Invoice Item` pii ON pii.parent = pi.name

		WHERE {conditions}

		GROUP BY pi.name, pi.status, pi.posting_date, pi.supplier, pi.grand_total

		ORDER BY pi.posting_date DESC, pi.name
	"""

	return frappe.db.sql(query, filters, as_dict=True)
