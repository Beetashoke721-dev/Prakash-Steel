import math
from collections import defaultdict
from collections.abc import Callable

import frappe
from frappe.utils import flt

from prakash_steel.utils.lead_time import get_default_bom as _resolve_default_bom

from .calculations import (
	_PRIORITY_TO_COLOUR,
	_STATUS_PRIORITY,
	_non_buffer_priority,
	apply_spike_threshold,
	buffer_order_recommendation_colour,
	calculate_final_order_recommendation,
	calculate_initial_order_recommendation,
	calculate_net_order_recommendation,
	calculate_sku_type,
	calculate_total_demand,
	get_qualified_demand_for_item,
)
from .data_fetchers import (
	calculate_spike_map,
	get_draft_wo_map,
	get_mrq_map,
	get_open_po_map,
	get_open_subcon_po_map,
	get_open_so_map_for_priority,
	get_planning_stock_map,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_wip_map,
)


def _req_cache(bucket: str) -> dict:
	"""A dict scoped to the current request/job (``frappe.flags`` is cleared
	between requests), used to memoise BOM lookups that repeat thousands of times
	inside one report run."""
	return frappe.flags.setdefault(bucket, {})


class _BomView:
	"""The only fields the BOM traversals read: the BOM's name, its output
	quantity and its direct components. Built once per run by ``preload_bom_graph``
	from two bulk queries instead of a full ``frappe.get_doc('BOM', ...)`` per
	edge (which also drags in exploded items, operations and the WebsiteGenerator
	mixin — none of which are used here)."""

	__slots__ = ("name", "quantity", "items")

	def __init__(self, name, quantity, items):
		self.name = name
		self.quantity = quantity
		self.items = items


def preload_default_boms() -> None:
	"""Populate the request-scoped default-BOM map in one query so the traversals
	never resolve a default BOM item-by-item."""
	if frappe.flags.get("_psp_default_bom_preloaded"):
		return
	frappe.flags["_psp_default_bom_preloaded"] = True
	cache = _req_cache("_psp_default_bom")
	rows = frappe.db.sql(
		"""
		SELECT item, name
		FROM `tabBOM`
		WHERE is_active = 1 AND is_default = 1 AND docstatus = 1
		ORDER BY creation DESC
		""",
		as_dict=True,
	)
	for row in rows:
		cache.setdefault(row.item, row.name)


def preload_bom_graph() -> None:
	"""Load every active BOM and its direct components in two queries, into the
	request-scoped BOM cache the traversals read from."""
	if frappe.flags.get("_psp_bom_graph_preloaded"):
		return
	frappe.flags["_psp_bom_graph_preloaded"] = True
	cache = _req_cache("_psp_bom_doc")
	bom_rows = frappe.db.sql(
		"SELECT name, quantity FROM `tabBOM` WHERE is_active = 1 AND docstatus = 1",
		as_dict=True,
	)
	items_by_bom: dict[str, list] = {}
	for item_row in frappe.db.sql(
		"""
		SELECT parent, item_code, qty
		FROM `tabBOM Item`
		WHERE parenttype = 'BOM'
		ORDER BY idx
		""",
		as_dict=True,
	):
		items_by_bom.setdefault(item_row.parent, []).append(item_row)
	for bom_row in bom_rows:
		cache[bom_row.name] = _BomView(
			bom_row.name, bom_row.quantity, items_by_bom.get(bom_row.name, [])
		)


def preload_item_groups() -> None:
	"""Load every item's group in one query into the request-scoped cache the
	traversals read via ``_get_item_group``."""
	if frappe.flags.get("_psp_item_groups_preloaded"):
		return
	frappe.flags["_psp_item_groups_preloaded"] = True
	cache = _req_cache("_psp_item_group")
	for row in frappe.db.sql("SELECT name, item_group FROM `tabItem`", as_dict=True):
		cache.setdefault(row.name, row.item_group)


