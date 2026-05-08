# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe

MONTH_MAP = {
	"January": 1,
	"February": 2,
	"March": 3,
	"April": 4,
	"May": 5,
	"June": 6,
	"July": 7,
	"August": 8,
	"September": 9,
	"October": 10,
	"November": 11,
	"December": 12,
}


def execute(filters=None):
	filters = filters or {}
	apply_financial_year_dates(filters)

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	return [
		{
			"label": "Months (Invoice Date)",
			"fieldname": "invoice_month",
			"fieldtype": "Data",
			"width": 150,
		},
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
		},
		{
			"label": "Customer Name",
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 220,
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
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 110},
		{"label": "Item Price", "fieldname": "item_price", "fieldtype": "Currency", "width": 120},
	]


def apply_financial_year_dates(filters):
	if not filters.get("financial_year"):
		return

	year_dates = frappe.db.get_value(
		"Fiscal Year",
		filters.get("financial_year"),
		["year_start_date", "year_end_date"],
		as_dict=True,
	)

	if not year_dates:
		return

	if not filters.get("from_date"):
		filters["from_date"] = year_dates.year_start_date

	if not filters.get("to_date"):
		filters["to_date"] = year_dates.year_end_date


def get_data(filters):
	conditions = ["si.docstatus = 1"]

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")

	if filters.get("company"):
		conditions.append("si.company = %(company)s")

	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")

	if filters.get("sales_order"):
		conditions.append("sii.sales_order = %(sales_order)s")

	if filters.get("item_code"):
		conditions.append("sii.item_code = %(item_code)s")

	if filters.get("category_name"):
		conditions.append("i.custom_category_name = %(category_name)s")

	if filters.get("place_of_supply"):
		conditions.append("si.place_of_supply = %(place_of_supply)s")

	if filters.get("month") in MONTH_MAP:
		filters["month_no"] = MONTH_MAP[filters.get("month")]
		conditions.append("MONTH(si.posting_date) = %(month_no)s")

	query = f"""
		SELECT
			DATE_FORMAT(si.posting_date, '%%b-%%y') AS invoice_month,
			si.posting_date AS invoice_date,
			si.name AS invoice_number,
			sii.sales_order AS sales_order_number,
			si.customer_name AS customer_name,
			si.place_of_supply,
			i.custom_category_name AS category_name,
			sii.item_name,
			sii.qty,
			sii.rate AS item_price
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		LEFT JOIN `tabItem` i ON i.name = sii.item_code
		WHERE {" AND ".join(conditions)}
		ORDER BY si.posting_date DESC, si.name DESC, sii.idx ASC
	"""

	return frappe.db.sql(query, filters, as_dict=True)
