# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe

from prakash_steel.utils import cs_tog_utils
from prakash_steel.utils.cs_tog_utils import BRIGHT_WAREHOUSE as WAREHOUSE
from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_cs_tog_data(view_by: str = "Sale Quantity") -> dict:
	require_permission("Sales Invoice", "read")
	return cs_tog_utils.get_cs_tog_data(WAREHOUSE, view_by)


@frappe.whitelist()
def save_tog(items, fos=None):
	require_permission("Item", "write")
	return cs_tog_utils.save_tog(WAREHOUSE, items, fos)


@frappe.whitelist()
def update_tog(items, fos=None):
	require_permission("Item", "write")
	return cs_tog_utils.update_tog(WAREHOUSE, items, fos)


@frappe.whitelist()
def save_buffer_flag(item_code, buffer_flag, sku_type):
	require_permission("Item", "write")
	return cs_tog_utils.save_buffer_flag(item_code, buffer_flag, sku_type)


@frappe.whitelist()
def export_cs_tog_xlsx(data, filename="CS_BRIGHT_TOG"):
	require_permission("Sales Invoice", "read")
	cs_tog_utils.export_cs_tog_xlsx(data, filename)
