# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math
from collections import defaultdict

import frappe
from frappe.utils import date_diff, flt, nowdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": "MR No",
			"fieldname": "mr_no",
			"fieldtype": "Link",
			"options": "Material Request",
			"width": 160,
		},
		{
			"label": "MR Date",
			"fieldname": "mr_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": "SKU Type",
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": "Description",
			"fieldname": "description",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Qty",
			"fieldname": "qty",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": "Balance Qty",
			"fieldname": "completed_qty",
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"label": "Colour",
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 120,
		},
	]


def get_data(filters):
	rows = frappe.db.sql(
		"""
		SELECT
			mr.name AS mr_no,
			mr.transaction_date AS mr_date,
			mr.creation AS mr_creation,
			mri.item_code,
			mri.description,
			ROUND(mri.qty) AS qty,
			ROUND(IFNULL(mri.ordered_qty, 0)) AS completed_qty
		FROM
			`tabMaterial Request` mr
		INNER JOIN
			`tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE
			mr.material_request_type = 'Manufacture'
			AND mr.docstatus = 1
			AND mr.status NOT IN ('Ordered', 'Received')
			AND IFNULL(mri.ordered_qty, 0) < mri.qty
		ORDER BY
			mr.transaction_date DESC, mr.name
		""",
		as_dict=True,
	)

	if not rows:
		return []

	item_codes = list({r.item_code for r in rows})

	stock_map = get_stock_map(item_codes)
	wip_map = get_wip_map(item_codes)
	item_master_map = get_item_master_map(item_codes)
	qd_map = get_qualified_demand_map(item_codes)
	prev_mr_qty_map = get_previous_mr_qty_map(rows)
	so_map = get_open_so_map(item_codes)

	for row in rows:
		ic = row.item_code
		master = item_master_map.get(ic, {"tog": 0.0, "buffer_flag": "Non-Buffer"})
		level = (
			flt(stock_map.get(ic, 0)) + flt(wip_map.get(ic, 0)) + flt(prev_mr_qty_map.get((row.mr_no, ic), 0))
		)

		row["sku_type"] = calculate_sku_type(master["buffer_flag"], master["item_type"])

		if master["buffer_flag"] == "Buffer":
			row["colour"] = _buffer_colour(level, master["tog"], qd_map.get(ic, 0))
		else:
			row["colour"] = _non_buffer_colour(ic, level, so_map)

	return rows


# ---------------------------------------------------------------------------
# SKU Type  (mirrors open_so_analysis logic)
# ---------------------------------------------------------------------------


def calculate_sku_type(buffer_flag, item_type):
	is_buffer = buffer_flag == "Buffer"
	mapping = {
		"BB": ("BBMTA", "BBMTO"),
		"RB": ("RBMTA", "RBMTO"),
		"BO": ("BOTA", "BOTO"),
		"RM": ("PTA", "PTO"),
		"Traded": ("TRMTA", "TRMTO"),
	}
	pair = mapping.get(item_type)
	if not pair:
		return ""
	return pair[0] if is_buffer else pair[1]


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _buffer_colour(level, tog, qualified_demand):
	total = flt(tog) + flt(qualified_demand)
	if level == 0:
		return "Black"
	if total <= 0:
		return ""
	if level <= total / 3:
		return "Red"
	if level <= (2 * total) / 3:
		return "Yellow"
	if level <= total:
		return "Green"
	return "White"


# Order-status priority: higher = worse
_STATUS_PRIORITY = {"BLACK": 5, "RED": 4, "YELLOW": 3, "GREEN": 2, "WHITE": 1}
_PRIORITY_TO_COLOUR = {5: "Black", 4: "Red", 3: "Yellow", 2: "Green", 1: "White"}


def _non_buffer_colour(item_code, level, so_map):
	"""
	FIFO-allocate `level` across open SOs (sorted by delivery_date ASC).
	Return the worst order_status colour among SOs that have a shortage.
	If no shortage anywhere → Green.
	"""
	sos = so_map.get(item_code, [])
	if not sos:
		return ""

	available = flt(level)
	worst_priority = 0  # no shortage yet

	for so in sos:
		required = flt(so["pending_qty"])
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated

		if shortage > 0:
			priority = _STATUS_PRIORITY.get(so["order_status"], 0)
			if priority > worst_priority:
				worst_priority = priority

	if worst_priority == 0:
		return "Green"  # all SOs fully covered
	return _PRIORITY_TO_COLOUR.get(worst_priority, "")


