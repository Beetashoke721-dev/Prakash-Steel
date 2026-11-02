# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, nowdate

from prakash_steel.utils.whitelist_permissions import require_permission

TOTAL_FIELDS = (
	"qty",
	"taxable_value",
	"cgst_amt",
	"sgst_amt",
	"igst_amt",
	"total_taxes_and_charges",
	"gross_total",
)

RETURN_DOCTYPES = {
	# return_type: (parent doctype, child doctype, party field on the parent)
	"sales_return": ("Sales Invoice", "Sales Invoice Item", "customer_name"),
	"purchase_return": ("Purchase Invoice", "Purchase Invoice Item", "supplier_name"),
}

TAX_CHILD_DOCTYPES = {
	"Sales Invoice": "Sales Taxes and Charges",
	"Purchase Invoice": "Purchase Taxes and Charges",
}

NOTE_PREFIXES = {
	"debit_note": "DN",
	"credit_note": "CN",
}

SALES_RETURN_FLAG_FIELDS = {
	# Sales Invoice carries authoritative is_return/is_debit_note flags -- some CN/DN-series
	# docs don't follow the naming convention (or vice versa), so sales_return filters on
	# these flags directly rather than the name prefix. Purchase Invoice has no equivalent
	# is_debit_note flag, so purchase_return still uses NOTE_PREFIXES.
	"debit_note": "is_debit_note",
	"credit_note": "is_return",
}


def _validate_filters(filters: dict[str, Any]) -> None:
	from_date, to_date = filters.get("from_date"), filters.get("to_date")

	if not from_date and to_date:
		frappe.throw(_("From and To Dates are required."))
	elif from_date and to_date and date_diff(to_date, from_date) < 0:
		frappe.throw(_("To Date cannot be before From Date."))


def _date_conditions(filters: dict[str, Any]) -> tuple[str, dict]:
	if filters.get("from_date") and filters.get("to_date"):
		return " AND txn.posting_date BETWEEN %(from_date)s AND %(to_date)s", {
			"from_date": filters["from_date"],
			"to_date": filters["to_date"],
		}
	return "", {}


def _run_summary_query(parent_doctype: str, child_doctype: str, conditions: str, values: dict) -> list[dict]:
	"""total_taxes_and_charges mirrors Item-wise Sales/Purchase Register's "Total Tax" column:
	the sum of each item's Item Wise Tax Detail amounts for tax rows whose linked Account is
	of account_type "Tax" (matches ERPNext's own is_other_charges classification). Unlike the
	india_compliance-populated cgst_amount/sgst_amount/igst_amount fields (which only capture
	rows with a GST-specific gst_tax_type), this also nets in TDS/TCS rows whenever their
	account is tagged account_type "Tax" -- which it is in this company's chart of accounts.
	"""
	tax_doctype = TAX_CHILD_DOCTYPES[parent_doctype]

	query = f"""
		SELECT
			item.custom_desc_code AS desc_code,
			item.gst_hsn_code AS hsn_code,
			SUM(txn_item.qty) AS qty,
			SUM(txn_item.taxable_value) AS taxable_value,
			SUM(txn_item.cgst_amount) AS cgst_amt,
			SUM(txn_item.sgst_amount) AS sgst_amt,
			SUM(txn_item.igst_amount) AS igst_amt,
			SUM(IFNULL(item_tax.tax_total, 0)) AS total_taxes_and_charges,
			SUM(txn_item.taxable_value + IFNULL(item_tax.tax_total, 0)) AS gross_total
		FROM `tab{child_doctype}` txn_item
		INNER JOIN `tab{parent_doctype}` txn ON txn.name = txn_item.parent
		INNER JOIN `tabItem` item ON item.name = txn_item.item_code
		LEFT JOIN (
			SELECT iwtd.item_row AS item_row, SUM(iwtd.amount) AS tax_total
			FROM `tabItem Wise Tax Detail` iwtd
			INNER JOIN `tab{tax_doctype}` tax_row ON tax_row.name = iwtd.tax_row
			INNER JOIN `tabAccount` acc ON acc.name = tax_row.account_head
			WHERE iwtd.parenttype = %(parent_doctype)s AND acc.account_type = 'Tax'
			GROUP BY iwtd.item_row
		) item_tax ON item_tax.item_row = txn_item.name
		WHERE txn.docstatus = 1
			AND item.custom_desc_code IS NOT NULL
			AND item.custom_desc_code != ''
			{conditions}
		GROUP BY item.custom_desc_code
		ORDER BY item.custom_desc_code
	"""

	data = frappe.db.sql(query, {**values, "parent_doctype": parent_doctype}, as_dict=True)

	for row in data:
		row["qty"] = int(flt(row.get("qty", 0)))

	return data


