# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Backfill Sales Invoice.custom_sales_order_date from linked Sales Orders.

Runs after migrate so Custom Field rows and DB columns exist (fixtures +
sync_customizations run before after_migrate hooks).
"""

import re
from datetime import datetime

import frappe


def _extract_sales_order_serial(so_name: str) -> str | None:
	if not so_name:
		return None

	so_name = str(so_name).strip()
	if not so_name:
		return None

	so_name = re.sub(r"(?<=/)\d{2}-\d{2}(?=/|$)", "", so_name)

	for match in re.finditer(r"\d+", so_name):
		token = match.group(0)
		if len(token) == 4 and 1900 <= int(token) <= 2099:
			continue
		return token

	return None


def _format_date(value) -> str | None:
	if not value:
		return None

	try:
		return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d-%m-%Y")
	except ValueError:
		return str(value)


def backfill_submitted_sales_invoices(*, only_if_empty: bool = True) -> None:
	if not frappe.db.has_column("Sales Invoice", "custom_sales_order_date"):
		return

	null_clause = ""
	if only_if_empty:
		null_clause = " AND IFNULL(si.custom_sales_order_date, '') = '' "

	rows = frappe.db.sql(
		f"""
		SELECT sii.parent AS sales_invoice, sii.sales_order
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
		  AND IFNULL(sii.sales_order, '') != ''
		  {null_clause}
		ORDER BY sii.parent, sii.idx
		""",
		as_dict=True,
	)

	if not rows:
		return

	refs_by_invoice = {}
	seen_serials_by_invoice = {}
	unique_so_names = set()

	for row in rows:
		invoice = row.sales_invoice
		so_name = row.sales_order
		serial = _extract_sales_order_serial(so_name)

		if not so_name or not serial:
			continue

		if invoice not in refs_by_invoice:
			refs_by_invoice[invoice] = []
			seen_serials_by_invoice[invoice] = set()

		if serial in seen_serials_by_invoice[invoice]:
			continue

		seen_serials_by_invoice[invoice].add(serial)
		refs_by_invoice[invoice].append(so_name)
		unique_so_names.add(so_name)

	if not refs_by_invoice or not unique_so_names:
		return

	so_rows = frappe.get_all(
		"Sales Order",
		filters={"name": ["in", list(unique_so_names)]},
		fields=["name", "transaction_date"],
	)
	so_date_map = {row.name: _format_date(row.transaction_date) for row in so_rows}

	for invoice, so_names in refs_by_invoice.items():
		seen_dates = set()
		ordered_dates = []

		for so_name in so_names:
			date_value = so_date_map.get(so_name)
			if date_value and date_value not in seen_dates:
				seen_dates.add(date_value)
				ordered_dates.append(date_value)

		frappe.db.set_value(
			"Sales Invoice",
			invoice,
			"custom_sales_order_date",
			", ".join(ordered_dates) if ordered_dates else None,
			update_modified=False,
		)

	frappe.db.commit()


def run_after_migrate():
	backfill_submitted_sales_invoices(only_if_empty=True)
