# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from prakash_steel.utils.whitelist_permissions import require_permission

PARTY_TYPES = ("regular", "service")
SERVICE_ITEM_GROUP = "Services"
TOP_N = 5


def _validate_dates(from_date, to_date):
	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))

	start = getdate(from_date)
	end = getdate(to_date)
	if start > end:
		frappe.throw(_("From Date cannot be after To Date."))

	return start, end


def _validate_party_type(party_type: str) -> str:
	party_type = (party_type or "regular").strip().lower()
	if party_type not in PARTY_TYPES:
		frappe.throw(_("Invalid party type: {0}").format(party_type))
	return party_type


def _item_filter_sql(party_type: str) -> str:
	if party_type == "regular":
		return "AND IFNULL(item.custom_store_item, 0) = 1"
	return "AND item.item_group = %(service_item_group)s"


def _optional_filters_sql(supplier=None, item_code=None) -> tuple[str, dict]:
	conditions = []
	values = {}
	if supplier:
		conditions.append("AND pi.supplier = %(supplier)s")
		values["supplier"] = supplier
	if item_code:
		conditions.append("AND pii.item_code = %(item_code)s")
		values["item_code"] = item_code
	return "\n\t\t\t".join(conditions), values


def _fetch_rows(from_date, to_date, party_type: str, supplier=None, item_code=None) -> list[dict]:
	"""Purchase Invoice item lines for the selected party type."""
	values = {
		"from_date": from_date,
		"to_date": to_date,
		"service_item_group": SERVICE_ITEM_GROUP,
	}
	item_filter = _item_filter_sql(party_type)
	optional_sql, optional_values = _optional_filters_sql(supplier, item_code)
	values.update(optional_values)

	query = f"""
		SELECT
			pi.posting_date AS posting_date,
			pi.supplier AS supplier,
			IFNULL(pi.supplier_name, pi.supplier) AS supplier_name,
			pii.item_code AS item_code,
			pii.stock_qty AS stock_qty,
			pii.stock_uom AS stock_uom,
			pii.rate AS rate,
			COALESCE(NULLIF(pii.warehouse, ''), pi.set_warehouse) AS set_accepted_warehouse,
			pii.amount AS amount,
			pi.name AS purchase_invoice
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		INNER JOIN `tabItem` item ON item.name = pii.item_code
		WHERE pi.docstatus = 1
			AND IFNULL(pi.is_return, 0) = 0
			AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
			{item_filter}
			{optional_sql}
		ORDER BY pi.posting_date, pi.name, pii.idx
	"""

	rows = frappe.db.sql(query, values, as_dict=True)
	for row in rows:
		row["stock_qty"] = flt(row.get("stock_qty"))
		row["rate"] = flt(row.get("rate"))
		row["amount"] = flt(row.get("amount"))
	return rows


def _top_parties(rows: list[dict], limit: int = TOP_N) -> list[dict]:
	"""Aggregate amount by supplier and return the top N (highest first)."""
	totals: dict[str, dict] = {}
	for row in rows:
		key = row.get("supplier") or row.get("supplier_name") or ""
		if not key:
			continue
		if key not in totals:
			totals[key] = {
				"supplier": key,
				"supplier_name": row.get("supplier_name") or key,
				"amount": 0.0,
			}
		totals[key]["amount"] += flt(row.get("amount"))

	ranked = sorted(totals.values(), key=lambda r: r["amount"], reverse=True)[:limit]
	for entry in ranked:
		entry["amount"] = round(flt(entry["amount"]), 2)
	return ranked


@frappe.whitelist()
def get_register_data(
	from_date=None, to_date=None, party_type="regular", supplier=None, item_code=None
):
	"""Return chart (top 5 parties) and detail rows for the selected tab."""
	require_permission("Purchase Invoice", "read")
	require_permission("Item", "read")
	if supplier:
		require_permission("Supplier", "read")

	start, end = _validate_dates(from_date, to_date)
	party_type = _validate_party_type(party_type)

	rows = _fetch_rows(start, end, party_type, supplier=supplier, item_code=item_code)
	return {
		"party_type": party_type,
		"chart": _top_parties(rows),
		"rows": rows,
	}


def _export_columns(party_type: str) -> list[tuple[str, str]]:
	service = party_type == "service"
	cols = [
		("posting_date", _("Posting Date")),
		("supplier_name", _("Supplier Name")),
		("item_code", _("Item Code")),
		("stock_qty", _("Qty") if service else _("Stock Qty")),
		("stock_uom", _("UOM") if service else _("Stock UOM")),
		("rate", _("Rate")),
	]
	if not service:
		cols.append(("set_accepted_warehouse", _("Set Accepted Warehouse")))
	cols.append(("amount", _("Amount")))
	return cols