def get_default_bom(item_code: str) -> str | None:
	"""Request-memoised wrapper around ``lead_time.get_default_bom`` (see
	``preload_default_boms``) — the default BOM for an item cannot change
	mid-request."""
	cache = _req_cache("_psp_default_bom")
	if item_code in cache:
		return cache[item_code]
	value = _resolve_default_bom(item_code)
	cache[item_code] = value
	return value


def get_bom_view(bom_name: str):
	"""Request-memoised BOM lookup. ``preload_bom_graph`` fills the cache up front;
	anything not preloaded (e.g. a non-default BOM returned by the fallback
	resolver) falls back to a full ``frappe.get_doc``."""
	cache = _req_cache("_psp_bom_doc")
	if bom_name in cache:
		return cache[bom_name]
	doc = frappe.get_doc("BOM", bom_name)
	cache[bom_name] = doc
	return doc


def _get_item_group(item_code: str) -> str | None:
	"""Request-memoised item-group lookup. Uses ``frappe.db.get_value`` (single
	column) instead of loading the whole Item doc with all its child tables."""
	cache = _req_cache("_psp_item_group")
	if item_code in cache:
		return cache[item_code]
	value = frappe.db.get_value("Item", item_code, "item_group")
	cache[item_code] = value
	return value


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

	item_group = item_groups_cache.get(parent_item_code)
	if not item_group:
		try:
			item_group = _get_item_group(parent_item_code)
			item_groups_cache[parent_item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {parent_item_code}: {e}", "PO Recommendation")
			item_group = None

	if item_group == "Raw Material":
		return

	bom = get_default_bom(parent_item_code)
	if not bom:
		return

	try:
		bom_doc = get_bom_view(bom)
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
	open_subcon_po_map: dict[str, float] | None = None,
) -> None:
	qualified_demand_map = qualified_demand_map or {}
	item_type_map = item_type_map or {}
	open_subcon_po_map = open_subcon_po_map or {}

	if parent_item_code in visited_items:
		return

	visited_items.add(parent_item_code)

	item_group = item_groups_cache.get(parent_item_code)
	if not item_group:
		try:
			item_group = _get_item_group(parent_item_code)
			item_groups_cache[parent_item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {parent_item_code}: {e}", "PO Recommendation")
			item_group = None

	if item_group == "Raw Material":
		return

	bom = get_default_bom(parent_item_code)
	if not bom:
		return

	try:
		bom_doc = get_bom_view(bom)
		bom_quantity = flt(bom_doc.quantity)
		if bom_quantity <= 0:
			bom_quantity = 1.0

		for bom_item in bom_doc.items:
			child_item_code = bom_item.item_code
			bom_item_qty = flt(bom_item.qty)

			normalized_bom_qty = bom_item_qty / bom_quantity
			child_required_qty = parent_net_order_qty * normalized_bom_qty

			get_item_details_func(child_item_code)
			child_buffer_flag = item_buffer_map.get(child_item_code, "Non-Buffer")
			is_child_buffer = child_buffer_flag == "Buffer"

			if child_item_code in parent_demand_map:
				parent_demand_map[child_item_code] += child_required_qty
			else:
				parent_demand_map[child_item_code] = child_required_qty

			if child_item_code not in parent_demand_details:
				parent_demand_details[child_item_code] = []

			if is_child_buffer:
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
				child_qualified_demand = flt(qualified_demand_map.get(child_item_code, 0))
			else:
				child_qualified_demand = flt(open_so_map.get(child_item_code, 0))

			child_parent_demand = flt(parent_demand_map.get(child_item_code, 0))
			child_stock = flt(stock_map.get(child_item_code, 0))
			child_sku_type = item_sku_type_map.get(child_item_code)
			child_wip = flt(wip_map.get(child_item_code, 0))
			child_open_po = flt(open_po_map.get(child_item_code, 0))
			child_open_subcon_po = flt(open_subcon_po_map.get(child_item_code, 0))
			child_mrq = flt(mrq_map.get(child_item_code, 0))

			if is_child_buffer:
				child_tog = flt(item_tog_map.get(child_item_code, 0))
				child_item_type = item_type_map.get(child_item_code)
				child_total_demand = apply_spike_threshold(
					child_qualified_demand + child_parent_demand,
					child_tog,
					child_item_type,
					spike_master_map,
				)

				# All buffer SKU types (BOTA/PTA/BBMTA/RBMTA/TRMTA) net off Open PO,
				# Open Subcon PO and WIP the same way.
				base_child_order_rec = (
					child_tog
					+ child_total_demand
					- child_stock
					- child_wip
					- child_open_po
					- child_open_subcon_po
				)
			else:
				child_requirement = child_qualified_demand + child_parent_demand

				# All non-buffer SKU types (PTO/BOTO/BBMTO/RBMTO/TRMTO) net off Open PO,
				# Open Subcon PO and WIP the same way.
				base_child_order_rec = (
					child_requirement - child_stock - child_wip - child_open_po - child_open_subcon_po
				)

			child_base_order_rec = max(0, base_child_order_rec - child_mrq)

			child_moq = flt(moq_map.get(child_item_code, 0))
			child_batch_size = flt(batch_size_map.get(child_item_code, 0))
			child_net_order_rec = calculate_net_order_recommendation(
				child_base_order_rec, child_moq, child_batch_size
			)

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
					open_subcon_po_map,
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

	item_group = item_groups_cache.get(item_code)
	if not item_group:
		try:
			item_group = _get_item_group(item_code)
			item_groups_cache[item_code] = item_group
		except Exception as e:
			frappe.log_error(f"BOM traversal: failed to fetch item group for {item_code}: {e}", "PO Recommendation")
			item_group = None

	if item_group == "Raw Material":
		return

	bom = get_default_bom(item_code)
	if not bom:
		return

	try:
		bom_doc = get_bom_view(bom)

		for bom_item in bom_doc.items:
			child_item_code = bom_item.item_code
			bom_qty = flt(bom_item.qty)

			child_required_qty = required_qty * bom_qty

			child_available_stock = flt(remaining_stock.get(child_item_code, 0))

			if child_item_code not in remaining_stock:
				child_available_stock = flt(
					get_planning_stock_map([child_item_code]).get(child_item_code, 0)
				)
				remaining_stock[child_item_code] = child_available_stock

			allocated = min(child_required_qty, child_available_stock)
			remaining_stock[child_item_code] = child_available_stock - allocated

			child_po = max(0, child_required_qty - allocated)

			if child_item_code in po_recommendations:
				po_recommendations[child_item_code] += child_po
			else:
				po_recommendations[child_item_code] = child_po

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


def build_bom_graph() -> tuple[dict[str, list[dict]], dict[str, str]]:
	rows = frappe.db.sql(
		"""
		SELECT b.item AS parent_item, b.name AS bom_name, b.quantity AS bom_quantity,
		       bi.item_code AS child_item, bi.qty AS bom_item_qty
		FROM `tabBOM Item` bi
		INNER JOIN `tabBOM` b ON b.name = bi.parent
		WHERE b.is_default = 1 AND b.docstatus = 1 AND b.is_active = 1
		""",
		as_dict=True,
	)
	bom_children_map = defaultdict(list)
	for r in rows:
		bom_children_map[r.parent_item].append(
			{
				"child_item": r.child_item,
				"bom_item_qty": flt(r.bom_item_qty),
				"bom_quantity": flt(r.bom_quantity) or 1.0,
				"bom_name": r.bom_name,
			}
		)

	item_group_rows = frappe.db.sql("SELECT name AS item_code, item_group FROM `tabItem`", as_dict=True)
	item_group_map = {r.item_code: r.item_group for r in item_group_rows}

	return dict(bom_children_map), item_group_map


def traverse_bom_for_parent_demand_simple_fast(
	parent_item_code: str,
	parent_net_order_qty: float,
	parent_demand_map: dict[str, float],
	visited_items: set[str],
	bom_children_map: dict[str, list[dict]],
	item_group_map: dict[str, str],
	level: int = 0,
) -> None:
	if parent_item_code in visited_items:
		return
	visited_items.add(parent_item_code)

	if item_group_map.get(parent_item_code) == "Raw Material":
		return

	children = bom_children_map.get(parent_item_code)
	if not children:
		return

	for c in children:
		child_item_code = c["child_item"]
		normalized_bom_qty = c["bom_item_qty"] / c["bom_quantity"] if c["bom_quantity"] else 0
		child_required_qty = parent_net_order_qty * normalized_bom_qty
		parent_demand_map[child_item_code] = parent_demand_map.get(child_item_code, 0) + child_required_qty

		if child_item_code not in visited_items:
			traverse_bom_for_parent_demand_simple_fast(
				child_item_code,
				child_required_qty,
				parent_demand_map,
				visited_items.copy(),
				bom_children_map,
				item_group_map,
				level + 1,
			)


def traverse_bom_for_parent_demand_fast(
	parent_item_code: str,
	parent_net_order_qty: float,
	parent_demand_map: dict[str, float],
	visited_items: set[str],
	bom_children_map: dict[str, list[dict]],
	item_group_map: dict[str, str],
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
	qualified_demand_map: dict[str, float],
	item_type_map: dict[str, str],
	spike_master_map: dict[str, dict],
	level: int = 0,
	open_subcon_po_map: dict[str, float] | None = None,
) -> None:
	open_subcon_po_map = open_subcon_po_map or {}

	if parent_item_code in visited_items:
		return
	visited_items.add(parent_item_code)

	if item_group_map.get(parent_item_code) == "Raw Material":
		return

	children = bom_children_map.get(parent_item_code)
	if not children:
		return

	for c in children:
		child_item_code = c["child_item"]
		bom_quantity = c["bom_quantity"]
		normalized_bom_qty = c["bom_item_qty"] / bom_quantity if bom_quantity else 0
		child_required_qty = parent_net_order_qty * normalized_bom_qty

		child_buffer_flag = item_buffer_map.get(child_item_code, "Non-Buffer")
		is_child_buffer = child_buffer_flag == "Buffer"

		parent_demand_map[child_item_code] = parent_demand_map.get(child_item_code, 0) + child_required_qty

		if is_child_buffer:
			child_qualified_demand = flt(qualified_demand_map.get(child_item_code, 0))
		else:
			child_qualified_demand = flt(open_so_map.get(child_item_code, 0))

		child_parent_demand = flt(parent_demand_map.get(child_item_code, 0))
		child_stock = flt(stock_map.get(child_item_code, 0))
		child_sku_type = item_sku_type_map.get(child_item_code)
		child_wip = flt(wip_map.get(child_item_code, 0))
		child_open_po = flt(open_po_map.get(child_item_code, 0))
		child_open_subcon_po = flt(open_subcon_po_map.get(child_item_code, 0))
		child_mrq = flt(mrq_map.get(child_item_code, 0))

		if is_child_buffer:
			child_tog = flt(item_tog_map.get(child_item_code, 0))
			child_item_type = item_type_map.get(child_item_code)
			child_total_demand = apply_spike_threshold(
				child_qualified_demand + child_parent_demand,
				child_tog,
				child_item_type,
				spike_master_map,
			)
			# All buffer SKU types (BOTA/PTA/BBMTA/RBMTA/TRMTA) net off Open PO,
			# Open Subcon PO and WIP the same way.
			base_child_order_rec = (
				child_tog
				+ child_total_demand
				- child_stock
				- child_wip
				- child_open_po
				- child_open_subcon_po
			)
		else:
			child_requirement = child_qualified_demand + child_parent_demand
			# All non-buffer SKU types (PTO/BOTO/BBMTO/RBMTO/TRMTO) net off Open PO,
			# Open Subcon PO and WIP the same way.
			base_child_order_rec = (
				child_requirement - child_stock - child_wip - child_open_po - child_open_subcon_po
			)

		child_base_order_rec = max(0, base_child_order_rec - child_mrq)
		child_moq = flt(moq_map.get(child_item_code, 0))
		child_batch_size = flt(batch_size_map.get(child_item_code, 0))
		child_net_order_rec = calculate_net_order_recommendation(child_base_order_rec, child_moq, child_batch_size)

		if child_net_order_rec > 0 and child_item_code not in visited_items:
			traverse_bom_for_parent_demand_fast(
				child_item_code,
				child_net_order_rec,
				parent_demand_map,
				visited_items.copy(),
				bom_children_map,
				item_group_map,
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
				qualified_demand_map,
				item_type_map,
				spike_master_map,
				level + 1,
				open_subcon_po_map,
			)


def compute_universe_net_order_recommendations() -> tuple[dict[str, float], dict[str, float]]:
	bom_children_map, item_group_map = build_bom_graph()

	item_rows = frappe.db.sql(
		"""
		SELECT name AS item_code, custom_buffer_flag AS buffer_flag, custom_item_type AS item_type,
		       safety_stock AS tog, min_order_qty AS moq, custom_batch_size AS batch_size
		FROM `tabItem`
		""",
		as_dict=True,
	)
	all_item_codes = [r.item_code for r in item_rows]

	item_buffer_map_all = {}
	item_sku_type_map_all = {}
	item_tog_map_all = {}
	item_type_map_all = {}
	moq_map_all = {}
	batch_size_map_all = {}
	for r in item_rows:
		item_buffer_map_all[r.item_code] = r.buffer_flag or "Non-Buffer"
		item_sku_type_map_all[r.item_code] = calculate_sku_type(r.buffer_flag or "Non-Buffer", r.item_type)
		item_tog_map_all[r.item_code] = flt(r.tog or 0)
		item_type_map_all[r.item_code] = r.item_type
		moq_map_all[r.item_code] = flt(r.moq or 0)
		batch_size_map_all[r.item_code] = flt(r.batch_size or 0)

	so_qty_map = get_sales_order_qty_map({})
	till_today_map, spike_map = get_qualified_demand_map()
	wip_map = get_wip_map()
	mrq_map = get_mrq_map()
	open_po_map = get_open_po_map()
	open_subcon_po_map = get_open_subcon_po_map()
	stock_map = get_planning_stock_map(all_item_codes)

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}

	calculated_spike_map = calculate_spike_map(
		all_item_codes, item_buffer_map_all, item_type_map_all, item_tog_map_all, spike_master_map
	)
	spike_map = dict(spike_map)
	spike_map.update(calculated_spike_map)

	qualified_demand_map = {}
	for item_code in all_item_codes:
		qd, _, _ = get_qualified_demand_for_item(item_code, till_today_map, spike_map, item_buffer_map_all)
		qualified_demand_map[item_code] = qd

	initial_net_order_recommendations = {}
	for item_code in all_item_codes:
		base = calculate_initial_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			stock_map,
			wip_map,
			so_qty_map,
			qualified_demand_map,
			open_po_map,
			open_subcon_po_map,
		)
		initial_net_order_recommendations[item_code] = calculate_net_order_recommendation(
			base, moq_map_all.get(item_code, 0), batch_size_map_all.get(item_code, 0)
		)

	parent_demand_map = {}
	for item_code in sorted(ic for ic, v in initial_net_order_recommendations.items() if v > 0):
		traverse_bom_for_parent_demand_simple_fast(
			item_code,
			initial_net_order_recommendations[item_code],
			parent_demand_map,
			set(),
			bom_children_map,
			item_group_map,
		)

	net_order_recommendations = {}
	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			stock_map,
			wip_map,
			so_qty_map,
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map,
			item_type_map_all,
			spike_master_map,
			open_subcon_po_map,
		)
		net_order_recommendations[item_code] = calculate_net_order_recommendation(
			order_rec, moq_map_all.get(item_code, 0), batch_size_map_all.get(item_code, 0)
		)

	parent_demand_map_net = {}
	global_visited_items: set[str] = set()
	for item_code in sorted(ic for ic, v in net_order_recommendations.items() if v > 0):
		if item_code not in global_visited_items:
			traverse_bom_for_parent_demand_fast(
				item_code,
				net_order_recommendations[item_code],
				parent_demand_map_net,
				global_visited_items,
				bom_children_map,
				item_group_map,
				so_qty_map,
				stock_map,
				wip_map,
				open_po_map,
				mrq_map,
				moq_map_all,
				batch_size_map_all,
				item_buffer_map_all,
				item_sku_type_map_all,
				item_tog_map_all,
				qualified_demand_map,
				item_type_map_all,
				spike_master_map,
				level=0,
				open_subcon_po_map=open_subcon_po_map,
			)

	net_order_recommendations_final = {}
	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			stock_map,
			wip_map,
			so_qty_map,
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map_net,
			item_type_map_all,
			spike_master_map,
			open_subcon_po_map,
		)
		net_order_recommendations_final[item_code] = calculate_net_order_recommendation(
			order_rec, moq_map_all.get(item_code, 0), batch_size_map_all.get(item_code, 0)
		)

	total_demand_map = {}
	for item_code in all_item_codes:
		is_buffer = item_buffer_map_all.get(item_code) == "Buffer"
		total_demand_map[item_code] = calculate_total_demand(
			item_code,
			is_buffer,
			qualified_demand_map,
			parent_demand_map_net,
			item_tog_map_all,
			item_type_map_all,
			spike_master_map,
		)

	return net_order_recommendations_final, total_demand_map


