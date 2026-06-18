# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from prakash_steel.utils.lead_time import calculate_decoupled_lead_time


@frappe.whitelist()
def get_decoupled_lead_time(item_code):
	"""
	API method to get decoupled lead time for an item.
	This is called from the Item form to display the decoupled lead time.

	Args:
		item_code (str): Item code

	Returns:
		float: Decoupled lead time value
	"""
	if not frappe.has_permission("Item", "read"):
		frappe.throw(_("Not permitted to access decoupled lead time."), frappe.PermissionError)

	if not item_code:
		return 0

	# Check if item exists in database (not a new item being created)
	if not frappe.db.exists("Item", item_code):
		# Item doesn't exist yet (new item), return 0 or lead_time_days if available
		# This prevents errors when creating new items
		return 0

	try:
		decoupled_lead_time = calculate_decoupled_lead_time(item_code)
		return decoupled_lead_time
	except frappe.DoesNotExistError:
		# Item was deleted or doesn't exist, return 0 silently
		return 0
	except Exception as e:
		# Log error but don't show to user (silent failure)
		frappe.log_error(
			f"Error calculating decoupled lead time for item {item_code}: {str(e)}",
			"Get Decoupled Lead Time Error",
		)
		return 0
