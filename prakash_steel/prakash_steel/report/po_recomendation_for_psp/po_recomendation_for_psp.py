import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import date_diff, flt, nowdate
from prakash_steel.utils.lead_time import get_default_bom


def calculate_sku_type(buffer_flag, item_type):
	if not item_type:
		return None

	is_buffer = buffer_flag == "Buffer"

	if item_type == "BB":
		return "BBMTA" if is_buffer else "BBMTO"
	elif item_type == "RB":
		return "RBMTA" if is_buffer else "RBMTO"
	elif item_type == "BO":
		return "BOTA" if is_buffer else "BOTO"
	elif item_type == "RM":
		return "PTA" if is_buffer else "PTO"
	elif item_type == "Traded":
		return "TRMTA" if is_buffer else "TRMTO"

	return None


# ---------------------------------------------------------------------------
# Non-buffer priority helpers (same logic as open_mr_for_manufacture/purchase)
# ---------------------------------------------------------------------------

_STATUS_PRIORITY = {"BLACK": 5, "RED": 4, "YELLOW": 3, "GREEN": 2, "WHITE": 1}
_PRIORITY_TO_COLOUR = {5: "Black", 4: "Red", 3: "Yellow", 2: "Green", 1: "White"}


def _compute_order_status(delivery_date, transaction_date):
	if not delivery_date:
		return None
	today = nowdate()
	remaining_days = date_diff(delivery_date, today)
	lead_time = date_diff(delivery_date, transaction_date) if transaction_date else None
	if lead_time:
		buffer_pct = (flt(remaining_days) / flt(lead_time)) * 100
	else:
		buffer_pct = flt(remaining_days) * 100
	numeric = math.ceil(buffer_pct)
	if numeric < 0:
		return "BLACK"
	elif numeric <= 34:
		return "RED"
	elif numeric <= 67:
		return "YELLOW"
	elif numeric <= 100:
		return "GREEN"
	else:
		return "WHITE"


def _non_buffer_priority(item_code, level, so_map):
	"""
	FIFO-allocate `level` across open SOs sorted by delivery_date ASC.
	- If any SO has shortage → return worst order_status colour of shortage SOs.
	- If no shortage anywhere → return worst order_status colour of no-shortage SOs.
	- If no open SOs → return ''.
	"""
	sos = so_map.get(item_code, [])
	if not sos:
		return ""
	available = flt(level)
	worst_shortage = 0
	worst_no_shortage = 0
	for so in sos:
		required = flt(so["pending_qty"])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		priority = _STATUS_PRIORITY.get(so["order_status"], 0)
		if shortage > 0:
			if priority > worst_shortage:
				worst_shortage = priority
		else:
			if priority > worst_no_shortage:
				worst_no_shortage = priority
	if worst_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_shortage, "")
	if worst_no_shortage > 0:
		return _PRIORITY_TO_COLOUR.get(worst_no_shortage, "")
	return ""


def build_calculation_breakdown_po_report(
	item_code,
	buffer_flag,
	is_buffer,
	sku_type,
	tog,
	qualified_demand,
	open_so,
	stock,
	wip,
	open_po,
	mrq,
	moq,
	batch_size,
	total_parent_demand,
	final_order_rec,
	net_order_rec,
	parent_demand_details_list,
	till_today=None,
	spike=None,
):
	lines = []
	lines.append(f"\n  Item: {item_code}")
	lines.append(f"  Type: {buffer_flag}")
	if sku_type and sku_type != "N/A":
		lines.append(f"  SKU Type: {sku_type}")

	if is_buffer:
		lines.append(f"  TOG: {tog}")
		# Show till_today and spike separately if provided
		if till_today is not None and spike is not None:
			lines.append(f"  Till Today: {till_today}")
			lines.append(f"  Spike: {spike}")
			lines.append(f"  Qualified Demand (Till Today + Spike): {qualified_demand}")
		else:
			lines.append(f"  Qualified Demand: {qualified_demand}")
		lines.append(f"  Total Parent Demand: {total_parent_demand}")

		# Show parent demand breakdown if available
		if total_parent_demand > 0 and parent_demand_details_list:
			lines.append("  Parent Demands Breakdown:")
			for pd in parent_demand_details_list:
				if pd.get("applied", True):
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} {pd.get('reason', '')}"
					)
				else:
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} [IGNORED - {pd.get('reason', '')}]"
					)

		# Calculate total demand (Qualified Demand + Parent Demand)
		total_demand = qualified_demand + total_parent_demand
		lines.append(
			f"  Total Demand (Qualified Demand + Parent Demand): {qualified_demand} + {total_parent_demand} = {total_demand}"
		)

		lines.append(f"  Stock: {stock}")
		lines.append(f"  WIP: {wip}")
		lines.append(f"  Open PO: {open_po}")
		lines.append(f"  MRQ: {mrq}")

		if sku_type in ["BOTA", "PTA"]:
			base_calc = tog + total_demand - stock - wip - open_po
			lines.append(
				"  Base Calculation: TOG + (Qualified Demand + Parent Demand) - Stock - WIP - Open PO"
			)
			lines.append(
				f"                    = {tog} + ({qualified_demand} + {total_parent_demand}) - {stock} - {wip} - {open_po}"
			)
			lines.append(f"                    = {tog} + {total_demand} - {stock} - {wip} - {open_po}")
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")
		else:
			base_calc = tog + total_demand - stock - wip
			lines.append("  Base Calculation: TOG + (Qualified Demand + Parent Demand) - Stock - WIP")
			lines.append(
				f"                    = {tog} + ({qualified_demand} + {total_parent_demand}) - {stock} - {wip}"
			)
			lines.append(f"                    = {tog} + {total_demand} - {stock} - {wip}")
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")

		# Show MOQ/Batch Size logic
		if final_order_rec <= 0:
			if moq > 0:
				lines.append(f"  MOQ: {moq} (Not applied - base order rec is {final_order_rec} <= 0)")
			elif batch_size > 0:
				lines.append(
					f"  Batch Size: {batch_size} (Not applied - base order rec is {final_order_rec} <= 0)"
				)
			else:
				lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: 0 (Base order rec is {final_order_rec} <= 0)")
		elif moq > 0:
			if moq < final_order_rec:
				lines.append(f"  MOQ: {moq} (MOQ < Order Rec, using Order Rec)")
				lines.append(f"  Net Order Recommendation: {final_order_rec}")
			else:
				lines.append(f"  MOQ: {moq} (MOQ >= Order Rec, using MOQ)")
				lines.append(f"  Net Order Recommendation: {moq}")
		elif batch_size > 0:
			net_calc = math.ceil(final_order_rec / batch_size) * batch_size
			lines.append(f"  Batch Size: {batch_size}")
			lines.append(
				f"  Net Order Recommendation: ceil({final_order_rec} / {batch_size}) × {batch_size} = {net_calc}"
			)
		else:
			lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: {final_order_rec}")
	else:
		# For non-buffer items, Open SO in breakdown should be qualified_demand (Open SO with delivery_date <= today)
		# This matches the buffer items' logic where Open SO = Qualified Demand
		open_so_for_breakdown = qualified_demand  # Use qualified demand instead of all-time open_so
		lines.append(f"  Open SO: {open_so_for_breakdown}")
		# Show till_today and spike separately if provided (spike should always be 0 for non-buffer)
		if till_today is not None and spike is not None:
			lines.append(f"    - Till Today: {till_today}")
			lines.append(f"    - Spike: {spike} (always 0 for non-buffer items)")
		lines.append(f"  Stock: {stock}")
		lines.append(f"  WIP: {wip}")
		lines.append(f"  Open PO: {open_po}")
		lines.append(f"  Total Parent Demand: {total_parent_demand}")

		if total_parent_demand > 0 and parent_demand_details_list:
			lines.append("  Parent Demands Breakdown:")
			for pd in parent_demand_details_list:
				if pd.get("applied", True):
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} {pd.get('reason', '')}"
					)
				else:
					lines.append(
						f"    - From {pd['parent_item']} (BOM: {pd['bom_name']}): {pd['demand_qty']} [IGNORED - {pd.get('reason', '')}]"
					)

		requirement = open_so_for_breakdown + total_parent_demand

		if sku_type in ["PTO", "BOTO"]:
			base_calc = requirement - stock - wip - open_po
			lines.append(
				f"  Requirement: Open SO + Parent Demand = {open_so_for_breakdown} + {total_parent_demand} = {requirement}"
			)
			lines.append("  Base Calculation: Requirement - Stock - WIP - Open PO")
			lines.append(f"                    = {requirement} - {stock} - {wip} - {open_po}")
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")
		else:
			base_calc = requirement - stock - wip
			lines.append(
				f"  Requirement: Open SO + Parent Demand = {open_so_for_breakdown} + {total_parent_demand} = {requirement}"
			)
			lines.append("  Base Calculation: Requirement - Stock - WIP")
			lines.append(f"                    = {requirement} - {stock} - {wip}")
			lines.append(f"                    = {base_calc}")
			lines.append(f"  After MRQ: Base - MRQ = {base_calc} - {mrq} = {final_order_rec}")

		# Show MOQ/Batch Size logic
		if final_order_rec <= 0:
			if moq > 0:
				lines.append(f"  MOQ: {moq} (Not applied - base order rec is {final_order_rec} <= 0)")
			elif batch_size > 0:
				lines.append(
					f"  Batch Size: {batch_size} (Not applied - base order rec is {final_order_rec} <= 0)"
				)
			else:
				lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: 0 (Base order rec is {final_order_rec} <= 0)")
		elif moq > 0:
			if moq < final_order_rec:
				lines.append(f"  MOQ: {moq} (MOQ < Order Rec, using Order Rec)")
				lines.append(f"  Net Order Recommendation: {final_order_rec}")
			else:
				lines.append(f"  MOQ: {moq} (MOQ >= Order Rec, using MOQ)")
				lines.append(f"  Net Order Recommendation: {moq}")
		elif batch_size > 0:
			net_calc = math.ceil(final_order_rec / batch_size) * batch_size
			lines.append(f"  Batch Size: {batch_size}")
			lines.append(
				f"  Net Order Recommendation: ceil({final_order_rec} / {batch_size}) × {batch_size} = {net_calc}"
			)
		else:
			lines.append("  No MOQ or Batch Size")
			lines.append(f"  Net Order Recommendation: {final_order_rec}")

	return "\n".join(lines)


