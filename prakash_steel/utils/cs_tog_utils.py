# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""Shared backend for the per-warehouse CS TOG pages (CS Bright TOG / CS Rolled TOG).

A CS item can carry one row per warehouse in its CS Tog Table (Item.custom_cs_tog_table).
Each page is scoped to one warehouse: an item appears on a page only when it has a CS Tog
Table row for that warehouse, and the TOG read/written is that row's — so an item with both
warehouses shows on both pages with independent TOGs.
"""

import json
import math
import frappe

from prakash_steel.utils.hbt_utils import (
	METRIC_COL as _METRIC_COL_MAP,
	assign_hbt_labels,
	get_default_fos,
	get_last_fos,
	get_tog_horizon_range,
	set_updated_fos,
)

BRIGHT_WAREHOUSE = "Bright Bar Unit - PSPL"
ROLLED_WAREHOUSE = "Rolling Mill - PSPL"

CS_TOG_CHILD_DOCTYPE = "CS Tog table"
CS_TOG_PARENTFIELD = "custom_cs_tog_table"


def get_cs_tog_data(warehouse: str, view_by: str = "Sale Quantity") -> dict:
	if view_by not in _METRIC_COL_MAP:
		view_by = "Sale Quantity"
	metric_col = _METRIC_COL_MAP[view_by]

	from_date, to_date = get_tog_horizon_range("CS")
	period_label = f"{from_date.strftime('%b %Y')} – {to_date.strftime('%b %Y')}"
	params = {"from_date": from_date, "to_date": to_date, "warehouse": warehouse}

	empty = {
		"data": [],
		"period_label": period_label,
		"warehouse": warehouse,
		"default_fos": get_default_fos("CS"),
		"last_fos": get_last_fos("CS"),
	}

	# Only items having a CS Tog Table row for this warehouse
	raw_rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			i.name AS item_code,
			COALESCE(s.total, 0) AS total,
			COALESCE(s.frequency, 0) AS frequency
		FROM `tabItem` i
		LEFT JOIN (
			SELECT
				sii.item_code,
				SUM({metric_col}) AS total,
				COUNT(DISTINCT YEAR(si.posting_date) * 100 + MONTH(si.posting_date)) AS frequency
			FROM `tabSales Invoice` si
			INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
			WHERE
				si.docstatus = 1
				AND sii.warehouse = %(warehouse)s
				AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
			GROUP BY sii.item_code
		) s ON s.item_code = i.name
		WHERE
			i.custom_item_type = 'CS'
			AND i.custom_sku_type IN ('CSMTA', 'CSMTO')
			AND i.disabled = 0
			AND EXISTS (
				SELECT 1 FROM `tabCS Tog table` ct
				WHERE ct.parent = i.name
					AND ct.parenttype = 'Item'
					AND ct.parentfield = 'custom_cs_tog_table'
					AND ct.warehouse = %(warehouse)s
			)
		ORDER BY total DESC
		""",
		params,
		as_dict=True,
	)

	if not raw_rows:
		return empty

	# ADU horizon = full period from TOG Horizon Setting
	horizon_days = (to_date - from_date).days + 1

	item_codes = [row["item_code"] for row in raw_rows]
	params["item_codes"] = item_codes

	item_master_rows = frappe.db.sql(
		"""
		SELECT
			name AS item_code,
			lead_time_days AS lt,
			custom_sku_type AS sku_type,
			custom_buffer_flag AS buffer_flag
		FROM `tabItem`
		WHERE name IN %(item_codes)s
		""",
		params,
		as_dict=True,
	)
	item_master_map = {r.item_code: r for r in item_master_rows}

	tog_row_map = get_tog_row_map(item_codes, warehouse)

	# On Hand Stock — this warehouse only (same as Bright/Rolled Critical Spares)
	stock_rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) AS stock
		FROM `tabBin`
		WHERE item_code IN %(item_codes)s AND warehouse = %(warehouse)s
		GROUP BY item_code
		""",
		params,
		as_dict=True,
	)
	stock_map = {r.item_code: float(r.stock or 0) for r in stock_rows}

	# CS items (consumables & spares) are consumed through Material Issue Stock Entries
	# issued from this warehouse
	consumption_rows = frappe.db.sql(
		"""
		SELECT sed.item_code, COALESCE(SUM(sed.transfer_qty), 0) AS qty
		FROM `tabStock Entry Detail` sed
		INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1
			AND se.purpose = 'Material Issue'
			AND sed.s_warehouse = %(warehouse)s
			AND sed.item_code IN %(item_codes)s
			AND se.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY sed.item_code
		""",
		params,
		as_dict=True,
	)
	consumption_map = {r.item_code: float(r.qty or 0) for r in consumption_rows}

	# total_value = sale_qty + consumption
	for row in raw_rows:
		consumption = consumption_map.get(row["item_code"], 0.0)
		row["consumption"] = consumption
		row["total_value"] = float(row["total"] or 0) + consumption

	# Sort and rank by total_value (sale + consumption) — same as Rolled Product HBT report
	raw_rows.sort(key=lambda r: r["total_value"], reverse=True)
	assign_hbt_labels(raw_rows, total_key="total_value")

	data = []
	for row in raw_rows:
		item_code = row["item_code"]
		master = item_master_map.get(item_code, {})
		tog_row = tog_row_map.get(item_code, {})
		sale_qty = float(row["total"] or 0)
		consumption = float(row.get("consumption", 0))
		total_value = float(row.get("total_value", sale_qty))
		adu = math.ceil(total_value / horizon_days) if horizon_days > 0 and total_value > 0 else 0
		lt = float(master.get("lt") or 0)
		tog = math.ceil(adu * lt * 1.25)
		current_tog = float(tog_row.get("top_of_green") or 0)

		data.append({
			"item_code": item_code,
			"sale_qty": sale_qty,
			"consumption": consumption,
			"total": total_value,
			"contr_pct": round(float(row.get("contr_pct") or 0), 1),
			"cumu_pct": round(float(row.get("cumu_pct") or 0), 1),
			"hbt": row["hbt"],
			"on_hand_stock": math.ceil(stock_map.get(item_code, 0)),
			"frequency": int(row["frequency"] or 0),
			"sku_type": master.get("sku_type") or "",
			"adu": adu,
			"lt": lt,
			"fos": 25,
			"tog": tog,
			"current_tog": current_tog,
			"new_tog": tog_row.get("last_saved_tog") or None,
			"buffer_flag": master.get("buffer_flag") or "Non-Buffer",
			"change_pct": round((tog - current_tog) / current_tog * 100, 1) if current_tog else None,
		})

	return {**empty, "data": data}


def get_tog_row_map(item_codes: list[str], warehouse: str) -> dict[str, dict]:
	"""item_code -> its CS Tog Table row for `warehouse` (first row by idx if duplicated)."""
	rows = frappe.get_all(
		CS_TOG_CHILD_DOCTYPE,
		filters={
			"parenttype": "Item",
			"parentfield": CS_TOG_PARENTFIELD,
			"warehouse": warehouse,
			"parent": ["in", item_codes],
		},
		fields=["name", "parent", "top_of_green", "last_saved_tog"],
		order_by="idx asc",
	)
	tog_row_map: dict[str, dict] = {}
	for r in rows:
		tog_row_map.setdefault(r.parent, r)
	return tog_row_map


def _set_tog_rows(item_code: str, warehouse: str, values: dict) -> int:
	"""Write `values` to every CS Tog Table row of `item_code` for `warehouse`."""
	names = frappe.get_all(
		CS_TOG_CHILD_DOCTYPE,
		filters={
			"parent": item_code,
			"parenttype": "Item",
			"parentfield": CS_TOG_PARENTFIELD,
			"warehouse": warehouse,
		},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value(CS_TOG_CHILD_DOCTYPE, name, values)
	return len(names)


def save_tog(warehouse: str, items, fos=None) -> dict:
	items = json.loads(items) if isinstance(items, str) else items
	for item in items:
		_set_tog_rows(item["item_code"], warehouse, {"last_saved_tog": item["tog"]})
	last_fos = None
	if fos is not None:
		last_fos = set_updated_fos("CS", fos)
	frappe.db.commit()
	return {"saved": len(items), "last_fos": last_fos}


def update_tog(warehouse: str, items, fos=None) -> dict:
	"""Buffer flag / SKU type are item-level; the TOG goes to this warehouse's CS Tog Table row."""
	items = json.loads(items) if isinstance(items, str) else items
	for item in items:
		buffer_flag = item.get("buffer_flag") or "Non-Buffer"
		tog = float(item["tog"] or 0) if buffer_flag == "Buffer" else 0
		frappe.db.set_value("Item", item["item_code"], {
			"custom_buffer_flag": buffer_flag,
			"custom_sku_type": item.get("sku_type") or "",
		})
		_set_tog_rows(item["item_code"], warehouse, {
			"top_of_green": tog,
			"top_of_yellow": math.ceil((2 / 3) * tog),
			"top_of_red": math.ceil((1 / 3) * tog),
			"last_saved_tog": tog,
		})
	last_fos = None
	if fos is not None:
		last_fos = set_updated_fos("CS", fos)
	frappe.db.commit()
	return {"updated": len(items), "last_fos": last_fos}


