# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _active_doc_conditions(alias="p"):
	"""Submitted docs only — never Draft or Cancelled."""
	return f"""
		{alias}.docstatus = 1
		AND IFNULL({alias}.status, '') NOT IN ('Cancelled', 'Draft')
		AND IFNULL({alias}.workflow_state, '') NOT IN ('Cancelled', 'Draft')
	"""


@frappe.whitelist()
def get_top_items(doctype="Purchase Invoice", from_date=None, to_date=None, limit=5, order_by="amount"):
	"""
	Top N items by qty or amount, aggregated across submitted Purchase/Sales
	Invoices in the given date range. Used by the M.D Dashboard overview tables.
	"""
	if doctype not in ("Purchase Invoice", "Sales Invoice"):
		frappe.throw(_("Invalid doctype for top items report."))

	if not frappe.has_permission(doctype, "report"):
		frappe.throw(_("Not permitted to access {0} data.").format(doctype), frappe.PermissionError)

	order_field = "qty" if order_by == "qty" else "amount"

	child_table = "tab" + doctype + " Item"
	parent_table = "tab" + doctype

	conditions = _active_doc_conditions("p")
	params = {"limit": int(limit)}

	if from_date:
		conditions += " AND p.posting_date >= %(from_date)s"
		params["from_date"] = from_date
	if to_date:
		conditions += " AND p.posting_date <= %(to_date)s"
		params["to_date"] = to_date

	rows = frappe.db.sql(
		f"""
		SELECT
			c.item_code AS item_code,
			MAX(c.item_name) AS item_name,
			SUM(c.qty) AS qty,
			SUM(c.amount) AS amount
		FROM `{child_table}` c
		INNER JOIN `{parent_table}` p ON p.name = c.parent
		WHERE {conditions}
		GROUP BY c.item_code
		ORDER BY {order_field} DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)

	return rows


@frappe.whitelist()
def get_top_parties(doctype="Purchase Invoice", from_date=None, to_date=None, limit=5):
	"""
	Top N suppliers/customers by invoiced quantity, aggregated across submitted
	Purchase/Sales Invoices in the given date range. Used by the M.D Dashboard
	overview tables.
	"""
	if doctype not in ("Purchase Invoice", "Sales Invoice"):
		frappe.throw(_("Invalid doctype for top parties report."))

	if not frappe.has_permission(doctype, "report"):
		frappe.throw(_("Not permitted to access {0} data.").format(doctype), frappe.PermissionError)

	party_field = "supplier" if doctype == "Purchase Invoice" else "customer"
	party_name_field = "supplier_name" if doctype == "Purchase Invoice" else "customer_name"
	parent_table = "tab" + doctype
	child_table = "tab" + doctype + " Item"

	conditions = _active_doc_conditions("p")
	params = {"limit": int(limit)}

	if from_date:
		conditions += " AND p.posting_date >= %(from_date)s"
		params["from_date"] = from_date
	if to_date:
		conditions += " AND p.posting_date <= %(to_date)s"
		params["to_date"] = to_date

	rows = frappe.db.sql(
		f"""
		SELECT
			p.{party_field} AS party,
			MAX(p.{party_name_field}) AS party_name,
			SUM(c.qty) AS qty
		FROM `{parent_table}` p
		INNER JOIN `{child_table}` c ON c.parent = p.name
		WHERE {conditions}
		GROUP BY p.{party_field}
		ORDER BY qty DESC
		LIMIT %(limit)s
		""",
		params,
		as_dict=True,
	)

	return rows
