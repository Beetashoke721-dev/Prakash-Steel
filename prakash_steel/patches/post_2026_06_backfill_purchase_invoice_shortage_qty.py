import frappe


def execute():
	"""Backfill custom_shortage_qty = total_qty - sum(item weight slip qty) on existing Purchase Invoices."""
	if not frappe.db.has_column("Purchase Invoice", "custom_shortage_qty"):
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
		SET pi.custom_shortage_qty = CAST(
			IFNULL(pi.total_qty, 0) - IFNULL(item_totals.total, 0) AS SIGNED
		)
		"""
	)
