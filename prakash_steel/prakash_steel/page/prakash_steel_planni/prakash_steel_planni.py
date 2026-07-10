# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import math
import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission


def calculate_sku_type(buffer_flag, item_type) -> str | None:
	"""
	Same mapping logic as calculate_sku_type in production_order_recomendation.py
	buffer_flag: 'Buffer' or other
	item_type: 'BB', 'RB', 'BO', 'RM', 'Traded'
	"""
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


@frappe.whitelist()
def get_sku_type_on_hand_status() -> dict | list:
	"""
	Get on-hand status data grouped by SKU type for buffer items
	Returns data for pie charts showing distribution by color (BLACK, RED, YELLOW, GREEN, WHITE)

	For each SKU type:
	- Count items by on_hand_colour
	- Calculate percentage: (count_of_color / total_items) * 100
	- Return data in format suitable for pie charts
	"""
	require_permission("Item", "report")
	# Get ALL buffer items - same as po_recomendation_for_psp report
	items_data = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.custom_buffer_flag as buffer_flag,
			i.custom_item_type as item_type,
			i.safety_stock as tog
		FROM
			`tabItem` i
		WHERE
			i.custom_buffer_flag = 'Buffer'
		""",
		as_dict=1,
	)

	if not items_data:
		return {}

	# Get stock for all items
	item_codes = [item.item_code for item in items_data]
	if len(item_codes) == 1:
		item_codes_tuple = (item_codes[0],)
	else:
		item_codes_tuple = tuple(item_codes)

	stock_data = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) as stock
		FROM `tabBin`
		WHERE item_code IN %s
		GROUP BY item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)

	stock_map = {d.item_code: flt(d.stock) for d in stock_data}

	# Get qualified demand map (Open SO with delivery_date <= today) - same as po_recomendation_for_psp report
	qualified_demand_map = get_qualified_demand_map()

	items_with_sku_type = []

	for item in items_data:
		item_code = item.item_code
		buffer_flag = item.get("buffer_flag") or "Non-Buffer"
		item_type = item.get("item_type")

		# Calculate SKU type exactly as report does (all items are buffer, so use "Buffer" flag)
		sku_type = calculate_sku_type("Buffer", item_type)

		# Store item with its calculated SKU type
		items_with_sku_type.append(
			{
				"item_code": item_code,
				"buffer_flag": buffer_flag,
				"item_type": item_type,
				"tog": item.get("tog", 0),
				"sku_type": sku_type,
			}
		)

	# Now filter to only the SKU types we want for charts: BBMTA, RBMTA, BOTA, RMTA, PTA, TRMTA
	# But handle RM buffer items: they calculate as PTA but should display as RMTA
	target_sku_types = ["BBMTA", "RBMTA", "BOTA", "RMTA", "PTA", "TRMTA"]

	# Group items by SKU type and calculate on-hand status
	sku_type_data = {}

	for item in items_with_sku_type:
		item_code = item["item_code"]
		buffer_flag = item["buffer_flag"]
		item_type = item["item_type"]
		sku_type = item["sku_type"]

		# Skip items without SKU type
		if not sku_type:
			continue

		# Map RM buffer items to RMTA for display (even though code logic uses PTA)
		# User wants to see RMTA in the dashboard
		display_sku_type = sku_type
		if sku_type == "PTA" and item_type == "RM" and buffer_flag == "Buffer":
			display_sku_type = "RMTA"

		# Only process target SKU types
		if display_sku_type not in target_sku_types:
			continue

		# Initialize SKU type if not exists
		if display_sku_type not in sku_type_data:
			sku_type_data[display_sku_type] = {
				"BLACK": {"count": 0},
				"RED": {"count": 0},
				"YELLOW": {"count": 0},
				"GREEN": {"count": 0},
				"WHITE": {"count": 0},
			}

		# Calculate on-hand status and colour - EXACTLY as in po_recomendation_for_psp report
		on_hand_stock = flt(stock_map.get(item_code, 0))
		tog = flt(item["tog"])
		qualify_demand = flt(qualified_demand_map.get(item_code, 0))

		# Calculate On Hand Status = (on_hand_stock / (TOG + qualify_demand)) * 100, then rounded up
		# This matches the report exactly
		on_hand_status_value = None
		denominator = flt(tog) + flt(qualify_demand)
		if denominator > 0:
			on_hand_status_value = (flt(on_hand_stock) / denominator) * 100
		else:
			# If denominator is 0, set to None (cannot calculate)
			on_hand_status_value = None

		numeric_status = None
		if on_hand_status_value is not None:
			numeric_status = math.ceil(on_hand_status_value)

		# Derive On Hand Colour from numeric status - EXACTLY as in report
		# 0% → BLACK, 1-34% → RED, 35-67% → YELLOW, 68-100% → GREEN, >100% → WHITE
		if numeric_status is None:
			on_hand_colour = None  # Report sets this to None, but we'll count as BLACK
		elif numeric_status == 0:
			on_hand_colour = "BLACK"
		elif 1 <= numeric_status <= 34:
			on_hand_colour = "RED"
		elif 35 <= numeric_status <= 67:
			on_hand_colour = "YELLOW"
		elif 68 <= numeric_status <= 100:
			on_hand_colour = "GREEN"
		else:  # > 100
			on_hand_colour = "WHITE"

		# Count items by colour - ALWAYS count every item
		# If on_hand_colour is None (numeric_status is None), count as BLACK
		final_colour = on_hand_colour if on_hand_colour else "BLACK"
		if final_colour in sku_type_data[display_sku_type]:
			sku_type_data[display_sku_type][final_colour]["count"] += 1

	# Calculate percentages and format data for charts
	chart_data = {}

	for sku_type, colour_data in sku_type_data.items():
		# Calculate total items
		total_items = sum(colour["count"] for colour in colour_data.values())

		if total_items == 0:
			continue

		# Prepare chart data
		chart_data[sku_type] = {"total_items": total_items, "colours": []}

		# Process each colour
		for colour_name in ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]:
			count = colour_data[colour_name]["count"]
			if count > 0:
				percentage = (count / total_items) * 100
				chart_data[sku_type]["colours"].append(
					{"name": colour_name, "count": count, "percentage": round(percentage)}
				)

	return chart_data


def get_qualified_demand_map() -> dict:
	"""Get qualified demand map - same as po_recomendation_for_psp report
	Qualified Demand = all open SO quantity (delivery_date <= today)
	"""
	from frappe.utils import today

	so_rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(soi.qty - IFNULL(soi.delivered_qty, 0)) as so_qty
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
		GROUP BY
			soi.item_code
		""",
		(today(),),
		as_dict=True,
	)

	return {d.item_code: flt(d.so_qty) for d in so_rows}