def generate_detailed_log_po_report(data, net_order_recommendations):
	lines = []
	lines.append("\n" + "=" * 100)
	lines.append("PO RECOMMENDATION FOR PSP - DETAILED BREAKDOWN (NET ORDER RECOMMENDATIONS)")
	lines.append("=" * 100)

	# Build a map of item_code -> row for quick lookup
	item_row_map = {}
	for row in data:
		item_code = row.get("item_code")
		if item_code:
			if item_code not in item_row_map:
				item_row_map[item_code] = []
			item_row_map[item_code].append(row)

	# Get all unique item codes from data
	all_item_codes = set(item_row_map.keys())

	# Show total count of items
	total_items = len(all_item_codes)
	lines.append(f"\nTotal Items Processed: {total_items}")

	# Get items with net_order_rec > 0
	items_with_net_rec = [
		item_code for item_code in all_item_codes if flt(net_order_recommendations.get(item_code, 0)) > 0
	]

	# First, show summary - include ALL items with net_order_rec > 0
	lines.append("\n" + "-" * 100)
	lines.append("SUMMARY (Items with Net Order Recommendation > 0)")
	lines.append("-" * 100)

	for item_code in sorted(items_with_net_rec):
		net_rec = flt(net_order_recommendations.get(item_code, 0))
		rows = item_row_map.get(item_code, [])
		if rows:
			first_row = rows[0]
			buffer_flag = first_row.get("buffer_flag", "Unknown")
			order_rec = first_row.get("order_recommendation", 0)
			lines.append(f"  {item_code} ({buffer_flag}): Net Order Rec = {net_rec} (Base: {order_rec})")

	# Then show detailed breakdown for ALL items
	lines.append("\n" + "=" * 100)
	lines.append("DETAILED BREAKDOWN FOR ALL ITEMS")
	lines.append("=" * 100)

	# Sort items by net_order_rec (descending), then by item_code
	sorted_item_codes = sorted(
		all_item_codes,
		key=lambda x: (flt(net_order_recommendations.get(x, 0)), x),
		reverse=True,
	)

	for item_code in sorted_item_codes:
		rows = item_row_map.get(item_code, [])
		if rows:
			# Get the first row (parent item row)
			first_row = rows[0]
			breakdown = first_row.get("calculation_breakdown", "")
			if breakdown and breakdown.strip():
				lines.append(breakdown)
			else:
				# Create a basic breakdown if not available
				buffer_flag = first_row.get("buffer_flag", "Unknown")
				order_rec = first_row.get("order_recommendation", 0)
				net_rec = flt(net_order_recommendations.get(item_code, 0))
				moq = first_row.get("moq", 0)
				batch_size = first_row.get("batch_size", 0)
				lines.append(f"\n  Item: {item_code}")
				lines.append(f"  Type: {buffer_flag}")
				lines.append(f"  Base Order Recommendation: {order_rec}")
				lines.append(f"  Net Order Recommendation: {net_rec}")
				if moq > 0:
					lines.append(f"  MOQ: {moq}")
				if batch_size > 0:
					lines.append(f"  Batch Size: {batch_size}")
				lines.append("  Note: Detailed breakdown not available")
		else:
			# Item not in data - create a minimal breakdown
			net_rec = flt(net_order_recommendations.get(item_code, 0))
			lines.append(f"\n  Item: {item_code}")
			lines.append(f"  Net Order Recommendation: {net_rec}")
			lines.append("  Note: Item not in data")
		lines.append("-" * 100)

	lines.append("\n" + "=" * 100)

	return "\n".join(lines)


def calculate_net_order_recommendation(base_order_rec, moq, batch_size):
	base_order_rec = flt(base_order_rec)
	moq = flt(moq)
	batch_size = flt(batch_size)

	if base_order_rec <= 0:
		return 0

	if moq > 0:
		if moq < base_order_rec:
			net_order_rec = base_order_rec
		else:
			net_order_rec = moq
	elif batch_size > 0:
		net_order_rec = math.ceil(base_order_rec / batch_size) * batch_size
	else:
		net_order_rec = base_order_rec

	return max(0, flt(net_order_rec))


def calculate_initial_order_recommendation(
	item_code,
	item_buffer_map,
	item_tog_map,
	item_sku_type_map,
	stock_map,
	wip_map,
	open_so_map,
	qualified_demand_map,
	open_po_map,
):
	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	is_buffer = buffer_flag == "Buffer"

	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))

	if is_buffer:
		tog = flt(item_tog_map.get(item_code, 0))
		qualified_demand = flt(qualified_demand_map.get(item_code, 0))
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["BOTA", "PTA"]:
			order_rec = max(0, tog + qualified_demand - stock - wip - open_po)
		else:
			order_rec = max(0, tog + qualified_demand - stock - wip)
	else:
		qualified_demand = flt(open_so_map.get(item_code, 0))  # all-time open SO for non-buffer
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["PTO", "BOTO"]:
			order_rec = max(0, qualified_demand - stock - wip - open_po)
		else:
			order_rec = max(0, qualified_demand - stock - wip)

	return order_rec


def calculate_final_order_recommendation(
	item_code,
	item_buffer_map,
	item_tog_map,
	item_sku_type_map,
	stock_map,
	wip_map,
	open_so_map,
	qualified_demand_map,
	open_po_map,
	mrq_map,
	parent_demand_map,
):
	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	is_buffer = buffer_flag == "Buffer"

	stock = flt(stock_map.get(item_code, 0))
	wip = flt(wip_map.get(item_code, 0))
	mrq = flt(mrq_map.get(item_code, 0))

	if is_buffer:
		tog = flt(item_tog_map.get(item_code, 0))
		qualified_demand = flt(qualified_demand_map.get(item_code, 0))
		parent_demand = flt(parent_demand_map.get(item_code, 0))
		total_demand = qualified_demand + parent_demand
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["BOTA", "PTA"]:
			base_order_rec = tog + total_demand - stock - wip - open_po
		else:
			base_order_rec = tog + total_demand - stock - wip

		order_rec = max(0, base_order_rec - mrq)
	else:
		open_so = flt(open_so_map.get(item_code, 0))  # all-time open SO for non-buffer
		parent_demand = flt(parent_demand_map.get(item_code, 0))
		requirement = open_so + parent_demand
		sku_type = item_sku_type_map.get(item_code)
		open_po = flt(open_po_map.get(item_code, 0))

		if sku_type in ["PTO", "BOTO"]:
			base_order_rec = requirement - stock - wip - open_po
		else:
			base_order_rec = requirement - stock - wip

		order_rec = max(0, base_order_rec - mrq)

	return order_rec


def execute(filters=None):
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def save_daily_on_hand_colour():
	from frappe.utils import nowdate

	posting_date = nowdate()

	all_data = []
	seen_item_codes = {}

	try:
		filters_purchase = {"purchase": 1, "buffer_flag": 1}
		_, data_purchase = execute(filters_purchase)
		if data_purchase:
			for row in data_purchase:
				item_code = row.get("item_code")
				if item_code and item_code not in seen_item_codes:
					seen_item_codes[item_code] = row
	except Exception as e:
		pass

	try:
		filters_sell = {"sell": 1, "buffer_flag": 1}
		_, data_sell = execute(filters_sell)
		if data_sell:
			for row in data_sell:
				item_code = row.get("item_code")
				if item_code and item_code not in seen_item_codes:
					seen_item_codes[item_code] = row
	except Exception as e:
		pass

	all_data = list(seen_item_codes.values())

	if not all_data:
		return

	try:
		doc = frappe.new_doc("Item wise Daily On Hand Colour")
		doc.posting_date = posting_date

		saved_rows = 0

		for row in all_data:
			item_code = row.get("item_code")
			sku_type = row.get("sku_type")
			on_hand_colour = row.get("on_hand_colour")

			if not item_code or not on_hand_colour:
				continue

			child = doc.append("item_wise_on_hand_colour", {})
			child.item_code = item_code
			child.sku_type = sku_type
			child.on_hand_colour = on_hand_colour
			saved_rows += 1

		if saved_rows == 0:
			return

		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		pass


def get_columns(filters=None):
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
					"fieldtype": "Link",
					"options": "Item",
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


