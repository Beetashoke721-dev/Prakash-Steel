"""Fallback to item_name when Sales Invoice print row description is empty."""

import frappe


OLD = "{{ item.description }}"
NEW = "{{ item.description or item.item_name }}"


def execute():
	if not frappe.db.exists("Print Format", "Custom Sales Invoice"):
		return

	html = frappe.db.get_value("Print Format", "Custom Sales Invoice", "html") or ""
	if OLD not in html or NEW in html:
		return

	frappe.db.set_value(
		"Print Format",
		"Custom Sales Invoice",
		"html",
		html.replace(OLD, NEW, 1),
		update_modified=True,
	)