def save_buffer_flag(item_code, buffer_flag, sku_type) -> dict:
	frappe.db.set_value("Item", item_code, {
		"custom_buffer_flag": buffer_flag,
		"custom_sku_type": sku_type,
	})
	frappe.db.commit()
	return {"ok": True}


def export_cs_tog_xlsx(data, filename) -> None:
	from frappe.utils.xlsxutils import build_xlsx_response

	rows_data = json.loads(data) if isinstance(data, str) else data

	headers = [
		"SKU Type", "Item Code", "Contr%", "Cumu%", "HBT", "On Hand Stock", "Frequency", "Total Qty",
		"ADU", "LT", "FOS", "TOG", "Current TOG", "Change%",
	]
	rows = [headers] + [
		[
			r.get("sku_type") or "",
			r.get("item_code") or "",
			r.get("contr_pct") or 0,
			r.get("cumu_pct") or 0,
			r.get("hbt") or "",
			r.get("on_hand_stock") or 0,
			r.get("frequency") or 0,
			r.get("total") or 0,
			r.get("adu") or 0,
			r.get("lt") or 0,
			r.get("fos") or 0,
			r.get("tog") or 0,
			r.get("current_tog") or 0,
			r.get("change_pct"),
		]
		for r in rows_data
	]
	build_xlsx_response(rows, filename)
