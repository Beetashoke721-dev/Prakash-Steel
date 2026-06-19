import frappe


def execute() -> tuple[list, list]:
	"""Backfill custom_total_weight_slip_qty from item rows on existing Purchase Invoices."""
	if not frappe.db.has_column("Purchase Invoice", "custom_total_weight_slip_qty"):
		return
	if not frappe.db.has_column("Purchase Invoice Item", "custom_weight_slip_qty"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPurchase Invoice` pi
		LEFT JOIN (
			SELECT parent, SUM(IFNULL(custom_weight_slip_qty, 0)) AS total
			FROM `tabPurchase Invoice Item`
			GROUP BY parent
		) item_totals ON item_totals.parent = pi.name
		SET pi.custom_total_weight_slip_qty = IFNULL(item_totals.total, 0)
		"""
	)
