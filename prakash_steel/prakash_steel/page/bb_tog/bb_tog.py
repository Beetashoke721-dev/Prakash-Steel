# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe

from prakash_steel.utils.hbt_utils import (
	METRIC_COL as _METRIC_COL_MAP,
	MONTH_TO_NUM,
	FISCAL_MONTH_ORDER,
	assign_hbt_labels,
	get_customer_hbt_map,
	period_date_range,
)
from prakash_steel.utils.whitelist_permissions import require_permission
from frappe.utils import getdate


def _get_tog_period_months() -> list[tuple[int, int]]:
	"""Same logic as get_period_months() but reads from TOG Horizon Settings."""
	settings = frappe.get_single("TOG Horizon Settings")

	fiscal_year = settings.fiscal_year
	from_month = settings.from_month
	to_month = settings.to_month

	if not fiscal_year or not from_month or not to_month:
		frappe.throw(
			"Please configure Fiscal Year, From Month, and To Month in TOG Horizon Settings.",
			title="Incomplete TOG Horizon Settings",
		)

	from_num = MONTH_TO_NUM[from_month]
	to_num = MONTH_TO_NUM[to_month]

	from_idx = FISCAL_MONTH_ORDER.index(from_num)
	to_idx = FISCAL_MONTH_ORDER.index(to_num)

	if from_idx > to_idx:
		frappe.throw(
			f"From Month ({from_month}) must come before To Month ({to_month}) in TOG Horizon Settings.",
			title="Invalid Period Range",
		)

	fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
	start_year = getdate(fy_doc.year_start_date).year
	end_year = getdate(fy_doc.year_end_date).year

	return [(start_year if m >= 4 else end_year, m) for m in FISCAL_MONTH_ORDER[from_idx: to_idx + 1]]


@frappe.whitelist()
def get_bb_tog_data(view_by: str = "Sale Quantity") -> dict:
	require_permission("Sales Invoice", "read")

	if view_by not in _METRIC_COL_MAP:
		view_by = "Sale Quantity"
	metric_col = _METRIC_COL_MAP[view_by]

	period_months = _get_tog_period_months()
	if not period_months:
		return {"data": [], "period_label": ""}

	from_date, to_date = period_date_range(period_months)

	period_label = f"{from_date.strftime('%b %Y')} – {to_date.strftime('%b %Y')}"

	raw_rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			sii.item_code,
			SUM({metric_col}) AS total,
			COUNT(DISTINCT YEAR(si.posting_date) * 100 + MONTH(si.posting_date)) AS frequency
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		WHERE
			si.docstatus = 1
			AND i.custom_item_type = 'BB'
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY sii.item_code
		ORDER BY total DESC
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	if not raw_rows:
		return {"data": [], "period_label": period_label}

	customer_hbt_map = get_customer_hbt_map(from_date, to_date, metric_col)

	item_group_rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			sii.item_code,
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer) AS group_name,
			SUM({metric_col}) AS total
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		INNER JOIN `tabCustomer` cust ON cust.name = si.customer
		WHERE
			si.docstatus = 1
			AND i.custom_item_type = 'BB'
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			sii.item_code,
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer)
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	item_hbt_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"H": 0.0, "B": 0.0, "T": 0.0})
	for r in item_group_rows:
		bucket = customer_hbt_map.get(r.group_name, "T")
		item_hbt_buckets[r.item_code][bucket] += float(r.total or 0)

	assign_hbt_labels(raw_rows)

	_empty = {"H": 0.0, "B": 0.0, "T": 0.0}
	data = [
		{
			"item_code": row["item_code"],
			"total": float(row["total"] or 0),
			"contr_pct": round(float(row.get("contr_pct") or 0), 1),
			"cumu_pct": round(float(row.get("cumu_pct") or 0), 1),
			"hbt": row["hbt"],
			"frequency": int(row["frequency"] or 0),
			"h": item_hbt_buckets.get(row["item_code"], _empty)["H"],
			"b": item_hbt_buckets.get(row["item_code"], _empty)["B"],
			"t": item_hbt_buckets.get(row["item_code"], _empty)["T"],
			# --- new columns: logic TBD ---
			"adu": None,          # Average Daily Usage
			"lt": None,           # Lead Time
			"fos": None,          # Fill Order Size
			"tog": None,          # TOG
			"current_tog": None,  # Current TOG
		}
		for row in raw_rows
	]

	return {"data": data, "period_label": period_label}
