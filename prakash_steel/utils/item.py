# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from prakash_steel.utils.lead_time import update_decoupled_lead_time_for_item, get_default_bom


def update_decoupled_lead_time_on_item_save(doc, method=None) -> None:
	# Only update if item_code exists (not a new item being created)
	if not doc.name:
		return

	# Safety check: Item should never be submitted (it's a save doctype)
	# If somehow it's submitted, log a warning
	if doc.docstatus != 0:
		frappe.log_error(
			f"WARNING: Item {doc.name} has docstatus={doc.docstatus} (expected 0). "
			"Item is a save doctype and should not be submitted. "
			"Updating decoupled lead time anyway, but please investigate why Item was submitted.",
			"Item Docstatus Warning",
		)

	# Always update to ensure database has latest calculated value
	# This is safe because the calculation is idempotent
	try:
		from prakash_steel.utils.lead_time import calculate_decoupled_lead_time

		# Calculate the decoupled lead time
		decoupled_lead_time = calculate_decoupled_lead_time(doc.name)

		doc.custom_decoupled_lead_time = decoupled_lead_time

		if doc.has_value_changed("lead_time_days") or doc.has_value_changed("custom_buffer_flag"):
			# Use frappe.enqueue to update parent items asynchronously after save
			frappe.enqueue(
				"prakash_steel.utils.item._update_parent_items_lead_time",
				item_code=doc.name,
				now=False,  # Run after current transaction
			)
	except Exception as e:
		frappe.log_error(
			f"Error updating decoupled lead time for item {doc.name} on save: {str(e)}",
			"Item Lead Time Update Error",
		)


def update_decoupled_lead_time_on_bom_save(doc, method=None) -> None:
	# Only process submitted BOMs
	if doc.docstatus != 1:
		return

	# Update the main item's decoupled lead time
	if doc.item:
		try:
			update_decoupled_lead_time_for_item(doc.item)

			# Also update parent items that use this item in their BOM
			_update_parent_items_lead_time(doc.item)
		except Exception as e:
			frappe.log_error(
				f"Error updating decoupled lead time for item {doc.item} when BOM {doc.name} changed: {str(e)}",
				"BOM Lead Time Update Error",
			)


def _update_parent_items_lead_time(item_code) -> None:
	"""
	Update decoupled lead time for all parent items that use this item in their BOM.
	This is needed because when a child item's lead time changes, parent items are affected.

	Args:
		item_code: Item code whose parents need to be updated
	"""
	try:
		# Find all BOMs that use this item
		parent_boms = frappe.db.sql(
			"""
			SELECT DISTINCT b.item
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON b.name = bi.parent
			WHERE bi.item_code = %s
			AND b.is_active = 1
			AND b.docstatus = 1
			""",
			(item_code,),
			as_dict=True,
		)

		# Update each parent item
		for bom in parent_boms:
			parent_item = bom.item
			if parent_item:
				try:
					update_decoupled_lead_time_for_item(parent_item)
				except Exception as e:
					frappe.log_error(
						f"Error updating parent item {parent_item} lead time: {str(e)}",
						"Parent Item Lead Time Update Error",
					)
	except Exception as e:
		frappe.log_error(
			f"Error finding parent items for {item_code}: {str(e)}",
			"Parent Item Lead Time Update Error",
		)


def calculate_sku_type_on_validate(doc, method=None) -> None:
	"""
	Server-side calculation of custom_sku_type based on custom_item_type and custom_buffer_flag.
	Mirrors the client-side calculate_sku_type function in item.js.
	"""
	item_type = doc.get("custom_item_type")
	buffer_flag = doc.get("custom_buffer_flag") or "Non-Buffer"

	new_sku_type = None

	if item_type:
		is_buffer = buffer_flag == "Buffer"

		if item_type == "BB":
			new_sku_type = "BBMTA" if is_buffer else "BBMTO"
		elif item_type == "RB":
			new_sku_type = "RBMTA" if is_buffer else "RBMTO"
		elif item_type == "BO":
			new_sku_type = "BOTA" if is_buffer else "BOTO"
		elif item_type == "RM":
			new_sku_type = "PTA" if is_buffer else "PTO"
		elif item_type == "Traded":
			new_sku_type = "TRMTA" if is_buffer else "TRMTO"

	doc.custom_sku_type = new_sku_type


def validate_min_order_qty_and_batch_size(doc, method=None) -> None:
	"""
	Validate that min_order_qty and custom_batch_size are mutually exclusive.
	Only one field can have a value greater than 0 at a time.
	If min_order_qty > 0, custom_batch_size must be 0.
	If custom_batch_size > 0, min_order_qty must be 0.
	"""
	min_order_qty = doc.get("min_order_qty") or 0
	custom_batch_size = doc.get("custom_batch_size") or 0
	
	# Convert to float/int for comparison
	try:
		min_order_qty = float(min_order_qty) if min_order_qty else 0
		custom_batch_size = int(custom_batch_size) if custom_batch_size else 0
	except (ValueError, TypeError):
		min_order_qty = 0
		custom_batch_size = 0
	
	# Check if both fields have values greater than 0
	if min_order_qty > 0 and custom_batch_size > 0:
		frappe.throw(
			_("Min Order Qty and Batch Size cannot both have values greater than 0. "
			  "Please set one field to 0 before setting the other."),
			title=_("Validation Error")
		)
	
	# If min_order_qty > 0, ensure custom_batch_size is 0
	if min_order_qty > 0:
		if custom_batch_size > 0:
			doc.custom_batch_size = 0
	
	# If custom_batch_size > 0, ensure min_order_qty is 0
	if custom_batch_size > 0:
		if min_order_qty > 0:
			doc.min_order_qty = 0
