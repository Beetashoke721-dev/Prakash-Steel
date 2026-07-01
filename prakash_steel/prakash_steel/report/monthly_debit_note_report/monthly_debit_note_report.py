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
			"fieldname": "original_invoice_no",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Original Invoice Date",
			"fieldname": "original_invoice_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": "Debit Note No",
			"fieldname": "debit_note_no",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 180,
		},
		{
			"label": "Debit Note Date",
			"fieldname": "debit_note_date",
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
			"label": "Input IGST",
			"fieldname": "input_igst",
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

	if not filters.get("company"):
		frappe.throw("Company is mandatory.")

	if not filters.get("from_date"):
		filters["from_date"] = get_first_day(today)
	if not filters.get("to_date"):
		filters["to_date"] = get_last_day(today)

	if filters["from_date"] > filters["to_date"]:
		frappe.throw("From Date cannot be after To Date.")

	return filters


def get_data(filters: dict[str, Any]):
	query = """
		SELECT
			pi.supplier_name AS party_name,
			pi.bill_no AS original_invoice_no,
			pi.bill_date AS original_invoice_date,
			pi.name AS debit_note_no,
			pi.posting_date AS debit_note_date,
			COALESCE(pii.qty_kg, 0) AS qty_kg,
			pi.grand_total AS gross_amount,
			pi.net_total AS taxable_amount,
			COALESCE(ptc.input_cgst, 0) AS input_cgst,
			COALESCE(ptc.input_sgst, 0) AS input_sgst,
			COALESCE(ptc.input_igst, 0) AS input_igst,
			pi.total_taxes_and_charges AS total_tax
		FROM `tabPurchase Invoice` pi
		LEFT JOIN (
			SELECT
				parent,
				SUM(qty) AS qty_kg
			FROM `tabPurchase Invoice Item`
			GROUP BY parent
		) pii ON pii.parent = pi.name
		LEFT JOIN (
			SELECT
				parent,
				SUM(CASE WHEN account_head LIKE %(cgst_pattern)s THEN tax_amount ELSE 0 END) AS input_cgst,
				SUM(CASE WHEN account_head LIKE %(sgst_pattern)s THEN tax_amount ELSE 0 END) AS input_sgst,
				SUM(CASE WHEN account_head LIKE %(igst_pattern)s THEN tax_amount ELSE 0 END) AS input_igst
			FROM `tabPurchase Taxes and Charges`
			GROUP BY parent
		) ptc ON ptc.parent = pi.name
		WHERE
			pi.is_return = 1
			AND pi.docstatus = 1
			AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND pi.company = %(company)s
		GROUP BY pi.name
		ORDER BY pi.posting_date ASC
	"""

	params = {
		**filters,
		"cgst_pattern": "%CGST%",
		"sgst_pattern": "%SGST%",
		"igst_pattern": "%IGST%",
	}

	return frappe.db.sql(query, params, as_dict=True)
