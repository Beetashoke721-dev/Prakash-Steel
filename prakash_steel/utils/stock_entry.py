# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
# from prakash_steel.utils.lead_time import update_decoupled_lead_time_for_item


def validate_vehicle_no_for_material_transfer(doc, method=None) -> None:
	"""
	Validate that vehicle_no is mandatory when stock_entry_type/purpose is Material Transfer.

	Args:
		doc: Stock Entry document
		method: Method name (for compatibility with doc_events)
	"""
	# Check both possible field names for Stock Entry Type
	stock_entry_type = getattr(doc, "stock_entry_type", None) or getattr(doc, "purpose", None)

	# Check if it's Material Transfer
	if stock_entry_type == "Material Transfer":
		# Check for vehicle_no field
		vehicle_no = getattr(doc, "vehicle_no", None)

		# Validate vehicle_no is not empty
		if not vehicle_no or (isinstance(vehicle_no, str) and not vehicle_no.strip()):
			frappe.throw(
				_("Vehicle No is mandatory when Stock Entry Type is Material Transfer."),
				title=_("Validation Error"),
			)


# def update_decoupled_lead_time_on_stock_entry_submit(doc, method=None):
# 	"""
# 	Update decoupled lead time for items when Stock Entry is submitted.
# 	This hook is called when Stock Entry is submitted, specifically for stock conditions.

# 	Args:
# 		doc: Stock Entry document
# 		method: Method name (for compatibility with doc_events)
# 	"""
# 	# Only process if Stock Entry is submitted (docstatus = 1)
# 	if doc.docstatus != 1:
# 		return

# 	# Get unique items from Stock Entry items
# 	items_to_update = set()

# 	for item in doc.items:
# 		item_code = item.item_code
# 		if item_code:
# 			items_to_update.add(item_code)

# 	# Update decoupled lead time for each item
# 	for item_code in items_to_update:
# 		try:
# 			# Check if item has a BOM (finished good)
# 			from prakash_steel.utils.lead_time import get_default_bom

# 			bom = get_default_bom(item_code)

# 			if bom:
# 				# This is a finished good, update its decoupled lead time
# 				update_decoupled_lead_time_for_item(item_code)

# 				# Also check if any BOM items need updating
# 				# (in case sub-assembly or raw material lead times changed)
# 				bom_doc = frappe.get_doc("BOM", bom)
# 				for bom_item in bom_doc.items:
# 					child_item = bom_item.item_code
# 					child_bom = get_default_bom(child_item)
# 					if child_bom:
# 						# This is a sub-assembly, update it too
# 						update_decoupled_lead_time_for_item(child_item)
# 		except Exception as e:
# 			frappe.log_error(
# 				f"Error updating decoupled lead time for item {item_code} in Stock Entry {doc.name}: {str(e)}",
# 				"Stock Entry Lead Time Update Error",
# 			)