@frappe.whitelist()
def get_pending_so_status() -> dict | list:
	"""
	Summary for Pending SO pie chart.
	All sales orders with pending delivery (all time).
	We calculate order_status using the same buffer logic as open_so_analysis
	(but at SO header level).
	"""
	require_permission("Item", "report")
	from frappe.utils import date_diff, today

	so_data = frappe.db.sql(
		"""
		SELECT
			so.name as sales_order,
			so.transaction_date as date,
			soi.delivery_date as delivery_date
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled')
			AND so.docstatus = 1
			AND (soi.qty - soi.delivered_qty) > 0
			AND IFNULL(soi.custom_closed, 0) = 0
		GROUP BY soi.name
		""",
		as_dict=1,
	)

	if not so_data:
		return {"total_items": 0, "colours": []}

	status_counts = {"BLACK": 0, "RED": 0, "YELLOW": 0, "GREEN": 0, "WHITE": 0}

	for so in so_data:
		delivery_date = so.get("delivery_date")
		transaction_date = so.get("date")
		so_name = so.get("sales_order")

		if not delivery_date or not transaction_date:
			status_counts["BLACK"] += 1
			continue

		delay_days = date_diff(today(), delivery_date)
		remaining_days = -flt(delay_days)
		lead_time = date_diff(delivery_date, transaction_date)

		buffer_status = None
		if remaining_days is not None:
			if flt(remaining_days) == 0:
				buffer_status = 0
			elif lead_time and lead_time > 0:
				buffer_status = (flt(remaining_days) / flt(lead_time)) * 100
			else:
				buffer_status = flt(remaining_days) * 100

		numeric_status = None
		if buffer_status is not None:
			numeric_status = math.ceil(buffer_status)

		if numeric_status is None:
			order_status = "BLACK"
		elif numeric_status < 0:
			order_status = "BLACK"
		elif numeric_status == 0:
			order_status = "RED"
		elif 1 <= numeric_status <= 34:
			order_status = "RED"
		elif 35 <= numeric_status <= 67:
			order_status = "YELLOW"
		elif 68 <= numeric_status <= 100:
			order_status = "GREEN"
		else:
			order_status = "WHITE"

		if order_status in status_counts:
			status_counts[order_status] += 1

	total_items = sum(status_counts.values())
	if total_items == 0:
		return {"total_items": 0, "colours": []}

	colours = []
	for colour in ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]:
		count = status_counts[colour]
		if count:
			percentage = (count / total_items) * 100
			colours.append(
				{
					"name": colour,
					"count": count,
					"percentage": round(percentage),
				}
			)

	return {"total_items": total_items, "colours": colours}


