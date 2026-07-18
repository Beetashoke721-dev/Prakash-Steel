# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": _("ID"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 140,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Accepted Qty"),
			"fieldname": "stock_qty",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Rate"),
			"fieldname": "rate",
			"fieldtype": "Currency",
			"width": 110,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	"""Return data for the report."""
	filters = filters or {}

	conditions = ["pr.docstatus = 1"]
	values = {}

	if filters.get("from_date"):
		conditions.append("pr.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("pr.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("supplier"):
		conditions.append("pr.supplier = %(supplier)s")
		values["supplier"] = filters["supplier"]

	where_clause = " and ".join(conditions)

	return frappe.db.sql(
		f"""
		select
			pr.posting_date as posting_date,
			pr.name as name,
			pr.supplier as supplier,
			pri.item_code as item_code,
			pri.stock_qty as stock_qty,
			pri.rate as rate
		from `tabPurchase Receipt Item` pri
		inner join `tabPurchase Receipt` pr on pr.name = pri.parent
		where {where_clause}
		order by pr.posting_date desc, pr.name desc
		""",
		values,
		as_dict=True,
	)
