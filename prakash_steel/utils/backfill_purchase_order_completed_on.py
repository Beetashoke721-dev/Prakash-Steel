# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Backfill Purchase Order.custom_completed_on for Completed purchase orders.

Uses the Completed activity comment when present; otherwise falls back to the latest
linked submitted Purchase Receipt/Invoice time, then the Purchase Order modified time.
"""

import frappe

from prakash_steel.utils.purchase_order import get_completed_on_fallback


def backfill_completed_purchase_orders(*, only_if_empty: bool = True) -> int:
	if not frappe.db.has_column("Purchase Order", "custom_completed_on"):
		return 0

	empty_clause = "AND IFNULL(custom_completed_on, '') = ''" if only_if_empty else ""
	po_names = frappe.db.sql(
		f"""
		SELECT name
		FROM `tabPurchase Order`
		WHERE status = 'Completed'
			{empty_clause}
		""",
		pluck=True,
	)

	updated = 0
	for po_name in po_names:
		completed_on = get_completed_on_fallback(po_name)
		if not completed_on:
			continue

		frappe.db.set_value(
			"Purchase Order",
			po_name,
			"custom_completed_on",
			completed_on,
			update_modified=False,
		)
		updated += 1

	if updated:
		frappe.db.commit()

	return updated


def run_after_migrate() -> None:
	backfill_completed_purchase_orders(only_if_empty=True)
