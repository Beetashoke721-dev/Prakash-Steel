# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math
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

ITEM_TYPES = ("RB", "BO", "Traded")


def _get_tog_period_months() -> list[tuple[int, int]]:
	"""Same logic as bb_tog — reads from TOG Horizon Settings."""
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
def get_rb_tog_data(view_by: str = "Sale Quantity") -> dict:
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
			AND i.custom_item_type IN ('RB', 'BO', 'Traded')
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
			AND i.custom_item_type IN ('RB', 'BO', 'Traded')
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

	# ADU horizon = full period from TOG Horizon Settings
	horizon_days = (to_date - from_date).days + 1

	item_codes = [row["item_code"] for row in raw_rows]

	# Fetch LT, safety_stock (current_tog), sku_type, item_type from Item master
	item_master_rows = frappe.db.sql(
		"""
		SELECT
			name AS item_code,
			lead_time_days AS lt,
			safety_stock AS current_tog,
			custom_sku_type AS sku_type,
			custom_item_type AS item_type
		FROM `tabItem`
		WHERE name IN %(item_codes)s
		""",
		{"item_codes": item_codes},
		as_dict=True,
	)
	item_master_map = {r.item_code: r for r in item_master_rows}

	# Consumption for RB/BO items from Bright Bar Production
	bb_consumption_rows = frappe.db.sql(
		"""
		SELECT bbp.raw_material AS item_code, COALESCE(SUM(bbp.actual_rm_consumption), 0) AS qty
		FROM `tabBright Bar Production` bbp
		INNER JOIN `tabItem` i ON i.name = bbp.raw_material
		WHERE bbp.docstatus = 1
			AND LOWER(i.custom_item_type) IN ('rb', 'bo')
			AND bbp.raw_material IN %(item_codes)s
			AND bbp.production_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY bbp.raw_material
		""",
		{"item_codes": item_codes, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	bb_consumption_map = {r.item_code: float(r.qty or 0) for r in bb_consumption_rows}

	# Consumption for Traded items from Billet Cutting
	billet_consumption_rows = frappe.db.sql(
		"""
		SELECT bc.billet_size AS item_code, COALESCE(SUM(bc.billet_weight), 0) AS qty
		FROM `tabBillet Cutting` bc
		INNER JOIN `tabItem` i ON i.name = bc.billet_size
		WHERE bc.docstatus = 1
			AND LOWER(i.custom_item_type) = 'traded'
			AND bc.billet_size IN %(item_codes)s
			AND bc.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY bc.billet_size
		""",
		{"item_codes": item_codes, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	billet_consumption_map = {r.item_code: float(r.qty or 0) for r in billet_consumption_rows}

	sales_map = {row["item_code"]: float(row["total"] or 0) for row in raw_rows}

	_empty = {"H": 0.0, "B": 0.0, "T": 0.0}
	data = []
	for row in raw_rows:
		item_type = (item_master_map.get(row["item_code"], {}).get("item_type") or "").lower()
		sales_qty = sales_map.get(row["item_code"], 0.0)

		if item_type in ("rb", "bo"):
			consumption = bb_consumption_map.get(row["item_code"], 0.0)
		elif item_type == "traded":
			consumption = billet_consumption_map.get(row["item_code"], 0.0)
		else:
			consumption = 0.0

		total_usage = sales_qty + consumption
		adu = math.ceil(total_usage / horizon_days) if horizon_days > 0 and total_usage > 0 else 0
		lt = float(item_master_map.get(row["item_code"], {}).get("lt") or 0)

		data.append({
			"item_code": row["item_code"],
			"total": float(row["total"] or 0),
			"contr_pct": round(float(row.get("contr_pct") or 0), 1),
			"cumu_pct": round(float(row.get("cumu_pct") or 0), 1),
			"hbt": row["hbt"],
			"frequency": int(row["frequency"] or 0),
			"h": item_hbt_buckets.get(row["item_code"], _empty)["H"],
			"b": item_hbt_buckets.get(row["item_code"], _empty)["B"],
			"t": item_hbt_buckets.get(row["item_code"], _empty)["T"],
			"sku_type": item_master_map.get(row["item_code"], {}).get("sku_type") or "",
			"adu": adu,
			"lt": lt,
			"fos": 25,
			"tog": math.ceil(adu * lt * 1.25),
			"current_tog": float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0),
			"change_pct": round(
				(math.ceil(adu * lt * 1.25) - float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0))
				/ float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0) * 100, 1
			) if float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0) else None,
		})

	return {"data": data, "period_label": period_label}