def get_data(filters=None):
	if not filters:
		filters = {}

	purchase = filters.get("purchase", 0)
	sell = filters.get("sell", 0)
	buffer_flag = filters.get("buffer_flag", 0)

	if isinstance(purchase, str):
		purchase = 1 if purchase in ("1", "true", "True") else 0
	if isinstance(sell, str):
		sell = 1 if sell in ("1", "true", "True") else 0
	if isinstance(buffer_flag, str):
		buffer_flag = 1 if buffer_flag in ("1", "true", "True") else 0

	purchase = int(purchase) if purchase else 0
	sell = int(sell) if sell else 0
	buffer_flag = int(buffer_flag) if buffer_flag else 0

	if not (purchase or sell):
		return []

	allowed_sku_types = []
	if purchase:
		if buffer_flag:
			allowed_sku_types = ["PTA", "BOTA", "TRMTA"]
		else:
			allowed_sku_types = ["PTO", "BOTO", "TRMTO"]
	elif sell:
		if buffer_flag:
			allowed_sku_types = ["BBMTA", "RBMTA"]
		else:
			allowed_sku_types = ["BBMTO", "RBMTO"]

	so_qty_map = get_sales_order_qty_map(filters)

	till_today_map, spike_map = get_qualified_demand_map()

	if buffer_flag:
		items_query = """
			SELECT name as item_code
			FROM `tabItem`
			WHERE custom_buffer_flag = 'Buffer'
		"""
	else:
		items_query = """
			SELECT name as item_code
			FROM `tabItem`
			WHERE custom_buffer_flag != 'Buffer' OR custom_buffer_flag IS NULL
		"""

	items_result = frappe.db.sql(items_query, as_dict=1)
	item_codes = set(item.item_code for item in items_result)

	so_qty_map = {k: v for k, v in so_qty_map.items() if k in item_codes}

	wip_map = get_wip_map()

	mrq_map = get_mrq_map()

	open_po_map = get_open_po_map()

	items_with_po = set(open_po_map.keys())
	items_with_po_selected = {item for item in items_with_po if item in item_codes}

	all_items_to_process = item_codes | items_with_po_selected

	if not all_items_to_process:
		return []

	initial_stock_map = get_stock_map(all_items_to_process)
	so_map_for_priority = get_open_so_map_for_priority(all_items_to_process)

	remaining_stock = dict(initial_stock_map)

	po_recommendations = {}
	item_groups_cache = {}

	parent_demand_map = {}

	items_with_so = set(so_qty_map.keys())
	for item_code in sorted(items_with_so):
		so_qty = flt(so_qty_map.get(item_code, 0))
		available_stock = flt(remaining_stock.get(item_code, 0))

		required_qty = max(0, so_qty - available_stock)

		allocated = min(so_qty, available_stock)
		remaining_stock[item_code] = available_stock - allocated

		if item_code in po_recommendations:
			po_recommendations[item_code] += required_qty
		else:
			po_recommendations[item_code] = required_qty

		if required_qty > 0:
			traverse_bom_for_po(
				item_code,
				required_qty,
				po_recommendations,
				remaining_stock,
				set(),
				item_groups_cache,
				level=0,
			)

	all_item_codes = all_items_to_process

	if all_item_codes:
		if len(all_item_codes) == 1:
			all_items_tuple = (next(iter(all_item_codes)),)
		else:
			all_items_tuple = tuple(all_item_codes)

		items_details_all = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.custom_buffer_flag as buffer_flag,
				i.custom_item_type as item_type,
				i.safety_stock as tog
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
			""",
			(all_items_tuple,),
			as_dict=1,
		)

		item_buffer_map_all = {}
		item_sku_type_map_all = {}
		item_tog_map_all = {}
		item_type_map_all = {}
		for item in items_details_all:
			item_buffer_map_all[item.item_code] = item.buffer_flag or "Non-Buffer"
			item_sku_type_map_all[item.item_code] = calculate_sku_type(
				item.buffer_flag or "Non-Buffer", item.item_type
			)
			item_tog_map_all[item.item_code] = flt(item.tog or 0)
			item_type_map_all[item.item_code] = item.item_type
	else:
		item_buffer_map_all = {}
		item_sku_type_map_all = {}
		item_tog_map_all = {}
		item_type_map_all = {}

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {}
	for sm in spike_master_records:
		spike_master_map[sm.item_type] = {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}

	calculated_spike_map = calculate_spike_map(
		all_item_codes, item_buffer_map_all, item_type_map_all, item_tog_map_all
	)
	spike_map.update(calculated_spike_map)

	all_item_codes_for_demand = set(all_item_codes) | set(till_today_map.keys()) | set(spike_map.keys())
	qualified_demand_map = {}
	for item_code in all_item_codes_for_demand:
		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map_all,
			item_tog_map_all,
			item_type_map_all,
			spike_master_map,
		)
		qualified_demand_map[item_code] = qualified_demand

	initial_order_recommendations = {}
	for item_code in all_item_codes:
		order_rec = calculate_initial_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,
			qualified_demand_map,
			open_po_map,
		)
		initial_order_recommendations[item_code] = order_rec

	initial_net_order_recommendations = {}

	if all_item_codes:
		items_moq_batch_data = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.min_order_qty as moq,
				i.custom_batch_size as batch_size
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
			""",
			(all_items_tuple,),
			as_dict=1,
		)

		moq_map_all = {item.item_code: flt(item.moq or 0) for item in items_moq_batch_data}
		batch_size_map_all = {item.item_code: flt(item.batch_size or 0) for item in items_moq_batch_data}

		for item_code in all_item_codes:
			base_order_rec = initial_order_recommendations.get(item_code, 0)
			moq = moq_map_all.get(item_code, 0)
			batch_size = batch_size_map_all.get(item_code, 0)
			net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
			initial_net_order_recommendations[item_code] = net_order_rec
	else:
		moq_map_all = {}
		batch_size_map_all = {}

	items_to_process = [
		(item_code, net_order_rec)
		for item_code, net_order_rec in initial_net_order_recommendations.items()
		if net_order_rec > 0
	]
	items_to_process.sort(key=lambda x: x[0])

	for item_code, net_order_rec in items_to_process:
		traverse_bom_for_parent_demand_simple(
			item_code,
			net_order_rec,
			parent_demand_map,
			set(),
			item_groups_cache,
			item_buffer_map_all,
			level=0,
		)

	final_order_recommendations = {}
	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,           # all-time open SO for non-buffer; qualified_demand used for buffer
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map,
		)
		final_order_recommendations[item_code] = order_rec

	net_order_recommendations = {}
	for item_code in all_item_codes:
		base_order_rec = final_order_recommendations.get(item_code, 0)
		moq = moq_map_all.get(item_code, 0)
		batch_size = batch_size_map_all.get(item_code, 0)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
		net_order_recommendations[item_code] = net_order_rec

	# ── Include buffer items so their BOM children get parent demand ───────────
	# Buffer items are not in this report's item set but their BOM children
	# (RBMTO, PTO, etc.) need parent demand flowing from buffer parents.
	_buf_rows = frappe.db.sql(
		"""
		SELECT name AS item_code, safety_stock AS tog,
		       custom_item_type AS item_type, custom_buffer_flag AS buffer_flag,
		       min_order_qty AS moq, custom_batch_size AS batch_size
		FROM `tabItem`
		WHERE custom_buffer_flag = 'Buffer'
		""",
		as_dict=True,
	)
	if _buf_rows:
		_buf_codes = [r.item_code for r in _buf_rows]
		_buf_stock_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(tuple(_buf_codes) if len(_buf_codes) > 1 else (_buf_codes[0],),),
			as_dict=True,
		)
		_buf_stock_map = {r.item_code: flt(r.stock) for r in _buf_stock_rows}

		for _br in _buf_rows:
			_bic = _br.item_code
			_bsku = calculate_sku_type(_br.buffer_flag or "Buffer", _br.item_type) or ""
			_btog = flt(_br.tog or 0)
			_bstock = flt(_buf_stock_map.get(_bic, 0))
			_bwip = 0 if _bsku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_bic, 0))
			_bpo = flt(open_po_map.get(_bic, 0))
			_bqd = flt(qualified_demand_map.get(_bic, 0))
			_bmrq = flt(mrq_map.get(_bic, 0))
			_bmoq = flt(_br.moq or 0)
			_bbatch = flt(_br.batch_size or 0)

			if _bsku in ["BOTA", "PTA"]:
				_bbase = max(0, _btog + _bqd - _bstock - _bwip - _bpo - _bmrq)
			else:
				_bbase = max(0, _btog + _bqd - _bstock - _bwip - _bmrq)

			_bnet = calculate_net_order_recommendation(_bbase, _bmoq, _bbatch)

			if _bnet > 0:
				# Register in maps so traverse_bom_for_parent_demand can use them
				item_buffer_map_all[_bic] = _br.buffer_flag or "Buffer"
				item_sku_type_map_all[_bic] = _bsku
				item_tog_map_all[_bic] = _btog
				moq_map_all[_bic] = _bmoq
				batch_size_map_all[_bic] = _bbatch
				net_order_recommendations[_bic] = _bnet

	parent_demand_map_net = {}
	parent_demand_details = {}

	items_with_net_rec = [
		(item_code, net_rec) for item_code, net_rec in net_order_recommendations.items() if net_rec > 0
	]
	items_with_net_rec.sort(key=lambda x: x[0])

	global_visited_items = set()

	for item_code, net_rec in items_with_net_rec:
		if item_code not in global_visited_items:
			traverse_bom_for_parent_demand(
				item_code,
				net_rec,
				parent_demand_map_net,
				parent_demand_details,
				global_visited_items,
				item_groups_cache,
				so_qty_map,  # all-time open SO (used for non-buffer children; buffer children use qualified_demand_map via is_child_buffer branch)
				initial_stock_map,
				wip_map,
				open_po_map,
				mrq_map,
				moq_map_all,
				batch_size_map_all,
				item_buffer_map_all,
				item_sku_type_map_all,
				item_tog_map_all,
				lambda item_code: None,
				level=0,
			)

	final_order_recommendations_updated = {}
	net_order_recommendations_final = {}

	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,           # all-time open SO for non-buffer; qualified_demand used for buffer
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map_net,
		)
		final_order_recommendations_updated[item_code] = order_rec

		moq = moq_map_all.get(item_code, 0)
		batch_size = batch_size_map_all.get(item_code, 0)
		net_order_rec = calculate_net_order_recommendation(order_rec, moq, batch_size)
		net_order_recommendations_final[item_code] = net_order_rec

	final_order_recommendations = final_order_recommendations_updated
	net_order_recommendations = net_order_recommendations_final
	parent_demand_map = parent_demand_map_net

	all_items_to_show = all_items_to_process

	if not all_items_to_show:
		return []

	if len(all_items_to_show) == 1:
		item_codes_tuple = (next(iter(all_items_to_show)),)
	else:
		item_codes_tuple = tuple(all_items_to_show)

	if buffer_flag:
		items_data = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.item_name,
				i.safety_stock as tog,
				i.custom_top_of_yellow as toy,
				i.custom_top_of_red as tor,
				i.custom_item_type as item_type,
				i.custom_batch_size as batch_size,
				i.min_order_qty as moq,
				i.custom_buffer_flag as buffer_flag
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
				AND i.custom_buffer_flag = 'Buffer'
			""",
			(item_codes_tuple,),
			as_dict=1,
		)
	else:
		items_data = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.item_name,
				i.safety_stock as tog,
				i.custom_top_of_yellow as toy,
				i.custom_top_of_red as tor,
				i.custom_item_type as item_type,
				i.custom_batch_size as batch_size,
				i.min_order_qty as moq,
				i.custom_buffer_flag as buffer_flag
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
				AND (i.custom_buffer_flag != 'Buffer' OR i.custom_buffer_flag IS NULL)
			""",
			(item_codes_tuple,),
			as_dict=1,
		)

	# Create a map for quick lookup
	items_map = {item.item_code: item for item in items_data}

	child_stock_map = {}
	child_wip_open_po_map = {}

	data = []
	for item_code in sorted(all_items_to_show):
		item_info = items_map.get(item_code, {})

		# Skip if item is not in items_map
		if not item_info:
			continue

		# Calculate SKU Type based on buffer_flag
		item_type = item_info.get("item_type")
		item_buffer_flag = item_info.get("buffer_flag", "")
		sku_type = calculate_sku_type(item_buffer_flag, item_type)

		if sku_type not in allowed_sku_types:
			continue

		# Get stock and buffer levels
		on_hand_stock = flt(initial_stock_map.get(item_code, 0))
		tog = flt(item_info.get("tog", 0))
		toy = flt(item_info.get("toy", 0))
		tor = flt(item_info.get("tor", 0))
		qualify_demand, till_today, spike = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map_all,
			item_tog_map_all,
			item_type_map_all,
			spike_master_map,
		)
		qualify_demand = flt(qualify_demand)

		additional_demand = flt(till_today) + flt(spike)

		# Check if item is buffer or non-buffer
		is_item_buffer = item_buffer_flag == "Buffer"

		on_hand_status_value = None
		on_hand_status = None
		on_hand_colour = None

		if is_item_buffer:
			denominator = flt(tog) + flt(qualify_demand)
			if denominator > 0:
				on_hand_status_value = (flt(on_hand_stock) / denominator) * 100
			else:
				# If denominator is 0, set to None (cannot calculate)
				on_hand_status_value = None

			if on_hand_status_value is None:
				on_hand_colour = None
				on_hand_status = None
			else:
				numeric_status = round(on_hand_status_value, 2)

				if numeric_status == 0:
					on_hand_colour = "BLACK"
				elif 0 < numeric_status <= 34:
					on_hand_colour = "RED"
				elif 34 < numeric_status <= 67:
					on_hand_colour = "YELLOW"
				elif 67 < numeric_status <= 100:
					on_hand_colour = "GREEN"
				else:  # > 100
					on_hand_colour = "WHITE"

				on_hand_status = f"{numeric_status:.2f}%"

		# Get item name
		item_name = item_info.get("item_name", "")

		# Get WIP value (RBMTA and RBMTO do not consider WIP)
		wip = 0 if sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(item_code, 0))

		# Get batch size from item
		batch_size = flt(item_info.get("batch_size", 0))

		# Get MOQ from item
		moq = flt(item_info.get("moq", 0))

		mrq = flt(mrq_map.get(item_code, 0))

		# Get Open PO (Purchase Order quantity - received quantity)
		open_po = flt(open_po_map.get(item_code, 0))

		open_so = flt(so_qty_map.get(item_code, 0))

		parent_demand = flt(parent_demand_map.get(item_code, 0))
		parent_demand_details_list = parent_demand_details.get(item_code, [])

		final_order_rec = flt(final_order_recommendations.get(item_code, 0))
		net_order_rec = flt(net_order_recommendations.get(item_code, 0))

		order_recommendation = math.ceil(flt(final_order_rec))
		net_po_recommendation = math.ceil(
			flt(final_order_rec)
		)  # Base order recommendation (before MOQ/Batch Size)
		or_with_moq_batch_size = math.ceil(
			flt(net_order_rec)
		)  # Net order recommendation (after MOQ/Batch Size)

		# Get Open Subcon PO (will be populated with functionality later)
		open_subcon_po = 0

		# Calculate Net Flow: on_hand_stock + wip + open_po + open_subcon_po - qualified_demand
		# Use actual qualified_demand (not including parent_demand)
		net_flow = on_hand_stock + wip + open_po + open_subcon_po - qualify_demand

		# Base row with parent item data
		is_item_buffer = item_buffer_flag == "Buffer"

		wip_open_po_combined = wip + open_po + open_subcon_po

		if is_item_buffer:
			# Buffer: TOG + (Qualified Demand + Parent Demand) - Stock - (WIP + Open PO + Open Subcon PO) - MRQ
			total_demand = qualify_demand + parent_demand
			if sku_type in ["BOTA", "PTA"]:
				# For BOTA/PTA: subtract open_po separately (existing logic)
				base_order_rec = tog + total_demand - on_hand_stock - wip - open_po
			else:
				# For others: use combined value
				base_order_rec = tog + total_demand - on_hand_stock - wip_open_po_combined
			final_order_rec = max(0, base_order_rec - mrq)
		else:
			open_so_for_calc = qualify_demand  # Use qualified demand (Open SO with delivery_date <= today)
			requirement = open_so_for_calc + parent_demand
			if sku_type in ["PTO", "BOTO"]:
				# For PTO/BOTO: subtract open_po separately (existing logic)
				base_order_rec = requirement - on_hand_stock - wip - open_po
			else:
				# For others: use combined value
				base_order_rec = requirement - on_hand_stock - wip_open_po_combined
			final_order_rec = max(0, base_order_rec - mrq)

		# Calculate net order recommendation for breakdown
		net_order_rec_breakdown = calculate_net_order_recommendation(final_order_rec, moq, batch_size)
		open_so_for_breakdown = qualify_demand if not is_item_buffer else open_so
		calculation_breakdown = build_calculation_breakdown_po_report(
			item_code,
			item_buffer_flag,
			is_item_buffer,
			sku_type,
			tog,
			qualify_demand,
			open_so_for_breakdown,  # Use qualified_demand for non-buffer items in breakdown
			on_hand_stock,
			wip,
			open_po,
			mrq,
			moq,
			batch_size,
			parent_demand,
			final_order_rec,
			net_order_rec_breakdown,
			parent_demand_details_list,
			till_today=till_today,
			spike=spike,
		)

		if is_item_buffer:
			total_demand_for_display = qualify_demand + parent_demand
			base_row = {
				"item_code": item_code,
				"item_name": item_name,
				"sku_type": sku_type,
				"requirement": None,
				"tog": math.ceil(flt(tog)),
				"toy": math.ceil(flt(toy)),
				"tor": math.ceil(flt(tor)),
				"open_so": math.ceil(flt(additional_demand)),  # till_today + SOs within demand_horizon
				"total_so": math.ceil(flt(open_so)),  # All open SOs (no date filter)
				"on_hand_stock": math.ceil(flt(on_hand_stock)),
				"wip": math.ceil(flt(wip)),  # WIP value only
				"open_po": math.ceil(flt(open_po)),  # Open PO value only
				"open_subcon_po": math.ceil(flt(open_subcon_po)),  # Open Subcon PO value
				"additional_demand": math.ceil(
					flt(additional_demand)
				),  # till_today + spike (value compared with spike threshold)
				"qualify_demand": math.ceil(
					flt(total_demand_for_display)
				),  # Show total demand (qualified + parent)
			}
		else:
			base_row = {
				"item_code": item_code,
				"item_name": item_name,
				"sku_type": sku_type,
				"requirement": math.ceil(
					flt(parent_demand)
				),  # Parent demand only (Open SO is in separate column)
				"tog": None,
				"toy": None,
				"tor": None,
				"open_so": math.ceil(flt(open_so)),  # All-time Open SO
				"total_so": math.ceil(flt(open_so)),
				"on_hand_stock": math.ceil(flt(on_hand_stock)),
				"wip": math.ceil(flt(wip)),  # WIP value only
				"open_po": math.ceil(flt(open_po)),  # Open PO value only
				"open_subcon_po": math.ceil(flt(open_subcon_po)),  # Open Subcon PO value
				"additional_demand": math.ceil(flt(additional_demand)),
				"qualify_demand": math.ceil(flt(qualify_demand)),  # Qualified Demand
				"open_so_qualified": math.ceil(flt(open_so)),  # Same as total_so (no date filter)
				"priority": _non_buffer_priority(
					item_code,
					on_hand_stock + (open_po if sku_type in ["BOTO", "PTO", "TRMTO"] else wip),
					so_map_for_priority,
				),
			}
		common_fields = {
			"on_hand_status": on_hand_status,
			"on_hand_colour": on_hand_colour,
			"buffer_flag": item_buffer_flag,  # Add buffer_flag for JavaScript formatter
			"order_recommendation": math.ceil(flt(order_recommendation)),
			"batch_size": math.ceil(flt(batch_size)),
			"moq": math.ceil(flt(moq)),
			"or_with_moq_batch_size": math.ceil(flt(or_with_moq_batch_size)),
			"mrq": math.ceil(flt(mrq)),
			"net_po_recommendation": math.ceil(flt(net_po_recommendation)),
			"calculation_breakdown": calculation_breakdown,  # Add breakdown for console logging
			# Initialize child columns as None/0
			"batch_size_multiple": None,
			"production_qty_based_on_child_stock": None,
			"production_qty_based_on_child_stock_wip_open_po": None,
			"child_item_code": None,
			"child_item_type": None,
			"child_sku_type": None,
			"child_requirement": None,
			"child_stock": None,
			"child_stock_soft_allocation_qty": None,
			"child_stock_shortage": None,
			"child_full_kit_status": None,
			"child_wip_open_po": None,
			"child_wip_open_po_soft_allocation_qty": None,
			"child_wip_open_po_shortage": None,
			"child_wip_open_po_full_kit_status": None,
		}

		if is_item_buffer:
			common_fields["net_flow"] = math.ceil(flt(net_flow))
		else:
			common_fields["net_flow"] = None

		base_row.update(common_fields)

		bom = get_default_bom(item_code)
		child_items = []

		if bom:
			try:
				bom_doc = frappe.get_doc("BOM", bom)
				bom_quantity = flt(bom_doc.quantity) or 1.0
				# Get all child items from BOM
				for bom_item in bom_doc.items:
					child_item_code = bom_item.item_code
					child_bom_qty = flt(bom_item.qty)
					child_items.append(
						{
							"item_code": child_item_code,
							"bom_qty": child_bom_qty,
							"bom_quantity": bom_quantity,
						}
					)
			except Exception as e:
				pass

		if child_items:
			for child_item_info in child_items:
				child_item_code = child_item_info["item_code"]
				child_bom_qty = flt(child_item_info.get("bom_qty", 0))
				child_bom_quantity = flt(child_item_info.get("bom_quantity", 1.0)) or 1.0

				# Fetch child item details
				child_item_type = None
				child_sku_type = None
				child_stock = 0

				try:
					child_item_doc = frappe.get_doc("Item", child_item_code)
					child_item_type = child_item_doc.get("custom_item_type")
					child_buffer_flag = child_item_doc.get("custom_buffer_flag") or "Non-Buffer"
					child_sku_type = calculate_sku_type(child_buffer_flag, child_item_type)

					if child_item_code not in child_stock_map:
						stock_data = frappe.db.sql(
							"""
							SELECT SUM(actual_qty) as stock
							FROM `tabBin`
							WHERE item_code = %s
							""",
							(child_item_code,),
							as_dict=True,
						)
						total_stock = math.ceil(
							flt(stock_data[0].stock if stock_data and stock_data[0].stock else 0)
						)
						child_stock_map[child_item_code] = total_stock

					# Use total stock for display
					child_stock = child_stock_map.get(child_item_code, 0)
				except Exception as e:
					pass

				normalized_bom_qty = child_bom_qty / child_bom_quantity if child_bom_quantity else 0
				child_requirement = math.ceil(flt(or_with_moq_batch_size) * normalized_bom_qty)

				child_wip = (
					0 if child_sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(child_item_code, 0))
				)
				child_open_po = flt(open_po_map.get(child_item_code, 0))
				child_wip_open_po = math.ceil(flt(child_wip) + flt(child_open_po))
				if child_item_code not in child_wip_open_po_map:
					child_wip_open_po_map[child_item_code] = child_wip_open_po

				row = base_row.copy()
				row["child_item_code"] = child_item_code
				row["child_item_type"] = child_item_type
				row["child_sku_type"] = child_sku_type
				row["child_requirement"] = child_requirement
				row["child_stock"] = child_stock
				row["child_wip_open_po"] = child_wip_open_po
				row["child_bom_qty"] = child_bom_qty
				row["child_bom_quantity"] = child_bom_quantity
				row["child_stock_soft_allocation_qty"] = None
				row["child_stock_shortage"] = None

				data.append(row)
		else:
			data.append(base_row)

	# ── Priority propagation through BOM tree (N-level) ───────────────────────
	# Phase 1: build own FIFO priority map for all report items
	_item_priority_map = {}
	for _row in data:
		_ic = _row.get("item_code")
		if _ic and _ic not in _item_priority_map:
			_item_priority_map[_ic] = _row.get("priority") or ""

	_report_item_set = set(_item_priority_map.keys())
	if _report_item_set:
		# Phase 2: BFS upward — collect ALL ancestors (any depth) and
		# build the complete child→parents map in one pass per BFS level.
		_child_to_parents = defaultdict(set)
		_all_items = set(_report_item_set)
		_frontier = set(_report_item_set)
		while _frontier:
			_f_tuple = tuple(_frontier) if len(_frontier) > 1 else (next(iter(_frontier)),)
			_up_rows = frappe.db.sql(
				"""
				SELECT b.item AS parent_item, bi.item_code AS child_item
				FROM `tabBOM` b
				INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
				WHERE bi.item_code IN %s
				  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
				""",
				(_f_tuple,),
				as_dict=True,
			)
			_new_parents = set()
			for _br in _up_rows:
				_child_to_parents[_br.child_item].add(_br.parent_item)
				if _br.parent_item not in _all_items:
					_new_parents.add(_br.parent_item)
			_all_items.update(_new_parents)
			_frontier = _new_parents  # advance to next BFS level

		# Phase 3: compute own FIFO priority for ancestors not already in the report
		_external_items = _all_items - _report_item_set
		if _external_items:
			_ext_tuple = (
				tuple(_external_items) if len(_external_items) > 1 else (next(iter(_external_items)),)
			)
			_ext_so_map = get_open_so_map_for_priority(list(_external_items))
			_ext_item_rows = frappe.db.sql(
				"SELECT item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE item_code IN %s",
				(_ext_tuple,),
				as_dict=True,
			)
			_ext_stock_rows = frappe.db.sql(
				"SELECT item_code, SUM(actual_qty) as stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
				(_ext_tuple,),
				as_dict=True,
			)
			_ext_stock_map = {r.item_code: flt(r.stock) for r in _ext_stock_rows}
			for _ei in _ext_item_rows:
				_eic = _ei.item_code
				_esku = calculate_sku_type(_ei.custom_buffer_flag or "Non-Buffer", _ei.custom_item_type) or ""
				_estock = _ext_stock_map.get(_eic, 0)
				_ewip = 0 if _esku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_eic, 0))
				_epo = flt(open_po_map.get(_eic, 0))
				_elevel = (_estock + _epo) if _esku in ["BOTO", "PTO", "TRMTO"] else (_estock + _ewip)
				_item_priority_map[_eic] = _non_buffer_priority(_eic, _elevel, _ext_so_map)

		# Phase 4: BFS downward — propagate worst parent priority through the full tree
		# Roots = items that have no parents in the complete ancestor set
		_resolved = _all_items - set(_child_to_parents.keys())
		_changed = True
		while _changed:
			_changed = False
			for _child, _parents in _child_to_parents.items():
				if _child in _resolved:
					continue
				if not _parents.issubset(_resolved):
					continue
				_worst = 0
				for _parent in _parents:
					_pc = _item_priority_map.get(_parent, "")
					if _pc:
						_pv = _STATUS_PRIORITY.get(_pc.upper(), 0)
						if _pv > _worst:
							_worst = _pv
				# If all parents have empty priority, keep child's own FIFO priority
				_item_priority_map[_child] = (
					_PRIORITY_TO_COLOUR.get(_worst, "") if _worst > 0 else _item_priority_map.get(_child, "")
				)
				_resolved.add(_child)
				_changed = True

		# Write propagated priorities back to all data rows
		for _row in data:
			_ic = _row.get("item_code")
			if _ic and _row.get("buffer_flag") != "Buffer":
				_row["priority"] = _item_priority_map.get(_ic, "")

	# Apply filters
	filtered_data = []
	for row in data:
		# Filter by SKU Type
		if filters.get("sku_type"):
			sku_type_filter = filters.get("sku_type")
			sku_type_list = []
			if isinstance(sku_type_filter, str):
				# Try to parse as JSON first (in case it's a JSON string)
				if sku_type_filter.strip().startswith("[") or sku_type_filter.strip().startswith("{"):
					try:
						import json

						parsed = json.loads(sku_type_filter)
						if isinstance(parsed, list):
							sku_type_list = [str(s).strip() for s in parsed if s]
						else:
							sku_type_list = [str(parsed).strip()] if parsed else []
					except:
						# If JSON parsing fails, treat as comma-separated string
						sku_type_list = [s.strip() for s in sku_type_filter.split(",") if s.strip()]
				else:
					# Comma-separated string
					sku_type_list = [s.strip() for s in sku_type_filter.split(",") if s.strip()]
			elif isinstance(sku_type_filter, list):
				# Already a list
				sku_type_list = [str(s).strip() for s in sku_type_filter if s]
			else:
				# Single value
				sku_type_list = [str(sku_type_filter).strip()] if sku_type_filter else []
			if sku_type_list and row.get("sku_type") not in sku_type_list:
				continue

		# Filter by Item Code (exact match)
		if filters.get("item_code"):
			if row.get("item_code") != filters.get("item_code"):
				continue

		filtered_data.append(row)

	def get_on_hand_status_value(row):
		on_hand_status = row.get("on_hand_status")
		if on_hand_status is None:
			return float("inf")  # Put None values at the end
		# Extract number from string like "50%"
		try:
			# Remove % sign and convert to float
			numeric_value = float(on_hand_status.replace("%", "").strip())
			return numeric_value
		except (ValueError, AttributeError):
			return float("inf")  # Put invalid values at the end

	filtered_data.sort(key=get_on_hand_status_value)

	remaining_child_stock_fifo = {}
	# Re-initialize remaining_child_wip_open_po for FIFO allocation
	remaining_child_wip_open_po_fifo = {}

	for row in filtered_data:
		child_item_code = row.get("child_item_code")
		if child_item_code:
			# Initialize remaining stock if not already done
			if child_item_code not in remaining_child_stock_fifo:
				# Get total stock for this child item
				if child_item_code in child_stock_map:
					remaining_child_stock_fifo[child_item_code] = child_stock_map[child_item_code]
				else:
					# Fetch stock if not in map
					try:
						stock_data = frappe.db.sql(
							"""
							SELECT SUM(actual_qty) as stock
							FROM `tabBin`
							WHERE item_code = %s
							""",
							(child_item_code,),
							as_dict=True,
						)
						total_stock = int(
							flt(stock_data[0].stock if stock_data and stock_data[0].stock else 0)
						)
						child_stock_map[child_item_code] = total_stock
						remaining_child_stock_fifo[child_item_code] = total_stock
					except Exception:
						remaining_child_stock_fifo[child_item_code] = 0

			# Initialize remaining WIP/Open PO if not already done
			if child_item_code not in remaining_child_wip_open_po_fifo:
				# Get total WIP/Open PO for this child item
				if child_item_code in child_wip_open_po_map:
					remaining_child_wip_open_po_fifo[child_item_code] = flt(
						child_wip_open_po_map[child_item_code]
					)
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

			production_qty_based_on_child_stock = math.ceil(flt(stock_allocated) * parent_per_child_factor)
			row["production_qty_based_on_child_stock"] = production_qty_based_on_child_stock

			remaining_requirement_after_stock = stock_shortage
			available_wip_open_po = flt(remaining_child_wip_open_po_fifo.get(child_item_code, 0))
			wip_open_po_allocated = min(remaining_requirement_after_stock, available_wip_open_po)
			wip_open_po_shortage = remaining_requirement_after_stock - wip_open_po_allocated

			row["child_wip_open_po_soft_allocation_qty"] = math.ceil(wip_open_po_allocated)
			row["child_wip_open_po_shortage"] = math.ceil(wip_open_po_shortage)
			net_order_recommendation = flt(row.get("or_with_moq_batch_size", 0))

			if flt(net_order_recommendation) == 0:
				row["child_wip_open_po_full_kit_status"] = None
			elif flt(wip_open_po_shortage) == 0:
				row["child_wip_open_po_full_kit_status"] = "Full-kit"
			elif flt(wip_open_po_allocated) == 0:
				row["child_wip_open_po_full_kit_status"] = "Pending"
			else:
				row["child_wip_open_po_full_kit_status"] = "Partial"

			total_allocated = flt(stock_allocated) + flt(wip_open_po_allocated)
			production_qty_based_on_child_stock_wip_open_po = math.ceil(
				total_allocated * parent_per_child_factor
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

	return filtered_data


@frappe.whitelist()
def create_material_request(item_code, qty):
	"""
	Create and submit a Material Request for the given item_code and quantity
	"""
	if not item_code:
		return {"error": "Item code is required"}

	if not qty or flt(qty) <= 0:
		return {"error": "Quantity must be greater than 0"}

	# Get item details
	if not frappe.db.exists("Item", item_code):
		return {"error": f"Item {item_code} not found"}

	item_doc = frappe.get_doc("Item", item_code)

	# Get UOM from item
	uom = item_doc.get("uom")
	if not uom:
		# If uom is not set, use stock_uom
		uom = item_doc.get("stock_uom")

	if not uom:
		return {"error": f"UOM not found for item {item_code}"}

	# Get stock_uom from item
	stock_uom = item_doc.get("stock_uom")
	if not stock_uom:
		return {"error": f"Stock UOM not found for item {item_code}"}

	conversion_factor = 1.0
	if uom != stock_uom:
		for uom_detail in item_doc.get("uoms", []):
			if uom_detail.uom == uom:
				conversion_factor = flt(uom_detail.conversion_factor)
				break

		# If not found in child table, check if item has uom_conversion_factor field
		if conversion_factor == 1.0 and hasattr(item_doc, "uom_conversion_factor"):
			conversion_factor = flt(item_doc.get("uom_conversion_factor", 1.0))

	# Calculate schedule_date (7 days from now)
	from frappe.utils import add_days, today

	schedule_date = add_days(today(), 7)

	# Set company name
	company = "Prakash Steel Products Pvt Ltd"

	# Verify company exists
	if not frappe.db.exists("Company", company):
		return {"error": f"Company '{company}' not found in the system."}

	try:
		# Set warehouse
		warehouse = "Bright Bar Unit - PSPL"

		# Verify warehouse exists
		if not frappe.db.exists("Warehouse", warehouse):
			return {"error": f"Warehouse '{warehouse}' not found in the system."}

		# Create Material Request
		mr_doc = frappe.get_doc(
			{
				"doctype": "Material Request",
				"company": company,
				"transaction_date": today(),
				"schedule_date": schedule_date,
				"material_request_type": "Purchase",
				"items": [
					{
						"item_code": item_code,
						"qty": flt(qty),
						"uom": uom,
						"stock_uom": stock_uom,
						"conversion_factor": conversion_factor,
						"warehouse": warehouse,
					}
				],
			}
		)

		mr_doc.insert()
		mr_doc.submit()

		return {
			"material_request": mr_doc.name,
			"message": f"Material Request {mr_doc.name} created and submitted successfully",
		}
	except Exception as e:
		return {"error": f"Error creating Material Request: {str(e)}"}


@frappe.whitelist()
def create_material_requests_automatically(filters=None):
	"""
	Create Material Requests automatically for all items with net_po_recommendation > 0
	"""
	# Parse filters if it's a JSON string
	if isinstance(filters, str):
		import json

		try:
			filters = json.loads(filters)
		except:
			filters = {}

	if not filters:
		filters = {}

	# Get report data
	_, data = execute(filters)

	if not data:
		return {
			"success_count": 0,
			"error_count": 0,
			"material_requests": [],
			"message": "No data found in report",
		}

	# Filter items with net_po_recommendation > 0
	items_to_process = [
		row
		for row in data
		if row.get("net_po_recommendation") and flt(row.get("net_po_recommendation", 0)) > 0
	]

	if not items_to_process:
		return {
			"success_count": 0,
			"error_count": 0,
			"material_requests": [],
			"message": "No items with Net PO Recommendation > 0 found",
		}

	success_count = 0
	error_count = 0
	material_requests = []
	errors = []

	# Create Material Request for each item
	for row in items_to_process:
		item_code = row.get("item_code")
		qty = flt(row.get("net_po_recommendation", 0))

		if not item_code or qty <= 0:
			error_count += 1
			errors.append(f"{item_code}: Invalid quantity")
			continue

		try:
			result = create_material_request(item_code, qty)
			if result.get("error"):
				error_count += 1
				errors.append(f"{item_code}: {result.get('error')}")
			else:
				success_count += 1
				material_requests.append(result.get("material_request"))
		except Exception as e:
			error_count += 1
			errors.append(f"{item_code}: {str(e)}")

	return {
		"success_count": success_count,
		"error_count": error_count,
		"material_requests": material_requests,
		"errors": errors[:10] if len(errors) > 10 else errors,  # Limit errors to first 10
		"message": f"Created {success_count} Material Request(s), {error_count} failed",
	}


def get_stock_map(item_codes):
	if not item_codes:
		return {}

	if len(item_codes) == 1:
		item_codes_tuple = (next(iter(item_codes)),)
	else:
		item_codes_tuple = tuple(item_codes)

	# Use current live stock from Bin
	bin_rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) as stock
		FROM `tabBin`
		WHERE item_code IN %s
		GROUP BY item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)

	return {d.item_code: flt(d.stock) for d in bin_rows}


