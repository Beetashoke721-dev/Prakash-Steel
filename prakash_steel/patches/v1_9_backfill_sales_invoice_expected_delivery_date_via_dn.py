"""Backfill Sales Invoice Item.expected_delivery_date for invoices created via the
Sales Order -> Delivery Note -> Sales Invoice flow (which the v1_7 patch/override
did not cover), falling back to the Sales Order Item's delivery_date directly
when the Delivery Note Item has no expected date recorded.
"""

import frappe


def execute() -> None:
	frappe.db.sql(
		"""
		UPDATE `tabSales Invoice Item` sii
		LEFT JOIN `tabDelivery Note Item` dni ON dni.name = sii.dn_detail
		LEFT JOIN `tabSales Order Item` soi ON soi.name = sii.so_detail
		SET sii.expected_delivery_date = COALESCE(dni.custom_expexted_delivery_date, soi.delivery_date)
		WHERE (sii.expected_delivery_date IS NULL OR sii.expected_delivery_date = '0000-00-00')
			AND (dni.custom_expexted_delivery_date IS NOT NULL OR soi.delivery_date IS NOT NULL)
		"""
	)

	frappe.db.commit()
