# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from prakash_steel.utils.lead_time import get_default_bom


@frappe.whitelist()
def check_item_has_bom(item_code):
	"""
	API method to check if an item has a BOM.
	
	Args:
		item_code (str): Item code
		
	Returns:
		bool: True if item has a BOM, False otherwise
	"""
	if not item_code:
		return False

	if not frappe.has_permission("Item", "read"):
		frappe.throw(frappe._("Not permitted to access BOM information."), frappe.PermissionError)
	
	# Check if item exists in database
	if not frappe.db.exists("Item", item_code):
		return False
	
	try:
		bom = get_default_bom(item_code)
		return bool(bom)
	except Exception as e:
		# Log error but return False (silent failure)
		frappe.log_error(
			f"Error checking BOM for item {item_code}: {str(e)}",
			"Check Item Has BOM Error",
		)
		return False
