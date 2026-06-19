# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
BOM traversal functions for the PO Recommendation report.
All recursive BOM-tree walks live here.
"""

from collections.abc import Callable

import frappe
from frappe.utils import flt

from prakash_steel.utils.lead_time import get_default_bom

from .calculations import calculate_net_order_recommendation


# ---------------------------------------------------------------------------
# BOM traversal helpers
# ---------------------------------------------------------------------------


def traverse_bom_for_parent_demand_simple(
	parent_item_code: str,
	parent_net_order_qty: float,
	parent_demand_map: dict[str, float],
	visited_items: set[str],
	item_groups_cache: dict[str, str],
	item_buffer_map: dict[str, str],
	level: int = 0,
) -> None:
	if parent_item_code in visited_items:
		return

	visited_items.add(parent_item_code)

	# Check item_group - if Raw Material, stop BOM traversal
	item_group = item_groups_cache.get(parent_item_code)
	if not item_group:
		try:
			item_doc = frappe.get_doc("Item", parent_item_code)
			item_group = item_doc.get("item_group")
			item_groups_cache[parent_item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {parent_item_code}: {e}", "PO Recommendation")
			item_group = None

	if item_group == "Raw Material":
		return

	# Get BOM for this item
	bom = get_default_bom(parent_item_code)
	if not bom:
		return

	try:
		bom_doc = frappe.get_doc("BOM", bom)
		bom_quantity = flt(bom_doc.quantity)
		if bom_quantity <= 0:
			bom_quantity = 1.0

		for bom_item in bom_doc.items:
			child_item_code = bom_item.item_code
			bom_item_qty = flt(bom_item.qty)

			normalized_bom_qty = bom_item_qty / bom_quantity
			child_required_qty = parent_net_order_qty * normalized_bom_qty
			if child_item_code in parent_demand_map:
				parent_demand_map[child_item_code] += child_required_qty
			else:
				parent_demand_map[child_item_code] = child_required_qty

			# Recursively traverse child's BOM
			if child_item_code not in visited_items:
				traverse_bom_for_parent_demand_simple(
					child_item_code,
					child_required_qty,
					parent_demand_map,
					visited_items.copy(),
					item_groups_cache,
					item_buffer_map,
					level + 1,
				)
	except Exception as e:
		frappe.log_error(f"BOM traversal (simple) failed for {parent_item_code} BOM {bom}: {e}", "PO Recommendation")


def traverse_bom_for_parent_demand(
	parent_item_code: str,
	parent_net_order_qty: float,
	parent_demand_map: dict[str, float],
	parent_demand_details: dict[str, list],
	visited_items: set[str],
	item_groups_cache: dict[str, str],
	open_so_map: dict[str, float],
	stock_map: dict[str, float],
	wip_map: dict[str, float],
	open_po_map: dict[str, float],
	mrq_map: dict[str, float],
	moq_map: dict[str, float],
	batch_size_map: dict[str, float],
	item_buffer_map: dict[str, str],
	item_sku_type_map: dict[str, str],
	item_tog_map: dict[str, float],
	get_item_details_func: Callable[[str], None],
	level: int = 0,
) -> None:
	if parent_item_code in visited_items:
		return

	visited_items.add(parent_item_code)

	# Check item_group - if Raw Material, stop BOM traversal
	item_group = item_groups_cache.get(parent_item_code)
	if not item_group:
		try:
			item_doc = frappe.get_doc("Item", parent_item_code)
			item_group = item_doc.get("item_group")
			item_groups_cache[parent_item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {parent_item_code}: {e}", "PO Recommendation")
			item_group = None

	# If it's a Raw Material, stop BOM traversal (end of branch)
	if item_group == "Raw Material":
		return

	# Get BOM for this item
	bom = get_default_bom(parent_item_code)
	if not bom:
		return

	try:
		bom_doc = frappe.get_doc("BOM", bom)
		bom_quantity = flt(bom_doc.quantity)  # Quantity of parent item produced by this BOM
		if bom_quantity <= 0:
			bom_quantity = 1.0  # Default to 1 if BOM quantity is 0 or negative

		# Process each child item in BOM
		for bom_item in bom_doc.items:
			child_item_code = bom_item.item_code
			bom_item_qty = flt(bom_item.qty)  # Quantity of child item needed in BOM

			normalized_bom_qty = bom_item_qty / bom_quantity
			child_required_qty = parent_net_order_qty * normalized_bom_qty

			# Get child item details (populate maps if needed)
			get_item_details_func(child_item_code)
			child_buffer_flag = item_buffer_map.get(child_item_code, "Non-Buffer")
			is_child_buffer = child_buffer_flag == "Buffer"

			if child_item_code in parent_demand_map:
				parent_demand_map[child_item_code] += child_required_qty
			else:
				parent_demand_map[child_item_code] = child_required_qty

			# Record parent demand details for logging
			if child_item_code not in parent_demand_details:
				parent_demand_details[child_item_code] = []

			if is_child_buffer:
				# Buffer child: parent demand added to qualified demand
				parent_demand_details[child_item_code].append(
					{
						"parent_item": parent_item_code,
						"bom_name": bom_doc.name,
						"demand_qty": child_required_qty,
						"applied": True,
						"reason": f"Buffer item - parent demand added to qualified demand (from net_order_rec: {parent_net_order_qty})",
					}
				)
			else:
				# Non-buffer child: parent demand added to requirement
				parent_demand_details[child_item_code].append(
					{
						"parent_item": parent_item_code,
						"bom_name": bom_doc.name,
						"demand_qty": child_required_qty,
						"applied": True,
						"reason": f"From parent {parent_item_code} (Net Order Qty: {parent_net_order_qty}) × (BOM Item Qty: {bom_item_qty} / BOM Qty: {bom_quantity}) = {normalized_bom_qty:.4f}",
					}
				)

			child_qualified_demand = flt(open_so_map.get(child_item_code, 0))  # This is qualified_demand_map
			child_parent_demand = flt(parent_demand_map.get(child_item_code, 0))
			child_stock = flt(stock_map.get(child_item_code, 0))
			child_sku_type = item_sku_type_map.get(child_item_code)
			child_wip = 0 if child_sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(child_item_code, 0))
			child_open_po = flt(open_po_map.get(child_item_code, 0))
			child_mrq = flt(mrq_map.get(child_item_code, 0))

			if is_child_buffer:
				# Buffer child: TOG + (Qualified Demand + Parent Demand) - Stock - WIP - Open PO - MRQ
				child_tog = flt(item_tog_map.get(child_item_code, 0))
				child_total_demand = child_qualified_demand + child_parent_demand

				if child_sku_type in ["BOTA", "PTA"]:
					base_child_order_rec = (
						child_tog + child_total_demand - child_stock - child_wip - child_open_po
					)
				else:
					base_child_order_rec = child_tog + child_total_demand - child_stock - child_wip
			else:
				# Non-buffer child: (Qualified Demand + Parent Demand) - Stock - WIP - Open PO - MRQ
				child_requirement = child_qualified_demand + child_parent_demand

				if child_sku_type in ["PTO", "BOTO"]:
					base_child_order_rec = child_requirement - child_stock - child_wip - child_open_po
				else:
					base_child_order_rec = child_requirement - child_stock - child_wip

			# Subtract MRQ from base order recommendation
			child_base_order_rec = max(0, base_child_order_rec - child_mrq)

			# Apply MOQ/Batch Size to get net_order_recommendation
			child_moq = flt(moq_map.get(child_item_code, 0))
			child_batch_size = flt(batch_size_map.get(child_item_code, 0))
			child_net_order_rec = calculate_net_order_recommendation(
				child_base_order_rec, child_moq, child_batch_size
			)

			# If child has net_order_recommendation > 0, traverse its BOM recursively
			if child_net_order_rec > 0 and child_item_code not in visited_items:
				traverse_bom_for_parent_demand(
					child_item_code,
					child_net_order_rec,
					parent_demand_map,
					parent_demand_details,
					visited_items.copy(),
					item_groups_cache,
					open_so_map,
					stock_map,
					wip_map,
					open_po_map,
					mrq_map,
					moq_map,
					batch_size_map,
					item_buffer_map,
					item_sku_type_map,
					item_tog_map,
					get_item_details_func,
					level + 1,
				)

	except Exception as e:
		frappe.log_error(f"BOM traversal (full) failed for {parent_item_code} BOM {bom}: {e}", "PO Recommendation")


def traverse_bom_for_po(
	item_code: str,
	required_qty: float,
	po_recommendations: dict[str, float],
	remaining_stock: dict[str, float],
	visited_items: set[str],
	item_groups_cache: dict[str, str],
	level: int = 0,
) -> None:
	if item_code in visited_items:
		return

	visited_items.add(item_code)

	# Check item_group - if Raw Material, stop BOM traversal
	item_group = item_groups_cache.get(item_code)
	if not item_group:
		try:
			item_doc = frappe.get_doc("Item", item_code)
			item_group = item_doc.get("item_group")
			item_groups_cache[item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {item_code}: {e}", "PO Recommendation")
			item_group = None

	# If it's a Raw Material, stop BOM traversal (end of branch)
	if item_group == "Raw Material":
		return

	# Get BOM for this item
	bom = get_default_bom(item_code)
	if not bom:
		return

	try:
		bom_doc = frappe.get_doc("BOM", bom)

		# Process each child item in BOM
		for bom_item in bom_doc.items:
			child_item_code = bom_item.item_code
			bom_qty = flt(bom_item.qty)

			# Calculate required qty for child: required_qty of parent * bom_qty
			child_required_qty = required_qty * bom_qty

			# Get remaining available stock for child item
			child_available_stock = flt(remaining_stock.get(child_item_code, 0))

			# If stock not in map, fetch initial stock
			if child_item_code not in remaining_stock:
				stock_data = frappe.db.sql(
					"""
					SELECT SUM(actual_qty) as stock
					FROM `tabBin`
					WHERE item_code = %s
					""",
					(child_item_code,),
					as_dict=True,
				)
				child_available_stock = flt(stock_data[0].stock if stock_data else 0)
				remaining_stock[child_item_code] = child_available_stock

			# Allocate stock: use what we can from remaining stock
			allocated = min(child_required_qty, child_available_stock)
			remaining_stock[child_item_code] = child_available_stock - allocated

			# Calculate PO recommendation for child (what we still need after allocation)
			child_po = max(0, child_required_qty - allocated)

			# Add to PO recommendations (sum if already exists)
			if child_item_code in po_recommendations:
				po_recommendations[child_item_code] += child_po
			else:
				po_recommendations[child_item_code] = child_po

			# If we need to produce this child item, traverse its BOM recursively
			# Only traverse if stock is insufficient (child_po > 0)
			if child_po > 0:
				traverse_bom_for_po(
					child_item_code,
					child_po,
					po_recommendations,
					remaining_stock,
					visited_items.copy(),
					item_groups_cache,
					level + 1,
				)

	except Exception as e:
		frappe.log_error(f"BOM traversal (PO) failed for {item_code} BOM {bom}: {e}", "PO Recommendation")
