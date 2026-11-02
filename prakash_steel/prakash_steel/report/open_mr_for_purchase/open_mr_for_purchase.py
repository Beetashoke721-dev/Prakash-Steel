# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import math
from collections import defaultdict

import frappe
from frappe.utils import date_diff, flt, nowdate

from prakash_steel.utils.whitelist_permissions import require_permission

from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import (
	_rbmto_colour,
	get_parent_bom_map,
	get_rbmto_so_detail_map,
)
from prakash_steel.prakash_steel.report.po_recomendation_for_psp.data_fetchers import get_planning_stock_map


def execute(filters=None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
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


def get_data(filters) -> list[dict]:
	rows = frappe.db.sql(
		"""
		SELECT
			mr.name AS mr_no,
			mr.transaction_date AS mr_date,
			mr.creation AS mr_creation,
			mri.item_code,
			mri.description,
			ROUND(mri.qty) AS qty,
			ROUND(mri.qty - IFNULL(mri.ordered_qty, 0)) AS completed_qty
		FROM
			`tabMaterial Request` mr
		INNER JOIN
			`tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE
			mr.material_request_type = 'Purchase'
			AND mr.docstatus = 1
			AND mr.status NOT IN ('Ordered', 'Received', 'Stopped')
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
	open_po_map = get_open_po_map(item_codes)
	item_master_map = get_item_master_map(item_codes)
	qd_map = get_qualified_demand_map(item_codes, item_master_map)
	prev_mr_qty_map = get_previous_mr_qty_map(rows)
	rbmto_so_detail_map, child_parent_so_fifo = _build_parent_fifo_data(item_codes, item_master_map)

	for row in rows:
		ic = row.item_code
		master = item_master_map.get(ic, {"tog": 0.0, "buffer_flag": "Non-Buffer"})
		level = (
			flt(stock_map.get(ic, 0))
			+ flt(open_po_map.get(ic, 0))
			+ flt(prev_mr_qty_map.get((row.mr_no, ic), 0))
		)

		row["sku_type"] = calculate_sku_type(master["buffer_flag"], master["item_type"])

		if master["buffer_flag"] == "Buffer":
			row["colour"] = _buffer_colour(level, master["tog"], qd_map.get(ic, 0))
		else:
			row["colour"] = _rbmto_colour(
				level,
				rbmto_so_detail_map.get(ic, []),
				child_parent_so_fifo.get(ic, []),
			)

	return rows


# ---------------------------------------------------------------------------
# SKU Type
# ---------------------------------------------------------------------------


def calculate_sku_type(buffer_flag, item_type) -> str | None:
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


def _buffer_colour(level, tog, qualified_demand) -> str:
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


def _non_buffer_colour(item_code, level, so_map) -> str:
	"""
	FIFO-allocate `level` across open SOs (sorted by delivery_date ASC).
	Return the worst order_status colour among SOs that have a shortage.
	If no shortage anywhere → Green.
	"""
	sos = so_map.get(item_code, [])
	if not sos:
		return ""

	available = flt(level)
	worst_priority = 0

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
		return "Green"
	return _PRIORITY_TO_COLOUR.get(worst_priority, "")


def _compute_order_status(delivery_date, transaction_date) -> str | None:
	if not delivery_date:
		return None

	today = nowdate()
	remaining_days = date_diff(delivery_date, today)
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


def get_stock_map(item_codes) -> dict:
	return get_planning_stock_map(item_codes)


# ---------------------------------------------------------------------------
# Open PO  (qty ordered but not yet received)
# ---------------------------------------------------------------------------


def get_open_po_map(item_codes) -> dict:
	if not item_codes:
		return {}
	po_rows = frappe.db.sql(
		"""
		SELECT
			poi.item_code,
			poi.qty,
			IFNULL(poi.received_qty, 0) AS received_qty
		FROM
			`tabPurchase Order` po
		INNER JOIN
			`tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE
			po.docstatus = 1
			AND po.status NOT IN ('Cancelled', 'Closed')
			AND IFNULL(poi.custom_closed, 0) = 0
			AND poi.item_code IN %s
		""",
		(item_codes,),
		as_dict=True,
	)

	open_po_map = {}
	for row in po_rows:
		ic = row.item_code
		open_qty = max(0, flt(row.qty) - flt(row.received_qty))
		open_po_map[ic] = open_po_map.get(ic, 0) + open_qty

	return open_po_map


# ---------------------------------------------------------------------------
# Item master  (TOG = safety_stock, buffer_flag)
# ---------------------------------------------------------------------------


def get_item_master_map(item_codes) -> dict:
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
# Qualified Demand  (till today + spike from open Sales Orders)
# ---------------------------------------------------------------------------


def get_qualified_demand_map(item_codes, item_master_map) -> dict:
	if not item_codes:
		return {}
	today = nowdate()

	# Till today
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
	till_today_map = {r.item_code: flt(r.qd) for r in result}

	# Spike master config
	spike_master_map = {
		sm.item_type: {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}
		for sm in frappe.get_all(
			"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
		)
	}

	# Spike (future SOs within demand horizon, buffer items only)
	spike_map = _calculate_spike_map(item_codes, item_master_map, spike_master_map)

	# Combine till_today + spike with threshold check
	qd_map = {}
	for ic in item_codes:
		master = item_master_map.get(ic, {})
		till_today = flt(till_today_map.get(ic, 0))

		if master.get("buffer_flag") == "Buffer":
			spike = flt(spike_map.get(ic, 0))
			qd = till_today + spike
			# If qd < TOG * spike_threshold%, treat as 0
			item_type = master.get("item_type", "")
			tog = flt(master.get("tog", 0))
			spike_config = spike_master_map.get(item_type)
			if spike_config and tog > 0:
				threshold_qty = tog * spike_config["spike_threshold"] / 100
				if qd < threshold_qty:
					qd = 0.0
			qd_map[ic] = qd
		else:
			qd_map[ic] = till_today  # Non-buffer: no spike

	return qd_map


def _calculate_spike_map(item_codes, item_master_map, spike_master_map) -> dict:
	from frappe.utils import add_days

	spike_map = {ic: 0.0 for ic in item_codes}
	today = nowdate()

	# Group buffer items by item_type (only those with a spike master config)
	items_by_type = defaultdict(list)
	for ic in item_codes:
		master = item_master_map.get(ic, {})
		if master.get("buffer_flag") == "Buffer":
			item_type = master.get("item_type", "")
			if item_type in spike_master_map:
				items_by_type[item_type].append(ic)

	for item_type, items in items_by_type.items():
		demand_horizon = spike_master_map[item_type]["demand_horizon"]
		if demand_horizon <= 0:
			continue

		start_date = add_days(today, 1)
		end_date = add_days(today, int(demand_horizon))

		rows = frappe.db.sql(
			"""
			SELECT soi.item_code,
			       SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) AS future_qty
			FROM `tabSales Order` so
			INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
			WHERE so.docstatus = 1
			  AND so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			  AND IFNULL(soi.custom_closed, 0) = 0
			  AND soi.item_code IN %s
			  AND IFNULL(soi.delivery_date, '1900-01-01') >= %s
			  AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
			GROUP BY soi.item_code
			""",
			(tuple(items), start_date, end_date),
			as_dict=True,
		)
		for r in rows:
			spike_map[r.item_code] = flt(r.future_qty)

	return spike_map


# ---------------------------------------------------------------------------
# Parent BOM FIFO data for non-buffer colour
# ---------------------------------------------------------------------------


def _build_parent_fifo_data(item_codes, item_master_map) -> dict:
	"""
	For non-buffer items: build own-SO FIFO list and parent-SO FIFO list.
	Parent open SOs are fetched directly — no net_order_rec guard.
	child_req = ceil(parent_so_pending * bom_ratio), already in child units.
	Returns (rbmto_so_detail_map, child_parent_so_fifo).
	"""
	non_buffer_codes = [
		ic for ic in item_codes
		if item_master_map.get(ic, {}).get("buffer_flag") != "Buffer"
	]
	if not non_buffer_codes:
		return {}, {}

	rbmto_so_detail_map = get_rbmto_so_detail_map(non_buffer_codes)

	parent_bom_map = get_parent_bom_map(non_buffer_codes)
	all_parent_codes = {p["parent_item"] for plist in parent_bom_map.values() for p in plist}
	if not all_parent_codes:
		return rbmto_so_detail_map, {}

	parent_tuple = tuple(all_parent_codes)

	# Fetch parent open SOs directly — no net_order_rec check needed
	parent_so_rows = frappe.db.sql(
		"""
		SELECT soi.item_code AS parent_item,
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
		(parent_tuple,),
		as_dict=True,
	)

	parent_so_map = defaultdict(list)
	for r in parent_so_rows:
		status = _compute_order_status(r.delivery_date, r.transaction_date)
		colour = status.capitalize() if status else ""
		parent_so_map[r.parent_item].append({
			"pending_qty": flt(r.pending_qty),
			"colour": colour,
			"delivery_date": r.delivery_date,
		})

	priority_seq_rows = frappe.db.sql(
		"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
		as_dict=True,
	)
	priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

	child_parent_so_fifo = defaultdict(list)
	for child_ic in non_buffer_codes:
		flat = []
		for p in parent_bom_map.get(child_ic, []):
			parent_item = p["parent_item"]
			bom_ratio = flt(p["bom_qty"]) / (flt(p["bom_quantity"]) or 1.0)
			for so in parent_so_map.get(parent_item, []):
				child_req = math.ceil(flt(so["pending_qty"]) * bom_ratio)
				colour = so["colour"]
				pc_str = "MTO" + (colour.upper() if colour else "")
				pri_seq = priority_seq_map.get(pc_str, 999999)
				flat.append({
					"parent_item": parent_item,
					"parent_so_pending": flt(so["pending_qty"]),
					"batch_qty": child_req,  # child units — used by _rbmto_colour
					"child_req": child_req,
					"colour": colour,
					"priority_colour": pc_str,
					"priority_sequence": pri_seq,
					"delivery_date": so["delivery_date"],
				})
		flat.sort(key=lambda x: (x["priority_sequence"], str(x["delivery_date"] or "")))
		child_parent_so_fifo[child_ic] = flat

	return rbmto_so_detail_map, dict(child_parent_so_fifo)


# ---------------------------------------------------------------------------
# Open SO map for non-buffer FIFO allocation
# ---------------------------------------------------------------------------


def get_open_so_map(item_codes) -> dict:
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


def get_previous_mr_qty_map(rows) -> dict:
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
		WHERE mr.material_request_type = 'Purchase'
		  AND mr.docstatus = 1
		  AND mr.status NOT IN ('Ordered', 'Received', 'Stopped')
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
def get_item_breakdown(mr_name) -> list[dict]:
	"""
	Returns per-item breakdown for the given MR:
	  buffer items  → stock, open_po, tog, qualified_demand, previous_mr_qty, level, colour
	  non-buffer    → stock, open_po, previous_mr_qty, level, SO-level FIFO detail, colour
	"""
	require_permission("Material Request", "read")
	mr = frappe.db.get_value(
		"Material Request",
		mr_name,
		["name", "creation", "material_request_type", "docstatus"],
		as_dict=True,
	)
	if not mr:
		frappe.throw(f"Material Request {mr_name} not found.")
	if mr.material_request_type != "Purchase":
		frappe.throw(f"{mr_name} is not a Purchase type MR.")

	items = frappe.db.sql(
		"""
		SELECT item_code, description,
		       ROUND(qty) AS qty,
		       ROUND(qty - IFNULL(ordered_qty, 0)) AS completed_qty
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
	open_po_map = get_open_po_map(item_codes)
	item_master_map = get_item_master_map(item_codes)
	qd_map = get_qualified_demand_map(item_codes, item_master_map)
	rbmto_so_detail_map, child_parent_so_fifo = _build_parent_fifo_data(item_codes, item_master_map)

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
		WHERE mr.material_request_type = 'Purchase'
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
	# Build debug maps: parent BOM and parent SO counts per child item
	_debug_parent_bom_map = get_parent_bom_map(item_codes)
	_debug_all_parents = {p["parent_item"] for plist in _debug_parent_bom_map.values() for p in plist}
	_debug_parent_so_counts = {}
	if _debug_all_parents:
		_pt = tuple(_debug_all_parents)
		_pso_rows = frappe.db.sql(
			"""
			SELECT soi.item_code, COUNT(*) AS cnt
			FROM `tabSales Order Item` soi
			INNER JOIN `tabSales Order` so ON so.name = soi.parent
			WHERE so.docstatus = 1
			  AND so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			  AND IFNULL(soi.custom_closed,0) = 0
			  AND soi.item_code IN %s
			  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty,0)) > 0
			GROUP BY soi.item_code
			""",
			(_pt,),
			as_dict=True,
		)
		_debug_parent_so_counts = {r.item_code: r.cnt for r in _pso_rows}

	for row in items:
		ic = row.item_code
		master = item_master_map.get(ic, {"tog": 0.0, "buffer_flag": "Non-Buffer"})
		prev_qty = flt(sum(p.pending_qty for p in item_pending_map[ic] if p.creation < mr.creation))
		stock = flt(stock_map.get(ic, 0))
		open_po = flt(open_po_map.get(ic, 0))
		level = stock + open_po + prev_qty
		is_buffer = master["buffer_flag"] == "Buffer"

		item_entry = {
			"item_code": ic,
			"description": row.description,
			"buffer_flag": master["buffer_flag"],
			"sku_type": calculate_sku_type(master["buffer_flag"], master["item_type"]),
			"qty": flt(row.qty),
			"completed_qty": flt(row.completed_qty),
			"stock": stock,
			"open_po": open_po,
			"previous_mr_qty": prev_qty,
			"level": level,
		}

		if is_buffer:
			tog = master["tog"]
			qd = flt(qd_map.get(ic, 0))
			item_entry["tog"] = tog
			item_entry["qualified_demand"] = qd
			item_entry["total"] = tog + qd
			item_entry["colour"] = _buffer_colour(level, tog, qd)
			item_entry["own_so_detail"] = []
			item_entry["parent_fifo_detail"] = []
			item_entry["debug_parent_bom"] = []
		else:
			item_entry["tog"] = "N/A"
			item_entry["qualified_demand"] = "N/A"
			item_entry["total"] = "N/A"
			own_so_list = rbmto_so_detail_map.get(ic, [])
			parent_fifo_list = child_parent_so_fifo.get(ic, [])
			item_entry["colour"] = _rbmto_colour(level, own_so_list, parent_fifo_list)

			# Debug: which parents found in BOM and whether they have SOs
			bom_parents = _debug_parent_bom_map.get(ic, [])
			item_entry["debug_parent_bom"] = [
				{
					"parent_item": p["parent_item"],
					"bom_qty": p["bom_qty"],
					"bom_quantity": p["bom_quantity"],
					"open_so_count": _debug_parent_so_counts.get(p["parent_item"], 0),
				}
				for p in bom_parents
			]

			# Own SO FIFO detail
			available = flt(level)
			own_so_rows = []
			for so in own_so_list:
				required = flt(so["pending_qty"])
				allocated = min(required, available)
				shortage = required - allocated
				available -= allocated
				own_so_rows.append({
					"pending_qty": required,
					"colour": so["colour"],
					"allocated": allocated,
					"shortage": shortage,
				})

			# Parent SO FIFO detail (remaining after own SOs)
			parent_rows = []
			for fifo_entry in parent_fifo_list:
				child_req = flt(fifo_entry["child_req"])
				allocated = min(child_req, available)
				shortage = child_req - allocated
				available -= allocated
				parent_rows.append({
					"parent_item": fifo_entry["parent_item"],
					"parent_so_pending": fifo_entry.get("parent_so_pending", child_req),
					"child_req": child_req,
					"colour": fifo_entry["colour"],
					"priority_colour": fifo_entry["priority_colour"],
					"allocated": allocated,
					"shortage": shortage,
				})

			item_entry["own_so_detail"] = own_so_rows
			item_entry["parent_fifo_detail"] = parent_rows

		breakdown.append(item_entry)

	return breakdown