def get_sales_order_qty_map(filters):
	so_rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as so_qty
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.custom_closed, 0) = 0
		GROUP BY
			soi.item_code
		""",
		as_dict=True,
	)

	return {d.item_code: flt(d.so_qty) for d in so_rows}


def get_qualified_demand_map():
	from frappe.utils import today

	today_date = today()

	so_rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as so_qty
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.custom_closed, 0) = 0
			AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
		GROUP BY
			soi.item_code
		""",
		(today_date,),
		as_dict=True,
	)

	till_today_map = {d.item_code: flt(d.so_qty) for d in so_rows}
	spike_map = {item_code: 0.0 for item_code in till_today_map}

	return till_today_map, spike_map


def calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map):

	from frappe.utils import today, add_days

	today_date = today()
	spike_map = {}

	# Get all Spike Master records
	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)

	# Create a map of item_type -> spike master config
	spike_master_map = {}
	for sm in spike_master_records:
		spike_master_map[sm.item_type] = {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}

	# IMPORTANT: Spike logic ONLY applies to buffer items
	# Get all buffer items only
	buffer_items = [
		item_code for item_code in item_codes if item_buffer_map.get(item_code, "Non-Buffer") == "Buffer"
	]

	if not buffer_items:
		# No buffer items, return empty spike_map (all items will get spike = 0)
		return spike_map

	# Get item details for buffer items (item_type and TOG)
	buffer_items_with_details = []
	for item_code in buffer_items:
		item_type = item_type_map.get(item_code)
		tog = flt(item_tog_map.get(item_code, 0))
		if item_type and tog > 0:
			buffer_items_with_details.append(
				{
					"item_code": item_code,
					"item_type": item_type,
					"tog": tog,
				}
			)

	# Group items by item_type for efficient querying
	items_by_type = {}
	for item_info in buffer_items_with_details:
		item_type = item_info["item_type"]
		if item_type not in items_by_type:
			items_by_type[item_type] = []
		items_by_type[item_type].append(item_info)

	# Calculate spike for each item_type group
	for item_type, items_list in items_by_type.items():
		# Get spike master config for this item_type
		spike_config = spike_master_map.get(item_type)
		if not spike_config:
			# No spike master config for this item_type, set spike = 0 for all items
			for item_info in items_list:
				spike_map[item_info["item_code"]] = 0.0
			continue

		demand_horizon = spike_config["demand_horizon"]

		# If demand_horizon is 0, spike is disabled for this item type
		if not demand_horizon or demand_horizon <= 0:
			for item_info in items_list:
				spike_map[item_info["item_code"]] = 0.0
			continue

		start_date = add_days(today_date, 1)  # Tomorrow
		end_date = add_days(today_date, demand_horizon)

		# Get item codes for this item_type
		item_codes_for_type = [item["item_code"] for item in items_list]

		if not item_codes_for_type:
			continue

		# Build SQL query for items in this type
		if len(item_codes_for_type) == 1:
			item_codes_tuple = (item_codes_for_type[0],)
		else:
			item_codes_tuple = tuple(item_codes_for_type)

		if end_date:
			so_rows = frappe.db.sql(
				"""
				SELECT
					soi.item_code,
					GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) as so_qty,
					IFNULL(soi.delivery_date, '1900-01-01') as delivery_date,
					so.name as sales_order_name
				FROM
					`tabSales Order` so
				INNER JOIN
					`tabSales Order Item` soi ON soi.parent = so.name
				WHERE
					so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
					AND so.docstatus = 1
					AND IFNULL(soi.custom_closed, 0) = 0
					AND soi.item_code IN %s
					AND IFNULL(soi.delivery_date, '1900-01-01') >= %s
					AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
				""",
				(item_codes_tuple, start_date, end_date),
				as_dict=True,
			)
		else:
			# All future SOs (no upper bound)
			# If delivered_qty > qty, returns 0 (not negative)
			so_rows = frappe.db.sql(
				"""
				SELECT
					soi.item_code,
					GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) as so_qty,
					IFNULL(soi.delivery_date, '1900-01-01') as delivery_date,
					so.name as sales_order_name
				FROM
					`tabSales Order` so
				INNER JOIN
					`tabSales Order Item` soi ON soi.parent = so.name
				WHERE
					so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
					AND so.docstatus = 1
					AND IFNULL(soi.custom_closed, 0) = 0
					AND soi.item_code IN %s
					AND IFNULL(soi.delivery_date, '1900-01-01') > %s
				""",
				(item_codes_tuple, today_date),
				as_dict=True,
			)

		so_by_item = {}
		for row in so_rows:
			item_code = row.item_code
			so_qty = flt(row.so_qty)
			if so_qty > 0:  # Only consider positive quantities
				if item_code not in so_by_item:
					so_by_item[item_code] = []
				so_by_item[item_code].append(
					{
						"qty": so_qty,
						"delivery_date": row.delivery_date,
						"sales_order": row.sales_order_name,
					}
				)

		# Calculate spike for each item
		for item_info in items_list:
			item_code = item_info["item_code"]

			# Get sales orders for this item
			so_data_list = so_by_item.get(item_code, [])

			if not so_data_list:
				spike_map[item_code] = 0.0
				continue

			# Sum ALL future SO qty within demand horizon
			# No threshold check here - combined (till_today + spike) is compared against threshold in get_qualified_demand_for_item
			total_future_qty = sum(so_data["qty"] for so_data in so_data_list)
			spike_map[item_code] = total_future_qty

	for item_code in item_codes:
		if item_buffer_map.get(item_code, "Non-Buffer") != "Buffer":
			spike_map[item_code] = 0.0

	return spike_map


