# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Column definitions for the PO Recommendation report.
No database calls — filter-conditional static column lists only.
"""

from frappe import _


def get_columns(filters: dict | None = None) -> list[dict]:
	if not filters:
		filters = {}

	sell = filters.get("sell", 0)
	if isinstance(sell, str):
		sell = 1 if sell in ("1", "true", "True") else 0
	sell = int(sell) if sell else 0

	buffer_flag = filters.get("buffer_flag", 0)
	if isinstance(buffer_flag, str):
		buffer_flag = 1 if buffer_flag in ("1", "true", "True") else 0
	buffer_flag = int(buffer_flag) if buffer_flag else 0

	columns = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("Machine Name"),
			"fieldname": "machine_name",
			"fieldtype": "Link",
			"options": "Bright Machine",
			"width": 140,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
	]

	if not buffer_flag:
		columns.append(
			{
				"label": _("Priority"),
				"fieldname": "priority",
				"fieldtype": "Data",
				"width": 120,
			}
		)

	if not buffer_flag:
		columns.append(
			{
				"label": _("Requirement"),
				"fieldname": "requirement",
				"fieldtype": "Int",
				"width": 120,
			}
		)

	if buffer_flag:
		columns.extend(
			[
				{
					"label": _("TOG"),
					"fieldname": "tog",
					"fieldtype": "Int",
					"width": 100,
				},
				{
					"label": _("TOY"),
					"fieldname": "toy",
					"fieldtype": "Int",
					"width": 100,
				},
				{
					"label": _("TOR"),
					"fieldname": "tor",
					"fieldtype": "Int",
					"width": 100,
				},
			]
		)

	if buffer_flag:
		columns.extend(
			[
				{
					"label": _("Open SO"),
					"fieldname": "open_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Total SO"),
					"fieldname": "total_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("On Hand Stock"),
					"fieldname": "on_hand_stock",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("WIP"),
					"fieldname": "wip",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open PO"),
					"fieldname": "open_po",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open Subcon PO"),
					"fieldname": "open_subcon_po",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Additional Demand"),
					"fieldname": "additional_demand",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Qualified Demand"),
					"fieldname": "qualify_demand",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("On Hand Status"),
					"fieldname": "on_hand_status",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("On Hand Colour"),
					"fieldname": "on_hand_colour",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Net Flow"),
					"fieldname": "net_flow",
					"fieldtype": "Int",
					"width": 120,
				},
			]
		)
	else:
		columns.extend(
			[
				{
					"label": _("Total SO"),
					"fieldname": "total_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open SO"),
					"fieldname": "open_so_qualified",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("On Hand Stock"),
					"fieldname": "on_hand_stock",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("WIP"),
					"fieldname": "wip",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open PO"),
					"fieldname": "open_po",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open Subcon PO"),
					"fieldname": "open_subcon_po",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Additional Demand"),
					"fieldname": "additional_demand",
					"fieldtype": "Int",
					"width": 130,
					"hidden": 1,
				},
				{
					"label": _("Qualified Demand"),
					"fieldname": "qualify_demand",
					"fieldtype": "Int",
					"width": 130,
					"hidden": 1,
				},
			]
		)

	columns.extend(
		[
			{
				"label": _("Order Recommendation"),
				"fieldname": "order_recommendation",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("MRQ"),
				"fieldname": "mrq",
				"fieldtype": "Int",
				"width": 120,
			},
			{
				"label": _("Balance Order Recommendation"),
				"fieldname": "net_po_recommendation",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("Net Order Recommendation"),
				"fieldname": "or_with_moq_batch_size",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("MOQ"),
				"fieldname": "moq",
				"fieldtype": "Int",
				"width": 120,
			},
			{
				"label": _("Order Multiple Qty"),
				"fieldname": "batch_size",
				"fieldtype": "Int",
				"width": 120,
			},
		]
	)

	if sell:
		columns.extend(
			[
				{
					"label": _("Production qty based on child stock"),
					"fieldname": "production_qty_based_on_child_stock",
					"fieldtype": "Int",
					"width": 220,
				},
				{
					"label": _("Child Stock Full-Kit Status"),
					"fieldname": "child_full_kit_status",
					"fieldtype": "Data",
					"width": 160,
				},
				{
					"label": _("Production qty based on child stock+WIP/Open PO"),
					"fieldname": "production_qty_based_on_child_stock_wip_open_po",
					"fieldtype": "Int",
					"width": 280,
				},
				{
					"label": _("Child Stock + WIP/Open PO Full-Kit Status"),
					"fieldname": "child_wip_open_po_full_kit_status",
					"fieldtype": "Data",
					"width": 160,
				},
				{
					"label": _("Child Item Code"),
					"fieldname": "child_item_code",
					"fieldtype": "Data",
					"width": 150,
				},
				{
					"label": _("Child Item Type"),
					"fieldname": "child_item_type",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Child SKU Type"),
					"fieldname": "child_sku_type",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Child Requirement"),
					"fieldname": "child_requirement",
					"fieldtype": "Int",
					"width": 150,
				},
				{
					"label": _("Child stock"),
					"fieldname": "child_stock",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Child Stock soft Allocation qty"),
					"fieldname": "child_stock_soft_allocation_qty",
					"fieldtype": "Int",
					"width": 200,
				},
				{
					"label": _("Child Stock shortage"),
					"fieldname": "child_stock_shortage",
					"fieldtype": "Int",
					"width": 160,
				},
				{
					"label": _("Child WIP/Open PO"),
					"fieldname": "child_wip_open_po",
					"fieldtype": "Int",
					"width": 150,
				},
				{
					"label": _("Child WIP/Open PO soft allocation qty"),
					"fieldname": "child_wip_open_po_soft_allocation_qty",
					"fieldtype": "Int",
					"width": 250,
				},
				{
					"label": _("Child WIP/Open PO Shortage"),
					"fieldname": "child_wip_open_po_shortage",
					"fieldtype": "Int",
					"width": 200,
				},
			]
		)

	return columns
