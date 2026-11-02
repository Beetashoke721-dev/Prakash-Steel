# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math

from frappe import _
from frappe.utils import flt

from prakash_steel.prakash_steel.report.bright_plan.bright_plan import (
	get_data as get_bright_plan_data,
)

# RB children show up in the Bright Plan as these SKU types (custom_item_type "RB",
# buffer / non-buffer). We roll their per-parent Child Stock Shortage up by item.
RB_CHILD_SKU_TYPES = {"RBMTA", "RBMTO"}


def execute(filters: dict | None = None):
	return get_columns(), get_data(filters)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 220,
		},
		{
			"label": _("RB Shortage"),
			"fieldname": "rb_shortage",
			"fieldtype": "Int",
			"width": 160,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	# The Bright Plan emits one row per (BB parent, RB child), each carrying the
	# Child Stock Shortage left after sequential soft-allocation. A single RB item
	# feeds many BB parents, so we sum those shortages per child item code.
	rows = get_bright_plan_data(filters)

	shortage_by_item: dict[str, float] = {}
	for row in rows:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue
		if not _is_rb_child(row):
			continue
		shortage_by_item[child_item_code] = shortage_by_item.get(child_item_code, 0.0) + flt(
			row.get("child_stock_shortage")
		)

	data = [
		{"item_code": item_code, "rb_shortage": math.ceil(shortage)}
		for item_code, shortage in shortage_by_item.items()
	]
	# Only RB items that are actually short feed a requirement, mirroring the
	# other "Req Plan" reports which drop zero-recommendation rows.
	data = [row for row in data if row["rb_shortage"] > 0]
	# Highest shortage first; item code as a stable tie-breaker.
	data.sort(key=lambda row: (-row["rb_shortage"], row["item_code"]))
	return data


def _is_rb_child(row: dict) -> bool:
	return (row.get("child_sku_type") or "").upper() in RB_CHILD_SKU_TYPES