def _run_return_detail_query(
	parent_doctype: str, child_doctype: str, party_field: str, conditions: str, values: dict
) -> list[dict]:
	"""Row-level return lines -- one row per invoice item, no desc-code grouping.

	The per-line tax total mirrors _run_summary_query: the sum of that item's Item Wise
	Tax Detail amounts for tax rows whose linked Account is of account_type "Tax".
	"""
	tax_doctype = TAX_CHILD_DOCTYPES[parent_doctype]

	query = f"""
		SELECT
			txn_item.item_code AS item_code,
			txn.name AS note_no,
			txn.return_against AS return_against,
			txn.posting_date AS posting_date,
			txn.{party_field} AS party_name,
			item.gst_hsn_code AS hsn_code,
			txn_item.qty AS qty,
			txn_item.taxable_value AS taxable_value,
			txn_item.cgst_amount AS cgst_amt,
			txn_item.sgst_amount AS sgst_amt,
			txn_item.igst_amount AS igst_amt,
			IFNULL(item_tax.tax_total, 0) AS total_taxes_and_charges,
			txn_item.taxable_value + IFNULL(item_tax.tax_total, 0) AS gross_total
		FROM `tab{child_doctype}` txn_item
		INNER JOIN `tab{parent_doctype}` txn ON txn.name = txn_item.parent
		INNER JOIN `tabItem` item ON item.name = txn_item.item_code
		LEFT JOIN (
			SELECT iwtd.item_row AS item_row, SUM(iwtd.amount) AS tax_total
			FROM `tabItem Wise Tax Detail` iwtd
			INNER JOIN `tab{tax_doctype}` tax_row ON tax_row.name = iwtd.tax_row
			INNER JOIN `tabAccount` acc ON acc.name = tax_row.account_head
			WHERE iwtd.parenttype = %(parent_doctype)s AND acc.account_type = 'Tax'
			GROUP BY iwtd.item_row
		) item_tax ON item_tax.item_row = txn_item.name
		WHERE txn.docstatus = 1
			AND IFNULL(item.custom_store_item, 0) = 0
			{conditions}
		ORDER BY txn.posting_date, txn.name, txn_item.idx
	"""

	data = frappe.db.sql(query, {**values, "parent_doctype": parent_doctype}, as_dict=True)

	for row in data:
		row["qty"] = int(flt(row.get("qty", 0)))

	return data


def _get_data(filters: dict[str, Any]) -> list[dict]:
	if filters.get("transaction_type") == "Purchase":
		parent_doctype, child_doctype = "Purchase Invoice", "Purchase Invoice Item"
	else:
		parent_doctype, child_doctype = "Sales Invoice", "Sales Invoice Item"

	conditions, values = _date_conditions(filters)
	if filters.get("exclude_returns"):
		conditions = " AND txn.is_return = 0" + conditions
		if parent_doctype == "Sales Invoice":
			# Debit Notes carry is_return = 0 (they're not returns), so the Sale tab needs
			# its own check to keep them out too -- Purchase Invoice has no such flag.
			conditions = " AND txn.is_debit_note = 0" + conditions
		else:
			# On the purchase side, is_return = 1 already covers "Debit Note" (return to
			# supplier). "Credit Note" here has no dedicated flag -- those docs are
			# otherwise ordinary (is_return = 0) and only identifiable by the CN naming
			# prefix, so the Purchase tab excludes them by name.
			values["cn_prefix"] = "CN%"
			conditions = " AND txn.name NOT LIKE %(cn_prefix)s" + conditions
	return _run_summary_query(parent_doctype, child_doctype, conditions, values)


