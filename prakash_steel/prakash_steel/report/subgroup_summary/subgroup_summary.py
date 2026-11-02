# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from collections import defaultdict

from frappe import _
from frappe.utils import flt

from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import get_data as get_rolled_plan_data


def execute(filters: dict | None = None):
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Subgrp+Shape"),
			"fieldname": "subgrp_shape",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Sum of Order Recommendation"),
			"fieldname": "sum_of_order_recommendation",
			"fieldtype": "Float",
			"width": 220,
		},
		{
			"label": _("Sum of Net Qty"),
			"fieldname": "sum_of_net_qty",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Actual / Planned Qty%"),
			"fieldname": "actual_planned_qty_pct",
			"fieldtype": "Float",
			"precision": 2,
			"width": 170,
		},
	]


def get_data(filters: dict | None = None) -> list[dict]:
	"""One row per distinct subgrp_shape, aggregating Rolled Plan's
	net_order_recommendation and net_qty across all its rows for that group.
	actual_planned_qty_pct is already computed per subgrp_shape group in Rolled
	Plan (same value on every row of the group), so it's picked up as-is rather
	than recomputed here."""
	rolled_plan_rows = get_rolled_plan_data(filters)

	order_rec_sum = defaultdict(float)
	net_qty_sum = defaultdict(float)
	actual_planned_pct_map = {}
	subgrp_shapes = []
	seen = set()
	for row in rolled_plan_rows:
		subgrp_shape = row.get("subgrp_shape") or ""
		if subgrp_shape not in seen:
			seen.add(subgrp_shape)
			subgrp_shapes.append(subgrp_shape)
			actual_planned_pct_map[subgrp_shape] = row.get("actual_planned_qty_pct")
		order_rec_sum[subgrp_shape] += flt(row.get("net_order_recommendation"))
		net_qty_sum[subgrp_shape] += flt(row.get("net_qty"))

	return [
		{
			"subgrp_shape": subgrp_shape,
			"sum_of_order_recommendation": order_rec_sum[subgrp_shape],
			"sum_of_net_qty": net_qty_sum[subgrp_shape],
			"actual_planned_qty_pct": actual_planned_pct_map[subgrp_shape],
		}
		for subgrp_shape in subgrp_shapes
	]