def _compute_order_status(delivery_date, transaction_date):
	"""
	Replicate Open SO Analysis order_status logic.
	remaining_days = delivery_date - today
	buffer_status  = (remaining_days / lead_time) * 100
	"""
	if not delivery_date:
		return None

	today = nowdate()
	remaining_days = date_diff(delivery_date, today)  # positive = future
	lead_time = date_diff(delivery_date, transaction_date) if transaction_date else None

	if lead_time:
		buffer_pct = (flt(remaining_days) / flt(lead_time)) * 100
	else:
		buffer_pct = flt(remaining_days) * 100

	numeric = math.ceil(buffer_pct)

	if numeric < 0:
		return "BLACK"
	elif numeric == 0:
		return "RED"
	elif 1 <= numeric <= 34:
		return "RED"
	elif 35 <= numeric <= 67:
		return "YELLOW"
	elif 68 <= numeric <= 100:
		return "GREEN"
	else:
		return "WHITE"


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------


def get_stock_map(item_codes):
	if not item_codes:
		return {}
	result = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) AS stock
		FROM `tabBin`
		WHERE item_code IN %s
		GROUP BY item_code
		""",
		(item_codes,),
		as_dict=True,
	)
	return {r.item_code: flt(r.stock) for r in result}


# ---------------------------------------------------------------------------
# WIP  (static 0 until logic is confirmed)
# ---------------------------------------------------------------------------


def get_wip_map(item_codes):
	return {item: 0.0 for item in item_codes}


# ---------------------------------------------------------------------------
# Item master  (TOG = safety_stock, buffer_flag)
# ---------------------------------------------------------------------------


def get_item_master_map(item_codes):
	if not item_codes:
		return {}
	result = frappe.db.sql(
		"""
		SELECT name AS item_code,
		       safety_stock AS tog,
		       custom_buffer_flag AS buffer_flag,
		       custom_item_type AS item_type
		FROM `tabItem`
		WHERE name IN %s
		""",
		(item_codes,),
		as_dict=True,
	)
	return {
		r.item_code: {
			"tog": flt(r.tog),
			"buffer_flag": r.buffer_flag or "Non-Buffer",
			"item_type": r.item_type or "",
		}
		for r in result
	}


# ---------------------------------------------------------------------------
# Qualified Demand  (till today from open Sales Orders — buffer items only)
# ---------------------------------------------------------------------------


def get_qualified_demand_map(item_codes):
	if not item_codes:
		return {}
	today = nowdate()
	result = frappe.db.sql(
		"""
		SELECT soi.item_code,
		       SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) AS qd
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
		  AND soi.item_code IN %s
		GROUP BY soi.item_code
		""",
		(today, item_codes),
		as_dict=True,
	)
	return {r.item_code: flt(r.qd) for r in result}


# ---------------------------------------------------------------------------
# Open SO map for non-buffer FIFO allocation
#   Returns {item_code: [ {pending_qty, order_status}, ... ]} sorted delivery_date ASC
# ---------------------------------------------------------------------------


def get_open_so_map(item_codes):
	if not item_codes:
		return {}
	result = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			so.transaction_date,
			soi.delivery_date,
			GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code IN %s
		  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
		ORDER BY soi.delivery_date ASC
		""",
		(item_codes,),
		as_dict=True,
	)

	so_map = defaultdict(list)
	for r in result:
		so_map[r.item_code].append(
			{
				"pending_qty": flt(r.pending_qty),
				"order_status": _compute_order_status(r.delivery_date, r.transaction_date),
				"delivery_date": r.delivery_date,
				"transaction_date": r.transaction_date,
			}
		)
	return so_map


# ---------------------------------------------------------------------------
# Previous MR pending qty
# ---------------------------------------------------------------------------


def get_previous_mr_qty_map(rows):
	"""
	Returns {(mr_no, item_code): previous_pending_qty}.
	Only counts MRs whose status is not Ordered or Received.
	"""
	item_codes = list({r.item_code for r in rows})
	if not item_codes:
		return {}

	all_pending = frappe.db.sql(
		"""
		SELECT
			mr.name AS mr_no,
			mr.creation,
			mri.item_code,
			GREATEST(0, mri.qty - IFNULL(mri.ordered_qty, 0)) AS pending_qty
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE mr.material_request_type = 'Manufacture'
		  AND mr.docstatus = 1
		  AND mr.status NOT IN ('Ordered', 'Received')
		  AND mri.item_code IN %s
		""",
		(item_codes,),
		as_dict=True,
	)

	item_pending_map = defaultdict(list)
	for p in all_pending:
		item_pending_map[p.item_code].append(p)

	result_map = {}
	for row in rows:
		key = (row.mr_no, row.item_code)
		result_map[key] = flt(
			sum(p.pending_qty for p in item_pending_map[row.item_code] if p.creation < row.mr_creation)
		)
	return result_map


