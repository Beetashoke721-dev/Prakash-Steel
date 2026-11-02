"""Backfill custom_sku_type for CS Items — missed by v1_4_backfill_sku_type before CS was handled."""

import frappe


def execute() -> None:
	items = frappe.db.sql(
		"""
		SELECT name, custom_buffer_flag
		FROM `tabItem`
		WHERE custom_item_type = 'CS'
		""",
		as_dict=True,
	)

	for item in items:
		is_buffer = (item.custom_buffer_flag or "Non-Buffer") == "Buffer"
		new_sku_type = "CSMTA" if is_buffer else "CSMTO"

		frappe.db.set_value("Item", item.name, "custom_sku_type", new_sku_type, update_modified=False)

	frappe.db.commit()