def get_qualified_demand_for_item(
	item_code,
	till_today_map,
	spike_map,
	item_buffer_map,
	item_tog_map=None,
	item_type_map=None,
	spike_master_map=None,
):
	till_today = flt(till_today_map.get(item_code, 0))

	# IMPORTANT: Spike logic ONLY applies to buffer items
	# For non-buffer items, spike is always 0 (no calculation needed)
	buffer_flag = item_buffer_map.get(item_code, "Non-Buffer")
	if buffer_flag != "Buffer":
		spike = 0.0  # Non-buffer items always have spike = 0 (no spike logic)
		qualified_demand = till_today + spike
		return qualified_demand, till_today, spike
	else:
		# Buffer items only: calculate spike from Spike Master
		spike = flt(spike_map.get(item_code, 0))  # Buffer items can have spike
		qualified_demand = till_today + spike

		# Additional check for buffer items ONLY: if qualified_demand < (TOG * spike_threshold / 100), set to 0
		if item_tog_map and item_type_map and spike_master_map:
			tog = flt(item_tog_map.get(item_code, 0))
			item_type = item_type_map.get(item_code)

			if tog > 0 and item_type:
				spike_config = spike_master_map.get(item_type)
				if spike_config:
					spike_threshold_pct = flt(spike_config.get("spike_threshold", 0))
					spike_threshold_qty = tog * spike_threshold_pct / 100

					# If qualified_demand < spike_threshold_qty, set to 0
					if qualified_demand < spike_threshold_qty:
						qualified_demand = 0.0

		return qualified_demand, till_today, spike


