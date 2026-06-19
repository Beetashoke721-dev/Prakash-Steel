import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt, today, add_days

from prakash_steel.utils.lead_time import get_default_bom


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


@frappe.whitelist()
def get_tog_parent_sell_console_payload() -> dict | list:
	"""
	Return parent-sell debug JSON for the browser console.

	Loaded via a separate request so it is not lost when the report pipeline
	(e.g. user-permission filtering on Item rows) strips or reorders rows.
	"""
	if not frappe.has_permission("Item", "report"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	rows = get_data(None)
	if not rows:
		return {}
	return rows[0].get("tog_parent_sell_debug") or {}


@frappe.whitelist()
def get_item_tog_debug(item_code) -> dict | list:
	"""
	Full per-item debug for browser console.

	Returns:
	  - direct_sells               : every Sales Invoice line that sold this item (→ Sell column)
	  - parent_sell_contributions  : every BOM hop that pushed demand onto this item (→ Parent Sell column)
	  - sd_daily_breakdown         : per-day qty, mean, deviation, squared deviation (→ SD column)
	  - total_sell / total_parent_sell_raw / total_parent_sell_ceiled / sd / adu / cov : summary numbers
	"""
	if not frappe.has_permission("Item", "report"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	days = _get_horizon_days()
	sales_lines = _get_sales_invoice_lines()

	# ── Direct sells (Sell column) ─────────────────────────────────────────
	direct_sells = [l for l in sales_lines if l.get("item_code") == item_code]
	total_sell = sum(flt(l.get("qty", 0)) for l in direct_sells)

	# ── Propagation trace ──────────────────────────────────────────────────
	trace = _compute_parent_sell_from_lines(sales_lines, collect_trace=True)[1]

	# Only hops where demand lands ON this item
	contributions = [t for t in (trace or []) if t.get("to_item") == item_code]

	# parent_sell accumulator = sum of path_total_accrued_to_to_item (same as acc[item_code])
	total_parent_sell_raw = sum(flt(t.get("path_total_accrued_to_to_item", 0)) for t in contributions)

	# ── SD breakdown (→ SD column) ─────────────────────────────────────────
	end_date = today()
	start_date = add_days(end_date, -(days - 1))

	# Per-date sales for this item
	date_rows = frappe.db.sql(
		"""
		SELECT si.posting_date, SUM(sii.qty) AS daily_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
		  AND sii.item_code = %s
		  AND si.posting_date BETWEEN %s AND %s
		GROUP BY si.posting_date
		""",
		(item_code, start_date, end_date),
		as_dict=True,
	)
	daily_map = {str(r["posting_date"]): flt(r["daily_qty"]) for r in date_rows}

	mean = total_sell / days if days > 0 else 0.0
	daily_breakdown = []
	sum_sq = 0.0
	for i in range(days):
		d = str(add_days(start_date, i))
		qty = daily_map.get(d, 0.0)
		dev = qty - mean
		sq = dev ** 2
		sum_sq += sq
		daily_breakdown.append({
			"date": d,
			"qty": qty,
			"deviation": round(dev, 4),
			"squared_deviation": round(sq, 4),
		})

	variance = sum_sq / days if days > 0 else 0.0
	sd_val = math.sqrt(variance)

	# ADU for COV (Sell + Parent Sell + Consumption)
	consumption_map = _get_consumption_by_item(days)
	consumption = flt(consumption_map.get(item_code, 0.0))
	total_usage = total_sell + total_parent_sell_raw + consumption
	adu_val = math.ceil(total_usage / days) if days > 0 and total_usage > 0 else 0

	return {
		"item_code": item_code,
		"horizon_days": days,
		"start_date": start_date,
		"end_date": end_date,
		"total_sell": int(total_sell),
		"mean_daily_qty": round(mean, 4),
		"variance": round(variance, 4),
		"sd": round(sd_val, 4),
		"adu": adu_val,
		"cov": round(sd_val / adu_val, 4) if adu_val and sd_val else None,
		"total_parent_sell_raw": total_parent_sell_raw,
		"total_parent_sell_ceiled": int(math.ceil(total_parent_sell_raw)) if total_parent_sell_raw > 0 else 0,
		"direct_sells": direct_sells,
		"parent_sell_contributions": contributions,
		"sd_daily_breakdown": daily_breakdown,
	}


def get_columns() -> list[dict]:
	"""Report column definitions."""
	return [
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{
			"label": "Category Name",
			"fieldname": "custom_category_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Item Type",
			"fieldname": "custom_item_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Sell",
			"fieldname": "sell",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": "Parent Sell",
			"fieldname": "parent_sell",
			"fieldtype": "Int",
			"width": 110,
		},
		{
			"label": "Consumption",
			"fieldname": "consumption",
			"fieldtype": "Int",
			"width": 110,
			"hidden": 1,  # Not shown by default since it's not used in ADU calculation for all items; can be toggled on if needed
		},
		{
			"label": "ADU",
			"fieldname": "custom_adu",
			"fieldtype": "Int",
			"width": 90,
		},
		{
			"label": "SD",
			"fieldname": "sd",
			"fieldtype": "Float",
			"width": 90,
		},
		{
			"label": "COV",
			"fieldname": "cov",
			"fieldtype": "Float",
			"width": 90,
		},
	]


def get_data(filters=None) -> list[dict]:
	"""
	Get data from Item doctype.

	Populates:
	- item_code (from Item.name)
	- custom_category_name
	- custom_item_type
	- custom_adu (ceil((Sell + Parent Sell + Consumption) / horizon days))

	Also fills sell, parent_sell, consumption, sd, cov.

	Debug payload is stored on the first row as `tog_parent_sell_debug` and also
	exposed via `get_tog_parent_sell_console_payload` (used by report JS) so it
	survives row filtering in `generate_report_result`.
	"""
	# Number of days in horizon (based on ADU Horizon)
	days = _get_horizon_days()
	# Map of item_code -> total sales qty in horizon
	sales_qty_map = _get_sales_qty_by_item()
	# Map of item_code -> total consumption (filtered by same date range as sales)
	consumption_map = _get_consumption_by_item(days)
	# Map of item_code -> population SD of daily sales qty
	sd_map = _get_sd_by_item(days)

	sales_lines = _get_sales_invoice_lines()
	parent_sell_map, propagation_trace = _compute_parent_sell_from_lines(
		sales_lines, collect_trace=True
	)

	items = frappe.db.get_all(
		"Item",
		fields=[
			"name as item_code",
			"custom_category_name",
			"custom_item_type",
			"custom_adu",
		],
		# Adjust filters if you want to limit which items appear
		# Example: only stock items, not disabled
		# filters={"is_stock_item": 1, "disabled": 0},
	)

	# Populate measure columns
	for item in items:
		item_code = item.get("item_code")

		# 1) Sell: live total sales qty in current horizon (integer)
		sell_qty = flt(sales_qty_map.get(item_code, 0.0))
		item["sell"] = int(sell_qty) if sell_qty else 0

		# 1b) Parent sell: demand on this item from exploding other items' sales through BOMs (ceiled int)
		ps = flt(parent_sell_map.get(item_code, 0.0))
		item["parent_sell"] = int(math.ceil(ps)) if ps > 0 else 0

		# 2) Consumption: live total consumption (integer)
		consumption_qty = flt(consumption_map.get(item_code, 0.0))
		item["consumption"] = int(consumption_qty) if consumption_qty else 0

		# 3) ADU: (Sell + Parent Sell + Consumption) / days (ceiled to whole number)
		total_usage = sell_qty + consumption_qty + ps
		if days > 0 and total_usage > 0:
			adu_raw = total_usage / days
			item["custom_adu"] = math.ceil(adu_raw)
		else:
			# If horizon not configured or no sell/parent sell/consumption, set ADU to 0
			item["custom_adu"] = 0

		# 4) SD: population standard deviation of daily sales qty over the horizon
		sd_val = flt(sd_map.get(item_code, 0.0))
		item["sd"] = round(sd_val, 2) if sd_val else None

		# 5) COV: coefficient of variation = SD / ADU
		adu_val = item.get("custom_adu", 0)
		item["cov"] = round(sd_val / adu_val, 2) if adu_val and sd_val else None

	# Browser console: one payload on first row (always present in API result; not a column).
	if items:
		per_item = []
		for row in items:
			ic = row.get("item_code")
			ps = flt(parent_sell_map.get(ic, 0.0))
			sd_val = flt(sd_map.get(ic, 0.0))
			adu_val = row.get("custom_adu", 0)
			per_item.append(
				{
					"item_code": ic,
					"parent_sell_float": ps,
					"parent_sell_in_grid": int(math.ceil(ps)) if ps > 0 else 0,
					"sell_in_grid": row.get("sell"),
					"sd": round(sd_val, 4) if sd_val else None,
					"adu": adu_val,
					"cov": round(sd_val / adu_val, 4) if adu_val and sd_val else None,
				}
			)
		items[0]["tog_parent_sell_debug"] = {
			"horizon_days": days,
			"sales_invoice_lines": sales_lines,
			"propagation_trace": propagation_trace or [],
			"per_item_parent_sell": per_item,
		}

	return items


def _get_horizon_days() -> int:
	"""Return number of days to look back based on ADU Horizon single DocType."""
	horizon = frappe.get_single("ADU Horizon")
	weeks_raw = getattr(horizon, "week", None) or 0
	weeks = cint(weeks_raw) or 0
	if weeks <= 0:
		return 0
	return weeks * 7


def _get_sales_qty_by_item() -> dict[str, float]:
	"""
	Return a mapping of item_code -> total sales quantity
	within the ADU horizon (same range used in ADU calculation),
	but WITHOUT dividing by days/weeks.
	"""
	days = _get_horizon_days()
	if days <= 0:
		return {}

	end_date = today()
	# Include "days" number of days including today
	start_date = add_days(end_date, -(days - 1))

	rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			COALESCE(SUM(sii.qty), 0) AS total_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %s AND %s
		GROUP BY sii.item_code
		""",
		(start_date, end_date),
		as_dict=True,
	)

	return {row["item_code"]: flt(row.get("total_qty", 0.0)) for row in rows}


def _get_sales_invoice_lines() -> list[dict]:
	"""Each submitted Sales Invoice line in the ADU horizon (one row per line item)."""
	days = _get_horizon_days()
	if days <= 0:
		return []

	end_date = today()
	start_date = add_days(end_date, -(days - 1))

	rows = frappe.db.sql(
		"""
		SELECT
			sii.name AS invoice_item_row,
			sii.parent AS sales_invoice,
			si.posting_date AS posting_date,
			sii.item_code AS item_code,
			sii.qty AS qty,
			sii.sales_order AS sales_order
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %s AND %s
		ORDER BY si.posting_date, sii.parent, sii.idx
		""",
		(start_date, end_date),
		as_dict=True,
	)

	out = []
	for row in rows:
		out.append(
			{
				"invoice_item_row": row.get("invoice_item_row"),
				"sales_invoice": row.get("sales_invoice"),
				"posting_date": str(row.get("posting_date") or ""),
				"item_code": row.get("item_code"),
				"qty": flt(row.get("qty")),
				"sales_order": row.get("sales_order") or None,
			}
		)
	return out


def _compute_parent_sell_map(sales_qty_map: dict[str, float]) -> dict[str, float]:
	"""Aggregated by item (no per–sales-invoice trace)."""
	lines = [
		{
			"invoice_item_row": None,
			"sales_invoice": None,
			"posting_date": None,
			"item_code": k,
			"qty": flt(v),
			"sales_order": None,
		}
		for k, v in sales_qty_map.items()
		if flt(v) > 0
	]
	acc, _ = _compute_parent_sell_from_lines(lines, collect_trace=False)
	return acc


def _compute_parent_sell_from_lines(
	lines: list[dict],
	collect_trace: bool,
) -> tuple[dict[str, float], list | None]:
	"""
	For each sales line, explode through default BOMs.

	Per BOM row: child_need = incoming_qty * (bom.quantity / bom_item.qty).
	Parent sell for a component is the cumulative demand along the path.

	If collect_trace, each hop is appended with sales invoice / SO context.
	"""
	acc = defaultdict(float)
	trace: list[dict] | None = [] if collect_trace else None
	bom_doc_cache: dict[str, object] = {}
	default_bom_cache: dict[str, str | None] = {}
	rm_cache: dict[str, bool] = {}

	def _is_rm_stop(item_code: str) -> bool:
		if item_code not in rm_cache:
			raw = frappe.db.get_value("Item", item_code, "custom_item_type")
			rm_cache[item_code] = bool(raw and str(raw).strip().lower() == "rm")
		return rm_cache[item_code]

	def _get_bom_doc(bom_name: str):
		if bom_name not in bom_doc_cache:
			bom_doc_cache[bom_name] = frappe.get_doc("BOM", bom_name)
		return bom_doc_cache[bom_name]

	def _propagate(
		item_code: str,
		incoming_qty: float,
		visited: frozenset[str],
		path_cumulative: float,
		line_ctx: dict,
	) -> None:
		if not incoming_qty or item_code in visited:
			return
		if _is_rm_stop(item_code):
			return

		if item_code not in default_bom_cache:
			default_bom_cache[item_code] = get_default_bom(item_code)
		bom_name = default_bom_cache[item_code]
		if not bom_name:
			return

		bom_doc = _get_bom_doc(bom_name)
		fg_qty = flt(bom_doc.quantity)
		if fg_qty <= 0:
			return

		next_visited = visited | {item_code}

		for bom_item in bom_doc.items:
			child_code = bom_item.item_code
			child_line_qty = flt(bom_item.qty)
			if not child_code or child_line_qty <= 0:
				continue
			child_need = incoming_qty * (fg_qty / child_line_qty)
			path_total = path_cumulative + child_need
			acc[child_code] += path_total

			if trace is not None:
				trace.append(
					{
						"sales_invoice": line_ctx.get("sales_invoice"),
						"sales_order": line_ctx.get("sales_order"),
						"invoice_item_row": line_ctx.get("invoice_item_row"),
						"posting_date": line_ctx.get("posting_date"),
						"sold_item": line_ctx.get("item_code"),
						"sold_qty_this_line": flt(line_ctx.get("qty")),
						"from_item": item_code,
						"to_item": child_code,
						"bom": bom_name,
						"bom_fg_qty": fg_qty,
						"bom_line_qty": child_line_qty,
						"child_need": child_need,
						"path_cumulative_before_hop": path_cumulative,
						"path_total_accrued_to_to_item": path_total,
					}
				)

			if _is_rm_stop(child_code):
				continue
			_propagate(child_code, child_need, next_visited, path_total, line_ctx)

	for line in lines:
		sq = flt(line.get("qty"))
		if sq <= 0 or not line.get("item_code"):
			continue
		line_ctx = {
			"invoice_item_row": line.get("invoice_item_row"),
			"sales_invoice": line.get("sales_invoice"),
			"posting_date": line.get("posting_date"),
			"item_code": line.get("item_code"),
			"qty": sq,
			"sales_order": line.get("sales_order"),
		}
		_propagate(line["item_code"], sq, frozenset(), 0.0, line_ctx)

	return dict(acc), trace


def _get_parent_sell_map_for_horizon() -> dict[str, float]:
	"""BOM-exploded demand from all sales in the ADU horizon (same as Parent Sell column)."""
	days = _get_horizon_days()
	if days <= 0:
		return {}
	sales_lines = _get_sales_invoice_lines()
	parent_sell_map, _ = _compute_parent_sell_from_lines(sales_lines, collect_trace=False)
	return parent_sell_map


def _get_sd_by_item(days: int) -> dict[str, float]:
	"""
	Return population standard deviation of daily sales qty for each item
	over the ADU horizon.

	For each day in the horizon:
	  - If no sales invoice exists for that day → daily qty = 0
	  - mean  = total_qty / days          (same as: sell / days)
	  - var   = sum((daily_qty - mean)²) / days
	  - SD    = sqrt(var)
	"""
	if days <= 0:
		return {}

	end_date = today()
	start_date = add_days(end_date, -(days - 1))

	rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			si.posting_date,
			SUM(sii.qty) AS daily_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE
			si.docstatus = 1
			AND si.posting_date BETWEEN %s AND %s
		GROUP BY sii.item_code, si.posting_date
		""",
		(start_date, end_date),
		as_dict=True,
	)

	# item_code -> {date_str -> qty}
	item_daily: dict[str, dict[str, float]] = defaultdict(dict)
	for row in rows:
		item_daily[row["item_code"]][str(row["posting_date"])] = flt(row["daily_qty"])

	sd_map: dict[str, float] = {}
	for item_code, daily_map in item_daily.items():
		# Build a full list of daily quantities (0 for days with no sale)
		daily_qtys = [
			daily_map.get(str(add_days(start_date, i)), 0.0)
			for i in range(days)
		]
		mean = sum(daily_qtys) / days
		variance = sum((q - mean) ** 2 for q in daily_qtys) / days
		sd_map[item_code] = math.sqrt(variance)

	return sd_map


def _get_consumption_by_item(days: int) -> dict[str, float]:
	"""
	Return a mapping of item_code -> total consumption within the ADU horizon.

	Logic:
	- For items with item_type = "rb" or "bo": sum actual_rm_consumption from Bright Bar Production doctype
	- For items with item_type = "rm" or "traded": sum billet_weight from Billet Cutting doctype
	- Filtered by the same date range as sales (ADU horizon)
	"""
	consumption_map = {}

	if days <= 0:
		return consumption_map

	end_date = today()
	# Include "days" number of days including today
	start_date = add_days(end_date, -(days - 1))

	# Get consumption from Bright Bar Production for items with item_type = "rb" or "bo"

	bright_bar_rows = frappe.db.sql(
		"""
		SELECT
			bbp.raw_material AS item_code,
			COALESCE(SUM(bbp.actual_rm_consumption), 0) AS total_rm_consumption
		FROM `tabBright Bar Production` bbp
		INNER JOIN `tabItem` i ON i.name = bbp.raw_material
		WHERE
			bbp.docstatus = 1
			AND LOWER(i.custom_item_type) IN ('rb', 'bo')
			AND bbp.production_date BETWEEN %s AND %s
		GROUP BY bbp.raw_material
		""",
		(start_date, end_date),
		as_dict=True,
	)

	for row in bright_bar_rows:
		item_code = row.get("item_code")
		if item_code:
			consumption_map[item_code] = flt(row.get("total_rm_consumption", 0.0))

	# Get consumption from Billet Cutting for items with item_type = "rm" or "traded"
	billet_cutting_rows = frappe.db.sql(
		"""
		SELECT
			bc.billet_size AS item_code,
			COALESCE(SUM(bc.billet_weight), 0) AS total_billet_weight
		FROM `tabBillet Cutting` bc
		INNER JOIN `tabItem` i ON i.name = bc.billet_size
		WHERE
			bc.docstatus = 1
			AND LOWER(i.custom_item_type) IN ('rm', 'traded')
			AND bc.posting_date BETWEEN %s AND %s
		GROUP BY bc.billet_size
		""",
		(start_date, end_date),
		as_dict=True,
	)

	for row in billet_cutting_rows:
		item_code = row.get("item_code")
		if item_code:
			# If item already has consumption from Bright Bar Production, add to it
			# Otherwise, set it
			current_consumption = consumption_map.get(item_code, 0.0)
			consumption_map[item_code] = current_consumption + flt(row.get("total_billet_weight", 0.0))

	return consumption_map
