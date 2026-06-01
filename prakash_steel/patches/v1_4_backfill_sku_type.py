"""Backfill custom_sku_type for all Items based on custom_item_type and custom_buffer_flag."""

import frappe


SKU_TYPE_MAP = {
	("BB", True): "BBMTA",
	("BB", False): "BBMTO",
	("RB", True): "RBMTA",
	("RB", False): "RBMTO",
	("BO", True): "BOTA",
	("BO", False): "BOTO",
	("RM", True): "PTA",
	("RM", False): "PTO",
	("Traded", True): "TRMTA",
	("Traded", False): "TRMTO",
}


def execute():
	items = frappe.db.sql(
		"""
		SELECT name, custom_item_type, custom_buffer_flag
		FROM `tabItem`
		WHERE custom_item_type IS NOT NULL AND custom_item_type != ''
		""",
		as_dict=True,
	)

	for item in items:
		is_buffer = (item.custom_buffer_flag or "Non-Buffer") == "Buffer"
		new_sku_type = SKU_TYPE_MAP.get((item.custom_item_type, is_buffer))

		frappe.db.set_value("Item", item.name, "custom_sku_type", new_sku_type, update_modified=False)

	frappe.db.commit()