def get_wip_map():
	# Get Production Plan Settings
	try:
		settings = frappe.get_single("Production planning settings")
	except Exception:
		# If settings don't exist, default to work order method
		settings = frappe._dict({"from_work_order": 1, "from_production_plan": 0})

	wip_map = {}

	# Check which method is selected
	if settings.get("from_work_order"):
		# Existing logic: Get WIP from Work Order (qty - produced_qty) - only for Work Orders that are not Completed or Cancelled
		wip_rows_wo = frappe.db.sql(
			"""
			SELECT
				wo.production_item as item_code,
				SUM(GREATEST(0, IFNULL(wo.qty, 0) - IFNULL(wo.produced_qty, 0))) as wip_qty
			FROM
				`tabWork Order` wo
			WHERE
				wo.status NOT IN ('Completed', 'Cancelled')
				AND wo.docstatus = 1
			GROUP BY
				wo.production_item
			""",
			as_dict=True,
		)

		# Build WIP map from Work Orders only
		for row in wip_rows_wo:
			item_code = row.item_code
			wip_map[item_code] = flt(row.wip_qty)

	elif settings.get("from_production_plan"):
		# New logic: Get WIP from Production Plan
		pp_filters = {"docstatus": 1}
		production_plans = frappe.get_all("Production Plan", filters=pp_filters, fields=["name"])

		for pp in production_plans:
			pp_name = pp.name

			# Get Production Plan document to access po_items child table
			try:
				pp_doc = frappe.get_doc("Production Plan", pp_name)

				# Check if po_items child table exists
				if hasattr(pp_doc, "po_items") and pp_doc.po_items:
					# Iterate through each item in po_items
					for po_item in pp_doc.po_items:
						item_code = po_item.item_code
						planned_qty = flt(po_item.planned_qty) if po_item.planned_qty else 0

						if not item_code:
							continue

						finished_weight_docs = frappe.db.sql(
							"""
							SELECT name, finish_weight
							FROM `tabFinish Weight`
							WHERE production_plan = %s
							AND docstatus = 1
							AND item_code = %s
							ORDER BY name
							""",
							(pp_name, item_code),
							as_dict=True,
						)

						total_finished_from_fw = sum(flt(doc.finish_weight) for doc in finished_weight_docs)

						bright_bar_production_docs = frappe.db.sql(
							"""
							SELECT name, fg_weight
							FROM `tabBright Bar Production`
							WHERE production_plan = %s
							AND docstatus = 1
							AND finished_good = %s
							ORDER BY name
							""",
							(pp_name, item_code),
							as_dict=True,
						)

						total_finished_from_bbp = sum(
							flt(doc.fg_weight) for doc in bright_bar_production_docs
						)

						total_finished = total_finished_from_fw + total_finished_from_bbp

						wip_qty = max(0, planned_qty - total_finished)

						if item_code in wip_map:
							wip_map[item_code] += wip_qty
						else:
							wip_map[item_code] = wip_qty

			except Exception as e:
				continue

	return wip_map


