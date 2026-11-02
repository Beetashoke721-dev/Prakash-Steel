# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import date_diff, flt

# Item whose PSP/LC/... invoices are broken out into a separate "(LC)" row.
WASTAGE_ITEM = "WASTAGE SCRAP OF STEEL BARS & RODS SCRAP"
# Non-scrap item pulled in as the final row.
RENT_ITEM = "Rent"
# Invoice name (bill no.) prefix that identifies a labour-charge / LC bill.
LC_PREFIX = "PSP/LC/"


def execute(filters: dict[str, Any] | None = None):
	filters = filters or {}

	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def validate_filters(filters: dict[str, Any]) -> None:
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif from_date and to_date and date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Data",
			"width": 300,
		},
		{
			"label": _("HSN Code"),
			"fieldname": "hsn_code",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Qty"),
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Taxable Value"),
			"fieldname": "taxable_value",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("CGST Amt"),
			"fieldname": "cgst_amt",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("SGST Amt"),
			"fieldname": "sgst_amt",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("IGST Amt"),
			"fieldname": "igst_amt",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Total Taxes and Charges"),
			"fieldname": "total_taxes_and_charges",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Gross Total"),
			"fieldname": "gross_total",
			"fieldtype": "Currency",
			"width": 130,
		},
	]


def get_data(filters: dict[str, Any]) -> list[dict]:
	conditions = ""
	values = {
		"wastage_item": WASTAGE_ITEM,
		"rent_item": RENT_ITEM,
		"lc_like": f"{LC_PREFIX}%",
	}
	if filters.get("from_date") and filters.get("to_date"):
		conditions = " AND txn.posting_date BETWEEN %(from_date)s AND %(to_date)s"
		values["from_date"] = filters["from_date"]
		values["to_date"] = filters["to_date"]

	# For WASTAGE SCRAP only, split lines billed on a PSP/LC/... invoice into a
	# separate "(LC)WASTAGE ..." bucket; its base row then excludes those lines.
	# Every other Scrap item stays a single row. "Rent" is appended last.
	query = f"""
		SELECT
			CASE
				WHEN item.name = %(wastage_item)s AND txn.name LIKE %(lc_like)s
					THEN CONCAT('(LC)', item.name)
				ELSE item.name
			END AS item_code,
			item.gst_hsn_code AS hsn_code,
			SUM(txn_item.qty) AS qty,
			SUM(txn_item.taxable_value) AS taxable_value,
			SUM(txn_item.cgst_amount) AS cgst_amt,
			SUM(txn_item.sgst_amount) AS sgst_amt,
			SUM(txn_item.igst_amount) AS igst_amt,
			SUM(txn_item.igst_amount + txn_item.cgst_amount + txn_item.sgst_amount) AS total_taxes_and_charges,
			SUM(txn_item.custom_gross_amount) AS gross_total
		FROM `tabSales Invoice Item` txn_item
		INNER JOIN `tabSales Invoice` txn ON txn.name = txn_item.parent
		INNER JOIN `tabItem` item ON item.name = txn_item.item_code
		WHERE txn.docstatus = 1
			AND (item.custom_category_name = 'Scrap' OR item.name = %(rent_item)s)
			{conditions}
		GROUP BY item_code, item.gst_hsn_code
		ORDER BY
			(MAX(item.name) = %(rent_item)s) ASC,
			MAX(item.name) ASC,
			MAX(CASE WHEN txn.name LIKE %(lc_like)s THEN 1 ELSE 0 END) ASC
	"""

	data = frappe.db.sql(query, values, as_dict=True)

	for row in data:
		row["qty"] = int(flt(row.get("qty", 0)))

	return data
