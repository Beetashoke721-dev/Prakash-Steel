# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
BOM traversal functions for the PO Recommendation report.
All recursive BOM-tree walks live here.
"""

import math
from collections import defaultdict
from collections.abc import Callable

import frappe
from frappe.utils import flt

from prakash_steel.utils.lead_time import get_default_bom

from .calculations import (
	_PRIORITY_TO_COLOUR,
	_STATUS_PRIORITY,
	_non_buffer_priority,
	apply_spike_threshold,
	calculate_net_order_recommendation,
	calculate_sku_type,
)
from .data_fetchers import get_open_so_map_for_priority, get_stock_map


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
	qualified_demand_map: dict[str, float] | None = None,
	item_type_map: dict[str, str] | None = None,
	spike_master_map: dict[str, dict] | None = None,
	level: int = 0,
) -> None:
	qualified_demand_map = qualified_demand_map or {}
	item_type_map = item_type_map or {}

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

			if is_child_buffer:
				# Buffer child: own demand is till_today + spike (raw, un-thresholded)
				child_qualified_demand = flt(qualified_demand_map.get(child_item_code, 0))
			else:
				# Non-buffer child: own demand is all-time open SO
				child_qualified_demand = flt(open_so_map.get(child_item_code, 0))

			child_parent_demand = flt(parent_demand_map.get(child_item_code, 0))
			child_stock = flt(stock_map.get(child_item_code, 0))
			child_sku_type = item_sku_type_map.get(child_item_code)
			child_wip = 0 if child_sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(child_item_code, 0))
			child_open_po = flt(open_po_map.get(child_item_code, 0))
			child_mrq = flt(mrq_map.get(child_item_code, 0))

			if is_child_buffer:
				# Buffer child: TOG + (Qualified Demand + Parent Demand) - Stock - WIP - Open PO - MRQ
				# Spike threshold is evaluated against the combined total (own demand +
				# parent demand), not the child's own demand alone.
				child_tog = flt(item_tog_map.get(child_item_code, 0))
				child_item_type = item_type_map.get(child_item_code)
				child_total_demand = apply_spike_threshold(
					child_qualified_demand + child_parent_demand,
					child_tog,
					child_item_type,
					spike_master_map,
				)

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
					qualified_demand_map,
					item_type_map,
					spike_master_map,
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


def propagate_priority_through_bom_tree(
	data: list[dict],
	wip_map: dict[str, float],
	open_po_map: dict[str, float],
) -> None:
	"""
	Mutates `data` rows in place, writing a propagated `priority` for every
	non-buffer row: the worst-priority colour found anywhere among the item's
	BOM ancestors (any depth), falling back to the item's own FIFO priority
	when no ancestor has one.
	"""
	item_priority_map: dict[str, str] = {}
	for row in data:
		item_code = row.get("item_code")
		if item_code and item_code not in item_priority_map:
			item_priority_map[item_code] = row.get("priority") or ""

	report_item_set = set(item_priority_map.keys())
	if not report_item_set:
		return

	# Phase 2: BFS upward — collect ALL ancestors (any depth) and
	# build the complete child→parents map in one pass per BFS level.
	child_to_parents: dict[str, set[str]] = defaultdict(set)
	all_items = set(report_item_set)
	frontier = set(report_item_set)
	while frontier:
		f_tuple = tuple(frontier)
		up_rows = frappe.db.sql(
			"""
			SELECT b.item AS parent_item, bi.item_code AS child_item
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
			WHERE bi.item_code IN %s
			  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
			""",
			(f_tuple,),
			as_dict=True,
		)
		new_parents = set()
		for br in up_rows:
			child_to_parents[br.child_item].add(br.parent_item)
			if br.parent_item not in all_items:
				new_parents.add(br.parent_item)
		all_items.update(new_parents)
		frontier = new_parents  # advance to next BFS level

	# Phase 3: compute own FIFO priority for ancestors not already in the report
	external_items = all_items - report_item_set
	if external_items:
		ext_tuple = tuple(external_items)
		ext_so_map = get_open_so_map_for_priority(list(external_items))
		ext_item_rows = frappe.db.sql(
			"SELECT item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE item_code IN %s",
			(ext_tuple,),
			as_dict=True,
		)
		ext_stock_map = get_stock_map(list(external_items))
		for ei in ext_item_rows:
			eic = ei.item_code
			esku = calculate_sku_type(ei.custom_buffer_flag or "Non-Buffer", ei.custom_item_type) or ""
			estock = ext_stock_map.get(eic, 0)
			ewip = 0 if esku in ["RBMTA", "RBMTO"] else flt(wip_map.get(eic, 0))
			epo = flt(open_po_map.get(eic, 0))
			elevel = (estock + epo) if esku in ["BOTO", "PTO", "TRMTO"] else (estock + ewip)
			item_priority_map[eic] = _non_buffer_priority(eic, elevel, ext_so_map)

	# Phase 4: BFS downward — propagate worst parent priority through the full tree.
	# Roots = items that have no parents in the complete ancestor set.
	resolved = all_items - set(child_to_parents.keys())
	changed = True
	while changed:
		changed = False
		for child, parents in child_to_parents.items():
			if child in resolved:
				continue
			if not parents.issubset(resolved):
				continue
			worst = 0
			for parent in parents:
				pc = item_priority_map.get(parent, "")
				if pc:
					pv = _STATUS_PRIORITY.get(pc.upper(), 0)
					if pv > worst:
						worst = pv
			# If all parents have empty priority, keep child's own FIFO priority
			item_priority_map[child] = (
				_PRIORITY_TO_COLOUR.get(worst, "") if worst > 0 else item_priority_map.get(child, "")
			)
			resolved.add(child)
			changed = True

	# Write propagated priorities back to all data rows
	for row in data:
		item_code = row.get("item_code")
		if item_code and row.get("buffer_flag") != "Buffer":
			row["priority"] = item_priority_map.get(item_code, "")


def soft_allocate_child_requirements(
	filtered_data: list[dict],
	child_stock_map: dict[str, float],
	child_wip_open_po_map: dict[str, float],
) -> None:
	"""
	FIFO-allocates each child item's stock and WIP/open-PO across `filtered_data`
	rows (expected to already be sorted by on-hand-status priority), mutating
	each row's child_stock_soft_allocation_qty / child_stock_shortage /
	production_qty_based_on_child_stock / child_wip_open_po_soft_allocation_qty /
	child_wip_open_po_shortage / child_wip_open_po_full_kit_status /
	production_qty_based_on_child_stock_wip_open_po / child_full_kit_status
	fields in place. Also backfills `child_stock_map` for any child item missing
	from it.
	"""
	remaining_child_stock_fifo: dict[str, float] = {}
	remaining_child_wip_open_po_fifo: dict[str, float] = {}

	for row in filtered_data:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue

		# Initialize remaining stock if not already done
		if child_item_code not in remaining_child_stock_fifo:
			if child_item_code in child_stock_map:
				remaining_child_stock_fifo[child_item_code] = child_stock_map[child_item_code]
			else:
				try:
					total_stock = int(flt(get_stock_map([child_item_code]).get(child_item_code, 0)))
					child_stock_map[child_item_code] = total_stock
					remaining_child_stock_fifo[child_item_code] = total_stock
				except Exception:
					remaining_child_stock_fifo[child_item_code] = 0

		# Initialize remaining WIP/Open PO if not already done
		if child_item_code not in remaining_child_wip_open_po_fifo:
			if child_item_code in child_wip_open_po_map:
				remaining_child_wip_open_po_fifo[child_item_code] = flt(child_wip_open_po_map[child_item_code])
			else:
				remaining_child_wip_open_po_fifo[child_item_code] = flt(row.get("child_wip_open_po", 0))

		child_requirement = flt(row.get("child_requirement", 0))
		available_stock = flt(remaining_child_stock_fifo.get(child_item_code, 0))
		stock_allocated = min(child_requirement, available_stock)
		stock_shortage = child_requirement - stock_allocated

		row["child_stock_soft_allocation_qty"] = math.ceil(stock_allocated)
		row["child_stock_shortage"] = math.ceil(stock_shortage)

		child_bom_qty = flt(row.get("child_bom_qty", 0))
		child_bom_quantity = flt(row.get("child_bom_quantity", 1.0)) or 1.0
		parent_per_child_factor = (child_bom_quantity / child_bom_qty) if child_bom_quantity else 0

		net_order_recommendation = flt(row.get("or_with_moq_batch_size", 0))

		production_qty_based_on_child_stock = math.ceil(flt(stock_allocated) * parent_per_child_factor)
		# Cap at net order recommendation — can't produce more than what's actually needed
		production_qty_based_on_child_stock = min(
			production_qty_based_on_child_stock, math.ceil(net_order_recommendation)
		)
		row["production_qty_based_on_child_stock"] = production_qty_based_on_child_stock

		remaining_requirement_after_stock = stock_shortage
		available_wip_open_po = flt(remaining_child_wip_open_po_fifo.get(child_item_code, 0))
		wip_open_po_allocated = min(remaining_requirement_after_stock, available_wip_open_po)
		wip_open_po_shortage = remaining_requirement_after_stock - wip_open_po_allocated

		row["child_wip_open_po_soft_allocation_qty"] = math.ceil(wip_open_po_allocated)
		row["child_wip_open_po_shortage"] = math.ceil(wip_open_po_shortage)

		if flt(net_order_recommendation) == 0:
			row["child_wip_open_po_full_kit_status"] = None
		elif flt(wip_open_po_shortage) == 0:
			row["child_wip_open_po_full_kit_status"] = "Full-kit"
		elif flt(wip_open_po_allocated) == 0:
			row["child_wip_open_po_full_kit_status"] = "Pending"
		else:
			row["child_wip_open_po_full_kit_status"] = "Partial"

		total_allocated = flt(stock_allocated) + flt(wip_open_po_allocated)
		production_qty_based_on_child_stock_wip_open_po = math.ceil(total_allocated * parent_per_child_factor)
		# Cap at net order recommendation — can't produce more than what's actually needed
		production_qty_based_on_child_stock_wip_open_po = min(
			production_qty_based_on_child_stock_wip_open_po, math.ceil(net_order_recommendation)
		)
		row["production_qty_based_on_child_stock_wip_open_po"] = (
			production_qty_based_on_child_stock_wip_open_po
		)

		order_recommendation = flt(row.get("order_recommendation", 0))

		if flt(order_recommendation) == 0:
			row["child_full_kit_status"] = None
		elif flt(stock_shortage) == 0:
			row["child_full_kit_status"] = "Full-kit"
		elif flt(stock_allocated) == 0:
			row["child_full_kit_status"] = "Pending"
		else:
			row["child_full_kit_status"] = "Partial"

		remaining_child_stock_fifo[child_item_code] = available_stock - stock_allocated
		remaining_child_wip_open_po_fifo[child_item_code] = available_wip_open_po - wip_open_po_allocated