def propagate_priority_through_bom_tree(
	data: list[dict],
	wip_map: dict[str, float],
	open_po_map: dict[str, float],
) -> None:
	item_priority_map: dict[str, str] = {}
	for row in data:
		item_code = row.get("item_code")
		if item_code and item_code not in item_priority_map:
			item_priority_map[item_code] = row.get("priority") or ""

	report_item_set = set(item_priority_map.keys())
	if not report_item_set:
		return

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
		frontier = new_parents

	external_items = all_items - report_item_set
	if external_items:
		ext_tuple = tuple(external_items)
		ext_so_map = get_open_so_map_for_priority(list(external_items))
		ext_item_rows = frappe.db.sql(
			"""
			SELECT item_code, custom_buffer_flag, custom_item_type, safety_stock,
			       min_order_qty, custom_batch_size
			FROM `tabItem` WHERE item_code IN %s
			""",
			(ext_tuple,),
			as_dict=True,
		)
		ext_stock_map = get_planning_stock_map(list(external_items))

		ext_bb_buffer = [
			ei.item_code
			for ei in ext_item_rows
			if (ei.custom_buffer_flag or "Non-Buffer") == "Buffer" and ei.custom_item_type == "BB"
		]
		ext_bb_set = set(ext_bb_buffer)
		draft_wo_map: dict[str, float] = {}
		ext_bb_tog_map: dict[str, float] = {}
		# {item_code: Bright Plan "Order Recommendation" colour}. Only buffer BB
		# ancestors with a net order recommendation > 0 appear in the Bright Plan
		# report; the rest are absent there and contribute no colour signal.
		ext_bb_colour_map: dict[str, str] = {}
		if ext_bb_buffer:
			draft_wo_map = get_draft_wo_map()
			ext_bb_mrq_map = get_mrq_map()
			ext_bb_tog_map = {
				ei.item_code: flt(ei.safety_stock or 0)
				for ei in ext_item_rows
				if ei.item_code in ext_bb_set
			}
			_bb_moq_map = {
				ei.item_code: flt(ei.min_order_qty or 0)
				for ei in ext_item_rows
				if ei.item_code in ext_bb_set
			}
			_bb_batch_map = {
				ei.item_code: flt(ei.custom_batch_size or 0)
				for ei in ext_item_rows
				if ei.item_code in ext_bb_set
			}
			_bb_buffer_map = {ic: "Buffer" for ic in ext_bb_buffer}
			_bb_type_map = {ic: "BB" for ic in ext_bb_buffer}
			spike_master_map = {
				sm.item_type: {
					"demand_horizon": flt(sm.demand_horizon),
					"spike_threshold": flt(sm.spike_threshold),
				}
				for sm in frappe.get_all(
					"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
				)
			}
			_bb_till_today_map, _bb_spike_map = get_qualified_demand_map()
			_bb_spike_map.update(
				calculate_spike_map(
					ext_bb_buffer, _bb_buffer_map, _bb_type_map, ext_bb_tog_map, spike_master_map
				)
			)
			for ic in ext_bb_buffer:
				tog = flt(ext_bb_tog_map.get(ic, 0))
				_raw_qd, _, _ = get_qualified_demand_for_item(
					ic, _bb_till_today_map, _bb_spike_map, _bb_buffer_map
				)
				qd = apply_spike_threshold(flt(_raw_qd), tog, "BB", spike_master_map)
				stock = flt(ext_stock_map.get(ic, 0))
				wip = flt(wip_map.get(ic, 0))
				mrq = flt(ext_bb_mrq_map.get(ic, 0))
				# Same net-order-rec formula as the Bright Plan report (bright_plan.py):
				# base excludes open PO / draft WO; then MOQ / batch size.
				base_order_rec = max(0, tog + qd - stock - wip - mrq)
				net_order_rec = calculate_net_order_recommendation(
					base_order_rec, _bb_moq_map.get(ic, 0), _bb_batch_map.get(ic, 0)
				)
				if net_order_rec <= 0:
					continue  # not in Bright Plan -> no colour contribution
				# Worst Bright Plan batch row = first batch (level before any batch
				# is produced): stock + WIP + draft WO vs TOG + qualified demand.
				level = stock + wip + flt(draft_wo_map.get(ic, 0))
				ext_bb_colour_map[ic] = buffer_order_recommendation_colour(level, tog + qd).upper()

		for ei in ext_item_rows:
			eic = ei.item_code
			buffer_flag = ei.custom_buffer_flag or "Non-Buffer"
			estock = flt(ext_stock_map.get(eic, 0))
			ewip = flt(wip_map.get(eic, 0))
			if buffer_flag == "Buffer":
				if eic in ext_bb_set:
					item_priority_map[eic] = ext_bb_colour_map.get(eic, "")
				else:
					item_priority_map[eic] = _non_buffer_priority(eic, estock + ewip, ext_so_map)
			else:
				esku = calculate_sku_type(buffer_flag, ei.custom_item_type) or ""
				epo = flt(open_po_map.get(eic, 0))
				elevel = (estock + epo) if esku in ["BOTO", "PTO", "TRMTO"] else (estock + ewip)
				item_priority_map[eic] = _non_buffer_priority(eic, elevel, ext_so_map)

	resolved = all_items - set(child_to_parents.keys())
	changed = True
	while changed:
		changed = False
		for child, parents in child_to_parents.items():
			if child in resolved:
				continue
			if not parents.issubset(resolved):
				continue
			worst = _STATUS_PRIORITY.get((item_priority_map.get(child, "") or "").upper(), 0)
			for parent in parents:
				pc = item_priority_map.get(parent, "")
				if pc:
					pv = _STATUS_PRIORITY.get(pc.upper(), 0)
					if pv > worst:
						worst = pv
			item_priority_map[child] = (
				_PRIORITY_TO_COLOUR.get(worst, "") if worst > 0 else item_priority_map.get(child, "")
			)
			resolved.add(child)
			changed = True

	for row in data:
		item_code = row.get("item_code")
		if item_code and row.get("buffer_flag") != "Buffer":
			row["priority"] = item_priority_map.get(item_code, "")


def soft_allocate_child_requirements(
	filtered_data: list[dict],
	child_stock_map: dict[str, float],
	child_wip_open_po_map: dict[str, float],
) -> None:
	remaining_child_stock_fifo: dict[str, float] = {}
	remaining_child_wip_open_po_fifo: dict[str, float] = {}

	for row in filtered_data:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue

		if child_item_code not in remaining_child_stock_fifo:
			if child_item_code in child_stock_map:
				remaining_child_stock_fifo[child_item_code] = child_stock_map[child_item_code]
			else:
				try:
					total_stock = int(flt(get_planning_stock_map([child_item_code]).get(child_item_code, 0)))
					child_stock_map[child_item_code] = total_stock
					remaining_child_stock_fifo[child_item_code] = total_stock
				except Exception:
					remaining_child_stock_fifo[child_item_code] = 0

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