# ---------------------------------------------------------------------------
# Debug API - called from the JS button
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_item_breakdown(mr_name):
	"""
	Returns per-item breakdown for the given MR:
	  buffer items  → stock, wip, tog, qualified_demand, previous_mr_qty, level, colour
	  non-buffer    → stock, wip, previous_mr_qty, level, SO-level FIFO detail, colour
	"""
	mr = frappe.db.get_value(
		"Material Request",
		mr_name,
		["name", "creation", "material_request_type", "docstatus"],
		as_dict=True,
	)
	if not mr:
		frappe.throw(f"Material Request {mr_name} not found.")
	if mr.material_request_type != "Manufacture":
		frappe.throw(f"{mr_name} is not a Manufacture type MR.")

	items = frappe.db.sql(
		"""
		SELECT item_code, description,
		       ROUND(qty) AS qty,
		       ROUND(IFNULL(ordered_qty, 0)) AS completed_qty
		FROM `tabMaterial Request Item`
		WHERE parent = %s
		""",
		(mr_name,),
		as_dict=True,
	)
	if not items:
		return []

	item_codes = [r.item_code for r in items]

	stock_map = get_stock_map(item_codes)
	wip_map = get_wip_map(item_codes)
	item_master_map = get_item_master_map(item_codes)
	qd_map = get_qualified_demand_map(item_codes)
	so_map = get_open_so_map(item_codes)

	# Previous MR qty relative to this MR
	all_pending = frappe.db.sql(
		"""
		SELECT
			mr.name AS mr_no,
			mr.creation,
			mri.item_code,
			GREATEST(0, mri.qty - IFNULL(mri.ordered_qty, 0)) AS pending_qty
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE mr.material_request_type = 'Manufacture'
		  AND mr.docstatus = 1
		  AND mr.status NOT IN ('Ordered', 'Received')
		  AND mri.item_code IN %s
		""",
		(item_codes,),
		as_dict=True,
	)
	item_pending_map = defaultdict(list)
	for p in all_pending:
		item_pending_map[p.item_code].append(p)

	breakdown = []
	for row in items:
		ic = row.item_code
		master = item_master_map.get(ic, {"tog": 0.0, "buffer_flag": "Non-Buffer"})
		prev_qty = flt(sum(p.pending_qty for p in item_pending_map[ic] if p.creation < mr.creation))
		stock = flt(stock_map.get(ic, 0))
		wip = flt(wip_map.get(ic, 0))
		level = stock + wip + prev_qty
		is_buffer = master["buffer_flag"] == "Buffer"

		entry = {
			"item_code": ic,
			"description": row.description,
			"buffer_flag": master["buffer_flag"],
			"sku_type": calculate_sku_type(master["buffer_flag"], master["item_type"]),
			"qty": flt(row.qty),
			"completed_qty": flt(row.completed_qty),
			"stock": stock,
			"wip": wip,
			"previous_mr_qty": prev_qty,
			"level": level,
		}

		if is_buffer:
			tog = master["tog"]
			qd = flt(qd_map.get(ic, 0))
			entry["tog"] = tog
			entry["qualified_demand"] = qd
			entry["total"] = tog + qd
			entry["colour"] = _buffer_colour(level, tog, qd)
			entry["so_fifo_detail"] = []
		else:
			entry["tog"] = "N/A"
			entry["qualified_demand"] = "N/A"
			entry["total"] = "N/A"
			# FIFO SO detail
			sos = so_map.get(ic, [])
			available = level
			fifo_rows = []
			worst_priority = 0

			for so in sos:
				required = flt(so["pending_qty"])
				allocated = min(required, available)
				shortage = required - allocated
				available -= allocated
				status = so["order_status"] or ""

				if shortage > 0:
					priority = _STATUS_PRIORITY.get(status, 0)
					if priority > worst_priority:
						worst_priority = priority

				fifo_rows.append(
					{
						"delivery_date": str(so["delivery_date"]) if so["delivery_date"] else "",
						"pending_qty": required,
						"allocated": allocated,
						"shortage": shortage,
						"order_status": status,
					}
				)

			colour = (
				"Green"
				if worst_priority == 0 and sos
				else (_PRIORITY_TO_COLOUR.get(worst_priority, "") if worst_priority else "")
			)
			entry["colour"] = colour
			entry["so_fifo_detail"] = fifo_rows

		breakdown.append(entry)

	return breakdown
