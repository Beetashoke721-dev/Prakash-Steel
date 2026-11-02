# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Match TDS/TCS tax rows by account or description (is_tax_withholding_account is often unset).
RATE_FROM_TEXT_PATTERN = re.compile(r"@\s*(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)


def execute(filters: dict[str, Any] | None = None) -> tuple[list, list]:
	filters = frappe._dict(filters or {})
	_validate_filters(filters)
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def _validate_filters(filters: frappe._dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be before To Date"))


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Party Name"),
			"fieldname": "party_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("PAN"),
			"fieldname": "pan",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Supplier Invoice No"),
			"fieldname": "supplier_invoice_no",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("TDS/TCS %"),
			"fieldname": "tds_tcs_percent",
			"fieldtype": "Float",
			"width": 100,
			"precision": 3,
			"disable_total": 1,
		},
		{
			"label": _("TDS/TCS Value"),
			"fieldname": "tds_tcs_value",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Supplier Taxable Value"),
			"fieldname": "taxable_value",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Voucher Type"),
			"fieldname": "voucher_type",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Against Voucher Number"),
			"fieldname": "against_voucher",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
	]


def get_data(filters: frappe._dict) -> list[dict]:
	voucher_type = (filters.get("voucher_type") or "").strip()
	rows: list[dict] = []

	if voucher_type in ("", "Purchase Invoice"):
		rows.extend(_get_purchase_invoice_rows(filters))
	if voucher_type in ("", "Sales Invoice"):
		rows.extend(_get_sales_invoice_rows(filters))

	rows.sort(key=lambda r: (r.get("posting_date") or "", r.get("against_voucher") or ""))
	return rows


def _get_purchase_invoice_rows(filters: frappe._dict) -> list[dict]:
	conditions, values = _base_conditions(filters, alias="pi")
	if filters.get("party"):
		conditions.append("pi.supplier LIKE %(party)s")
		values["party"] = f"%{filters.party}%"

	where_clause = " AND ".join(conditions)
	pan_select = "IFNULL(s.pan, '')" if frappe.db.has_column("Supplier", "pan") else "IFNULL(s.tax_id, '')"

	query = f"""
		SELECT
			pi.posting_date AS posting_date,
			pi.supplier AS party_name,
			{pan_select} AS pan,
			pi.bill_no AS supplier_invoice_no,
			tax.rate AS rate,
			tax.tax_amount AS tax_amount,
			tax.account_head AS account_head,
			tax.description AS description,
			pi.total AS taxable_value,
			'Purchase Invoice' AS voucher_type,
			pi.name AS against_voucher,
			pi.status AS status
		FROM
			`tabPurchase Invoice` pi
		INNER JOIN
			`tabPurchase Taxes and Charges` tax
				ON tax.parent = pi.name AND tax.parenttype = 'Purchase Invoice'
		LEFT JOIN
			`tabSupplier` s ON s.name = pi.supplier
		WHERE
			{where_clause}
			AND (
				IFNULL(tax.is_tax_withholding_account, 0) = 1
				OR tax.account_head LIKE %(tds_like)s
				OR tax.account_head LIKE %(tcs_like)s
				OR tax.description LIKE %(tds_like)s
				OR tax.description LIKE %(tcs_like)s
			)
		ORDER BY
			pi.posting_date ASC,
			pi.name ASC
	"""
	values.update({"tds_like": "%TDS%", "tcs_like": "%TCS%"})
	return [_normalize_row(row) for row in frappe.db.sql(query, values=values, as_dict=True)]


def _get_sales_invoice_rows(filters: frappe._dict) -> list[dict]:
	conditions, values = _base_conditions(filters, alias="si")
	if filters.get("party"):
		conditions.append("si.customer LIKE %(party)s")
		values["party"] = f"%{filters.party}%"

	where_clause = " AND ".join(conditions)
	pan_select = "IFNULL(c.pan, '')" if frappe.db.has_column("Customer", "pan") else "IFNULL(c.tax_id, '')"

	query = f"""
		SELECT
			si.posting_date AS posting_date,
			si.customer AS party_name,
			{pan_select} AS pan,
			NULL AS supplier_invoice_no,
			tax.rate AS rate,
			tax.tax_amount AS tax_amount,
			tax.account_head AS account_head,
			tax.description AS description,
			si.total AS taxable_value,
			'Sales Invoice' AS voucher_type,
			si.name AS against_voucher,
			si.status AS status
		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Taxes and Charges` tax
				ON tax.parent = si.name AND tax.parenttype = 'Sales Invoice'
		LEFT JOIN
			`tabCustomer` c ON c.name = si.customer
		WHERE
			{where_clause}
			AND (
				IFNULL(tax.is_tax_withholding_account, 0) = 1
				OR tax.account_head LIKE %(tds_like)s
				OR tax.account_head LIKE %(tcs_like)s
				OR tax.description LIKE %(tds_like)s
				OR tax.description LIKE %(tcs_like)s
			)
		ORDER BY
			si.posting_date ASC,
			si.name ASC
	"""
	values.update({"tds_like": "%TDS%", "tcs_like": "%TCS%"})
	return [_normalize_row(row) for row in frappe.db.sql(query, values=values, as_dict=True)]


def _base_conditions(filters: frappe._dict, alias: str) -> tuple[list[str], dict]:
	conditions = [
		f"{alias}.company = %(company)s",
		f"{alias}.posting_date >= %(from_date)s",
		f"{alias}.posting_date <= %(to_date)s",
	]
	values = {
		"company": filters.company,
		"from_date": getdate(filters.from_date),
		"to_date": getdate(filters.to_date),
	}

	if filters.get("include_cancelled"):
		conditions.append(f"{alias}.docstatus IN (1, 2)")
	else:
		conditions.append(f"{alias}.docstatus = 1")

	return conditions, values


def _normalize_row(row: dict) -> dict:
	taxable_value = flt(row.get("taxable_value"))
	tax_amount = abs(flt(row.get("tax_amount")))
	row["tds_tcs_value"] = tax_amount
	row["taxable_value"] = taxable_value
	row["tds_tcs_percent"] = _resolve_rate(row, taxable_value, tax_amount)
	row.pop("rate", None)
	row.pop("tax_amount", None)
	row.pop("account_head", None)
	row.pop("description", None)
	return row


def _resolve_rate(row: dict, taxable_value: float, tax_amount: float) -> float:
	rate = abs(flt(row.get("rate")))
	if rate:
		return rate

	for text in (row.get("description") or "", row.get("account_head") or ""):
		match = RATE_FROM_TEXT_PATTERN.search(text)
		if match:
			return flt(match.group(1))

	if taxable_value:
		return flt((tax_amount / taxable_value) * 100, 3)

	return 0.0
