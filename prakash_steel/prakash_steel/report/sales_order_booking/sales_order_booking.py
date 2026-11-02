# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, flt


def execute(filters=None) -> tuple[list, list]:
	if not filters:
		return [], []

	validate_filters(filters)

	columns = get_columns()
	conditions = get_conditions(filters)
	data = get_data(conditions, filters)

	return columns, data


def validate_filters(filters) -> None:
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))


def get_conditions(filters) -> str:
	conditions = ""
	if filters.get("from_date") and filters.get("to_date"):
		conditions += " and so.transaction_date between %(from_date)s and %(to_date)s"

	if filters.get("company"):
		conditions += " and so.company = %(company)s"

	if filters.get("sales_order"):
		conditions += " and so.name in %(sales_order)s"

	if filters.get("status"):
		conditions += " and so.status in %(status)s"

	if filters.get("customer"):
		conditions += " and so.customer = %(customer)s"

	if filters.get("item_code"):
		conditions += " and soi.item_code = %(item_code)s"

	return conditions


def get_data(conditions, filters) -> list[dict]:
	data = frappe.db.sql(
		f"""
        SELECT
            so.transaction_date as date,
            so.customer,
            cust.custom_customer_group_name as customer_group_name,
            soi.item_code,
            soi.description as description,
            soi.qty,
            soi.rate,
            so.payment_terms_template as payment_terms_template,
            so.custom_special_condition as special_condition,
            so.status,
            so.name as sales_order,
            soi.delivered_qty,
            so.custom_loading_and_cutting as loading_and_cutting,
            soi.delivery_date as delivery_date
        FROM
            `tabSales Order` so
        INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
        LEFT JOIN `tabCustomer` cust ON cust.name = so.customer
        WHERE
            so.status not in ('Stopped', 'On Hold')
            and so.docstatus = 1
            and IFNULL(soi.custom_closed, 0) = 0
            {conditions}
        ORDER BY
            so.transaction_date ASC,
            so.name,
            soi.item_code
    """,
		filters,
		as_dict=1,
	)

	for row in data:
		row["qty"] = int(flt(row.get("qty", 0)))
		row["delivered_qty"] = int(flt(row.get("delivered_qty", 0)))

		if row.get("delivery_date") and row.get("date"):
			row["lead_time"] = date_diff(row["delivery_date"], row["date"])
		else:
			row["lead_time"] = None

	return data


def get_columns() -> list[dict]:
	return [
		{"label": _("Sales Order Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 140,
		},
		{
			"label": _("Customer Group Name"),
			"fieldname": "customer_group_name",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Description"),
			"fieldname": "description",
			"fieldtype": "Small Text",
			"width": 150,
		},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Int", "width": 90},
		{
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 100,
		},
		{
			"label": _("Payment Terms Template"),
			"fieldname": "payment_terms_template",
			"fieldtype": "Link",
			"options": "Payment Terms Template",
			"width": 160,
		},
		{"label": _("Lead Time"), "fieldname": "lead_time", "fieldtype": "Int", "width": 90},
		{
			"label": _("Special Condition"),
			"fieldname": "special_condition",
			"fieldtype": "Data",
			"width": 130,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
		{
			"label": _("Sales Order"),
			"fieldname": "sales_order",
			"fieldtype": "Link",
			"options": "Sales Order",
			"width": 150,
		},
		{"label": _("Delivered Qty"), "fieldname": "delivered_qty", "fieldtype": "Int", "width": 100},
		{
			"label": _("Loading and Cutting"),
			"fieldname": "loading_and_cutting",
			"fieldtype": "Data",
			"width": 130,
		},
		{"label": _("Delivery Date"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 110},
	]