def get_mrq_map():
	mrq_rows = frappe.db.sql(
		"""
		SELECT
			mri.item_code,
			SUM(GREATEST(0, mri.qty - IFNULL(mri.ordered_qty, 0))) as mrq_qty
		FROM
			`tabMaterial Request` mr
		INNER JOIN
			`tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE
			mr.docstatus = 1
			AND mr.status IN ('Pending', 'Partially Ordered')
		GROUP BY
			mri.item_code
		""",
		as_dict=True,
	)

	return {d.item_code: flt(d.mrq_qty) for d in mrq_rows}


def get_open_po_map():
	# Get all Purchase Order Items with their qty and received_qty
	po_rows = frappe.db.sql(
		"""
		SELECT
			poi.item_code,
			poi.qty,
			IFNULL(poi.received_qty, 0) as received_qty
		FROM
			`tabPurchase Order` po
		INNER JOIN
			`tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE
			po.docstatus = 1
			AND po.status NOT IN ('Cancelled', 'Closed')
			AND IFNULL(poi.custom_closed, 0) = 0
		""",
		as_dict=True,
	)

	# Calculate open_po for each item
	# For each PO item: if (qty - received_qty) < 0, treat as 0, otherwise use (qty - received_qty)
	open_po_map = {}
	for row in po_rows:
		item_code = row.item_code
		qty = flt(row.qty)
		received_qty = flt(row.received_qty)
		open_qty = max(0, qty - received_qty)  # If negative, treat as 0

		if item_code in open_po_map:
			open_po_map[item_code] += open_qty
		else:
			open_po_map[item_code] = open_qty

	return open_po_map


