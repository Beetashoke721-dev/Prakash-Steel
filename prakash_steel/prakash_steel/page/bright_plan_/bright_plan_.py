import math
import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	_non_buffer_priority,
	apply_spike_threshold,
	calculate_spike_map,
	calculate_sku_type,
	get_open_po_map,
	get_open_so_map_for_priority,
	get_planning_stock_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_wip_map,
)
from prakash_steel.utils.lead_time import get_default_bom
from prakash_steel.utils.whitelist_permissions import require_all_permissions, require_permission


def _get_draft_wo_map() -> dict:
	"""Returns {item_code: draft_wo_qty} — sum of qty from draft (docstatus=0) Work Orders."""
	rows = frappe.db.sql(
		"""
		SELECT production_item AS item_code, SUM(qty) AS draft_wo_qty
		FROM `tabWork Order`
		WHERE docstatus = 0
		GROUP BY production_item
		""",
		as_dict=True,
	)
	return {r.item_code: flt(r.draft_wo_qty) for r in rows}


def _get_manufacture_mr_lines_map() -> dict:
	"""Pending Material Request lines per BB item, one entry per open, submitted
	Material Request of type Manufacture: {item_code: [{qty, material_request, date}, ...]}."""
	rows = frappe.db.sql(
		"""
		SELECT
			mri.item_code,
			mr.name AS material_request,
			mr.transaction_date AS date,
			GREATEST(0, mri.qty - IFNULL(mri.ordered_qty, 0)) AS pending_qty
		FROM `tabMaterial Request` mr
		INNER JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
		INNER JOIN `tabItem` i ON i.name = mri.item_code
		WHERE mr.docstatus = 1
		  AND mr.material_request_type = 'Manufacture'
		  AND mr.status NOT IN ('Ordered', 'Received', 'Stopped', 'Cancelled')
		  AND i.custom_item_type = 'BB'
		ORDER BY mr.transaction_date, mr.name, mri.idx
		""",
		as_dict=True,
	)
	lines_map = {}
	for r in rows:
		if flt(r.pending_qty) <= 0:
			continue
		lines_map.setdefault(r.item_code, []).append(
			{"qty": flt(r.pending_qty), "material_request": r.material_request, "date": r.date}
		)
	return lines_map


def get_columns() -> list[dict]:
	return [
		{"label": _("Machine"), "fieldname": "machine", "fieldtype": "Link", "options": "Bright Machine", "width": 130},
		{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("SKU Type"), "fieldname": "sku_type", "fieldtype": "Data", "width": 100},
		{"label": _("Open SO"), "fieldname": "open_so", "fieldtype": "Int", "width": 120},
		{"label": _("On Hand Stock"), "fieldname": "on_hand_stock", "fieldtype": "Int", "width": 130},
		{
			"label": _("Order Recommendation Colour"),
			"fieldname": "on_hand_colour_priority",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("MR Qty"),
			"fieldname": "or_with_moq_batch_size",
			"fieldtype": "Int",
			"width": 220,
		},
		{
			"label": _("Material Request"),
			"fieldname": "material_request",
			"fieldtype": "Link",
			"options": "Material Request",
			"width": 150,
		},
		{
			"label": _("Material Request Date"),
			"fieldname": "material_request_date",
			"fieldtype": "Date",
			"width": 140,
		},
		{"label": _("Priority"), "fieldname": "priority_colour", "fieldtype": "Data", "width": 160},
		{"label": _("Priority Sequence"), "fieldname": "priority_sequence", "fieldtype": "Int", "width": 140},
		{"label": _("OP/CP"), "fieldname": "op_cp", "fieldtype": "Data", "width": 80},
		{"label": _("MOQ"), "fieldname": "moq", "fieldtype": "Int", "width": 100},
		{"label": _("Order Multiple Qty"), "fieldname": "batch_size", "fieldtype": "Int", "width": 150},
		{
			"label": _("Prod Qty based on Child Stock"),
			"fieldname": "production_qty_based_on_child_stock",
			"fieldtype": "Int",
			"width": 220,
		},
		{
			"label": _("Process Time based on Child Stock"),
			"fieldname": "process_time_based_on_child_stock",
			"fieldtype": "Float",
			"precision": 2,
			"width": 220,
		},
		{
			"label": _("Prod Qty based on Child Stock+WIP/Open PO"),
			"fieldname": "production_qty_based_on_child_stock_wip_open_po",
			"fieldtype": "Int",
			"width": 280,
		},
		{"label": _("Child Item Code"), "fieldname": "child_item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Child Requirement"), "fieldname": "child_requirement", "fieldtype": "Int", "width": 150},
		{"label": _("Child Stock"), "fieldname": "child_stock", "fieldtype": "Int", "width": 120},
		{
			"label": _("Child Stock Soft Allocation"),
			"fieldname": "child_stock_soft_allocation_qty",
			"fieldtype": "Int",
			"width": 200,
		},
		{"label": _("Child Stock Shortage"), "fieldname": "child_stock_shortage", "fieldtype": "Int", "width": 160},
		{"label": _("Child WIP/Open PO"), "fieldname": "child_wip_open_po", "fieldtype": "Int", "width": 160},
		{"label": _("Child SKU Type"), "fieldname": "child_sku_type", "fieldtype": "Data", "width": 130},
		{
			"label": _("Per Hour Production"),
			"fieldname": "per_hour_production",
			"fieldtype": "Float",
			"precision": 2,
			"width": 160,
		},
		{"label": _("Process Time"), "fieldname": "process_time", "fieldtype": "Float", "precision": 2, "width": 130},
	]


