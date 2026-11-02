"""Backfill Delivery Note Item.custom_expexted_delivery_date from the linked Sales Order Item's delivery_date."""

import frappe


def execute() -> None:
	frappe.db.sql(
		"""
		UPDATE `tabDelivery Note Item` dni
		INNER JOIN `tabSales Order Item` soi ON soi.name = dni.so_detail
		SET dni.custom_expexted_delivery_date = soi.delivery_date
		WHERE dni.so_detail IS NOT NULL
			AND dni.so_detail != ''
			AND (dni.custom_expexted_delivery_date IS NULL OR dni.custom_expexted_delivery_date = '0000-00-00')
			AND soi.delivery_date IS NOT NULL
		"""
	)

	frappe.db.commit()
