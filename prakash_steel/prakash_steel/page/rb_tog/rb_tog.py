# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import json
import math
from collections import defaultdict

import frappe

from prakash_steel.utils.hbt_utils import (
	METRIC_COL as _METRIC_COL_MAP,
	assign_hbt_labels,
	get_customer_hbt_map,
	get_tog_horizon_range,
)
from prakash_steel.utils.whitelist_permissions import require_permission

ITEM_TYPES = ("RB",)


@frappe.whitelist()
def get_rb_tog_data(view_by: str = "Sale Quantity") -> dict:
	require_permission("Sales Invoice", "read")

	if view_by not in _METRIC_COL_MAP:
		view_by = "Sale Quantity"
	metric_col = _METRIC_COL_MAP[view_by]

	from_date, to_date = get_tog_horizon_range()
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
			AND i.custom_item_type = 'RB'
			AND i.custom_sku_type IN ('RBMTA', 'RBMTO')
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
			AND i.custom_item_type = 'RB'
			AND i.custom_sku_type IN ('RBMTA', 'RBMTO')
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			sii.item_code,
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer)
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	item_hbt_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"H": 0.0, "B": 0.0, "T": 0.0})
	item_customer_counts: dict[str, int] = defaultdict(int)
	for r in item_group_rows:
		bucket = customer_hbt_map.get(r.group_name, "T")
		item_hbt_buckets[r.item_code][bucket] += float(r.total or 0)
		item_customer_counts[r.item_code] += 1

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
			custom_item_type AS item_type,
			custom_last_saved_tog AS new_tog,
			custom_buffer_flag AS buffer_flag
		FROM `tabItem`
		WHERE name IN %(item_codes)s
		""",
		{"item_codes": item_codes},
		as_dict=True,
	)
	item_master_map = {r.item_code: r for r in item_master_rows}

	# Consumption from Bright Bar Production (both material and raw_material fields)
	bb_consumption_rows = frappe.db.sql(
		"""
		SELECT material AS item_code, SUM(actual_rm_consumption) AS qty
		FROM `tabBright Bar Production`
		WHERE docstatus = 1
			AND NULLIF(material, '') IS NOT NULL
			AND material IN %(item_codes)s
			AND production_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY material

		UNION ALL

		SELECT raw_material AS item_code, SUM(actual_rm_consumption) AS qty
		FROM `tabBright Bar Production`
		WHERE docstatus = 1
			AND NULLIF(raw_material, '') IS NOT NULL
			AND raw_material IN %(item_codes)s
			AND production_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY raw_material
		""",
		{"item_codes": item_codes, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	bb_consumption_map: dict[str, float] = {}
	for r in bb_consumption_rows:
		if r.item_code:
			bb_consumption_map[r.item_code] = bb_consumption_map.get(r.item_code, 0.0) + float(r.qty or 0)

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

	# Build consumption map per item and compute total_value = sale_qty + consumption
	sales_map = {row["item_code"]: float(row["total"] or 0) for row in raw_rows}
	for row in raw_rows:
		item_type = (item_master_map.get(row["item_code"], {}).get("item_type") or "").lower()
		sale_qty = sales_map.get(row["item_code"], 0.0)
		if item_type in ("rb", "bo"):
			consumption = bb_consumption_map.get(row["item_code"], 0.0)
		elif item_type == "traded":
			consumption = billet_consumption_map.get(row["item_code"], 0.0)
		else:
			consumption = 0.0
		row["consumption"] = consumption
		row["total_value"] = sale_qty + consumption

	# Sort and rank by total_value (sale + consumption) — same as Rolled Product HBT report
	raw_rows.sort(key=lambda r: r["total_value"], reverse=True)
	assign_hbt_labels(raw_rows, total_key="total_value")

	_empty = {"H": 0.0, "B": 0.0, "T": 0.0}
	data = []
	for row in raw_rows:
		sale_qty = float(row["total"] or 0)
		consumption = float(row.get("consumption", 0))
		total_value = float(row.get("total_value", sale_qty))
		adu = math.ceil(total_value / horizon_days) if horizon_days > 0 and total_value > 0 else 0
		lt = float(item_master_map.get(row["item_code"], {}).get("lt") or 0)
		_buckets = item_hbt_buckets.get(row["item_code"], _empty)

		data.append({
			"item_code": row["item_code"],
			"sale_qty": sale_qty,
			"consumption": consumption,
			"total": total_value,
			"contr_pct": round(float(row.get("contr_pct") or 0), 1),
			"cumu_pct": round(float(row.get("cumu_pct") or 0), 1),
			"hbt": row["hbt"],
			"frequency": int(row["frequency"] or 0),
			"h": _buckets["H"],
			"b": _buckets["B"],
			"t": _buckets["T"],
			"no_of_customer": item_customer_counts.get(row["item_code"], 0),
			"sku_type": item_master_map.get(row["item_code"], {}).get("sku_type") or "",
			"adu": adu,
			"lt": lt,
			"fos": 25,
			"tog": math.ceil(adu * lt * 1.25),
			"current_tog": float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0),
			"new_tog": item_master_map.get(row["item_code"], {}).get("new_tog") or None,
			"buffer_flag": item_master_map.get(row["item_code"], {}).get("buffer_flag") or "Non-Buffer",
			"change_pct": round(
				(math.ceil(adu * lt * 1.25) - float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0))
				/ float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0) * 100, 1
			) if float(item_master_map.get(row["item_code"], {}).get("current_tog") or 0) else None,
		})

	return {"data": data, "period_label": period_label}


@frappe.whitelist()
def save_tog(items):
	items = json.loads(items) if isinstance(items, str) else items
	for item in items:
		frappe.db.set_value("Item", item["item_code"], "custom_last_saved_tog", item["tog"])
	frappe.db.commit()
	return {"saved": len(items)}


@frappe.whitelist()
def update_tog(items):
	items = json.loads(items) if isinstance(items, str) else items
	for item in items:
		tog = float(item["tog"] or 0)
		frappe.db.set_value("Item", item["item_code"], {
			"safety_stock": tog,
			"custom_top_of_yellow": math.ceil((2 / 3) * tog),
			"custom_top_of_red": math.ceil((1 / 3) * tog),
		})
	frappe.db.commit()
	return {"updated": len(items)}


@frappe.whitelist()
def export_rb_tog_xlsx(data, filename="RB_TOG"):
	from frappe.utils.xlsxutils import build_xlsx_response

	rows_data = json.loads(data) if isinstance(data, str) else data

	headers = [
		"SKU Type", "Item Code", "Contr%", "Cumu%", "HBT", "Frequency", "Total Qty",
		"ADU", "LT", "FOS", "TOG", "Current TOG", "Change%",
		"No of Customer", "Head Customer", "Body Customer", "Tail Customer",
	]
	rows = [headers] + [
		[
			r.get("sku_type") or "",
			r.get("item_code") or "",
			r.get("contr_pct") or 0,
			r.get("cumu_pct") or 0,
			r.get("hbt") or "",
			r.get("frequency") or 0,
			r.get("total") or 0,
			r.get("adu") or 0,
			r.get("lt") or 0,
			r.get("fos") or 0,
			r.get("tog") or 0,
			r.get("current_tog") or 0,
			r.get("change_pct"),
			r.get("no_of_customer") or 0,
			r.get("h") or 0,
			r.get("b") or 0,
			r.get("t") or 0,
		]
		for r in rows_data
	]
	build_xlsx_response(rows, filename)
