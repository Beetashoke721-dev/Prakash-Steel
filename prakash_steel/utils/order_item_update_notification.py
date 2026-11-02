# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.utils import flt, fmt_money, get_fullname, get_url

NOTIFICATION_RECIPIENTS = ["avinash@prakashsteel.com"]

DOCTYPE_ROUTES = {
	"Sales Order": "sales-order",
	"Purchase Order": "purchase-order",
}

PARTY_FIELDS = {
	"Sales Order": ("customer_name", "Customer"),
	"Purchase Order": ("supplier_name", "Supplier"),
}

ROW_COLORS = {
	"deleted": "#fdecea",
	"added": "#eafaf1",
}


@frappe.whitelist()
def update_child_qty_rate(parent_doctype, trans_items, parent_doctype_name, child_docname="items"):
	"""Wrap ERPNext's `update_child_qty_rate` (used by the "Update Items" dialog on
	Sales Order / Purchase Order) to notify a fixed recipient whenever items are updated.
	"""
	from erpnext.controllers.accounts_controller import (
		update_child_qty_rate as _update_child_qty_rate,
	)

	before_items = {}
	if parent_doctype in DOCTYPE_ROUTES:
		before_items = get_items_before_update(parent_doctype, parent_doctype_name)

	_update_child_qty_rate(parent_doctype, trans_items, parent_doctype_name, child_docname)

	if parent_doctype in DOCTYPE_ROUTES:
		send_item_update_notification(parent_doctype, parent_doctype_name, trans_items, before_items)


def get_items_before_update(parent_doctype, parent_doctype_name) -> dict:
	"""Snapshot of the child item rows as they stood before "Update Items" is applied,
	keyed by child docname, so the notification can show what actually changed."""
	rows = frappe.get_all(
		parent_doctype + " Item",
		filters={"parent": parent_doctype_name, "parenttype": parent_doctype},
		fields=["name", "item_code", "qty", "rate"],
	)
	return {row.name: row for row in rows}


def build_changed_rows(trans_items, before_items) -> list:
	"""Diff the submitted item rows against the pre-update snapshot.

	Returns a list of row dicts to render in the notification: rows whose qty/rate
	actually changed (type "updated"), rows removed (type "deleted"), rows newly
	added or whose item_code was swapped on an existing row (type "added").
	Rows with no change are left out entirely.
	"""
	changed_rows = []
	seen_docnames = set()

	for item in trans_items:
		if not item.get("item_code"):
			continue

		docname = item.get("docname")
		before = before_items.get(docname) if docname else None

		if before is None:
			changed_rows.append(
				{"type": "added", "item_code": item.get("item_code"), "qty": item.get("qty"), "rate": item.get("rate")}
			)
			continue

		seen_docnames.add(docname)

		if before.item_code != item.get("item_code"):
			changed_rows.append(
				{"type": "deleted", "item_code": before.item_code, "qty": before.qty, "rate": before.rate}
			)
			changed_rows.append(
				{"type": "added", "item_code": item.get("item_code"), "qty": item.get("qty"), "rate": item.get("rate")}
			)
			continue

		qty_changed = flt(before.qty) != flt(item.get("qty"))
		rate_changed = flt(before.rate) != flt(item.get("rate"))
		if qty_changed or rate_changed:
			changed_rows.append(
				{
					"type": "updated",
					"item_code": item.get("item_code"),
					"qty": before.qty,
					"updated_qty": item.get("qty") if qty_changed else 0,
					"rate": before.rate,
					"updated_rate": item.get("rate") if rate_changed else 0,
				}
			)

	for docname, before in before_items.items():
		if docname not in seen_docnames:
			changed_rows.append(
				{"type": "deleted", "item_code": before.item_code, "qty": before.qty, "rate": before.rate}
			)

	return changed_rows


def send_item_update_notification(parent_doctype, parent_doctype_name, trans_items, before_items) -> None:
	"""Email NOTIFICATION_RECIPIENTS with only the item rows that actually changed."""
	try:
		items = json.loads(trans_items)
	except (TypeError, ValueError):
		items = []

	changed_rows = build_changed_rows(items, before_items)
	if not changed_rows:
		return

	route = DOCTYPE_ROUTES[parent_doctype]
	subject = f"{parent_doctype} Updated - {parent_doctype_name}"
	updated_by = get_fullname(frappe.session.user)

	party_field, party_label = PARTY_FIELDS[parent_doctype]
	party_name = frappe.db.get_value(parent_doctype, parent_doctype_name, party_field)

	cell_style = "text-align: center; border: 1px solid #999; padding: 5px;"

	message = f"""
	<p>Dear Team,</p>

	<p>Items on the following {parent_doctype} were updated using the <strong>Update Items</strong> action by <strong>{updated_by}</strong>:</p>

	<p><strong>{parent_doctype}:</strong> <a href="{get_url()}/app/{route}/{parent_doctype_name}">{parent_doctype_name}</a>
	&nbsp;&nbsp;&nbsp; <strong>{party_label}:</strong> {party_name or ""}</p>

	<table cellpadding="0" cellspacing="0" style="border-collapse: collapse; border: 1px solid #999; width: 100%; margin-top: 10px;">
		<thead>
			<tr style="background-color: #f0f0f0;">
				<th style="{cell_style}">Item Code</th>
				<th style="{cell_style}">Qty</th>
				<th style="{cell_style}">Updated Qty</th>
				<th style="{cell_style}">Rate</th>
				<th style="{cell_style}">Updated Rate</th>
			</tr>
		</thead>
		<tbody>
	"""

	has_added_or_deleted = False
	for row in changed_rows:
		row_bg = ""
		if row["type"] in ROW_COLORS:
			row_bg = f'background-color: {ROW_COLORS[row["type"]]};'
			has_added_or_deleted = True

		qty = fmt_money(row.get("qty"), precision=0)
		rate = fmt_money(row.get("rate"), precision=2)
		updated_qty = fmt_money(row.get("updated_qty", 0), precision=0)
		updated_rate = fmt_money(row.get("updated_rate", 0), precision=2)

		message += f"""
			<tr style="{row_bg}">
				<td style="{cell_style}">{row["item_code"]}</td>
				<td style="{cell_style}">{qty}</td>
				<td style="{cell_style}">{updated_qty}</td>
				<td style="{cell_style}">{rate}</td>
				<td style="{cell_style}">{updated_rate}</td>
			</tr>
		"""

	message += """
		</tbody>
	</table>
	"""

	if has_added_or_deleted:
		message += """
		<p style="margin-top: 10px;">
			<strong style="color: #c0392b;">Red:</strong> Item is deleted<br>
			<strong style="color: #1e8449;">Green:</strong> Item is added
		</p>
		<p>Best regards,<br>System Notification</p>
		"""
	else:
		message += """
		<p style="margin-top: 32px;">Best regards,<br>System Notification</p>
		"""

	try:
		frappe.sendmail(
			recipients=NOTIFICATION_RECIPIENTS,
			subject=subject,
			message=message,
			reference_doctype=parent_doctype,
			reference_name=parent_doctype_name,
		)
	except Exception as e:
		frappe.log_error(
			f"Error sending Update Items notification for {parent_doctype} {parent_doctype_name}: {str(e)}",
			"Update Items Notification Error",
		)
