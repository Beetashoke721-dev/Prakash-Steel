# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _

from prakash_steel.utils.hbt_utils import (
	METRIC_COL,
	assign_hbt_labels,
	get_customer_hbt_map,
	get_period_months,
	period_date_range,
)
from prakash_steel.utils.whitelist_permissions import require_permission

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	require_permission("Sales Invoice", "read")

	filters = filters or {}
	view_by: str = filters.get("view_by") or "Sale Quantity"

	period_months = get_period_months()
	columns = _get_columns(view_by)
	data = _get_data(period_months, view_by)

	return columns, data


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns(view_by: str) -> list[dict]:
	# Sale Value temporarily hidden — _get_data returns [] for it; use Sale Quantity columns as placeholder
	if view_by == "Sale Value":
		view_by = "Sale Quantity"

	if view_by not in METRIC_COL:
		frappe.throw(_("{0} is not yet implemented for this report.").format(view_by))

	# Uncomment when Sale Value is ready to expose:
	# if view_by == "Sale Value":
	#     total_label = _("Total Sale Value")
	#     total_fieldtype = "Currency"
	# else:
	total_label = _("Total Sale Quantity")
	total_fieldtype = "Int"

	return [
		{"label": _("Item Name"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 220},
		{"label": _("Item Type"), "fieldname": "item_type", "fieldtype": "Data", "width": 100},
		{"label": _("SKU Type"), "fieldname": "sku_type", "fieldtype": "Data", "width": 110},
		{"label": total_label, "fieldname": "total", "fieldtype": total_fieldtype, "width": 160},
		{"label": _("Contr%"), "fieldname": "contr_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
		{"label": _("Cumu%"), "fieldname": "cumu_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
		{"label": _("HBT"), "fieldname": "hbt", "fieldtype": "Data", "width": 60},
		{"label": _("Frequency"), "fieldname": "frequency", "fieldtype": "Int", "width": 100},
		{"label": "<span style='color:#1a7a3f;font-weight:700;'>Head Customer</span>", "fieldname": "h", "fieldtype": total_fieldtype, "width": 160},
		{"label": "<span style='color:#d4a000;font-weight:700;'>Body Customer</span>", "fieldname": "b", "fieldtype": total_fieldtype, "width": 160},
		{"label": "<span style='color:#c0152a;font-weight:700;'>Tail Customer</span>", "fieldname": "t", "fieldtype": total_fieldtype, "width": 160},
	]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(period_months: list[tuple[int, int]], view_by: str) -> list[dict]:
	if not period_months:
		return []

	# Sale Value is implemented but temporarily hidden from users
	if view_by == "Sale Value":
		return []

	if view_by not in METRIC_COL:
		frappe.throw(_("{0} is not yet implemented for this report.").format(view_by))

	metric_col = METRIC_COL[view_by]
	from_date, to_date = period_date_range(period_months)

	# Step 1: item totals + frequency — metric_col from internal constant, safe to interpolate
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
		return []

	# Step 2: company-wide customer-group HBT map
	customer_hbt_map = get_customer_hbt_map(from_date, to_date, metric_col)

	# Step 3: per-item per-customer-group totals (BB only)
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

	# Build {item_code: {H: x, B: x, T: x}} buckets
	item_hbt_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"H": 0.0, "B": 0.0, "T": 0.0})
	for r in item_group_rows:
		bucket = customer_hbt_map.get(r.group_name, "T")
		item_hbt_buckets[r.item_code][bucket] += float(r.total or 0)

	# Step 4: assign HBT labels in-place via shared utility
	assign_hbt_labels(raw_rows)

	# Step 5: fetch item_type and sku_type from Item master
	item_codes = [row["item_code"] for row in raw_rows]
	item_master_rows = frappe.db.sql(
		"""
		SELECT name AS item_code, custom_item_type AS item_type, custom_sku_type AS sku_type
		FROM `tabItem` WHERE name IN %(item_codes)s
		""",
		{"item_codes": item_codes},
		as_dict=True,
	)
	item_master_map = {r.item_code: r for r in item_master_rows}

	_empty = {"H": 0.0, "B": 0.0, "T": 0.0}
	return [
		{
			"item_code": row["item_code"],
			"item_type": item_master_map.get(row["item_code"], {}).get("item_type") or "",
			"sku_type": item_master_map.get(row["item_code"], {}).get("sku_type") or "",
			"total": int(row["total"] or 0),
			"contr_pct": row["contr_pct"],
			"cumu_pct": row["cumu_pct"],
			"hbt": row["hbt"],
			"frequency": int(row["frequency"] or 0),
			"h": int(item_hbt_buckets.get(row["item_code"], _empty)["H"]),
			"b": int(item_hbt_buckets.get(row["item_code"], _empty)["B"]),
			"t": int(item_hbt_buckets.get(row["item_code"], _empty)["T"]),
		}
		for row in raw_rows
	]
