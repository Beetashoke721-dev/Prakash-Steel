# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math

import frappe
from frappe import _

from prakash_steel.utils.hbt_utils import get_period_months, period_date_range


def _ceil(v) -> int:
	"""Round any numeric value up to the nearest integer."""
	return math.ceil(v) if v else 0


def _get_projection_factor() -> float:
	"""Projected Qty multiplier = 1 + FOS (factor of safety) from RB Batch Planning Settings.

	e.g. FOS = 0.3 -> factor 1.3.
	"""
	fos = frappe.db.get_single_value("RB Batch Planning Settings", "fos")
	return 1 + (fos or 0)


MAX_PROD_COLS = 10


def execute(filters: dict | None = None):
	filters = filters or {}
	period_months = get_period_months("RB Batch Planning Settings")
	from_date, to_date = period_date_range(period_months)

	data, max_prod_cols = get_data(filters, from_date, to_date)
	columns = get_columns(max_prod_cols)
	return columns, data


def get_columns(max_prod_cols: int = 0) -> list[dict]:
	cols = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 180,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Item Type"),
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("Sales Qty"),
			"fieldname": "sales_qty",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Consumption Qty"),
			"fieldname": "consumption_qty",
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"label": _("Total"),
			"fieldname": "total",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Projected Qty"),
			"fieldname": "projected_qty",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Recommended Batch Size"),
			"fieldname": "batch_size",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": _("Production Count"),
			"fieldname": "production_count",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": _("No of Setup"),
			"fieldname": "no_of_setup",
			"fieldtype": "Int",
			"width": 110,
			"editable": 1,
		},
		{
			"label": _("Production Qty"),
			"fieldname": "production_qty",
			"fieldtype": "Int",
			"width": 120,
		},
	]

	for i in range(1, max_prod_cols + 1):
		cols.append({
			"label": _(f"Prod {i}"),
			"fieldname": f"prod_{i}",
			"fieldtype": "Int",
			"width": 110,
		})

	return cols


