# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters: dict[str, Any] | None = None):
	filters = filters or {}
	validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	report_summary = get_report_summary(data)
	return columns, data, None, None, report_summary


def validate_filters(filters):
	if not filters.get("item_code") and not filters.get("grade"):
		frappe.throw(_("Please select either Item or Grade."))

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("PO Date"), "fieldname": "po_date", "fieldtype": "Date", "width": 110},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 220},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": _("Item Grade"), "fieldname": "item_grade", "fieldtype": "Link", "options": "Item Grade", "width": 120},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Float", "width": 100},
		{
			"label": _("Purchase Order No."),
			"fieldname": "purchase_order_no",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 180,
		},
	]


def get_data(filters):
	where = ["po.docstatus = 1", "po.workflow_state != 'Cancelled'"]
	params: dict[str, Any] = {}

	if filters.get("from_date") and filters.get("to_date"):
		where.append("po.transaction_date BETWEEN %(from_date)s AND %(to_date)s")
		params["from_date"] = str(getdate(filters["from_date"]))
		params["to_date"] = str(getdate(filters["to_date"]))
	elif filters.get("from_date"):
		where.append("po.transaction_date >= %(from_date)s")
		params["from_date"] = str(getdate(filters["from_date"]))
	elif filters.get("to_date"):
		where.append("po.transaction_date <= %(to_date)s")
		params["to_date"] = str(getdate(filters["to_date"]))

	if filters.get("item_code"):
		where.append("poi.item_code = %(item_code)s")
		params["item_code"] = filters["item_code"]

	if filters.get("grade"):
		where.append("i.custom_grade = %(grade)s")
		params["grade"] = filters["grade"]

	where_clause = " AND ".join(where)

	return frappe.db.sql(
		f"""
		SELECT
			po.transaction_date AS po_date,
			po.supplier_name AS party_name,
			poi.item_name,
			i.custom_grade AS item_grade,
			poi.rate,
			po.name AS purchase_order_no
		FROM `tabPurchase Order` po
		INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		INNER JOIN `tabItem` i ON i.name = poi.item_code
		WHERE {where_clause}
		ORDER BY po.transaction_date DESC, po.name DESC
		""",
		params,
		as_dict=True,
	)


def get_report_summary(data):
	if not data:
		return None

	rates = [flt(row.get("rate")) for row in data if row.get("rate") is not None]
	if not rates:
		return None

	average_rate = sum(rates) / len(rates)

	return [
		{
			"value": average_rate,
			"indicator": "Blue",
			"label": _("Average Rate"),
			"datatype": "Float",
		}
	]