def get_open_so_map_for_priority(item_codes):
	"""
	Returns {item_code: [{pending_qty, order_status}, ...]}
	All open SOs (Total SO), sorted by delivery_date ASC — used for FIFO priority calculation.
	"""
	if not item_codes:
		return {}
	if len(item_codes) == 1:
		items_tuple = (next(iter(item_codes)),)
	else:
		items_tuple = tuple(item_codes)
	result = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			so.transaction_date,
			soi.delivery_date,
			GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code IN %s
		  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
		ORDER BY soi.delivery_date ASC
		""",
		(items_tuple,),
		as_dict=True,
	)
	so_map = defaultdict(list)
	for r in result:
		so_map[r.item_code].append(
			{
				"pending_qty": flt(r.pending_qty),
				"order_status": _compute_order_status(r.delivery_date, r.transaction_date),
			}
		)
	return so_map


@frappe.whitelist()
def get_priority_breakdown(item_code):
	"""
	Returns full priority calculation breakdown for a non-buffer item:
	- Own FIFO priority (level vs open SOs)
	- BOM parents and their priorities
	- Final propagated priority
	"""
	item = frappe.db.get_value("Item", item_code, ["custom_buffer_flag", "custom_item_type"], as_dict=True)
	if not item:
		frappe.throw(f"Item {item_code} not found")

	buffer_flag = item.custom_buffer_flag or "Non-Buffer"
	item_type = item.custom_item_type
	sku_type = calculate_sku_type(buffer_flag, item_type) or ""

	# Stock
	stock_data = frappe.db.sql(
		"SELECT SUM(actual_qty) as stock FROM `tabBin` WHERE item_code = %s",
		(item_code,),
		as_dict=True,
	)
	stock = flt(stock_data[0].stock if stock_data else 0)

	wip_map = get_wip_map()
	wip = 0 if sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(item_code, 0))

	open_po_map = get_open_po_map()
	open_po = flt(open_po_map.get(item_code, 0))

	if sku_type in ["BOTO", "PTO", "TRMTO"]:
		level = stock + open_po
		level_formula = f"Stock ({stock}) + Open PO ({open_po})"
	else:
		level = stock + wip
		level_formula = f"Stock ({stock}) + WIP ({wip})"

	# Open SOs with full FIFO detail (including delivery_date)
	so_rows = frappe.db.sql(
		"""
		SELECT so.transaction_date, soi.delivery_date,
		       GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code = %s
		  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
		ORDER BY soi.delivery_date ASC
		""",
		(item_code,),
		as_dict=True,
	)

	available = flt(level)
	worst_shortage = 0
	worst_no_shortage = 0
	fifo_detail = []
	for so in so_rows:
		required = flt(so.pending_qty)
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		order_status = _compute_order_status(so.delivery_date, so.transaction_date) or ""
		p = _STATUS_PRIORITY.get(order_status, 0)
		if shortage > 0:
			if p > worst_shortage:
				worst_shortage = p
		else:
			if p > worst_no_shortage:
				worst_no_shortage = p
		fifo_detail.append(
			{
				"delivery_date": str(so.delivery_date) if so.delivery_date else "",
				"pending_qty": math.ceil(required),
				"allocated": math.ceil(allocated),
				"shortage": math.ceil(shortage),
				"order_status": order_status,
			}
		)

	if not so_rows:
		own_priority = ""
	elif worst_shortage > 0:
		own_priority = _PRIORITY_TO_COLOUR.get(worst_shortage, "")
	elif worst_no_shortage > 0:
		own_priority = _PRIORITY_TO_COLOUR.get(worst_no_shortage, "")
	else:
		own_priority = ""

	# BOM parents — N-level upward BFS to collect all ancestors
	# Then propagate downward so each parent shows its true propagated priority.
	_bd_child_to_parents = defaultdict(set)
	_bd_all_items = {item_code}
	_bd_frontier = {item_code}
	while _bd_frontier:
		_bd_f_tuple = tuple(_bd_frontier) if len(_bd_frontier) > 1 else (next(iter(_bd_frontier)),)
		_bd_up = frappe.db.sql(
			"""
			SELECT b.item AS parent_item, bi.item_code AS child_item
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
			WHERE bi.item_code IN %s
			  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
			""",
			(_bd_f_tuple,),
			as_dict=True,
		)
		_bd_new = set()
		for _r in _bd_up:
			_bd_child_to_parents[_r.child_item].add(_r.parent_item)
			if _r.parent_item not in _bd_all_items:
				_bd_new.add(_r.parent_item)
		_bd_all_items.update(_bd_new)
		_bd_frontier = _bd_new

	# Compute own FIFO priority for all ancestors
	_bd_ancestors = _bd_all_items - {item_code}
	_bd_priority_map = {item_code: own_priority}
	if _bd_ancestors:
		_bd_anc_tuple = tuple(_bd_ancestors) if len(_bd_ancestors) > 1 else (next(iter(_bd_ancestors)),)
		_bd_item_rows = frappe.db.sql(
			"SELECT item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE item_code IN %s",
			(_bd_anc_tuple,),
			as_dict=True,
		)
		_bd_stock_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) as stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(_bd_anc_tuple,),
			as_dict=True,
		)
		_bd_stock_map = {r.item_code: flt(r.stock) for r in _bd_stock_rows}
		_bd_anc_so_map = get_open_so_map_for_priority(list(_bd_ancestors))
		for _ai in _bd_item_rows:
			_aic = _ai.item_code
			_asku = calculate_sku_type(_ai.custom_buffer_flag or "Non-Buffer", _ai.custom_item_type) or ""
			_astock = _bd_stock_map.get(_aic, 0)
			_awip = 0 if _asku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_aic, 0))
			_apo = flt(open_po_map.get(_aic, 0))
			_alevel = (_astock + _apo) if _asku in ["BOTO", "PTO", "TRMTO"] else (_astock + _awip)
			_bd_priority_map[_aic] = _non_buffer_priority(_aic, _alevel, _bd_anc_so_map)

	# BFS downward — propagate worst parent priority through the ancestor tree
	_bd_resolved = _bd_all_items - set(_bd_child_to_parents.keys())
	_bd_changed = True
	while _bd_changed:
		_bd_changed = False
		for _child, _parents in _bd_child_to_parents.items():
			if _child in _bd_resolved:
				continue
			if not _parents.issubset(_bd_resolved):
				continue
			_worst = 0
			for _par in _parents:
				_pc = _bd_priority_map.get(_par, "")
				if _pc:
					_pv = _STATUS_PRIORITY.get(_pc.upper(), 0)
					if _pv > _worst:
						_worst = _pv
			_bd_priority_map[_child] = (
				_PRIORITY_TO_COLOUR.get(_worst, "") if _worst > 0 else _bd_priority_map.get(_child, "")
			)
			_bd_resolved.add(_child)
			_bd_changed = True

	# Build parent_details for direct parents only (show own + propagated priority)
	_direct_parent_codes = [
		r.parent_item
		for r in frappe.db.sql(
			"""
		SELECT DISTINCT b.item AS parent_item
		FROM `tabBOM` b
		INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
		WHERE bi.item_code = %s
		  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
		""",
			(item_code,),
			as_dict=True,
		)
	]
	parent_details = []
	for pic in _direct_parent_codes:
		pitem = frappe.db.get_value("Item", pic, ["custom_buffer_flag", "custom_item_type"], as_dict=True)
		if not pitem:
			continue
		p_sku = calculate_sku_type(pitem.custom_buffer_flag or "Non-Buffer", pitem.custom_item_type) or ""
		p_stock = flt(
			(
				frappe.db.sql(
					"SELECT SUM(actual_qty) as s FROM `tabBin` WHERE item_code=%s", (pic,), as_dict=True
				)
				or [{}]
			)[0].get("s")
			or 0
		)
		p_wip = 0 if p_sku in ["RBMTA", "RBMTO"] else flt(wip_map.get(pic, 0))
		p_open_po = flt(open_po_map.get(pic, 0))
		p_level = (p_stock + p_open_po) if p_sku in ["BOTO", "PTO", "TRMTO"] else (p_stock + p_wip)
		parent_details.append(
			{
				"item_code": pic,
				"sku_type": p_sku,
				"stock": math.ceil(p_stock),
				"wip": math.ceil(p_wip),
				"open_po": math.ceil(p_open_po),
				"level": math.ceil(p_level),
				"own_priority": _bd_priority_map.get(pic, ""),  # propagated priority of this parent
			}
		)

	# Final priority = worst of direct parents' propagated priorities; own if no parents
	final_priority = own_priority
	if parent_details:
		worst = 0
		for pd in parent_details:
			pc = pd["own_priority"]
			if pc:
				pv = _STATUS_PRIORITY.get(pc.upper(), 0)
				if pv > worst:
					worst = pv
		if worst > 0:
			final_priority = _PRIORITY_TO_COLOUR.get(worst, "")

	return {
		"item_code": item_code,
		"sku_type": sku_type,
		"stock": math.ceil(stock),
		"wip": math.ceil(wip),
		"open_po": math.ceil(open_po),
		"level": math.ceil(level),
		"level_formula": level_formula,
		"own_priority": own_priority,
		"fifo_detail": fifo_detail,
		"parent_details": parent_details,
		"final_priority": final_priority,
	}


def traverse_bom_for_parent_demand_simple(
	parent_item_code,
	parent_net_order_qty,
	parent_demand_map,
	visited_items,
	item_groups_cache,
	item_buffer_map,
	level=0,
):
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
		except:
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
		pass


def traverse_bom_for_parent_demand(
	parent_item_code,
	parent_net_order_qty,
	parent_demand_map,
	parent_demand_details,
	visited_items,
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
	level=0,
):
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
		except:
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
		pass


def traverse_bom_for_po(
	item_code, required_qty, po_recommendations, remaining_stock, visited_items, item_groups_cache, level=0
):
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
		except:
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

			# Add to PO recommendations (sum if already exists - same item may appear in multiple BOMs or have its own SO)
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
		pass
