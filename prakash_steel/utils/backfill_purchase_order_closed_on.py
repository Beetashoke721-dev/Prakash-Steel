# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""Backfill Purchase Order.custom_closed_on from Closed activity comments.

Uses the latest Label comment with content "Closed" on each Purchase Order,
matching the timestamp shown in the form timeline.
"""

import frappe


def backfill_closed_purchase_orders(*, only_if_empty: bool = True) -> int:
	if not frappe.db.has_column("Purchase Order", "custom_closed_on"):
		return 0

	empty_clause = "AND IFNULL(po.custom_closed_on, '') = ''" if only_if_empty else ""

	rows = frappe.db.sql(
		f"""
		SELECT po.name, closed_comment.creation AS closed_on
		FROM `tabPurchase Order` po
		INNER JOIN (
			SELECT reference_name, MAX(creation) AS creation
			FROM `tabComment`
			WHERE reference_doctype = 'Purchase Order'
				AND comment_type = 'Label'
				AND content = 'Closed'
			GROUP BY reference_name
		) closed_comment ON closed_comment.reference_name = po.name
		WHERE po.status = 'Closed'
			{empty_clause}
		""",
		as_dict=True,
	)

	for row in rows:
		frappe.db.set_value(
			"Purchase Order",
			row.name,
			"custom_closed_on",
			row.closed_on,
			update_modified=False,
		)

	if rows:
		frappe.db.commit()

	return len(rows)


def run_after_migrate() -> None:
	backfill_closed_purchase_orders(only_if_empty=True)