def _get_cs_on_hand_status_for_warehouse(warehouse: str) -> dict:
	"""
	Shared logic for Bright/Rolled CS On Hand Status pie charts.
	Filters CS items that have an entry in CS Tog table for the given warehouse,
	uses that warehouse's TOG and stock.
	"""
	items = frappe.db.get_all(
		"Item",
		filters={"custom_item_type": "CS", "custom_buffer_flag": "Buffer", "disabled": 0},
		fields=["name as item_code", "min_order_qty as moq"],
	)

	if not items:
		return {"total_items": 0, "colours": []}

	item_codes = {d.item_code for d in items}

	# Get TOG from CS Tog table for this warehouse
	tog_rows = frappe.db.get_all(
		"CS Tog table",
		filters=[
			["warehouse", "=", warehouse],
			["parenttype", "=", "Item"],
			["parentfield", "=", "custom_cs_tog_table"],
		],
		fields=["parent as item_code", "top_of_green"],
	)
	cs_tog_map = {row.item_code: flt(row.top_of_green) for row in tog_rows}

	# Only keep items that have this warehouse in their CS Tog table
	items = [item for item in items if item.item_code in cs_tog_map]

	if not items:
		return {"total_items": 0, "colours": []}

	# Get stock for this warehouse
	warehouse_item_codes = {d.item_code for d in items}
	stock_rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) AS stock
		FROM `tabBin`
		WHERE item_code IN %s AND warehouse = %s
		GROUP BY item_code
		""",
		(tuple(warehouse_item_codes), warehouse),
		as_dict=True,
	)
	stock_map = {row.item_code: flt(row.stock) for row in stock_rows}

	status_counts = {"BLACK": 0, "RED": 0, "YELLOW": 0, "GREEN": 0, "WHITE": 0}

	for item in items:
		tog = flt(cs_tog_map.get(item.item_code, 0))
		on_hand_stock = flt(stock_map.get(item.item_code, 0))
		on_hand_status_value = round((on_hand_stock / tog) * 100, 2) if tog else 0

		if on_hand_status_value == 0:
			colour = "BLACK"
		elif on_hand_status_value <= 34:
			colour = "RED"
		elif on_hand_status_value <= 67:
			colour = "YELLOW"
		elif on_hand_status_value <= 100:
			colour = "GREEN"
		else:
			colour = "WHITE"

		status_counts[colour] += 1

	total_items = sum(status_counts.values())
	colours = []
	for colour in ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]:
		count = status_counts[colour]
		if count:
			colours.append({
				"name": colour,
				"count": count,
				"percentage": round((count / total_items) * 100),
			})

	return {"total_items": total_items, "colours": colours}


@frappe.whitelist()
def get_bright_cs_on_hand_status() -> dict:
	"""Bright Critical Spares On Hand Status pie chart (Bright Bar Unit - PSPL)."""
	require_permission("Item", "report")
	return _get_cs_on_hand_status_for_warehouse("Bright Bar Unit - PSPL")


@frappe.whitelist()
def get_rolled_cs_on_hand_status() -> dict:
	"""Rolled Critical Spares On Hand Status pie chart (Rolling Mill - PSPL)."""
	require_permission("Item", "report")
	return _get_cs_on_hand_status_for_warehouse("Rolling Mill - PSPL")


@frappe.whitelist()
def get_open_po_status() -> dict | list:
	"""
	Placeholder for Open PO pie chart.
	For now: single black slice = 100%.
	"""
	require_permission("Item", "report")
	return {
		"total_orders": 1,
		"colours": [
			{
				"name": "BLACK",
				"count": 1,
				"percentage": 100.0,
			}
		],
	}
