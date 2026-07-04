# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import json
import frappe
from frappe import _
from typing import Optional


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_bom_items_for_filter(doctype, txt, searchfield, start, page_len, filters):
	"""Return Items that have at least one BOM matching the is_active/is_default filters.

	Used by the Parent Item Code autocomplete in the BOM Details report.
	"""
	if isinstance(filters, str):
		filters = json.loads(filters)

	conditions = ["(b.is_active = 1 OR b.is_default = 1)"]

	is_active = filters.get("is_active", "")
	is_default = filters.get("is_default", "")

	if is_active == "Yes":
		conditions.append("b.is_active = 1")
	elif is_active == "No":
		conditions.append("b.is_active = 0")

	if is_default == "Yes":
		conditions.append("b.is_default = 1")
	elif is_default == "No":
		conditions.append("b.is_default = 0")

	where = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
			SELECT DISTINCT b.item, b.item_name
			FROM `tabBOM` b
			WHERE {where}
			  AND (b.item LIKE %(txt)s OR b.item_name LIKE %(txt)s)
			ORDER BY b.item
			LIMIT %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_boms_for_filter(doctype, txt, searchfield, start, page_len, filters):
	"""Return BOMs matching the is_active/is_default filters.

	Used by the BOM Name autocomplete in the BOM Details report.
	"""
	if isinstance(filters, str):
		filters = json.loads(filters)

	conditions = ["(b.is_active = 1 OR b.is_default = 1)"]

	is_active = filters.get("is_active", "")
	is_default = filters.get("is_default", "")

	if is_active == "Yes":
		conditions.append("b.is_active = 1")
	elif is_active == "No":
		conditions.append("b.is_active = 0")

	if is_default == "Yes":
		conditions.append("b.is_default = 1")
	elif is_default == "No":
		conditions.append("b.is_default = 0")

	where = " AND ".join(conditions)

	return frappe.db.sql(
		f"""
			SELECT DISTINCT b.name, b.item_name
			FROM `tabBOM` b
			WHERE {where}
			  AND (b.name LIKE %(txt)s OR b.item_name LIKE %(txt)s)
			ORDER BY b.name
			LIMIT %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "start": int(start), "page_len": int(page_len)},
	)


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
		{"label": _("Is Active"), "fieldname": "is_active", "fieldtype": "Check", "width": 70},
		{"label": _("Is Default"), "fieldname": "is_default", "fieldtype": "Check", "width": 70},
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
	is_default_filter = filters.get("is_default")
	is_active_value = str(is_active_filter).strip().lower() if is_active_filter is not None else ""
	is_default_value = str(is_default_filter).strip().lower() if is_default_filter is not None else ""

	_yes_values = ("yes", "active", "1", "true", "on")
	_no_values  = ("no", "inactive", "0", "false", "off")

	# Yes → filter = 1 | No → filter = 0 | blank → no filter
	if is_active_value in _yes_values:
		bom_filters["is_active"] = 1
	elif is_active_value in _no_values:
		bom_filters["is_active"] = 0

	if is_default_value in _yes_values:
		bom_filters["is_default"] = 1
	elif is_default_value in _no_values:
		bom_filters["is_default"] = 0

	parent_item_code = filters.get("parent_item_code")
	if parent_item_code:
		bom_filters["item"] = ["like", f"%{parent_item_code}%"]

	bom_name = filters.get("bom_name")
	if bom_name:
		bom_filters["name"] = bom_name

	# Always exclude BOMs where BOTH is_active and is_default are unchecked
	boms = frappe.get_all(
		"BOM",
		filters=bom_filters,
		or_filters=[
			["is_active", "=", 1],
			["is_default", "=", 1],
		],
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