def _get_return_data(return_type: str, note_type: str, filters: dict[str, Any]) -> list[dict]:
	"""Row-level return lines; submitted docs only, never draft or cancelled.

	sales_return filters on Sales Invoice's is_return/is_debit_note flags (see
	SALES_RETURN_FLAG_FIELDS) so it lines up with what the Sale/HSN Report tabs
	include or exclude. purchase_return has no such flag for debit vs credit notes,
	so it still relies on the DN/CN naming-series prefix.
	"""
	parent_doctype, child_doctype, party_field = RETURN_DOCTYPES[return_type]
	conditions, values = _date_conditions(filters)

	if return_type == "sales_return":
		conditions = f" AND txn.{SALES_RETURN_FLAG_FIELDS[note_type]} = 1" + conditions
	else:
		values["name_prefix"] = f"{NOTE_PREFIXES[note_type]}%"
		conditions = " AND txn.name LIKE %(name_prefix)s" + conditions

	return _run_return_detail_query(parent_doctype, child_doctype, party_field, conditions, values)


def _append_total_row(rows: list[dict], label_field: str = "desc_code") -> list[dict]:
	"""Append a Total footer row, summing the numeric columns. The "Total" label goes in
	``label_field`` -- the first column of whichever table this feeds."""
	if not rows:
		return rows

	total = {label_field: _("Total"), "row_type": "Total"}
	for field in TOTAL_FIELDS:
		total[field] = sum(flt(r.get(field)) for r in rows)
	total["qty"] = int(total["qty"])

	return rows + [total]


@frappe.whitelist()
def get_summary(transaction_type=None, from_date=None, to_date=None, exclude_returns=0):
	"""``exclude_returns`` drops is_return docs (credit/debit notes) so the figures are
	gross sales/purchases only -- the "Sale" tab. Without it (the "HSN Report" tab) returns
	are netted in."""
	transaction_type = transaction_type or "Sale"
	require_permission("Purchase Invoice" if transaction_type == "Purchase" else "Sales Invoice", "read")
	require_permission("Item", "read")

	filters = {
		"transaction_type": transaction_type,
		"from_date": from_date,
		"to_date": to_date,
		"exclude_returns": cint(exclude_returns),
	}
	_validate_filters(filters)

	return _append_total_row(_get_data(filters))


@frappe.whitelist()
def get_return_summary(return_type=None, note_type=None, from_date=None, to_date=None):
	if return_type not in RETURN_DOCTYPES:
		frappe.throw(_("Invalid return type."))
	if note_type not in NOTE_PREFIXES:
		frappe.throw(_("Invalid note type."))

	parent_doctype, _child_doctype, _party_field = RETURN_DOCTYPES[return_type]
	require_permission(parent_doctype, "read")
	require_permission("Item", "read")

	filters = {"from_date": from_date, "to_date": to_date}
	_validate_filters(filters)

	return _append_total_row(_get_return_data(return_type, note_type, filters), label_field="item_code")


def _get_planning_engine_warehouses() -> list[str]:
	"""Same source used by the *_free_stock reports (bright/rolled/traded/bo)."""
	doc = frappe.get_single("Planning Engine Warehouse Setup")
	return [row.warehouse for row in doc.table_cmgr if row.warehouse]


