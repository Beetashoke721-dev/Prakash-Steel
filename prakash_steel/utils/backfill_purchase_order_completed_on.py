# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Backfill Purchase Order.custom_completed_on from Completed activity comments.

Uses the latest Label comment with content "Completed" on each Purchase Order,
matching the timestamp shown in the form timeline.
"""

import frappe


def backfill_completed_purchase_orders(*, only_if_empty: bool = True) -> int:
	if not frappe.db.has_column("Purchase Order", "custom_completed_on"):
		return 0

	empty_clause = "AND IFNULL(po.custom_completed_on, '') = ''" if only_if_empty else ""

	rows = frappe.db.sql(
		f"""
		SELECT po.name, completed_comment.creation AS completed_on
		FROM `tabPurchase Order` po
		INNER JOIN (
			SELECT reference_name, MAX(creation) AS creation
			FROM `tabComment`
			WHERE reference_doctype = 'Purchase Order'
				AND comment_type = 'Label'
				AND content = 'Completed'
			GROUP BY reference_name
		) completed_comment ON completed_comment.reference_name = po.name
		WHERE po.status = 'Completed'
			{empty_clause}
		""",
		as_dict=True,
	)

	for row in rows:
		frappe.db.set_value(
			"Purchase Order",
			row.name,
			"custom_completed_on",
			row.completed_on,
			update_modified=False,
		)

	if rows:
		frappe.db.commit()

	return len(rows)


def run_after_migrate() -> None:
	backfill_completed_purchase_orders(only_if_empty=True)
