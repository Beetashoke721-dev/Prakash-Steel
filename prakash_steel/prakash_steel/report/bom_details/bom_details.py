# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from typing import Optional


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	`filters` may contain `is_active` and `is_default` with values 'Yes'/'No'/'All'.
	"""
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{"label": _("BOM Name"), "fieldname": "bom_name", "fieldtype": "Link", "options": "BOM", "width": 200},
		{"label": _("Parent Item Type"), "fieldname": "parent_item_type", "fieldtype": "Data", "width": 90},
		{"label": _("Parent Item Code"), "fieldname": "parent_item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("Parent Item Name"), "fieldname": "parent_item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Qty"), "fieldname": "parent_qty", "fieldtype": "Float", "width": 80},
		{"label": _("UOM"), "fieldname": "parent_uom", "fieldtype": "Data", "width": 80},
		{"label": _("Child Item Type"), "fieldname": "child_item_type", "fieldtype": "Data", "width": 90},
		{"label": _("Child Item Code"), "fieldname": "child_item_code", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("Child Item Name"), "fieldname": "child_item_name", "fieldtype": "Data", "width": 200},
		{"label": _("Qty (Items)"), "fieldname": "child_qty", "fieldtype": "Float", "width": 80},
		{"label": _("UOM (Items)"), "fieldname": "child_uom", "fieldtype": "Data", "width": 80},
		{"label": _("isActive"), "fieldname": "is_active", "fieldtype": "Check", "width": 70},
		{"label": _("isDefault"), "fieldname": "is_default", "fieldtype": "Check", "width": 70},
	]


def get_data(filters: Optional[dict]) -> list[dict]:
	"""Build data rows by reading BOM records and their child items.

	Filters supported:
	- is_active: 'Yes'/'No'/'All' (or falsy)
	- is_default: 'Yes'/'No'/'All' (or falsy)
	"""
	filters = filters or {}

	# Build server-side filters for BOMs
	bom_filters = {}
	is_active_filter = filters.get("is_active")
	if is_active_filter == "Yes":
		bom_filters["is_active"] = 1
	elif is_active_filter == "No":
		bom_filters["is_active"] = 0

	is_default_filter = filters.get("is_default")
	if is_default_filter == "Yes":
		bom_filters["is_default"] = 1
	elif is_default_filter == "No":
		bom_filters["is_default"] = 0

	# Fetch BOMs matching the filters
	boms = frappe.get_all(
		"BOM",
		filters=bom_filters,
		fields=[
			"name",
			"item as parent_item_code",
			"item_name as parent_item_name",
			"custom_item_type as parent_item_type",
			"quantity as parent_qty",
			"uom as parent_uom",
			"is_active",
			"is_default",
		],
		order_by="name",
		limit_page_length=0,
	)

	data: list[dict] = []

	for bom in boms:
		# get child items from BOM Item child table
		children = frappe.get_all(
			"BOM Item",
			filters={"parent": bom["name"]},
			fields=["item_code as child_item_code", "item_name as child_item_name", "custom_item_type as child_item_type", "qty as child_qty", "uom as child_uom"],
			order_by="idx",
		)

		if not children:
			data.append(
				{
					"bom_name": bom["name"],
					"parent_item_type": bom.get("parent_item_type") or "",
					"parent_item_code": bom.get("parent_item_code") or "",
					"parent_item_name": bom.get("parent_item_name") or "",
					"parent_qty": bom.get("parent_qty") or 0,
					"parent_uom": bom.get("parent_uom") or "",
					"child_item_type": "",
					"child_item_code": "",
					"child_item_name": "",
					"child_qty": 0,
					"child_uom": "",
					"is_active": bool(bom.get("is_active")),
					"is_default": bool(bom.get("is_default")),
				}
			)
		else:
			for child in children:
				data.append(
					{
						"bom_name": bom["name"],
						"parent_item_type": bom.get("parent_item_type") or "",
						"parent_item_code": bom.get("parent_item_code") or "",
						"parent_item_name": bom.get("parent_item_name") or "",
						"parent_qty": bom.get("parent_qty") or 0,
						"parent_uom": bom.get("parent_uom") or "",
						"child_item_type": child.get("child_item_type") or "",
						"child_item_code": child.get("child_item_code") or "",
						"child_item_name": child.get("child_item_name") or "",
						"child_qty": child.get("child_qty") or 0,
						"child_uom": child.get("child_uom") or "",
						"is_active": bool(bom.get("is_active")),
						"is_default": bool(bom.get("is_default")),
					}
				)

	return data
