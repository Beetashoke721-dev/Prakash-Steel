# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from prakash_steel.utils.lead_time import calculate_decoupled_lead_time, get_default_bom
from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def check_custom_field_exists() -> None:
	"""API method to check if custom_decoupled_lead_time field exists in database"""
	require_permission("Item", "read")
	try:
		db_name = frappe.conf.db_name
		result = frappe.db.sql(
			"""
			SELECT COUNT(*) as count
			FROM information_schema.COLUMNS 
			WHERE TABLE_SCHEMA = %s 
			AND TABLE_NAME = 'tabItem' 
			AND COLUMN_NAME = 'custom_decoupled_lead_time'
			""",
			(db_name,),
			as_dict=True,
		)

		column_exists = result and result[0]["count"] > 0

		response = {
			"column_exists": column_exists,
			"message": "Column exists" if column_exists else "Column does not exist",
		}

		if column_exists:
			# Get sample data
			sample = frappe.db.sql(
				"""
				SELECT name, custom_decoupled_lead_time 
				FROM `tabItem` 
				WHERE custom_decoupled_lead_time IS NOT NULL 
				AND custom_decoupled_lead_time != 0
				LIMIT 5
				""",
				as_dict=True,
			)
			response["sample_items"] = sample

			# Get counts
			total = frappe.db.sql("SELECT COUNT(*) as count FROM `tabItem`", as_dict=True)[0]["count"]
			with_values = frappe.db.sql(
				"SELECT COUNT(*) as count FROM `tabItem` WHERE custom_decoupled_lead_time IS NOT NULL AND custom_decoupled_lead_time != 0",
				as_dict=True,
			)[0]["count"]
			response["total_items"] = total
			response["items_with_values"] = with_values

		return response
	except Exception as e:
		return {"error": str(e), "traceback": frappe.get_traceback()}


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	"""Define report columns"""
	return [
		{
			"fieldname": "item_code",
			"label": "Item Code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 300,
		},
		{
			"fieldname": "item_name",
			"label": "Item Name",
			"fieldtype": "Link",
			"options": "Item",
			"width": 250,
		},
		{"fieldname": "lead_time_days", "label": "Lead Time", "fieldtype": "Float", "width": 100},
		{
			"fieldname": "custom_decoupled_lead_time",
			"label": "Replenishment Lead Time",
			"fieldtype": "Float",
			"width": 120,
		},
		{"fieldname": "custom_buffer_flag", "label": "Buffer Flag", "fieldtype": "Data", "width": 100},
		{
			"fieldname": "buffer_img",
			"label": "Buffer Img",
			"fieldtype": "Attach Image",
			"width": 80,
		},
		{
			"fieldname": "buffer_impact",
			"label": "Buffer Impact",
			"fieldtype": "Data",
			"width": 120,
			"hidden": 1,
		},
		{"fieldname": "has_children", "label": "Has Children", "fieldtype": "Check", "width": 0, "hidden": 1},
		{
			"fieldname": "parent_item",
			"label": "Parent Item",
			"fieldtype": "Link",
			"options": "Item",
			"width": 0,
			"hidden": 1,
		},
		{"fieldname": "level", "label": "Level", "fieldtype": "Int", "width": 0, "hidden": 1},
	]


def get_all_items_recursively(bom_name, parent_item=None, level=0, visited_boms=None, item_groups_cache=None) -> list:
	"""
	Recursively get all items from a BOM and its nested BOMs.

	Args:
		bom_name: BOM name to process
		parent_item: Parent item code (for hierarchy tracking)
		level: Current nesting level (0 = top level)
		visited_boms: Set of visited BOMs to prevent circular references
		item_groups_cache: Dict to cache item_group lookups (for performance)

	Returns:
		list: List of dicts with item information including level, parent, and has_children flag
	"""
	if visited_boms is None:
		visited_boms = set()

	if item_groups_cache is None:
		item_groups_cache = {}

	# Prevent circular references
	if bom_name in visited_boms:
		return []

	visited_boms.add(bom_name)
	items_list = []

	try:
		# Get BOM document
		bom_doc = frappe.get_doc("BOM", bom_name)

		# Collect all item codes in this BOM for batch lookup
		bom_item_codes = [bom_item.item_code for bom_item in bom_doc.items]

		# Batch fetch item_groups for all items in this BOM (optimization)
		if bom_item_codes:
			items_to_fetch = [code for code in bom_item_codes if code not in item_groups_cache]
			if items_to_fetch:
				item_group_data = frappe.db.sql(
					"""
					SELECT name, item_group
					FROM `tabItem`
					WHERE name IN %s
					""",
					(tuple(items_to_fetch),),
					as_dict=True,
				)

				# Cache the results
				for item in item_group_data:
					item_groups_cache[item.name] = item.item_group

		# Process each item in the BOM
		for bom_item in bom_doc.items:
			item_code = bom_item.item_code

			# Optimization: Check item_group first - Raw Materials don't have BOMs
			# This avoids unnecessary BOM lookup for raw materials
			item_group = item_groups_cache.get(item_code)

			# Check if this item has a BOM (nested BOM)
			has_children = False
			child_bom = None

			# If it's not a Raw Material, check for BOM
			if not (item_group and item_group == "Raw Material"):
				child_bom = get_default_bom(item_code)
				if child_bom and child_bom not in visited_boms:
					has_children = True

			# Add this item to the list
			items_list.append(
				{
					"item_code": item_code,
					"parent_item": parent_item,
					"level": level,
					"has_children": has_children,
				}
			)

			# If it has children, recursively get items from child BOM
			if has_children and child_bom:
				# Recursively get items from child BOM
				# Pass the same visited_boms and cache to prevent cycles and reuse cache
				child_items = get_all_items_recursively(
					child_bom,
					parent_item=item_code,
					level=level + 1,
					visited_boms=visited_boms,  # Same set to prevent cycles
					item_groups_cache=item_groups_cache,  # Reuse cache for performance
				)
				items_list.extend(child_items)

	except frappe.DoesNotExistError:
		frappe.log_error(f"BOM {bom_name} does not exist", "BOM Wise Buffer Details Report Error")
	except Exception as e:
		frappe.log_error(
			f"Error processing BOM {bom_name}: {str(e)}",
			"BOM Wise Buffer Details Report Error",
		)

	return items_list