def get_data(filters: dict, from_date, to_date) -> tuple[list[dict], int]:
	item_type_filter = filters.get("item_type")
	sku_type_filter = filters.get("sku_type")
	item_code_filter = filters.get("item_code")

	item_type_in = (item_type_filter,) if item_type_filter else ("RB", "BO", "Traded")

	# ── Item master ──────────────────────────────────────────────────────────
	conditions = "WHERE custom_item_type IN %(item_types)s AND disabled = 0"
	params = {"item_types": item_type_in}

	if item_code_filter:
		conditions += " AND name = %(item_code)s"
		params["item_code"] = item_code_filter

	item_rows = frappe.db.sql(
		f"""
		SELECT
			name AS item_code,
			item_name,
			custom_item_type AS item_type,
			custom_sku_type AS sku_type
		FROM `tabItem`
		{conditions}
		""",
		params,
		as_dict=True,
	)

	if not item_rows:
		return [], 0

	if sku_type_filter:
		item_rows = [r for r in item_rows if r.sku_type == sku_type_filter]
		if not item_rows:
			return [], 0

	item_codes = [r.item_code for r in item_rows]
	item_names = [r.item_name for r in item_rows]
	item_map = {r.item_code: r for r in item_rows}

	# ── Sales qty from Sales Invoice (same logic as rolled_production_analysis) ─
	sales_rows = frappe.db.sql(
		"""
		SELECT sii.item_code, SUM(sii.qty) AS qty
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		WHERE si.docstatus = 1
		  AND i.custom_item_type IN %(item_types)s
		  AND sii.item_code IN %(item_codes)s
		  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY sii.item_code
		""",
		{"item_types": item_type_in, "item_codes": item_codes, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	sales_map = {r.item_code: float(r.qty or 0) for r in sales_rows}

	# ── Consumption: all types from Bright Bar Production ────────────────
	# An item can appear in either raw_material or material field; check both.
	bb_rows = frappe.db.sql(
		"""
		SELECT
			CASE
				WHEN bbp.raw_material IN %(item_codes)s THEN bbp.raw_material
				ELSE bbp.material
			END AS item_code,
			COALESCE(SUM(bbp.actual_rm_consumption), 0) AS qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
		  AND (bbp.raw_material IN %(item_codes)s OR bbp.material IN %(item_codes)s)
		  AND bbp.production_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY 1
		""",
		{"item_codes": item_codes, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	consumption_map = {r.item_code: float(r.qty or 0) for r in bb_rows}

	# ── Finish Weight: last MAX_PROD_COLS records per item + totals ────────
	# Window function gives us individual weights (newest first) alongside
	# total count and total weight without a second query.
	fw_rows = frappe.db.sql(
		"""
		SELECT item_name, finish_weight, total_count, total_fw
		FROM (
			SELECT
				item_name,
				finish_weight,
				ROW_NUMBER() OVER (
					PARTITION BY item_name ORDER BY posting_date DESC, name DESC
				) AS rn,
				COUNT(*) OVER (PARTITION BY item_name) AS total_count,
				SUM(finish_weight) OVER (PARTITION BY item_name) AS total_fw
			FROM `tabFinish Weight`
			WHERE docstatus = 1
			  AND item_name IN %(item_names)s
			  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
		) ranked
		WHERE rn <= %(max_cols)s
		ORDER BY item_name, rn
		""",
		{"item_names": item_names, "from_date": from_date, "to_date": to_date, "max_cols": MAX_PROD_COLS},
		as_dict=True,
	)

	# Build per-item structure: weights list is newest-first (prod_1 = most recent)
	fw_map: dict[str, dict] = {}
	for r in fw_rows:
		if r.item_name not in fw_map:
			fw_map[r.item_name] = {
				"production_qty": float(r.total_fw or 0),
				"production_count": int(r.total_count or 0),
				"weights": [],
			}
		fw_map[r.item_name]["weights"].append(float(r.finish_weight or 0))

	# max dynamic columns = min(highest count in this dataset, MAX_PROD_COLS)
	max_prod_cols = min(
		max((len(v["weights"]) for v in fw_map.values()), default=0),
		MAX_PROD_COLS,
	)

	# ── Build rows ────────────────────────────────────────────────────────
	projection_factor = _get_projection_factor()
	data = []
	for item_code in item_codes:
		item = item_map[item_code]

		sales_qty = _ceil(sales_map.get(item_code, 0.0))
		consumption_qty = _ceil(consumption_map.get(item_code, 0.0))

		total = sales_qty + consumption_qty
		projected_qty = _ceil(total * projection_factor)
		fw = fw_map.get(item.item_name, {})
		production_qty = _ceil(fw.get("production_qty", 0.0))
		production_count = fw.get("production_count", 0)
		weights = [_ceil(w) for w in fw.get("weights", [])]

		no_of_setup = production_count
		batch_size = _ceil(production_qty / no_of_setup) if no_of_setup else 0

		row = {
			"item_code": item_code,
			"item_name": item.item_name,
			"item_type": item.item_type,
			"sku_type": item.sku_type,
			"sales_qty": sales_qty,
			"consumption_qty": consumption_qty,
			"total": total,
			"projected_qty": projected_qty,
			"batch_size": batch_size,
			"production_count": production_count,
			"no_of_setup": no_of_setup,
			"production_qty": production_qty,
		}

		for i in range(max_prod_cols):
			row[f"prod_{i + 1}"] = weights[i] if i < len(weights) else None

		data.append(row)

	data.sort(key=lambda r: (-r["production_qty"], -r["total"]))
	return data, max_prod_cols


@frappe.whitelist()
def get_item_debug_info(item_code: str) -> dict:
	"""Return a full calculation breakdown for a single item — used by the Debug button."""
	period_months = get_period_months("RB Batch Planning Settings")
	from_date, to_date = period_date_range(period_months)
	period_label = f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}"

	item = frappe.db.get_value(
		"Item",
		item_code,
		["item_name", "custom_item_type", "custom_sku_type"],
		as_dict=True,
	)
	if not item:
		frappe.throw(f"Item {item_code} not found.")

	# Sales records (individual invoices)
	sales_records = frappe.db.sql(
		"""
		SELECT si.name, si.posting_date, sii.qty
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND sii.item_code = %(item_code)s
		  AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY si.posting_date
		""",
		{"item_code": item_code, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	sales_qty = _ceil(sum(float(r.qty or 0) for r in sales_records))

	# Consumption records from Bright Bar Production (raw_material OR material)
	consumption_records = frappe.db.sql(
		"""
		SELECT name, production_date,
		       actual_rm_consumption,
		       CASE WHEN raw_material = %(item_code)s THEN 'raw_material' ELSE 'material' END AS matched_field
		FROM `tabBright Bar Production`
		WHERE docstatus = 1
		  AND (raw_material = %(item_code)s OR material = %(item_code)s)
		  AND production_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY production_date
		""",
		{"item_code": item_code, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)
	consumption_qty = _ceil(sum(float(r.actual_rm_consumption or 0) for r in consumption_records))

	total = sales_qty + consumption_qty
	projection_factor = _get_projection_factor()
	projected_qty = _ceil(total * projection_factor)

	# Finish Weight records (all in period, newest first for prod columns)
	fw_records = frappe.db.sql(
		"""
		SELECT name, posting_date, finish_weight
		FROM `tabFinish Weight`
		WHERE docstatus = 1
		  AND item_name = %(item_name)s
		  AND posting_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY posting_date DESC, name DESC
		""",
		{"item_name": item.item_name, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	production_count = len(fw_records)
	production_qty = _ceil(sum(float(r.finish_weight or 0) for r in fw_records))
	batch_size = _ceil(projected_qty / production_count) if production_count else 0

	return {
		"item_name": item.item_name,
		"item_type": item.custom_item_type or "",
		"sku_type": item.custom_sku_type or "",
		"period_label": period_label,
		"sales_qty": sales_qty,
		"sales_records": [
			{"name": r.name, "date": str(r.posting_date), "qty": _ceil(float(r.qty or 0))}
			for r in sales_records
		],
		"consumption_qty": consumption_qty,
		"consumption_records": [
			{
				"name": r.name,
				"date": str(r.production_date),
				"qty": _ceil(float(r.actual_rm_consumption or 0)),
				"matched_field": r.matched_field,
			}
			for r in consumption_records
		],
		"total": total,
		"projection_factor": projection_factor,
		"projected_qty": projected_qty,
		"production_count": production_count,
		"production_qty": production_qty,
		"batch_size": batch_size,
		"fw_records": [
			{"name": r.name, "date": str(r.posting_date), "weight": _ceil(float(r.finish_weight or 0))}
			for r in fw_records
		],
	}
