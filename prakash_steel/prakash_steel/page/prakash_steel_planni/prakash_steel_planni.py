# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import math
import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_round_up_2dp,
)


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
	On Hand Colour distribution by SKU type (buffer items) for the dashboard pie
	charts.

	Runs the PO Recommendation for PSP report live (purchase-side + sell-side
	buffer views) and tallies its ``on_hand_colour`` per SKU type, so the charts
	always match the report exactly and stay real-time.
	"""
	require_permission("Item", "report")

	# RM buffer items compute as PTA in the report but the dashboard shows RMTA.
	target_sku_types = {"BBMTA", "RBMTA", "BOTA", "RMTA", "TRMTA"}
	colour_order = ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]

	sku_colour_pairs = _live_sku_on_hand_colours()

	sku_type_data = {}
	for sku_type, colour in sku_colour_pairs:
		if sku_type == "PTA":
			sku_type = "RMTA"
		if sku_type not in target_sku_types:
			continue
		if colour not in colour_order:
			continue

		bucket = sku_type_data.setdefault(sku_type, {c: 0 for c in colour_order})
		bucket[colour] += 1

	chart_data = {}
	for sku_type, colour_counts in sku_type_data.items():
		total_items = sum(colour_counts.values())
		if total_items == 0:
			continue
		chart_data[sku_type] = {
			"total_items": total_items,
			"colours": [
				{
					"name": colour_name,
					"count": colour_counts[colour_name],
					"percentage": round((colour_counts[colour_name] / total_items) * 100),
				}
				for colour_name in colour_order
				if colour_counts[colour_name] > 0
			],
		}

	return chart_data


def _live_sku_on_hand_colours() -> list[tuple[str, str]]:
	"""(sku_type, on_hand_colour) for every buffer item, straight from the PO
	Recommendation for PSP report.

	Mirrors save_daily_on_hand_colour: run the purchase-side and sell-side buffer
	views, keep the first row seen per item, and drop items the report could not
	band (on_hand_colour is None)."""
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
		execute as _po_rec_execute,
	)

	rows_by_item = {}
	for report_filters in ({"purchase": 1, "buffer_flag": 1}, {"sell": 1, "buffer_flag": 1}):
		_, rows = _po_rec_execute(report_filters)
		for row in rows or []:
			item_code = row.get("item_code")
			if item_code and item_code not in rows_by_item:
				rows_by_item[item_code] = row

	return [
		(row.get("sku_type"), row.get("on_hand_colour"))
		for row in rows_by_item.values()
		if row.get("on_hand_colour")
	]


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
		on_hand_status_value = _round_up_2dp((on_hand_stock / tog) * 100) if tog else 0

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