def _export_dataset(from_date, to_date, party_type, supplier, item_code):
	supplier = None if supplier in ("", "undefined", "null") else supplier
	item_code = None if item_code in ("", "undefined", "null") else item_code

	require_permission("Purchase Invoice", "read")
	require_permission("Item", "read")
	if supplier:
		require_permission("Supplier", "read")

	start, end = _validate_dates(from_date, to_date)
	party_type = _validate_party_type(party_type)
	rows = _fetch_rows(start, end, party_type, supplier=supplier, item_code=item_code)
	if not rows:
		frappe.throw(_("Nothing to export."))
	return start, end, party_type, rows, _export_columns(party_type)


def _export_title(party_type: str) -> str:
	label = _("Service") if party_type == "service" else _("Regular")
	return _("Store & Service Item Purchase Register - {0}").format(label)


@frappe.whitelist()
def export_xlsx(from_date=None, to_date=None, party_type="regular", supplier=None, item_code=None):
	"""Download the register for the selected tab/filters as .xlsx."""
	from io import BytesIO

	import xlsxwriter
	from frappe.utils.xlsxutils import make_xlsx

	start, end, party_type, rows, columns = _export_dataset(
		from_date, to_date, party_type, supplier, item_code
	)

	data = [[label for _f, label in columns]]
	for row in rows:
		data.append(
			[
				str(row[f]) if f == "posting_date" else (row.get(f) if row.get(f) is not None else "")
				for f, _label in columns
			]
		)
	total_row = ["" for _c in columns]
	total_row[0] = _("Total")
	total_row[-1] = flt(sum(flt(r.get("amount")) for r in rows), 2)
	data.append(total_row)

	xlsx_file = BytesIO()
	wb = xlsxwriter.Workbook(xlsx_file, {"constant_memory": True})
	make_xlsx(data, party_type.capitalize()[:31], wb=wb)
	wb.close()
	xlsx_file.seek(0)

	frappe.response["filename"] = f"Purchase Register {party_type} {start} to {end}.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def export_pdf(from_date=None, to_date=None, party_type="regular", supplier=None, item_code=None):
	"""Download the register for the selected tab/filters as PDF."""
	from frappe.utils import fmt_money, formatdate
	from frappe.utils.pdf import get_pdf

	start, end, party_type, rows, columns = _export_dataset(
		from_date, to_date, party_type, supplier, item_code
	)
	numeric = {"stock_qty", "rate", "amount"}
	esc = frappe.utils.escape_html

	def cell(row, field):
		val = row.get(field)
		if field == "posting_date":
			return formatdate(val)
		if field in ("rate", "amount"):
			return fmt_money(val)
		if field == "stock_qty":
			return f"{flt(val):g}"
		return esc(val or "")

	head = "".join(
		f'<th class="{"r" if f in numeric else ""}">{esc(label)}</th>' for f, label in columns
	)
	body = "".join(
		"<tr>"
		+ "".join(f'<td class="{"r" if f in numeric else ""}">{cell(row, f)}</td>' for f, _l in columns)
		+ "</tr>"
		for row in rows
	)
	total = fmt_money(sum(flt(r.get("amount")) for r in rows))
	filters = [f"{_('From')}: {formatdate(start)}", f"{_('To')}: {formatdate(end)}"]
	if supplier:
		filters.append(f"{_('Supplier')}: {esc(supplier)}")
	if item_code:
		filters.append(f"{_('Item Code')}: {esc(item_code)}")

	html = f"""
	<style>
		body {{ font-family: sans-serif; font-size: 10px; }}
		h3 {{ margin: 0 0 4px; }}
		.meta {{ color: #555; margin-bottom: 8px; }}
		table {{ width: 100%; border-collapse: collapse; }}
		th, td {{ border: 1px solid #bbb; padding: 3px 5px; }}
		th {{ background: #eee; text-align: left; }}
		.r {{ text-align: right; }}
		tr {{ page-break-inside: avoid; }}
	</style>
	<h3>{esc(_export_title(party_type))}</h3>
	<div class="meta">{" | ".join(filters)}</div>
	<table>
		<thead><tr>{head}</tr></thead>
		<tbody>{body}</tbody>
		<tfoot><tr><td colspan="{len(columns) - 1}" class="r"><b>{_("Total")}</b></td>
			<td class="r"><b>{total}</b></td></tr></tfoot>
	</table>
	"""

	frappe.response["filename"] = f"Purchase Register {party_type} {start} to {end}.pdf"
	frappe.response["filecontent"] = get_pdf(html, {"orientation": "Landscape"})
	frappe.response["type"] = "pdf"