def get_data() -> list[dict]:
	order_rec_map = _get_manufacture_mr_lines_map()
	if not order_rec_map:
		return []

	item_codes_filter = list(order_rec_map.keys())

	# Fetch only BB items that have a pending Manufacture Material Request line
	bb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.item_name,
			i.custom_buffer_flag as buffer_flag,
			i.custom_item_type as item_type,
			i.safety_stock as tog,
			i.min_order_qty as moq,
			i.custom_batch_size as batch_size
		FROM `tabItem` i
		WHERE i.custom_item_type = 'BB'
		  AND i.name IN %(items)s
		""",
		{"items": item_codes_filter},
		as_dict=True,
	)

	if not bb_items:
		return []

	item_codes = set(item.item_code for item in bb_items)

	# Build lookup maps
	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	moq_map = {}
	batch_size_map = {}
	item_name_map = {}

	for item in bb_items:
		ic = item.item_code
		item_buffer_map[ic] = item.buffer_flag or "Non-Buffer"
		item_type_map[ic] = item.item_type
		item_tog_map[ic] = flt(item.tog or 0)
		moq_map[ic] = flt(item.moq or 0)
		batch_size_map[ic] = flt(item.batch_size or 0)
		item_name_map[ic] = item.item_name or ic

	# Fetch shared data maps
	stock_map = get_planning_stock_map(item_codes)
	wip_map = get_wip_map()
	draft_wo_map = _get_draft_wo_map()
	open_po_map = get_open_po_map()
	till_today_map, spike_map = get_qualified_demand_map()

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}
		for sm in spike_master_records
	}

	calculated_spike_map = calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map)
	spike_map.update(calculated_spike_map)

	# Open SO qty map (all open SOs, not just till today)
	open_so_qty_map = get_sales_order_qty_map({})

	# For BBMTO priority calculation
	so_map_for_priority = get_open_so_map_for_priority(list(item_codes))

	# Build machine map: item_code -> {machine, per_hour_production} from default row
	machine_rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.machine_group_name, bmmt.mt_per_hour_production
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		WHERE bmmt.is_default = 1
		""",
		as_dict=True,
	)
	machine_map = {
		r.item_code: {
			"machine": r.machine_group_name,
			"per_hour_production": flt(r.mt_per_hour_production),
		}
		for r in machine_rows
	}

	# Build priority sequence map: priority_colour value -> sequence number
	priority_seq_rows = frappe.db.sql(
		"SELECT priority_colour, sequence FROM `tabPriority Colour Seq Master Table`",
		as_dict=True,
	)
	priority_seq_map = {r.priority_colour: r.sequence for r in priority_seq_rows}

	# Last 3 month sale map: item_code -> sum of (qty - delivered_qty) from submitted Sales Invoices
	last_3month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(GREATEST(0, sii.qty - IFNULL(sii.delivered_qty, 0))) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
		GROUP BY sii.item_code
		""",
		as_dict=True,
	)
	last_3month_sale_map = {r.item_code: math.ceil(flt(r.sale_qty)) for r in last_3month_rows}

	# Build base rows
	data = []
	child_stock_map = {}
	child_wip_open_po_map = {}
	child_item_detail_map = {}  # cache: item_code -> (custom_item_type, custom_buffer_flag)

	for item_code in sorted(item_codes):
		buffer_flag = item_buffer_map[item_code]
		is_buffer = buffer_flag == "Buffer"
		sku_type = calculate_sku_type(buffer_flag, "BB")  # BBMTA or BBMTO

		stock = flt(stock_map.get(item_code, 0))
		tog = item_tog_map[item_code]
		moq = moq_map[item_code]
		batch_size = batch_size_map[item_code]
		wip = flt(wip_map.get(item_code, 0))
		draft_wo = flt(draft_wo_map.get(item_code, 0))

		qualified_demand, till_today, spike = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map,
		)
		raw_qualified_demand = flt(qualified_demand)
		qualified_demand = raw_qualified_demand
		if is_buffer:
			qualified_demand = apply_spike_threshold(
				raw_qualified_demand, tog, item_type_map.get(item_code), spike_master_map
			)
		item_open_so = flt(open_so_qty_map.get(item_code, 0))

		# Manual plan: one row per pending Material Request line for this item —
		# order recommendation comes from the Material Request, not TOG/qualified-demand.
		batches = [
			{
				"qty": math.ceil(flt(line.get("qty"))),
				"material_request": line.get("material_request"),
				"material_request_date": line.get("date"),
			}
			for line in order_rec_map[item_code]
		]

		if sum(b["qty"] for b in batches) == 0:
			continue

		# Get BOM child items (fetched once per parent item)
		bom = get_default_bom(item_code)
		child_items = []

		if bom:
			try:
				bom_doc = frappe.get_doc("BOM", bom)
				bom_quantity = flt(bom_doc.quantity) or 1.0
				for bom_item in bom_doc.items:
					child_item_code = bom_item.item_code
					child_bom_qty = flt(bom_item.qty)

					child_item_type = None
					child_sku_type = None
					child_stock = 0
					child_wip_open_po = 0

					try:
						if child_item_code not in child_item_detail_map:
							child_item_detail_map[child_item_code] = (
								frappe.db.get_value(
									"Item",
									child_item_code,
									["custom_item_type", "custom_buffer_flag"],
									as_dict=True,
								)
								or {}
							)
						child_detail = child_item_detail_map[child_item_code]
						child_item_type = child_detail.get("custom_item_type")
						child_buffer_flag = child_detail.get("custom_buffer_flag") or "Non-Buffer"
						child_sku_type = calculate_sku_type(child_buffer_flag, child_item_type)

						if child_item_code not in child_stock_map:
							child_stock_map[child_item_code] = math.ceil(
								flt(get_planning_stock_map([child_item_code]).get(child_item_code, 0))
							)

						child_stock = child_stock_map[child_item_code]

						child_wip = (
							0
							if child_sku_type in ["RBMTA", "RBMTO"]
							else flt(wip_map.get(child_item_code, 0))
						)
						child_open_po = flt(open_po_map.get(child_item_code, 0))
						child_wip_open_po = math.ceil(child_wip + child_open_po)

						if child_item_code not in child_wip_open_po_map:
							child_wip_open_po_map[child_item_code] = child_wip_open_po
					except Exception:
						pass

					child_items.append(
						{
							"item_code": child_item_code,
							"bom_qty": child_bom_qty,
							"bom_quantity": bom_quantity,
							"child_item_type": child_item_type,
							"child_sku_type": child_sku_type,
							"child_stock": child_stock,
							"child_wip_open_po": child_wip_open_po,
						}
					)
			except Exception:
				pass

		# Buffer: open SO for display/OP-CP = qualified demand (delivery_date <= today + spike)
		# before the spike threshold, same as PO Recommendation / Manual Bright Plan.
		# Non-buffer: open SO for display/OP-CP = all-time open SO (no date filter)
		display_open_so = raw_qualified_demand if is_buffer else item_open_so
		remaining_so_for_op_cp = max(0, display_open_so - stock - wip - draft_wo)
		accumulated_batch_qty = 0.0

		for batch in batches:
			qty_per_row = batch["qty"]

			# Colour: level = stock + submitted_wo + draft_wo + qty already produced in previous batches
			level = stock + wip + draft_wo + accumulated_batch_qty
			if is_buffer:
				total = tog + qualified_demand
				if level == 0:
					on_hand_colour_priority = "Black"
				elif total <= 0:
					on_hand_colour_priority = ""
				elif level <= total / 3:
					on_hand_colour_priority = "Red"
				elif level <= (2 * total) / 3:
					on_hand_colour_priority = "Yellow"
				elif level <= total:
					on_hand_colour_priority = "Green"
				else:
					on_hand_colour_priority = "White"
			else:
				on_hand_colour_priority = _non_buffer_priority(item_code, level, so_map_for_priority)

			if not is_buffer:
				op_cp = ""
			elif qty_per_row == 0:
				op_cp = ""
			elif remaining_so_for_op_cp > 0:
				op_cp = "OP"
			else:
				op_cp = "CP"
			remaining_so_for_op_cp -= qty_per_row

			machine_info = machine_map.get(item_code) or {}
			machine_name = machine_info.get("machine")
			per_hour = machine_info.get("per_hour_production")
			priority_colour = (
				(("MTA" + (op_cp or "") + on_hand_colour_priority.upper())
				if sku_type == "BBMTA"
				else ("MTO" + on_hand_colour_priority.upper()))
				if on_hand_colour_priority else ""
			)

			base_row = {
				"machine": machine_name,
				"per_hour_production": per_hour,
				"process_time": round(qty_per_row / flt(per_hour), 2) if per_hour else None,
				"item_code": item_code,
				"item_name": item_name_map[item_code],
				"sku_type": sku_type,
				"open_so": math.ceil(display_open_so),
				"last_3month_sale": last_3month_sale_map.get(item_code, 0),
				"on_hand_stock": math.ceil(stock),
				"on_hand_colour_priority": on_hand_colour_priority,
				"op_cp": op_cp,
				"priority_colour": priority_colour,
				"priority_sequence": priority_seq_map.get(priority_colour) if priority_colour else None,
				"or_with_moq_batch_size": math.ceil(qty_per_row),
				"material_request": batch["material_request"],
				"material_request_date": batch["material_request_date"],
				"moq": math.ceil(moq),
				"batch_size": math.ceil(batch_size),
				"production_qty_based_on_child_stock": None,
				"process_time_based_on_child_stock": None,
				"production_qty_based_on_child_stock_wip_open_po": None,
				"child_item_code": None,
				"child_requirement": None,
				"child_stock": None,
				"child_stock_soft_allocation_qty": None,
				"child_stock_shortage": None,
				"child_sku_type": None,
				"child_bom_qty": None,
				"child_bom_quantity": None,
				"child_wip_open_po": None,
			}

			if child_items:
				for child_info in child_items:
					child_bom_qty = child_info["bom_qty"]
					child_bom_quantity = child_info["bom_quantity"] or 1.0
					normalized_qty = child_bom_qty / child_bom_quantity if child_bom_quantity else 0
					child_requirement = math.ceil(qty_per_row * normalized_qty)

					row = base_row.copy()
					row["child_item_code"] = child_info["item_code"]
					row["child_sku_type"] = child_info["child_sku_type"]
					row["child_requirement"] = child_requirement
					row["child_stock"] = child_info["child_stock"]
					row["child_wip_open_po"] = child_info["child_wip_open_po"]
					row["child_bom_qty"] = child_bom_qty
					row["child_bom_quantity"] = child_bom_quantity
					row["child_stock_soft_allocation_qty"] = None

					data.append(row)
			else:
				data.append(base_row)

			accumulated_batch_qty += qty_per_row

	# Sort by machine (grouped), then by priority_sequence (user-defined order from Priority Colour Sequence Master)
	# Rows with no machine go last; rows with no sequence go last within their machine group
	data.sort(
		key=lambda r: (
			r.get("machine") or "\xff",
			r.get("priority_sequence") if r.get("priority_sequence") is not None else 999999,
		)
	)

	# FIFO child stock allocation: deplete stock row by row in sorted order.
	# Each row sees the remaining child stock after all previous rows have consumed their share.
	remaining_child_stock = {k: flt(v) for k, v in child_stock_map.items()}
	remaining_child_wip_open_po = {k: flt(v) for k, v in child_wip_open_po_map.items()}

	for row in data:
		child_item_code = row.get("child_item_code")
		if not child_item_code:
			continue

		child_requirement = flt(row.get("child_requirement", 0))
		available_child_stock = flt(remaining_child_stock.get(child_item_code, 0))
		available_child_wip_open_po = flt(remaining_child_wip_open_po.get(child_item_code, 0))

		stock_allocated = min(child_requirement, available_child_stock)
		stock_shortage = child_requirement - stock_allocated
		wip_open_po_allocated = min(stock_shortage, available_child_wip_open_po)
		total_allocated = stock_allocated + wip_open_po_allocated

		# Deplete for subsequent rows
		remaining_child_stock[child_item_code] = available_child_stock - stock_allocated
		remaining_child_wip_open_po[child_item_code] = available_child_wip_open_po - wip_open_po_allocated

		child_bom_qty = flt(row.get("child_bom_qty", 0))
		child_bom_quantity = flt(row.get("child_bom_quantity", 1.0)) or 1.0
		parent_per_child = (child_bom_quantity / child_bom_qty) if child_bom_qty else 0

		net_order_recommendation = math.ceil(flt(row.get("or_with_moq_batch_size", 0)))
		per_hour = flt(row.get("per_hour_production") or 0)

		prod_qty_child_stock = math.ceil(stock_allocated * parent_per_child)
		prod_qty_child_stock = min(prod_qty_child_stock, net_order_recommendation)

		prod_qty_child_stock_wip = math.ceil(total_allocated * parent_per_child)
		prod_qty_child_stock_wip = min(prod_qty_child_stock_wip, net_order_recommendation)

		row["child_stock"] = math.ceil(flt(child_stock_map.get(child_item_code, 0)))
		row["child_stock_soft_allocation_qty"] = math.ceil(stock_allocated)
		row["child_stock_shortage"] = math.ceil(stock_shortage)
		row["production_qty_based_on_child_stock"] = prod_qty_child_stock
		row["process_time_based_on_child_stock"] = round(prod_qty_child_stock / per_hour, 2) if per_hour else None
		row["production_qty_based_on_child_stock_wip_open_po"] = prod_qty_child_stock_wip

	return data


@frappe.whitelist()
def get_bright_plan_data() -> list[dict]:
	require_permission("Item", "report")

	columns = get_columns()
	data = get_data()

	# Build item_code -> [machine_group_names] map from all rows in Bright Machine Master Table
	rows = frappe.db.sql(
		"""
		SELECT bmm.item_code, bmmt.machine_group_name
		FROM `tabBright Machine Master` bmm
		INNER JOIN `tabBright Machine Master Table` bmmt ON bmmt.parent = bmm.name
		ORDER BY bmm.item_code, bmmt.idx
		""",
		as_dict=True,
	)
	machine_groups = {}
	for r in rows:
		machine_groups.setdefault(r.item_code, []).append(r.machine_group_name)

	# Build Bright Machine -> [Workstation] map from Workstation.custom_machine_group.
	# The Machine dropdown holds a Bright Machine (machine group); the actual Work Order
	# operation needs a real Workstation, which the planner picks from this list.
	ws_rows = frappe.db.sql(
		"""
		SELECT name, custom_machine_group
		FROM `tabWorkstation`
		WHERE custom_machine_group IS NOT NULL AND custom_machine_group != ''
		ORDER BY name
		""",
		as_dict=True,
	)
	workstations_by_machine = {}
	for r in ws_rows:
		workstations_by_machine.setdefault(r.custom_machine_group, []).append(r.name)

	# Build child options for all parent items
	parent_items = list(set(r.get("item_code") for r in data if r.get("item_code")))
	child_options = _build_child_options(parent_items)

	return {
		"columns": columns,
		"data": data,
		"machine_groups": machine_groups,
		"workstations_by_machine": workstations_by_machine,
		"child_options": child_options,
	}


def _build_child_options(parent_items) -> list:
	"""Return {parent_item_code: [{child_item_code, child_bom_qty, child_bom_quantity,
	child_stock, child_wip_open_po, child_sku_type}, ...]} for all active BOMs."""
	if not parent_items:
		return {}

	bom_data = frappe.db.sql(
		"""
		SELECT
			b.item AS parent_item,
			b.quantity AS bom_quantity,
			bi.item_code AS child_item_code,
			bi.qty AS child_bom_qty,
			i.custom_buffer_flag,
			i.custom_item_type
		FROM `tabBOM` b
		INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
		INNER JOIN `tabItem` i ON i.name = bi.item_code
		WHERE b.item IN %(items)s
		  AND b.is_active = 1
		  AND b.docstatus = 1
		ORDER BY b.item, bi.idx
		""",
		{"items": parent_items},
		as_dict=True,
	)

	child_items = list(set(r.child_item_code for r in bom_data))
	if child_items:
		stock_map = get_planning_stock_map(child_items)
		wip_map = get_wip_map()
		open_po_map = get_open_po_map()
	else:
		stock_map = {}
		wip_map = {}
		open_po_map = {}

	child_options = {}
	seen = set()
	for r in bom_data:
		key = (r.parent_item, r.child_item_code)
		if key in seen:
			continue
		seen.add(key)

		child_sku_type = calculate_sku_type(
			r.custom_buffer_flag or "Non-Buffer",
			r.custom_item_type,
		)
		child_stock = math.ceil(flt(stock_map.get(r.child_item_code, 0)))
		child_wip = 0 if child_sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(r.child_item_code, 0))
		child_open_po = flt(open_po_map.get(r.child_item_code, 0))
		child_wip_open_po = math.ceil(child_wip + child_open_po)

		child_options.setdefault(r.parent_item, []).append(
			{
				"child_item_code": r.child_item_code,
				"child_bom_qty": flt(r.child_bom_qty),
				"child_bom_quantity": flt(r.bom_quantity) or 1.0,
				"child_stock": child_stock,
				"child_wip_open_po": child_wip_open_po,
				"child_sku_type": child_sku_type,
			}
		)

	return child_options


# Export column layout — mirrors the on-screen table in bright_plan_.js
# (index / select checkbox columns dropped; the editable Machine / Workstation /
# Planned Start Date / Shift Type columns come first, then the COLS list).
_EXPORT_COLUMNS = [
	("machine", "Machine"),
	("workstation", "Workstation"),
	("planned_start_date", "Planned Start Date"),
	("shift_type", "Shift Type"),
	("item_code", "Item Code"),
	("sku_type", "SKU Type"),
	("open_so", "Open SO"),
	("last_3month_sale", "Last 3 Month Sale"),
	("on_hand_stock", "On Hand Stock"),
	("on_hand_colour_priority", "Order Recommendation Colour"),
	("or_with_moq_batch_size", "MR Qty"),
	("material_request", "Material Request"),
	("material_request_date", "Material Request Date"),
	("priority_colour", "Priority"),
	("priority_sequence", "Priority Sequence"),
	("op_cp", "OP/CP"),
	("moq", "MOQ"),
	("batch_size", "Order Multiple Qty"),
	("child_item_code", "Child Item Code"),
	("child_requirement", "Child Requirement"),
	("child_stock", "Child Stock"),
	("child_stock_soft_allocation_qty", "Child Stock Soft Allocation"),
	("child_stock_shortage", "Child Stock Shortage"),
	("child_wip_open_po", "Child WIP/Open PO"),
	("child_sku_type", "Child SKU Type"),
	("production_qty_based_on_child_stock", "Prod Qty based on Child Stock"),
	("process_time_based_on_child_stock", "Process Time based on Child Stock"),
	("production_qty_based_on_child_stock_wip_open_po", "Prod Qty based on Child Stock+WIP/Open PO"),
	("per_hour_production", "Per Hour Production"),
	("process_time", "Process Time"),
]
_EXPORT_DATE_FIELDS = {"planned_start_date", "material_request_date"}


@frappe.whitelist()
def export_bright_plan_xlsx(rows=None, summary=None) -> None:
	"""Download the current Bright Plan as a single .xlsx with two sheets:
	"Bright Plan" (the main table, including on-screen edits) and "Tomorrow's Plan"
	(the machine-wise process-time summary panel)."""
	import json
	from io import BytesIO

	import xlsxwriter
	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Item", "report")

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	rows = rows or []

	if isinstance(summary, str):
		summary = json.loads(summary or "[]")
	summary = summary or []

	def _fmt(fieldname, value):
		if value is None:
			return ""
		if fieldname in _EXPORT_DATE_FIELDS:
			parts = str(value).split(" ")[0].split("-")
			if len(parts) == 3:
				return f"{parts[2]}-{parts[1]}-{parts[0]}"
		return value

	plan_data = [[label for _fieldname, label in _EXPORT_COLUMNS]]
	for row in rows:
		plan_data.append([_fmt(fieldname, row.get(fieldname)) for fieldname, _label in _EXPORT_COLUMNS])

	summary_data = [["Machine Name", "No of Machines", "Process Time (Hrs)"]]
	for srow in summary:
		summary_data.append(
			[
				srow.get("machine", ""),
				srow.get("no_of_machines", ""),
				round(flt(srow.get("process_time")), 1),
			]
		)

	xlsx_file = BytesIO()
	wb = xlsxwriter.Workbook(xlsx_file, {"constant_memory": True})
	make_xlsx(plan_data, "Bright Plan", wb=wb)
	make_xlsx(summary_data, "Tomorrow's Plan", wb=wb)
	wb.close()
	xlsx_file.seek(0)

	frappe.response["filename"] = "Bright Plan.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def execute_work_orders(rows) -> None:

	require_all_permissions(
		[("Work Order", "create"), ("Work Order", "write"), ("Work Order", "submit")],
		_("Not permitted to create Work Orders from Bright Plan."),
	)
	import json

	if isinstance(rows, str):
		rows = json.loads(rows)

	created = []
	errors = []

	for row in rows:
		item_code = row.get("item_code")
		qty = flt(row.get("production_qty_based_on_child_stock"))

		if not item_code or qty <= 0:
			continue

		# The Machine dropdown value is a Bright Machine (machine group), NOT a
		# Workstation — it must never be written to operation.workstation. Use the
		# Workstation the planner picked in the dedicated dropdown instead.
		workstation = (row.get("workstation") or "").strip()
		if workstation and not frappe.db.exists("Workstation", workstation):
			errors.append(
				f"<b>{item_code}</b>: Workstation {frappe.bold(workstation)} does not exist"
			)
			continue

		child_item_code = row.get("child_item_code")
		bom_no = None

		# Prefer the BOM that contains the user-selected child item
		if child_item_code:
			result = frappe.db.sql(
				"""
				SELECT b.name
				FROM `tabBOM` b
				INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
				WHERE b.item = %s
				  AND b.is_active = 1
				  AND b.docstatus = 1
				  AND bi.item_code = %s
				LIMIT 1
				""",
				(item_code, child_item_code),
			)
			bom_no = result[0][0] if result else None

		# Fall back to default BOM
		if not bom_no:
			bom_no = frappe.db.get_value(
				"BOM",
				{"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
				"name",
			)

		if not bom_no:
			errors.append(f"No active BOM found for <b>{item_code}</b>")
			continue

		# Wrap each Work Order in a savepoint: if save/submit fails, roll the
		# insert back too so a failed row never leaves an orphan draft behind.
		savepoint = "bp_wo_" + frappe.generate_hash(length=8)
		frappe.db.savepoint(savepoint)
		try:
			wo = frappe.new_doc("Work Order")
			wo.production_item = item_code
			wo.bom_no = bom_no
			wo.qty = qty
			wo.company = "Prakash Steel Products Pvt Ltd"
			wo.wip_warehouse = "Work In Progress - PSPL"
			wo.fg_warehouse = "Bright Bar Unit - PSPL"
			wo.source_warehouse = "Bright Bar Unit - PSPL"
			wo.update_consumed_material_cost_in_project = 1
			wo.custom_bright_production = 1
			wo.custom_shift_type = row.get("shift_type") or ""
			wo.custom_machine_name = workstation or row.get("machine") or ""

			planned_start_date = row.get("planned_start_date")
			if planned_start_date:
				wo.planned_start_date = planned_start_date

			wo.insert()
			# ERPNext auto-populates required_items on insert but not operations —
			# that only happens via this whitelisted call (normally triggered by the
			# Work Order form's JS), so fetch it explicitly here.
			wo.set_work_order_operations()
			# After insert, ERPNext populates required_items from BOM with each item's
			# own default warehouse. Override all of them to the correct source warehouse.
			for item in wo.required_items:
				item.source_warehouse = "Bright Bar Unit - PSPL"
			# Assign the chosen Workstation to every BOM operation.
			if workstation:
				for operation in wo.operations:
					operation.workstation = workstation
			wo.save()
			wo.submit()
			created.append(wo.name)

		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			errors.append(
				f"<b>{item_code}</b>: {frappe.get_traceback() if frappe.conf.developer_mode else str(e)}"
			)

	return {"created": created, "errors": errors}