def _get_stock_data(as_of_date: str) -> list[dict]:
	"""Desc-code-wise stock balance and valuation as of a date, restricted to the Planning
	Engine warehouses.

	Bin only holds the *current* balance, so a past as-of-date is reconstructed from each
	item/warehouse's latest Stock Ledger Entry on or before that date -- qty_after_transaction
	for the on-hand qty and stock_value for the running valuation of that item/warehouse.
	"""
	warehouses = _get_planning_engine_warehouses()
	if not warehouses:
		return []

	return frappe.db.sql(
		"""
		SELECT
			item.custom_desc_code AS desc_code,
			SUM(bal.qty_after_transaction) AS on_hand_stock,
			SUM(bal.stock_value) AS stock_value
		FROM (
			SELECT
				sle.item_code,
				sle.warehouse,
				sle.qty_after_transaction,
				sle.stock_value,
				ROW_NUMBER() OVER (
					PARTITION BY sle.item_code, sle.warehouse
					ORDER BY sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC
				) AS rn
			FROM `tabStock Ledger Entry` sle
			WHERE sle.is_cancelled = 0
				AND sle.warehouse IN %(warehouses)s
				AND sle.posting_date <= %(as_of_date)s
		) bal
		INNER JOIN `tabItem` item ON item.name = bal.item_code
		WHERE bal.rn = 1
			AND item.custom_desc_code IS NOT NULL
			AND item.custom_desc_code != ''
		GROUP BY item.custom_desc_code
		ORDER BY item.custom_desc_code
		""",
		{"warehouses": tuple(warehouses), "as_of_date": as_of_date},
		as_dict=True,
	)


def _append_stock_total_row(rows: list[dict]) -> list[dict]:
	if not rows:
		return rows

	total_qty = sum(flt(r.get("on_hand_stock")) for r in rows)
	total_value = sum(flt(r.get("stock_value")) for r in rows)
	return rows + [
		{
			"desc_code": _("Total"),
			"on_hand_stock": total_qty,
			"stock_value": total_value,
			"row_type": "Total",
		}
	]


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_SHEET_NAME_RE = re.compile(r"[\[\]:*?/\\]")


def _export_cell(value: Any) -> Any:
	if value is None:
		return ""
	if isinstance(value, str):
		m = _DATE_RE.match(value)
		if m:
			return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
	return value


@frappe.whitelist()
def export_xlsx(rows=None, columns=None, title=None):
	"""Export whichever tab/subtab table is currently on screen to a single-sheet .xlsx.

	``columns`` is a JSON list of ``[fieldname, label]`` pairs mirroring the on-screen
	DataTable; ``rows`` is the JSON row list exactly as returned by the ``get_*`` methods
	(including the appended Total footer row). Both come from the page so the download
	matches the current view without re-running the query.
	"""
	import json
	from io import BytesIO

	import xlsxwriter

	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Item", "read")

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	rows = rows or []

	if isinstance(columns, str):
		columns = json.loads(columns or "[]")
	columns = columns or []

	if not columns:
		frappe.throw(_("Nothing to export."))

	title = (title or "Desc Code Wise Summary").strip() or "Desc Code Wise Summary"
	sheet_name = _SHEET_NAME_RE.sub(" ", title)[:31].strip() or "Sheet1"

	data = [[label for _fieldname, label in columns]]
	for row in rows:
		data.append([_export_cell(row.get(fieldname)) for fieldname, _label in columns])

	xlsx_file = BytesIO()
	wb = xlsxwriter.Workbook(xlsx_file, {"constant_memory": True})
	make_xlsx(data, sheet_name, wb=wb)
	wb.close()
	xlsx_file.seek(0)

	frappe.response["filename"] = f"{title}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def get_stock_summary(from_date=None, to_date=None):
	require_permission("Bin", "read")
	require_permission("Item", "read")

	_validate_filters({"from_date": from_date, "to_date": to_date})

	return _append_stock_total_row(_get_stock_data(to_date or nowdate()))
