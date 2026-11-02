# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math

from frappe import _
from frappe.utils import flt

from prakash_steel.prakash_steel.report.bright_plan.bright_plan import (
	get_data as get_bright_plan_data,
)

# BO children show up in the Bright Plan as these SKU types (custom_item_type "BO",
# buffer / non-buffer). We roll their per-parent Child Stock Shortage up by item.
BO_CHILD_SKU_TYPES = {"BOTA", "BOTO"}


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
			"label": _("BO Shortage"),
			"fieldname": "bo_shortage",
			"fieldtype": "Int",
			"width": 160,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	# The Bright Plan emits one row per (BB parent, BO child), each carrying the
	# Child Stock Shortage left after sequential soft-allocation. A single BO item
	# feeds many BB parents, so we sum those shortages per child item code.
	rows = get_bright_plan_data(filters)

	shortage_by_item: dict[str, float] = {}
	for row in rows:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue
		if not _is_bo_child(row):
			continue
		shortage_by_item[child_item_code] = shortage_by_item.get(child_item_code, 0.0) + flt(
			row.get("child_stock_shortage")
		)

	data = [
		{"item_code": item_code, "bo_shortage": math.ceil(shortage)}
		for item_code, shortage in shortage_by_item.items()
	]
	# Only BO items that are actually short feed a requirement, mirroring the
	# other "Req Plan" reports which drop zero-recommendation rows.
	data = [row for row in data if row["bo_shortage"] > 0]
	# Highest shortage first; item code as a stable tie-breaker.
	data.sort(key=lambda row: (-row["bo_shortage"], row["item_code"]))
	return data


def _is_bo_child(row: dict) -> bool:
	return (row.get("child_sku_type") or "").upper() in BO_CHILD_SKU_TYPES
