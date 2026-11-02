"""Backfill Sales Invoice Item.expected_delivery_date from the linked Sales Order Item's delivery_date."""

import frappe


def execute() -> None:
	frappe.db.sql(
		"""
		UPDATE `tabSales Invoice Item` sii
		INNER JOIN `tabSales Order Item` soi ON soi.name = sii.so_detail
		SET sii.expected_delivery_date = soi.delivery_date
		WHERE sii.so_detail IS NOT NULL
			AND sii.so_detail != ''
			AND (sii.expected_delivery_date IS NULL OR sii.expected_delivery_date = '0000-00-00')
			AND soi.delivery_date IS NOT NULL
		"""
	)

	frappe.db.commit()
