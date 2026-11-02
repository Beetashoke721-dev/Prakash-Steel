# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

"""
Computes required_by / transaction_date for items being turned into
Material Requests by the MRP engine (mrp_genaration.py).

- Buffer items decouple: required_by = today() + Item.custom_decoupled_lead_time
  (that field is already auto-maintained by utils/lead_time.py; it already
  encodes "own lead time + critical non-buffer path to the next buffer/leaf").
- Non-buffer items inherit required_by from whatever demand drove them: the
  nearest Open Sales Order delivery date (if sold directly), or the
  transaction_date of whichever parent(s) need them as a BOM component.
- transaction_date(item) = required_by(item) - lead_time_days(item), for
  every item (buffer and non-buffer alike).
- transaction_date(parent) is the candidate required_by pushed down to each
  of the parent's children — buffer children ignore it (their own formula
  always wins) but still push their own transaction_date further down.
- When an item is reachable through multiple sources (multiple parents, or
  both its own Open SO and parent demand), the earliest (min) required_by
  wins.
- If an item has no traceable SO/parent source at all, fall back to
  required_by = today() + lead_time_days(item).
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from prakash_steel.utils.lead_time import get_default_bom


def get_item_lead_time_maps(item_codes) -> tuple:
	"""Return (lead_time_map, decoupled_lead_time_map) for the given item codes."""
	item_codes = list(item_codes)
	if not item_codes:
		return {}, {}

	rows = frappe.db.get_all(
		"Item",
		filters={"name": ["in", item_codes]},
		fields=["name", "lead_time_days", "custom_decoupled_lead_time"],
	)

	lead_time_map = {r.name: cint(r.lead_time_days) for r in rows}
	decoupled_lead_time_map = {r.name: cint(r.custom_decoupled_lead_time) for r in rows}
	return lead_time_map, decoupled_lead_time_map


def get_item_earliest_so_delivery_map() -> dict:
	"""Earliest (nearest) Open Sales Order delivery date per item_code.

	This looks at ALL still-open lines (past or future) to find the date
	that should drive scheduling — separate from the quantity-side open SO
	map (get_sales_order_qty_map, shared with the PO Recommendation for PSP
	report), which now also considers all open lines regardless of date.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			MIN(soi.delivery_date) as earliest_delivery_date
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND soi.qty > IFNULL(soi.delivered_qty, 0)
			AND IFNULL(soi.custom_closed, 0) = 0
			AND soi.delivery_date IS NOT NULL
		GROUP BY
			soi.item_code
		""",
		as_dict=True,
	)

	return {r.item_code: getdate(r.earliest_delivery_date) for r in rows}


def build_child_to_parents_map(item_codes) -> dict:
	"""Reverse BOM edge map: child_item_code -> [parent_item_code, ...].

	Only considers the default BOM of each item in item_codes (same BOM
	the MRP engine's quantity traversal uses via get_default_bom()).
	"""
	item_codes = list(item_codes)
	bom_to_parent = {}
	for item_code in item_codes:
		bom = get_default_bom(item_code)
		if bom:
			bom_to_parent[bom] = item_code

	if not bom_to_parent:
		return {}

	bom_item_rows = frappe.db.get_all(
		"BOM Item",
		filters={"parent": ["in", list(bom_to_parent.keys())]},
		fields=["parent", "item_code"],
	)

	child_to_parents = {}
	for row in bom_item_rows:
		parent_item_code = bom_to_parent.get(row.parent)
		if not parent_item_code:
			continue
		child_to_parents.setdefault(row.item_code, []).append(parent_item_code)

	return child_to_parents


def compute_required_by_and_transaction_dates(
	net_order_recommendations: dict,
	item_buffer_map: dict,
	lead_time_map: dict | None = None,
	decoupled_lead_time_map: dict | None = None,
	earliest_so_map: dict | None = None,
	child_to_parents_map: dict | None = None,
) -> dict:
	"""
	For every item_code with net_order_recommendations[item_code] > 0, compute
	{"required_by": date, "transaction_date": date}.

	All the *_map arguments are optional so this can be unit tested without a
	database — when omitted they're fetched here.
	"""
	items_with_demand = [
		item_code for item_code, qty in net_order_recommendations.items() if flt(qty) > 0
	]
	if not items_with_demand:
		return {}

	if lead_time_map is None or decoupled_lead_time_map is None:
		lead_time_map, decoupled_lead_time_map = get_item_lead_time_maps(items_with_demand)
	if earliest_so_map is None:
		earliest_so_map = get_item_earliest_so_delivery_map()
	if child_to_parents_map is None:
		child_to_parents_map = build_child_to_parents_map(items_with_demand)

	today_date = getdate(today())
	required_by_cache = {}

	def lead_time(item_code) -> int:
		return cint(lead_time_map.get(item_code, 0))

	def is_buffer(item_code) -> bool:
		return item_buffer_map.get(item_code, "Non-Buffer") == "Buffer"

	def not_before_today(d):
		# No backdated Material Requests: any computed date earlier than today
		# (overdue Open SO, a tight/negative lead-time chain, etc.) is clamped
		# up to today instead of being propagated as-is.
		return d if d >= today_date else today_date

	def transaction_date_of(required_by, item_code):
		return not_before_today(add_days(required_by, -lead_time(item_code)))

	def get_required_by(item_code, visiting):
		if item_code in required_by_cache:
			return required_by_cache[item_code]

		if item_code in visiting:
			# Circular BOM reference — break the cycle, don't propagate a date.
			return None

		if is_buffer(item_code):
			decoupled_lt = cint(decoupled_lead_time_map.get(item_code, 0))
			required_by = add_days(today_date, decoupled_lt)
		else:
			candidates = []

			own_so_date = earliest_so_map.get(item_code)
			if own_so_date:
				candidates.append(getdate(own_so_date))

			for parent_item_code in child_to_parents_map.get(item_code, []):
				if flt(net_order_recommendations.get(parent_item_code, 0)) <= 0:
					continue
				parent_required_by = get_required_by(parent_item_code, visiting | {item_code})
				if parent_required_by:
					parent_transaction_date = transaction_date_of(parent_required_by, parent_item_code)
					candidates.append(parent_transaction_date)

			if candidates:
				required_by = min(candidates)
			else:
				# No traceable SO or parent source — confirmed fallback.
				required_by = add_days(today_date, lead_time(item_code))

		required_by = not_before_today(required_by)
		required_by_cache[item_code] = required_by
		return required_by

	result = {}
	for item_code in items_with_demand:
		required_by = get_required_by(item_code, frozenset())
		transaction_date = transaction_date_of(required_by, item_code)
		result[item_code] = {
			"required_by": required_by,
			"transaction_date": transaction_date,
		}

	return result