def get_data(filters) -> list[dict]:
	"""Get report data based on filters"""
	data = []

	if not filters or not filters.get("bom"):
		return data

	bom_name = filters.get("bom")

	try:
		# Get BOM document to get the main item
		bom_doc = frappe.get_doc("BOM", bom_name)
		main_item_code = bom_doc.item if bom_doc.item else None

		# Check if main item has children (has a BOM with items)
		main_item_has_children = False
		if main_item_code:
			# Check if main item has a BOM (it should, since we're viewing its BOM)
			# But also check if the BOM has items
			if bom_doc.items and len(bom_doc.items) > 0:
				main_item_has_children = True

		# Get all items recursively (including nested BOMs)
		all_items_hierarchy = get_all_items_recursively(bom_name, parent_item=main_item_code, level=1)

		# Add main item as first row if it exists
		if main_item_code:
			all_items_hierarchy.insert(
				0,
				{
					"item_code": main_item_code,
					"parent_item": None,
					"level": 0,
					"has_children": main_item_has_children,
				},
			)

		if not all_items_hierarchy:
			return data

		# Get unique item codes (including main item)
		unique_item_codes = list(set([item["item_code"] for item in all_items_hierarchy]))

		if not unique_item_codes:
			return data

		# Query items from database (we don't need custom_decoupled_lead_time since we calculate it)
		items_data = frappe.db.sql(
			"""
			SELECT
				name as item_code,
				item_name,
				lead_time_days,
				custom_buffer_flag
			FROM `tabItem`
			WHERE name IN %s
			""",
			(tuple(unique_item_codes),),
			as_dict=True,
		)

		# Create a dictionary for quick lookup
		items_dict = {item["item_code"]: item for item in items_data}

		# Build data rows maintaining hierarchy order
		for item_info in all_items_hierarchy:
			item_code = item_info["item_code"]
			parent_item = item_info["parent_item"]
			level = item_info["level"]
			has_children = item_info.get("has_children", False)

			item_data = items_dict.get(item_code)

			if item_data:
				# Always calculate custom_decoupled_lead_time dynamically (like the UI does)
				try:
					decoupled_lead_time = calculate_decoupled_lead_time(item_code)
				except Exception as e:
					frappe.log_error(
						f"Error calculating decoupled lead time for item {item_code}: {str(e)}",
						"BOM Wise Buffer Details Report Error",
					)
					decoupled_lead_time = 0

				# Ensure it's a float
				decoupled_lead_time = flt(decoupled_lead_time or 0)

				# Get buffer flag
				buffer_flag = item_data.get("custom_buffer_flag") or "No"

				# Check if item is buffer (could be "Yes" or "Buffer")
				is_buffer = buffer_flag in ["Yes", "Buffer"]

				row = {
					"item_code": item_code,
					"item_name": item_data.get("item_name") or "",
					"lead_time_days": flt(item_data.get("lead_time_days") or 0),
					"custom_decoupled_lead_time": decoupled_lead_time,
					"custom_buffer_flag": buffer_flag,
					# Set image path if item is buffer
					"buffer_img": "/files/toc.jpeg" if is_buffer else "",
					"has_children": has_children,
					"level": level,
					"parent_item": parent_item or "",
					"indent": level,  # Frappe uses indent for collapsible rows
				}
				data.append(row)
			else:
				# Item doesn't exist, log and skip
				frappe.log_error(
					f"Item {item_code} does not exist",
					"BOM Wise Buffer Details Report Error",
				)

	except frappe.DoesNotExistError:
		frappe.throw(f"BOM {bom_name} does not exist")
	except Exception as e:
		frappe.log_error(f"Error processing BOM {bom_name}: {str(e)}", "BOM Wise Buffer Details Report Error")
		frappe.throw(f"Error processing BOM: {str(e)}")

	return data
