# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import get_first_day, get_last_day, nowdate


def execute(filters: dict[str, Any] | None = None):
	filters = _prepare_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	data.append(get_grand_total_row(data))
	return columns, data


def get_columns():
	return [
		{
			"label": "Party Name",
			"fieldname": "party_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": "Original Invoice No",
			"fieldname": "return_against",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 180,
		},
		{
			"label": "Original Invoice Date",
			"fieldname": "original_invoice_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "Credit Note No",
			"fieldname": "credit_note",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 180,
		},
		{
			"label": "Credit Note Date",
			"fieldname": "credit_note_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "Qty (Kg)",
			"fieldname": "qty_kg",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": "Gross Amount",
			"fieldname": "gross_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Taxable Amount",
			"fieldname": "taxable_amount",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Input CGST",
			"fieldname": "input_cgst",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Input SGST",
			"fieldname": "input_sgst",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": "Total Tax",
			"fieldname": "total_tax",
			"fieldtype": "Currency",
			"width": 120,
		},
	]


def _prepare_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
	filters = filters or {}
	today = nowdate()

	if not filters.get("from_date"):
		filters["from_date"] = get_first_day(today)
	if not filters.get("to_date"):
		filters["to_date"] = get_last_day(today)

	if filters["from_date"] > filters["to_date"]:
		frappe.throw("From Date cannot be after To Date.")

	return filters


def get_data(filters: dict[str, Any]):
	conditions = """
		cn.docstatus = 1
		AND cn.is_return = 1
		AND cn.posting_date BETWEEN %(from_date)s AND %(to_date)s
	"""

	if filters.get("company"):
		conditions += " AND cn.company = %(company)s"

	query = f"""
		SELECT
			cn.supplier_name AS party_name,
			cn.return_against AS return_against,
			original_pi.posting_date AS original_invoice_date,
			cn.name AS credit_note,
			cn.posting_date AS credit_note_date,
			COALESCE(pii.total_qty, 0) AS qty_kg,
			cn.base_grand_total AS gross_amount,
			cn.base_net_total AS taxable_amount,
			COALESCE(ptc.input_cgst, 0) AS input_cgst,
			COALESCE(ptc.input_sgst, 0) AS input_sgst,
			cn.total_taxes_and_charges AS total_tax
		FROM `tabPurchase Invoice` cn
		LEFT JOIN `tabPurchase Invoice` original_pi
			ON original_pi.name = cn.return_against
		LEFT JOIN (
			SELECT
				parent,
				SUM(qty) AS total_qty
			FROM `tabPurchase Invoice Item`
			GROUP BY parent
		) pii ON pii.parent = cn.name
		LEFT JOIN (
			SELECT
				parent,
				SUM(CASE WHEN account_head LIKE '%%CGST%%' THEN base_tax_amount ELSE 0 END) AS input_cgst,
				SUM(CASE WHEN account_head LIKE '%%SGST%%' THEN base_tax_amount ELSE 0 END) AS input_sgst
			FROM `tabPurchase Taxes and Charges`
			GROUP BY parent
		) ptc ON ptc.parent = cn.name
		WHERE {conditions}
		ORDER BY cn.supplier_name, cn.posting_date, cn.name
	"""

	return frappe.db.sql(query, filters, as_dict=True)


def get_grand_total_row(data):
	return {
		"party_name": "Grand Total",
		"return_against": "",
		"original_invoice_date": "",
		"credit_note": "",
		"credit_note_date": "",
		"qty_kg": sum((row.get("qty_kg") or 0) for row in data),
		"gross_amount": sum((row.get("gross_amount") or 0) for row in data),
		"taxable_amount": sum((row.get("taxable_amount") or 0) for row in data),
		"input_cgst": sum((row.get("input_cgst") or 0) for row in data),
		"input_sgst": sum((row.get("input_sgst") or 0) for row in data),
		"total_tax": sum((row.get("total_tax") or 0) for row in data),
	}
