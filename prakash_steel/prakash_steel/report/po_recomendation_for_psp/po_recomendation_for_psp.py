import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.lead_time import get_default_bom

# ---------------------------------------------------------------------------
# Re-export from sub-modules so existing callers keep working without changes
# ---------------------------------------------------------------------------
from .calculations import (
	_PRIORITY_TO_COLOUR,
	_STATUS_PRIORITY,
	_compute_order_status,
	_non_buffer_priority,
	build_calculation_breakdown_po_report,
	calculate_final_order_recommendation,
	calculate_initial_order_recommendation,
	calculate_net_order_recommendation,
	calculate_sku_type,
	generate_detailed_log_po_report,
	get_qualified_demand_for_item,
)
from .data_fetchers import (
	calculate_spike_map,
	get_mrq_map,
	get_open_po_map,
	get_open_so_map_for_priority,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_stock_map,
	get_wip_map,
)
from .bom_traversal import (
	traverse_bom_for_parent_demand,
	traverse_bom_for_parent_demand_simple,
	traverse_bom_for_po,
)




def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	columns = get_columns(filters)
	data = get_data(filters)
	return columns, data


def save_daily_on_hand_colour() -> None:
	from frappe.utils import nowdate

	posting_date = nowdate()

	all_data = []
	seen_item_codes = {}

	try:
		filters_purchase = {"purchase": 1, "buffer_flag": 1}
		_, data_purchase = execute(filters_purchase)
		if data_purchase:
			for row in data_purchase:
				item_code = row.get("item_code")
				if item_code and item_code not in seen_item_codes:
					seen_item_codes[item_code] = row
	except Exception as e:
		frappe.log_error(title="PO Recommendation daily colour (purchase)", message=frappe.get_traceback())

	try:
		filters_sell = {"sell": 1, "buffer_flag": 1}
		_, data_sell = execute(filters_sell)
		if data_sell:
			for row in data_sell:
				item_code = row.get("item_code")
				if item_code and item_code not in seen_item_codes:
					seen_item_codes[item_code] = row
	except Exception as e:
		frappe.log_error(title="PO Recommendation daily colour (sell)", message=frappe.get_traceback())

	all_data = list(seen_item_codes.values())

	if not all_data:
		return

	try:
		doc = frappe.new_doc("Item wise Daily On Hand Colour")
		doc.posting_date = posting_date

		saved_rows = 0

		for row in all_data:
			item_code = row.get("item_code")
			sku_type = row.get("sku_type")
			on_hand_colour = row.get("on_hand_colour")

			if not item_code or not on_hand_colour:
				continue

			child = doc.append("item_wise_on_hand_colour", {})
			child.item_code = item_code
			child.sku_type = sku_type
			child.on_hand_colour = on_hand_colour
			saved_rows += 1

		if saved_rows == 0:
			return

		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(title="PO Recommendation daily colour (save)", message=frappe.get_traceback())


def get_columns(filters: dict | None = None) -> list[dict]:
	if not filters:
		filters = {}

	sell = filters.get("sell", 0)
	if isinstance(sell, str):
		sell = 1 if sell in ("1", "true", "True") else 0
	sell = int(sell) if sell else 0

	buffer_flag = filters.get("buffer_flag", 0)
	if isinstance(buffer_flag, str):
		buffer_flag = 1 if buffer_flag in ("1", "true", "True") else 0
	buffer_flag = int(buffer_flag) if buffer_flag else 0

	columns = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
	]

	if not buffer_flag:
		columns.append(
			{
				"label": _("Priority"),
				"fieldname": "priority",
				"fieldtype": "Data",
				"width": 120,
			}
		)

	if not buffer_flag:
		columns.append(
			{
				"label": _("Requirement"),
				"fieldname": "requirement",
				"fieldtype": "Int",
				"width": 120,
			}
		)

	if buffer_flag:
		columns.extend(
			[
				{
					"label": _("TOG"),
					"fieldname": "tog",
					"fieldtype": "Int",
					"width": 100,
				},
				{
					"label": _("TOY"),
					"fieldname": "toy",
					"fieldtype": "Int",
					"width": 100,
				},
				{
					"label": _("TOR"),
					"fieldname": "tor",
					"fieldtype": "Int",
					"width": 100,
				},
			]
		)

	if buffer_flag:
		columns.extend(
			[
				{
					"label": _("Open SO"),
					"fieldname": "open_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Total SO"),
					"fieldname": "total_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("On Hand Stock"),
					"fieldname": "on_hand_stock",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("WIP"),
					"fieldname": "wip",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open PO"),
					"fieldname": "open_po",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open Subcon PO"),
					"fieldname": "open_subcon_po",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Additional Demand"),
					"fieldname": "additional_demand",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Qualified Demand"),
					"fieldname": "qualify_demand",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("On Hand Status"),
					"fieldname": "on_hand_status",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("On Hand Colour"),
					"fieldname": "on_hand_colour",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Net Flow"),
					"fieldname": "net_flow",
					"fieldtype": "Int",
					"width": 120,
				},
			]
		)
	else:
		columns.extend(
			[
				{
					"label": _("Total SO"),
					"fieldname": "total_so",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open SO"),
					"fieldname": "open_so_qualified",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("On Hand Stock"),
					"fieldname": "on_hand_stock",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("WIP"),
					"fieldname": "wip",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open PO"),
					"fieldname": "open_po",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Open Subcon PO"),
					"fieldname": "open_subcon_po",
					"fieldtype": "Int",
					"width": 130,
				},
				{
					"label": _("Additional Demand"),
					"fieldname": "additional_demand",
					"fieldtype": "Int",
					"width": 130,
					"hidden": 1,
				},
				{
					"label": _("Qualified Demand"),
					"fieldname": "qualify_demand",
					"fieldtype": "Int",
					"width": 130,
					"hidden": 1,
				},
			]
		)

	columns.extend(
		[
			{
				"label": _("Order Recommendation"),
				"fieldname": "order_recommendation",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("MRQ"),
				"fieldname": "mrq",
				"fieldtype": "Int",
				"width": 120,
			},
			{
				"label": _("Balance Order Recommendation"),
				"fieldname": "net_po_recommendation",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("Net Order Recommendation"),
				"fieldname": "or_with_moq_batch_size",
				"fieldtype": "Int",
				"width": 180,
			},
			{
				"label": _("MOQ"),
				"fieldname": "moq",
				"fieldtype": "Int",
				"width": 120,
			},
			{
				"label": _("Order Multiple Qty"),
				"fieldname": "batch_size",
				"fieldtype": "Int",
				"width": 120,
			},
		]
	)

	if sell:
		columns.extend(
			[
				{
					"label": _("Production qty based on child stock"),
					"fieldname": "production_qty_based_on_child_stock",
					"fieldtype": "Int",
					"width": 220,
				},
				{
					"label": _("Child Stock Full-Kit Status"),
					"fieldname": "child_full_kit_status",
					"fieldtype": "Data",
					"width": 160,
				},
				{
					"label": _("Production qty based on child stock+WIP/Open PO"),
					"fieldname": "production_qty_based_on_child_stock_wip_open_po",
					"fieldtype": "Int",
					"width": 280,
				},
				{
					"label": _("Child Stock + WIP/Open PO Full-Kit Status"),
					"fieldname": "child_wip_open_po_full_kit_status",
					"fieldtype": "Data",
					"width": 160,
				},
				{
					"label": _("Child Item Code"),
					"fieldname": "child_item_code",
					"fieldtype": "Link",
					"options": "Item",
					"width": 150,
				},
				{
					"label": _("Child Item Type"),
					"fieldname": "child_item_type",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Child SKU Type"),
					"fieldname": "child_sku_type",
					"fieldtype": "Data",
					"width": 130,
				},
				{
					"label": _("Child Requirement"),
					"fieldname": "child_requirement",
					"fieldtype": "Int",
					"width": 150,
				},
				{
					"label": _("Child stock"),
					"fieldname": "child_stock",
					"fieldtype": "Int",
					"width": 120,
				},
				{
					"label": _("Child Stock soft Allocation qty"),
					"fieldname": "child_stock_soft_allocation_qty",
					"fieldtype": "Int",
					"width": 200,
				},
				{
					"label": _("Child Stock shortage"),
					"fieldname": "child_stock_shortage",
					"fieldtype": "Int",
					"width": 160,
				},
				{
					"label": _("Child WIP/Open PO"),
					"fieldname": "child_wip_open_po",
					"fieldtype": "Int",
					"width": 150,
				},
				{
					"label": _("Child WIP/Open PO soft allocation qty"),
					"fieldname": "child_wip_open_po_soft_allocation_qty",
					"fieldtype": "Int",
					"width": 250,
				},
				{
					"label": _("Child WIP/Open PO Shortage"),
					"fieldname": "child_wip_open_po_shortage",
					"fieldtype": "Int",
					"width": 200,
				},
			]
		)

	return columns


def get_data(filters: dict | None = None) -> list[dict]:
	if not filters:
		filters = {}

	purchase = filters.get("purchase", 0)
	sell = filters.get("sell", 0)
	buffer_flag = filters.get("buffer_flag", 0)

	if isinstance(purchase, str):
		purchase = 1 if purchase in ("1", "true", "True") else 0
	if isinstance(sell, str):
		sell = 1 if sell in ("1", "true", "True") else 0
	if isinstance(buffer_flag, str):
		buffer_flag = 1 if buffer_flag in ("1", "true", "True") else 0

	purchase = int(purchase) if purchase else 0
	sell = int(sell) if sell else 0
	buffer_flag = int(buffer_flag) if buffer_flag else 0

	if not (purchase or sell):
		return []

	allowed_sku_types = []
	if purchase:
		if buffer_flag:
			allowed_sku_types = ["PTA", "BOTA", "TRMTA"]
		else:
			allowed_sku_types = ["PTO", "BOTO", "TRMTO"]
	elif sell:
		if buffer_flag:
			allowed_sku_types = ["BBMTA", "RBMTA"]
		else:
			allowed_sku_types = ["BBMTO", "RBMTO"]

	so_qty_map = get_sales_order_qty_map(filters)

	till_today_map, spike_map = get_qualified_demand_map()

	if buffer_flag:
		items_query = """
			SELECT name as item_code
			FROM `tabItem`
			WHERE custom_buffer_flag = 'Buffer'
		"""
	else:
		items_query = """
			SELECT name as item_code
			FROM `tabItem`
			WHERE custom_buffer_flag != 'Buffer' OR custom_buffer_flag IS NULL
		"""

	items_result = frappe.db.sql(items_query, as_dict=1)
	item_codes = set(item.item_code for item in items_result)

	so_qty_map = {k: v for k, v in so_qty_map.items() if k in item_codes}

	wip_map = get_wip_map()

	mrq_map = get_mrq_map()

	open_po_map = get_open_po_map()

	items_with_po = set(open_po_map.keys())
	items_with_po_selected = {item for item in items_with_po if item in item_codes}

	all_items_to_process = item_codes | items_with_po_selected

	if not all_items_to_process:
		return []

	initial_stock_map = get_stock_map(all_items_to_process)
	so_map_for_priority = get_open_so_map_for_priority(all_items_to_process)

	remaining_stock = dict(initial_stock_map)

	po_recommendations = {}
	item_groups_cache = {}

	parent_demand_map = {}

	items_with_so = set(so_qty_map.keys())
	for item_code in sorted(items_with_so):
		so_qty = flt(so_qty_map.get(item_code, 0))
		available_stock = flt(remaining_stock.get(item_code, 0))

		required_qty = max(0, so_qty - available_stock)

		allocated = min(so_qty, available_stock)
		remaining_stock[item_code] = available_stock - allocated

		if item_code in po_recommendations:
			po_recommendations[item_code] += required_qty
		else:
			po_recommendations[item_code] = required_qty

		if required_qty > 0:
			traverse_bom_for_po(
				item_code,
				required_qty,
				po_recommendations,
				remaining_stock,
				set(),
				item_groups_cache,
				level=0,
			)

	all_item_codes = all_items_to_process

	if all_item_codes:
		all_items_tuple = tuple(all_item_codes)

		items_details_all = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.custom_buffer_flag as buffer_flag,
				i.custom_item_type as item_type,
				i.safety_stock as tog,
				i.min_order_qty as moq,
				i.custom_batch_size as batch_size
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
			""",
			(all_items_tuple,),
			as_dict=1,
		)

		item_buffer_map_all = {}
		item_sku_type_map_all = {}
		item_tog_map_all = {}
		item_type_map_all = {}
		moq_map_all = {}
		batch_size_map_all = {}
		for item in items_details_all:
			item_buffer_map_all[item.item_code] = item.buffer_flag or "Non-Buffer"
			item_sku_type_map_all[item.item_code] = calculate_sku_type(
				item.buffer_flag or "Non-Buffer", item.item_type
			)
			item_tog_map_all[item.item_code] = flt(item.tog or 0)
			item_type_map_all[item.item_code] = item.item_type
			moq_map_all[item.item_code] = flt(item.moq or 0)
			batch_size_map_all[item.item_code] = flt(item.batch_size or 0)
	else:
		item_buffer_map_all = {}
		item_sku_type_map_all = {}
		item_tog_map_all = {}
		item_type_map_all = {}
		moq_map_all = {}
		batch_size_map_all = {}

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {}
	for sm in spike_master_records:
		spike_master_map[sm.item_type] = {
			"demand_horizon": flt(sm.demand_horizon),
			"spike_threshold": flt(sm.spike_threshold),
		}

	calculated_spike_map = calculate_spike_map(
		all_item_codes, item_buffer_map_all, item_type_map_all, item_tog_map_all, spike_master_map
	)
	spike_map.update(calculated_spike_map)

	all_item_codes_for_demand = set(all_item_codes) | set(till_today_map.keys()) | set(spike_map.keys())
	qualified_demand_map = {}
	for item_code in all_item_codes_for_demand:
		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map_all,
			item_tog_map_all,
			item_type_map_all,
			spike_master_map,
		)
		qualified_demand_map[item_code] = qualified_demand

	initial_order_recommendations = {}
	for item_code in all_item_codes:
		order_rec = calculate_initial_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,
			qualified_demand_map,
			open_po_map,
		)
		initial_order_recommendations[item_code] = order_rec

	initial_net_order_recommendations = {}

	for item_code in all_item_codes:
		base_order_rec = initial_order_recommendations.get(item_code, 0)
		moq = moq_map_all.get(item_code, 0)
		batch_size = batch_size_map_all.get(item_code, 0)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
		initial_net_order_recommendations[item_code] = net_order_rec

	items_to_process = [
		(item_code, net_order_rec)
		for item_code, net_order_rec in initial_net_order_recommendations.items()
		if net_order_rec > 0
	]
	items_to_process.sort(key=lambda x: x[0])

	for item_code, net_order_rec in items_to_process:
		traverse_bom_for_parent_demand_simple(
			item_code,
			net_order_rec,
			parent_demand_map,
			set(),
			item_groups_cache,
			item_buffer_map_all,
			level=0,
		)

	final_order_recommendations = {}
	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,           # all-time open SO for non-buffer; qualified_demand used for buffer
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map,
		)
		final_order_recommendations[item_code] = order_rec

	net_order_recommendations = {}
	for item_code in all_item_codes:
		base_order_rec = final_order_recommendations.get(item_code, 0)
		moq = moq_map_all.get(item_code, 0)
		batch_size = batch_size_map_all.get(item_code, 0)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)
		net_order_recommendations[item_code] = net_order_rec

	# ── Include buffer items so their BOM children get parent demand ───────────
	# Buffer items are not in this report's item set but their BOM children
	# (RBMTO, PTO, etc.) need parent demand flowing from buffer parents.
	_buf_rows = frappe.db.sql(
		"""
		SELECT name AS item_code, safety_stock AS tog,
		       custom_item_type AS item_type, custom_buffer_flag AS buffer_flag,
		       min_order_qty AS moq, custom_batch_size AS batch_size
		FROM `tabItem`
		WHERE custom_buffer_flag = 'Buffer'
		""",
		as_dict=True,
	)
	if _buf_rows:
		_buf_codes = [r.item_code for r in _buf_rows]
		_buf_stock_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(tuple(_buf_codes) if len(_buf_codes) > 1 else (_buf_codes[0],),),
			as_dict=True,
		)
		_buf_stock_map = {r.item_code: flt(r.stock) for r in _buf_stock_rows}

		for _br in _buf_rows:
			_bic = _br.item_code
			_bsku = calculate_sku_type(_br.buffer_flag or "Buffer", _br.item_type) or ""
			_btog = flt(_br.tog or 0)
			_bstock = flt(_buf_stock_map.get(_bic, 0))
			_bwip = 0 if _bsku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_bic, 0))
			_bpo = flt(open_po_map.get(_bic, 0))
			_bqd = flt(qualified_demand_map.get(_bic, 0))
			_bmrq = flt(mrq_map.get(_bic, 0))
			_bmoq = flt(_br.moq or 0)
			_bbatch = flt(_br.batch_size or 0)

			if _bsku in ["BOTA", "PTA"]:
				_bbase = max(0, _btog + _bqd - _bstock - _bwip - _bpo - _bmrq)
			else:
				_bbase = max(0, _btog + _bqd - _bstock - _bwip - _bmrq)

			_bnet = calculate_net_order_recommendation(_bbase, _bmoq, _bbatch)

			if _bnet > 0:
				# Register in maps so traverse_bom_for_parent_demand can use them
				item_buffer_map_all[_bic] = _br.buffer_flag or "Buffer"
				item_sku_type_map_all[_bic] = _bsku
				item_tog_map_all[_bic] = _btog
				moq_map_all[_bic] = _bmoq
				batch_size_map_all[_bic] = _bbatch
				net_order_recommendations[_bic] = _bnet

	# ── Include non-buffer items so their BOM children (buffer RM) get parent demand ──
	# When report runs with buffer_flag=1, non-buffer items are excluded from all_item_codes.
	# Their open SOs must still flow as parent demand to buffer child items via BOM traversal.
	if buffer_flag:
		_nonbuf_rows = frappe.db.sql(
			"""
			SELECT name AS item_code, custom_item_type AS item_type,
			       min_order_qty AS moq, custom_batch_size AS batch_size
			FROM `tabItem`
			WHERE (custom_buffer_flag != 'Buffer' OR custom_buffer_flag IS NULL)
			""",
			as_dict=True,
		)
		if _nonbuf_rows:
			_nonbuf_codes = [r.item_code for r in _nonbuf_rows]
			_nonbuf_tuple = tuple(_nonbuf_codes) if len(_nonbuf_codes) > 1 else (_nonbuf_codes[0],)

			_nonbuf_stock_rows = frappe.db.sql(
				"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
				(_nonbuf_tuple,),
				as_dict=True,
			)
			_nonbuf_stock_map = {r.item_code: flt(r.stock) for r in _nonbuf_stock_rows}

			_nonbuf_so_rows = frappe.db.sql(
				"""
				SELECT soi.item_code,
				       SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) AS so_qty
				FROM `tabSales Order` so
				INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
				WHERE so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
				  AND so.docstatus = 1
				  AND IFNULL(soi.custom_closed, 0) = 0
				  AND soi.item_code IN %s
				GROUP BY soi.item_code
				""",
				(_nonbuf_tuple,),
				as_dict=True,
			)
			_nonbuf_so_map = {r.item_code: flt(r.so_qty) for r in _nonbuf_so_rows}

			for _nr in _nonbuf_rows:
				_nic = _nr.item_code
				_nsku = calculate_sku_type("Non-Buffer", _nr.item_type) or ""
				_nstock = flt(_nonbuf_stock_map.get(_nic, 0))
				_nwip = 0 if _nsku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_nic, 0))
				_npo = flt(open_po_map.get(_nic, 0))
				_nso = flt(_nonbuf_so_map.get(_nic, 0))
				_nmoq = flt(_nr.moq or 0)
				_nbatch = flt(_nr.batch_size or 0)

				if _nsku in ["BOTO", "PTO", "TRMTO"]:
					_nbase = max(0, _nso - _nstock - _nwip - _npo)
				else:
					_nbase = max(0, _nso - _nstock - _nwip)

				_nnet = calculate_net_order_recommendation(_nbase, _nmoq, _nbatch)

				if _nnet > 0:
					item_buffer_map_all[_nic] = "Non-Buffer"
					item_sku_type_map_all[_nic] = _nsku
					moq_map_all[_nic] = _nmoq
					batch_size_map_all[_nic] = _nbatch
					net_order_recommendations[_nic] = _nnet

	parent_demand_map_net = {}
	parent_demand_details = {}

	items_with_net_rec = [
		(item_code, net_rec) for item_code, net_rec in net_order_recommendations.items() if net_rec > 0
	]
	items_with_net_rec.sort(key=lambda x: x[0])

	global_visited_items = set()

	for item_code, net_rec in items_with_net_rec:
		if item_code not in global_visited_items:
			traverse_bom_for_parent_demand(
				item_code,
				net_rec,
				parent_demand_map_net,
				parent_demand_details,
				global_visited_items,
				item_groups_cache,
				so_qty_map,  # all-time open SO (used for non-buffer children; buffer children use qualified_demand_map via is_child_buffer branch)
				initial_stock_map,
				wip_map,
				open_po_map,
				mrq_map,
				moq_map_all,
				batch_size_map_all,
				item_buffer_map_all,
				item_sku_type_map_all,
				item_tog_map_all,
				lambda item_code: None,
				level=0,
			)

	final_order_recommendations_updated = {}
	net_order_recommendations_final = {}

	for item_code in all_item_codes:
		order_rec = calculate_final_order_recommendation(
			item_code,
			item_buffer_map_all,
			item_tog_map_all,
			item_sku_type_map_all,
			initial_stock_map,
			wip_map,
			so_qty_map,           # all-time open SO for non-buffer; qualified_demand used for buffer
			qualified_demand_map,
			open_po_map,
			mrq_map,
			parent_demand_map_net,
		)
		final_order_recommendations_updated[item_code] = order_rec

		moq = moq_map_all.get(item_code, 0)
		batch_size = batch_size_map_all.get(item_code, 0)
		net_order_rec = calculate_net_order_recommendation(order_rec, moq, batch_size)
		net_order_recommendations_final[item_code] = net_order_rec

	final_order_recommendations = final_order_recommendations_updated
	net_order_recommendations = net_order_recommendations_final
	parent_demand_map = parent_demand_map_net

	all_items_to_show = all_items_to_process

	if not all_items_to_show:
		return []

	item_codes_tuple = tuple(all_items_to_show)

	if buffer_flag:
		items_data = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.item_name,
				i.safety_stock as tog,
				i.custom_top_of_yellow as toy,
				i.custom_top_of_red as tor,
				i.custom_item_type as item_type,
				i.custom_batch_size as batch_size,
				i.min_order_qty as moq,
				i.custom_buffer_flag as buffer_flag
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
				AND i.custom_buffer_flag = 'Buffer'
			""",
			(item_codes_tuple,),
			as_dict=1,
		)
	else:
		items_data = frappe.db.sql(
			"""
			SELECT
				i.name as item_code,
				i.item_name,
				i.safety_stock as tog,
				i.custom_top_of_yellow as toy,
				i.custom_top_of_red as tor,
				i.custom_item_type as item_type,
				i.custom_batch_size as batch_size,
				i.min_order_qty as moq,
				i.custom_buffer_flag as buffer_flag
			FROM
				`tabItem` i
			WHERE
				i.name IN %s
				AND (i.custom_buffer_flag != 'Buffer' OR i.custom_buffer_flag IS NULL)
			""",
			(item_codes_tuple,),
			as_dict=1,
		)

	# Create a map for quick lookup
	items_map = {item.item_code: item for item in items_data}

	child_stock_map = {}
	child_wip_open_po_map = {}

	# ── Bulk pre-fetch BOM items, child item details, child stock ─────────────
	# Replaces N x frappe.get_doc("BOM") + N x M x frappe.get_doc("Item") + N x M x Bin queries
	_bom_rows = frappe.db.sql(
		"""
		SELECT b.item AS item_code, b.name AS bom_name, b.quantity AS bom_quantity
		FROM `tabBOM` b
		WHERE b.item IN %s AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	_default_bom_map = {r.item_code: (r.bom_name, flt(r.bom_quantity) or 1.0) for r in _bom_rows}

	_bom_items_map = defaultdict(list)
	if _default_bom_map:
		_bom_names = list({bom_name for bom_name, _ in _default_bom_map.values()})
		_bom_names_tuple = tuple(_bom_names) if len(_bom_names) > 1 else (_bom_names[0],)
		_bom_item_rows = frappe.db.sql(
			"""
			SELECT bi.parent AS bom_name, bi.item_code, bi.qty
			FROM `tabBOM Item` bi
			WHERE bi.parent IN %s AND bi.parenttype = 'BOM'
			""",
			(_bom_names_tuple,),
			as_dict=True,
		)
		_bom_name_to_item = {v[0]: k for k, v in _default_bom_map.items()}
		for _bir in _bom_item_rows:
			_parent = _bom_name_to_item.get(_bir.bom_name)
			if _parent:
				_, _bom_qty = _default_bom_map[_parent]
				_bom_items_map[_parent].append({
					"item_code": _bir.item_code,
					"bom_qty": flt(_bir.qty),
					"bom_quantity": _bom_qty,
				})

	_all_child_codes = {c["item_code"] for children in _bom_items_map.values() for c in children}
	_child_detail_map = {}
	if _all_child_codes:
		_child_tuple = tuple(_all_child_codes)
		_child_item_rows = frappe.db.sql(
			"""
			SELECT name AS item_code, custom_item_type AS item_type, custom_buffer_flag AS buffer_flag
			FROM `tabItem`
			WHERE name IN %s
			""",
			(_child_tuple,),
			as_dict=True,
		)
		for _ci in _child_item_rows:
			_child_detail_map[_ci.item_code] = {
				"item_type": _ci.item_type,
				"buffer_flag": _ci.buffer_flag or "Non-Buffer",
				"sku_type": calculate_sku_type(_ci.buffer_flag or "Non-Buffer", _ci.item_type),
			}
		_child_stock_rows = frappe.db.sql(
			"""
			SELECT item_code, SUM(actual_qty) AS stock
			FROM `tabBin`
			WHERE item_code IN %s
			GROUP BY item_code
			""",
			(_child_tuple,),
			as_dict=True,
		)
		for _csr in _child_stock_rows:
			child_stock_map[_csr.item_code] = math.ceil(flt(_csr.stock))
	# ─────────────────────────────────────────────────────────────────────────

	data = []
	for item_code in sorted(all_items_to_show):
		item_info = items_map.get(item_code, {})

		# Skip if item is not in items_map
		if not item_info:
			continue

		# Calculate SKU Type based on buffer_flag
		item_type = item_info.get("item_type")
		item_buffer_flag = item_info.get("buffer_flag", "")
		sku_type = calculate_sku_type(item_buffer_flag, item_type)

		if sku_type not in allowed_sku_types:
			continue

		# Get stock and buffer levels
		on_hand_stock = flt(initial_stock_map.get(item_code, 0))
		tog = flt(item_info.get("tog", 0))
		toy = flt(item_info.get("toy", 0))
		tor = flt(item_info.get("tor", 0))
		qualify_demand, till_today, spike = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map,
			item_buffer_map_all,
			item_tog_map_all,
			item_type_map_all,
			spike_master_map,
		)
		qualify_demand = flt(qualify_demand)

		additional_demand = flt(till_today) + flt(spike)

		# Check if item is buffer or non-buffer
		is_item_buffer = item_buffer_flag == "Buffer"

		on_hand_status_value = None
		on_hand_status = None
		on_hand_colour = None

		# Get item name
		item_name = item_info.get("item_name", "")

		# Get WIP value (RBMTA and RBMTO do not consider WIP)
		wip = 0 if sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(item_code, 0))

		# Get batch size from item
		batch_size = flt(item_info.get("batch_size", 0))

		# Get MOQ from item
		moq = flt(item_info.get("moq", 0))

		mrq = flt(mrq_map.get(item_code, 0))

		# Get Open PO (Purchase Order quantity - received quantity)
		open_po = flt(open_po_map.get(item_code, 0))

		open_so = flt(so_qty_map.get(item_code, 0))

		parent_demand = flt(parent_demand_map.get(item_code, 0))
		parent_demand_details_list = parent_demand_details.get(item_code, [])

		if is_item_buffer:
			total_demand_for_status = qualify_demand + parent_demand
			denominator = flt(tog) + flt(total_demand_for_status)
			if denominator > 0:
				on_hand_status_value = (flt(on_hand_stock) / denominator) * 100
			else:
				on_hand_status_value = None

			if on_hand_status_value is None:
				on_hand_colour = None
				on_hand_status = None
			else:
				numeric_status = round(on_hand_status_value, 2)

				if numeric_status == 0:
					on_hand_colour = "BLACK"
				elif 0 < numeric_status <= 34:
					on_hand_colour = "RED"
				elif 34 < numeric_status <= 67:
					on_hand_colour = "YELLOW"
				elif 67 < numeric_status <= 100:
					on_hand_colour = "GREEN"
				else:  # > 100
					on_hand_colour = "WHITE"

				on_hand_status = f"{numeric_status:.2f}%"

		net_order_rec = flt(net_order_recommendations.get(item_code, 0))

		or_with_moq_batch_size = math.ceil(flt(net_order_rec))  # Net order recommendation (after MOQ/Batch Size)

		# Get Open Subcon PO (will be populated with functionality later)
		open_subcon_po = 0

		# Calculate Net Flow: on_hand_stock + wip + open_po + open_subcon_po - qualified_demand
		# Use actual qualified_demand (not including parent_demand)
		net_flow = on_hand_stock + wip + open_po + open_subcon_po - qualify_demand

		# Base row with parent item data
		is_item_buffer = item_buffer_flag == "Buffer"

		wip_open_po_combined = wip + open_po + open_subcon_po

		if is_item_buffer:
			# Buffer: TOG + (Qualified Demand + Parent Demand) - Stock - (WIP + Open PO + Open Subcon PO) - MRQ
			total_demand = qualify_demand + parent_demand
			if sku_type in ["BOTA", "PTA"]:
				# For BOTA/PTA: subtract open_po separately (existing logic)
				base_order_rec = tog + total_demand - on_hand_stock - wip - open_po
			else:
				# For others: use combined value
				base_order_rec = tog + total_demand - on_hand_stock - wip_open_po_combined
			final_order_rec = max(0, base_order_rec - mrq)
		else:
			open_so_for_calc = open_so  # Use all-time open SO (so_qty_map) for non-buffer
			requirement = open_so_for_calc + parent_demand
			if sku_type in ["PTO", "BOTO"]:
				# For PTO/BOTO: subtract open_po separately (existing logic)
				base_order_rec = requirement - on_hand_stock - wip - open_po
			else:
				# For others: use combined value
				base_order_rec = requirement - on_hand_stock - wip_open_po_combined
			final_order_rec = max(0, base_order_rec - mrq)

		# Order Recommendation = before MRQ subtraction (capped at 0)
		# Balance Order Recommendation = after MRQ subtraction
		order_recommendation = math.ceil(max(0, flt(base_order_rec)))
		net_po_recommendation = math.ceil(flt(final_order_rec))

		# Calculate net order recommendation for breakdown
		net_order_rec_breakdown = calculate_net_order_recommendation(final_order_rec, moq, batch_size)
		open_so_for_breakdown = open_so
		calculation_breakdown = build_calculation_breakdown_po_report(
			item_code,
			item_buffer_flag,
			is_item_buffer,
			sku_type,
			tog,
			qualify_demand,
			open_so_for_breakdown,  # Use qualified_demand for non-buffer items in breakdown
			on_hand_stock,
			wip,
			open_po,
			mrq,
			moq,
			batch_size,
			parent_demand,
			final_order_rec,
			net_order_rec_breakdown,
			parent_demand_details_list,
			till_today=till_today,
			spike=spike,
		)

		if is_item_buffer:
			total_demand_for_display = qualify_demand + parent_demand
			base_row = {
				"item_code": item_code,
				"item_name": item_name,
				"sku_type": sku_type,
				"requirement": None,
				"tog": math.ceil(flt(tog)),
				"toy": math.ceil(flt(toy)),
				"tor": math.ceil(flt(tor)),
				"open_so": math.ceil(flt(additional_demand)),  # till_today + SOs within demand_horizon
				"total_so": math.ceil(flt(open_so)),  # All open SOs (no date filter)
				"on_hand_stock": math.ceil(flt(on_hand_stock)),
				"wip": math.ceil(flt(wip)),  # WIP value only
				"open_po": math.ceil(flt(open_po)),  # Open PO value only
				"open_subcon_po": math.ceil(flt(open_subcon_po)),  # Open Subcon PO value
				"additional_demand": math.ceil(
					flt(additional_demand)
				),  # till_today + spike (value compared with spike threshold)
				"qualify_demand": math.ceil(
					flt(total_demand_for_display)
				),  # Show total demand (qualified + parent)
			}
		else:
			base_row = {
				"item_code": item_code,
				"item_name": item_name,
				"sku_type": sku_type,
				"requirement": math.ceil(
					flt(parent_demand)
				),  # Parent demand only (Open SO is in separate column)
				"tog": None,
				"toy": None,
				"tor": None,
				"open_so": math.ceil(flt(open_so)),  # All-time Open SO
				"total_so": math.ceil(flt(open_so)),
				"on_hand_stock": math.ceil(flt(on_hand_stock)),
				"wip": math.ceil(flt(wip)),  # WIP value only
				"open_po": math.ceil(flt(open_po)),  # Open PO value only
				"open_subcon_po": math.ceil(flt(open_subcon_po)),  # Open Subcon PO value
				"additional_demand": math.ceil(flt(additional_demand)),
				"qualify_demand": math.ceil(flt(qualify_demand)),  # Qualified Demand
				"open_so_qualified": math.ceil(flt(open_so)),  # Same as total_so (no date filter)
				"priority": _non_buffer_priority(
					item_code,
					on_hand_stock + (open_po if sku_type in ["BOTO", "PTO", "TRMTO"] else wip),
					so_map_for_priority,
				),
			}
		common_fields = {
			"on_hand_status": on_hand_status,
			"on_hand_colour": on_hand_colour,
			"buffer_flag": item_buffer_flag,  # Add buffer_flag for JavaScript formatter
			"order_recommendation": math.ceil(flt(order_recommendation)),
			"batch_size": math.ceil(flt(batch_size)),
			"moq": math.ceil(flt(moq)),
			"or_with_moq_batch_size": math.ceil(flt(or_with_moq_batch_size)),
			"mrq": math.ceil(flt(mrq)),
			"net_po_recommendation": math.ceil(flt(net_po_recommendation)),
			"calculation_breakdown": calculation_breakdown,  # Add breakdown for console logging
			# Initialize child columns as None/0
			"batch_size_multiple": None,
			"production_qty_based_on_child_stock": None,
			"production_qty_based_on_child_stock_wip_open_po": None,
			"child_item_code": None,
			"child_item_type": None,
			"child_sku_type": None,
			"child_requirement": None,
			"child_stock": None,
			"child_stock_soft_allocation_qty": None,
			"child_stock_shortage": None,
			"child_full_kit_status": None,
			"child_wip_open_po": None,
			"child_wip_open_po_soft_allocation_qty": None,
			"child_wip_open_po_shortage": None,
			"child_wip_open_po_full_kit_status": None,
		}

		if is_item_buffer:
			common_fields["net_flow"] = math.ceil(flt(net_flow))
		else:
			common_fields["net_flow"] = None

		base_row.update(common_fields)

		bom = get_default_bom(item_code)
		child_items = []

		if bom:
			try:
				bom_doc = frappe.get_doc("BOM", bom)
				bom_quantity = flt(bom_doc.quantity) or 1.0
				# Get all child items from BOM
				for bom_item in bom_doc.items:
					child_item_code = bom_item.item_code
					child_bom_qty = flt(bom_item.qty)
					child_items.append(
						{
							"item_code": child_item_code,
							"bom_qty": child_bom_qty,
							"bom_quantity": bom_quantity,
						}
					)
			except Exception as e:
				pass

		if child_items:
			for child_item_info in child_items:
				child_item_code = child_item_info["item_code"]
				child_bom_qty = flt(child_item_info.get("bom_qty", 0))
				child_bom_quantity = flt(child_item_info.get("bom_quantity", 1.0)) or 1.0

				# Fetch child item details
				child_item_type = None
				child_sku_type = None
				child_stock = 0

				try:
					child_item_doc = frappe.get_doc("Item", child_item_code)
					child_item_type = child_item_doc.get("custom_item_type")
					child_buffer_flag = child_item_doc.get("custom_buffer_flag") or "Non-Buffer"
					child_sku_type = calculate_sku_type(child_buffer_flag, child_item_type)

					if child_item_code not in child_stock_map:
						stock_data = frappe.db.sql(
							"""
							SELECT SUM(actual_qty) as stock
							FROM `tabBin`
							WHERE item_code = %s
							""",
							(child_item_code,),
							as_dict=True,
						)
						total_stock = math.ceil(
							flt(stock_data[0].stock if stock_data and stock_data[0].stock else 0)
						)
						child_stock_map[child_item_code] = total_stock

					# Use total stock for display
					child_stock = child_stock_map.get(child_item_code, 0)
				except Exception as e:
					pass

				normalized_bom_qty = child_bom_qty / child_bom_quantity if child_bom_quantity else 0
				child_requirement = math.ceil(flt(or_with_moq_batch_size) * normalized_bom_qty)

				child_wip = (
					0 if child_sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(child_item_code, 0))
				)
				child_open_po = flt(open_po_map.get(child_item_code, 0))
				child_wip_open_po = math.ceil(flt(child_wip) + flt(child_open_po))
				if child_item_code not in child_wip_open_po_map:
					child_wip_open_po_map[child_item_code] = child_wip_open_po

				row = base_row.copy()
				row["child_item_code"] = child_item_code
				row["child_item_type"] = child_item_type
				row["child_sku_type"] = child_sku_type
				row["child_requirement"] = child_requirement
				row["child_stock"] = child_stock
				row["child_wip_open_po"] = child_wip_open_po
				row["child_bom_qty"] = child_bom_qty
				row["child_bom_quantity"] = child_bom_quantity
				row["child_stock_soft_allocation_qty"] = None
				row["child_stock_shortage"] = None

				data.append(row)
		else:
			data.append(base_row)

	# ── Priority propagation through BOM tree (N-level) ───────────────────────
	# Phase 1: build own FIFO priority map for all report items
	_item_priority_map = {}
	for _row in data:
		_ic = _row.get("item_code")
		if _ic and _ic not in _item_priority_map:
			_item_priority_map[_ic] = _row.get("priority") or ""

	_report_item_set = set(_item_priority_map.keys())
	if _report_item_set:
		# Phase 2: BFS upward — collect ALL ancestors (any depth) and
		# build the complete child→parents map in one pass per BFS level.
		_child_to_parents = defaultdict(set)
		_all_items = set(_report_item_set)
		_frontier = set(_report_item_set)
		while _frontier:
			_f_tuple = tuple(_frontier)
			_up_rows = frappe.db.sql(
				"""
				SELECT b.item AS parent_item, bi.item_code AS child_item
				FROM `tabBOM` b
				INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
				WHERE bi.item_code IN %s
				  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
				""",
				(_f_tuple,),
				as_dict=True,
			)
			_new_parents = set()
			for _br in _up_rows:
				_child_to_parents[_br.child_item].add(_br.parent_item)
				if _br.parent_item not in _all_items:
					_new_parents.add(_br.parent_item)
			_all_items.update(_new_parents)
			_frontier = _new_parents  # advance to next BFS level

		# Phase 3: compute own FIFO priority for ancestors not already in the report
		_external_items = _all_items - _report_item_set
		if _external_items:
			_ext_tuple = tuple(_external_items)
			_ext_so_map = get_open_so_map_for_priority(list(_external_items))
			_ext_item_rows = frappe.db.sql(
				"SELECT item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE item_code IN %s",
				(_ext_tuple,),
				as_dict=True,
			)
			_ext_stock_rows = frappe.db.sql(
				"SELECT item_code, SUM(actual_qty) as stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
				(_ext_tuple,),
				as_dict=True,
			)
			_ext_stock_map = {r.item_code: flt(r.stock) for r in _ext_stock_rows}
			for _ei in _ext_item_rows:
				_eic = _ei.item_code
				_esku = calculate_sku_type(_ei.custom_buffer_flag or "Non-Buffer", _ei.custom_item_type) or ""
				_estock = _ext_stock_map.get(_eic, 0)
				_ewip = 0 if _esku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_eic, 0))
				_epo = flt(open_po_map.get(_eic, 0))
				_elevel = (_estock + _epo) if _esku in ["BOTO", "PTO", "TRMTO"] else (_estock + _ewip)
				_item_priority_map[_eic] = _non_buffer_priority(_eic, _elevel, _ext_so_map)

		# Phase 4: BFS downward — propagate worst parent priority through the full tree
		# Roots = items that have no parents in the complete ancestor set
		_resolved = _all_items - set(_child_to_parents.keys())
		_changed = True
		while _changed:
			_changed = False
			for _child, _parents in _child_to_parents.items():
				if _child in _resolved:
					continue
				if not _parents.issubset(_resolved):
					continue
				_worst = 0
				for _parent in _parents:
					_pc = _item_priority_map.get(_parent, "")
					if _pc:
						_pv = _STATUS_PRIORITY.get(_pc.upper(), 0)
						if _pv > _worst:
							_worst = _pv
				# If all parents have empty priority, keep child's own FIFO priority
				_item_priority_map[_child] = (
					_PRIORITY_TO_COLOUR.get(_worst, "") if _worst > 0 else _item_priority_map.get(_child, "")
				)
				_resolved.add(_child)
				_changed = True

		# Write propagated priorities back to all data rows
		for _row in data:
			_ic = _row.get("item_code")
			if _ic and _row.get("buffer_flag") != "Buffer":
				_row["priority"] = _item_priority_map.get(_ic, "")

	# Apply filters
	filtered_data = []
	for row in data:
		# Filter by SKU Type
		if filters.get("sku_type"):
			sku_type_filter = filters.get("sku_type")
			sku_type_list = []
			if isinstance(sku_type_filter, str):
				# Try to parse as JSON first (in case it's a JSON string)
				if sku_type_filter.strip().startswith("[") or sku_type_filter.strip().startswith("{"):
					try:
						import json

						parsed = json.loads(sku_type_filter)
						if isinstance(parsed, list):
							sku_type_list = [str(s).strip() for s in parsed if s]
						else:
							sku_type_list = [str(parsed).strip()] if parsed else []
					except:
						# If JSON parsing fails, treat as comma-separated string
						sku_type_list = [s.strip() for s in sku_type_filter.split(",") if s.strip()]
				else:
					# Comma-separated string
					sku_type_list = [s.strip() for s in sku_type_filter.split(",") if s.strip()]
			elif isinstance(sku_type_filter, list):
				# Already a list
				sku_type_list = [str(s).strip() for s in sku_type_filter if s]
			else:
				# Single value
				sku_type_list = [str(sku_type_filter).strip()] if sku_type_filter else []
			if sku_type_list and row.get("sku_type") not in sku_type_list:
				continue

		# Filter by Item Code (exact match)
		if filters.get("item_code"):
			if row.get("item_code") != filters.get("item_code"):
				continue

		filtered_data.append(row)

	def get_on_hand_status_value(row):
		on_hand_status = row.get("on_hand_status")
		if on_hand_status is None:
			return float("inf")  # Put None values at the end
		# Extract number from string like "50%"
		try:
			# Remove % sign and convert to float
			numeric_value = float(on_hand_status.replace("%", "").strip())
			return numeric_value
		except (ValueError, AttributeError):
			return float("inf")  # Put invalid values at the end

	filtered_data.sort(key=get_on_hand_status_value)

	remaining_child_stock_fifo = {}
	# Re-initialize remaining_child_wip_open_po for FIFO allocation
	remaining_child_wip_open_po_fifo = {}

	for row in filtered_data:
		child_item_code = row.get("child_item_code")
		if child_item_code:
			# Initialize remaining stock if not already done
			if child_item_code not in remaining_child_stock_fifo:
				# Get total stock for this child item
				if child_item_code in child_stock_map:
					remaining_child_stock_fifo[child_item_code] = child_stock_map[child_item_code]
				else:
					# Fetch stock if not in map
					try:
						stock_data = frappe.db.sql(
							"""
							SELECT SUM(actual_qty) as stock
							FROM `tabBin`
							WHERE item_code = %s
							""",
							(child_item_code,),
							as_dict=True,
						)
						total_stock = int(
							flt(stock_data[0].stock if stock_data and stock_data[0].stock else 0)
						)
						child_stock_map[child_item_code] = total_stock
						remaining_child_stock_fifo[child_item_code] = total_stock
					except Exception:
						remaining_child_stock_fifo[child_item_code] = 0

			# Initialize remaining WIP/Open PO if not already done
			if child_item_code not in remaining_child_wip_open_po_fifo:
				# Get total WIP/Open PO for this child item
				if child_item_code in child_wip_open_po_map:
					remaining_child_wip_open_po_fifo[child_item_code] = flt(
						child_wip_open_po_map[child_item_code]
					)
				else:
					remaining_child_wip_open_po_fifo[child_item_code] = flt(row.get("child_wip_open_po", 0))
			child_requirement = flt(row.get("child_requirement", 0))
			available_stock = flt(remaining_child_stock_fifo.get(child_item_code, 0))
			stock_allocated = min(child_requirement, available_stock)
			stock_shortage = child_requirement - stock_allocated

			row["child_stock_soft_allocation_qty"] = math.ceil(stock_allocated)
			row["child_stock_shortage"] = math.ceil(stock_shortage)

			child_bom_qty = flt(row.get("child_bom_qty", 0))
			child_bom_quantity = flt(row.get("child_bom_quantity", 1.0)) or 1.0
			parent_per_child_factor = (child_bom_quantity / child_bom_qty) if child_bom_quantity else 0

			net_order_recommendation = flt(row.get("or_with_moq_batch_size", 0))

			production_qty_based_on_child_stock = math.ceil(flt(stock_allocated) * parent_per_child_factor)
			# Cap at net order recommendation — can't produce more than what's actually needed
			production_qty_based_on_child_stock = min(production_qty_based_on_child_stock, math.ceil(net_order_recommendation))
			row["production_qty_based_on_child_stock"] = production_qty_based_on_child_stock

			remaining_requirement_after_stock = stock_shortage
			available_wip_open_po = flt(remaining_child_wip_open_po_fifo.get(child_item_code, 0))
			wip_open_po_allocated = min(remaining_requirement_after_stock, available_wip_open_po)
			wip_open_po_shortage = remaining_requirement_after_stock - wip_open_po_allocated

			row["child_wip_open_po_soft_allocation_qty"] = math.ceil(wip_open_po_allocated)
			row["child_wip_open_po_shortage"] = math.ceil(wip_open_po_shortage)

			if flt(net_order_recommendation) == 0:
				row["child_wip_open_po_full_kit_status"] = None
			elif flt(wip_open_po_shortage) == 0:
				row["child_wip_open_po_full_kit_status"] = "Full-kit"
			elif flt(wip_open_po_allocated) == 0:
				row["child_wip_open_po_full_kit_status"] = "Pending"
			else:
				row["child_wip_open_po_full_kit_status"] = "Partial"

			total_allocated = flt(stock_allocated) + flt(wip_open_po_allocated)
			production_qty_based_on_child_stock_wip_open_po = math.ceil(
				total_allocated * parent_per_child_factor
			)
			# Cap at net order recommendation — can't produce more than what's actually needed
			production_qty_based_on_child_stock_wip_open_po = min(production_qty_based_on_child_stock_wip_open_po, math.ceil(net_order_recommendation))
			row["production_qty_based_on_child_stock_wip_open_po"] = (
				production_qty_based_on_child_stock_wip_open_po
			)

			order_recommendation = flt(row.get("order_recommendation", 0))

			if flt(order_recommendation) == 0:
				row["child_full_kit_status"] = None
			elif flt(stock_shortage) == 0:
				row["child_full_kit_status"] = "Full-kit"
			elif flt(stock_allocated) == 0:
				row["child_full_kit_status"] = "Pending"
			else:
				row["child_full_kit_status"] = "Partial"

			remaining_child_stock_fifo[child_item_code] = available_stock - stock_allocated
			remaining_child_wip_open_po_fifo[child_item_code] = available_wip_open_po - wip_open_po_allocated

	return filtered_data


@frappe.whitelist()
def create_material_request(item_code: str, qty: float | str) -> dict:
	"""
	Create and submit a Material Request for the given item_code and quantity
	"""
	if not frappe.has_permission("Material Request", "create") and not frappe.has_permission(
		"Material Request", "write"
	):
		frappe.throw(_("Not permitted to create Material Requests."), frappe.PermissionError)

	if not frappe.has_permission("Material Request", "submit"):
		frappe.throw(
			_("Not permitted to submit Material Requests."),
			frappe.PermissionError,
		)

	if not item_code:
		return {"error": "Item code is required"}

	if not qty or flt(qty) <= 0:
		return {"error": "Quantity must be greater than 0"}

	# Get item details
	if not frappe.db.exists("Item", item_code):
		return {"error": f"Item {item_code} not found"}

	item_doc = frappe.get_doc("Item", item_code)

	# Get UOM from item
	uom = item_doc.get("uom")
	if not uom:
		# If uom is not set, use stock_uom
		uom = item_doc.get("stock_uom")

	if not uom:
		return {"error": f"UOM not found for item {item_code}"}

	# Get stock_uom from item
	stock_uom = item_doc.get("stock_uom")
	if not stock_uom:
		return {"error": f"Stock UOM not found for item {item_code}"}

	conversion_factor = 1.0
	if uom != stock_uom:
		for uom_detail in item_doc.get("uoms", []):
			if uom_detail.uom == uom:
				conversion_factor = flt(uom_detail.conversion_factor)
				break

		# If not found in child table, check if item has uom_conversion_factor field
		if conversion_factor == 1.0 and hasattr(item_doc, "uom_conversion_factor"):
			conversion_factor = flt(item_doc.get("uom_conversion_factor", 1.0))

	# Calculate schedule_date (7 days from now)
	from frappe.utils import add_days, today

	schedule_date = add_days(today(), 7)

	# Set company name
	company = "Prakash Steel Products Pvt Ltd"

	# Verify company exists
	if not frappe.db.exists("Company", company):
		return {"error": f"Company '{company}' not found in the system."}

	try:
		# Set warehouse
		warehouse = "Bright Bar Unit - PSPL"

		# Verify warehouse exists
		if not frappe.db.exists("Warehouse", warehouse):
			return {"error": f"Warehouse '{warehouse}' not found in the system."}

		# Create Material Request
		mr_doc = frappe.get_doc(
			{
				"doctype": "Material Request",
				"company": company,
				"transaction_date": today(),
				"schedule_date": schedule_date,
				"material_request_type": "Purchase",
				"items": [
					{
						"item_code": item_code,
						"qty": flt(qty),
						"uom": uom,
						"stock_uom": stock_uom,
						"conversion_factor": conversion_factor,
						"warehouse": warehouse,
					}
				],
			}
		)

		mr_doc.insert()
		mr_doc.submit()

		return {
			"material_request": mr_doc.name,
			"message": f"Material Request {mr_doc.name} created and submitted successfully",
		}
	except Exception as e:
		return {"error": f"Error creating Material Request: {str(e)}"}


@frappe.whitelist()
def create_material_requests_automatically(filters: dict | str | None = None) -> dict:
	"""
	Create Material Requests automatically for all items with net_po_recommendation > 0
	"""
	if not frappe.has_permission("Material Request", "create") and not frappe.has_permission(
		"Material Request", "write"
	):
		frappe.throw(_("Not permitted to create Material Requests."), frappe.PermissionError)

	if not frappe.has_permission("Material Request", "submit"):
		frappe.throw(
			_("Not permitted to submit Material Requests."),
			frappe.PermissionError,
		)

	# Parse filters if it's a JSON string
	if isinstance(filters, str):
		import json

		try:
			filters = json.loads(filters)
		except:
			filters = {}

	if not filters:
		filters = {}

	# Get report data
	_, data = execute(filters)

	if not data:
		return {
			"success_count": 0,
			"error_count": 0,
			"material_requests": [],
			"message": "No data found in report",
		}

	# Filter items with net_po_recommendation > 0
	items_to_process = [
		row
		for row in data
		if row.get("net_po_recommendation") and flt(row.get("net_po_recommendation", 0)) > 0
	]

	if not items_to_process:
		return {
			"success_count": 0,
			"error_count": 0,
			"material_requests": [],
			"message": "No items with Net PO Recommendation > 0 found",
		}

	success_count = 0
	error_count = 0
	material_requests = []
	errors = []

	# Create Material Request for each item
	for row in items_to_process:
		item_code = row.get("item_code")
		qty = flt(row.get("net_po_recommendation", 0))

		if not item_code or qty <= 0:
			error_count += 1
			errors.append(f"{item_code}: Invalid quantity")
			continue

		try:
			result = create_material_request(item_code, qty)
			if result.get("error"):
				error_count += 1
				errors.append(f"{item_code}: {result.get('error')}")
			else:
				success_count += 1
				material_requests.append(result.get("material_request"))
		except Exception as e:
			error_count += 1
			errors.append(f"{item_code}: {str(e)}")

	return {
		"success_count": success_count,
		"error_count": error_count,
		"material_requests": material_requests,
		"errors": errors[:10] if len(errors) > 10 else errors,  # Limit errors to first 10
		"message": f"Created {success_count} Material Request(s), {error_count} failed",
	}



@frappe.whitelist()
def get_priority_breakdown(item_code: str) -> dict:
	"""
	Returns full priority calculation breakdown for a non-buffer item:
	- Own FIFO priority (level vs open SOs)
	- BOM parents and their priorities
	- Final propagated priority
	"""
	if not frappe.has_permission("Item", "read"):
		frappe.throw("Not permitted to access PO recommendation breakdowns.", frappe.PermissionError)

	item = frappe.db.get_value("Item", item_code, ["custom_buffer_flag", "custom_item_type"], as_dict=True)
	if not item:
		frappe.throw(f"Item {item_code} not found")

	buffer_flag = item.custom_buffer_flag or "Non-Buffer"
	item_type = item.custom_item_type
	sku_type = calculate_sku_type(buffer_flag, item_type) or ""

	# Stock
	stock_data = frappe.db.sql(
		"SELECT SUM(actual_qty) as stock FROM `tabBin` WHERE item_code = %s",
		(item_code,),
		as_dict=True,
	)
	stock = flt(stock_data[0].stock if stock_data else 0)

	wip_map = get_wip_map()
	wip = 0 if sku_type in ["RBMTA", "RBMTO"] else flt(wip_map.get(item_code, 0))

	open_po_map = get_open_po_map()
	open_po = flt(open_po_map.get(item_code, 0))

	if sku_type in ["BOTO", "PTO", "TRMTO"]:
		level = stock + open_po
		level_formula = f"Stock ({stock}) + Open PO ({open_po})"
	else:
		level = stock + wip
		level_formula = f"Stock ({stock}) + WIP ({wip})"

	# Open SOs with full FIFO detail (including delivery_date)
	so_rows = frappe.db.sql(
		"""
		SELECT so.transaction_date, soi.delivery_date,
		       GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) AS pending_qty
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		  AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code = %s
		  AND GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) > 0
		ORDER BY soi.delivery_date ASC
		""",
		(item_code,),
		as_dict=True,
	)

	available = flt(level)
	worst_shortage = 0
	worst_no_shortage = 0
	fifo_detail = []
	for so in so_rows:
		required = flt(so.pending_qty)
		allocated = min(required, available)
		shortage = required - allocated
		available -= allocated
		order_status = _compute_order_status(so.delivery_date, so.transaction_date) or ""
		p = _STATUS_PRIORITY.get(order_status, 0)
		if shortage > 0:
			if p > worst_shortage:
				worst_shortage = p
		else:
			if p > worst_no_shortage:
				worst_no_shortage = p
		fifo_detail.append(
			{
				"delivery_date": str(so.delivery_date) if so.delivery_date else "",
				"pending_qty": math.ceil(required),
				"allocated": math.ceil(allocated),
				"shortage": math.ceil(shortage),
				"order_status": order_status,
			}
		)

	if not so_rows:
		own_priority = ""
	elif worst_shortage > 0:
		own_priority = _PRIORITY_TO_COLOUR.get(worst_shortage, "")
	elif worst_no_shortage > 0:
		own_priority = _PRIORITY_TO_COLOUR.get(worst_no_shortage, "")
	else:
		own_priority = ""

	# BOM parents — N-level upward BFS to collect all ancestors
	# Then propagate downward so each parent shows its true propagated priority.
	_bd_child_to_parents = defaultdict(set)
	_bd_all_items = {item_code}
	_bd_frontier = {item_code}
	while _bd_frontier:
		_bd_f_tuple = tuple(_bd_frontier)
		_bd_up = frappe.db.sql(
			"""
			SELECT b.item AS parent_item, bi.item_code AS child_item
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
			WHERE bi.item_code IN %s
			  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
			""",
			(_bd_f_tuple,),
			as_dict=True,
		)
		_bd_new = set()
		for _r in _bd_up:
			_bd_child_to_parents[_r.child_item].add(_r.parent_item)
			if _r.parent_item not in _bd_all_items:
				_bd_new.add(_r.parent_item)
		_bd_all_items.update(_bd_new)
		_bd_frontier = _bd_new

	# Compute own FIFO priority for all ancestors
	_bd_ancestors = _bd_all_items - {item_code}
	_bd_priority_map = {item_code: own_priority}
	if _bd_ancestors:
		_bd_anc_tuple = tuple(_bd_ancestors)
		_bd_item_rows = frappe.db.sql(
			"SELECT item_code, custom_buffer_flag, custom_item_type FROM `tabItem` WHERE item_code IN %s",
			(_bd_anc_tuple,),
			as_dict=True,
		)
		_bd_stock_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) as stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(_bd_anc_tuple,),
			as_dict=True,
		)
		_bd_stock_map = {r.item_code: flt(r.stock) for r in _bd_stock_rows}
		_bd_anc_so_map = get_open_so_map_for_priority(list(_bd_ancestors))
		for _ai in _bd_item_rows:
			_aic = _ai.item_code
			_asku = calculate_sku_type(_ai.custom_buffer_flag or "Non-Buffer", _ai.custom_item_type) or ""
			_astock = _bd_stock_map.get(_aic, 0)
			_awip = 0 if _asku in ["RBMTA", "RBMTO"] else flt(wip_map.get(_aic, 0))
			_apo = flt(open_po_map.get(_aic, 0))
			_alevel = (_astock + _apo) if _asku in ["BOTO", "PTO", "TRMTO"] else (_astock + _awip)
			_bd_priority_map[_aic] = _non_buffer_priority(_aic, _alevel, _bd_anc_so_map)

	# BFS downward — propagate worst parent priority through the ancestor tree
	_bd_resolved = _bd_all_items - set(_bd_child_to_parents.keys())
	_bd_changed = True
	while _bd_changed:
		_bd_changed = False
		for _child, _parents in _bd_child_to_parents.items():
			if _child in _bd_resolved:
				continue
			if not _parents.issubset(_bd_resolved):
				continue
			_worst = 0
			for _par in _parents:
				_pc = _bd_priority_map.get(_par, "")
				if _pc:
					_pv = _STATUS_PRIORITY.get(_pc.upper(), 0)
					if _pv > _worst:
						_worst = _pv
			_bd_priority_map[_child] = (
				_PRIORITY_TO_COLOUR.get(_worst, "") if _worst > 0 else _bd_priority_map.get(_child, "")
			)
			_bd_resolved.add(_child)
			_bd_changed = True

	# Build parent_details for direct parents only (show own + propagated priority)
	_direct_parent_codes = [
		r.parent_item
		for r in frappe.db.sql(
			"""
		SELECT DISTINCT b.item AS parent_item
		FROM `tabBOM` b
		INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
		WHERE bi.item_code = %s
		  AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
		""",
			(item_code,),
			as_dict=True,
		)
	]
	parent_details = []
	for pic in _direct_parent_codes:
		pitem = frappe.db.get_value("Item", pic, ["custom_buffer_flag", "custom_item_type"], as_dict=True)
		if not pitem:
			continue
		p_sku = calculate_sku_type(pitem.custom_buffer_flag or "Non-Buffer", pitem.custom_item_type) or ""
		p_stock = flt(
			(
				frappe.db.sql(
					"SELECT SUM(actual_qty) as s FROM `tabBin` WHERE item_code=%s", (pic,), as_dict=True
				)
				or [{}]
			)[0].get("s")
			or 0
		)
		p_wip = 0 if p_sku in ["RBMTA", "RBMTO"] else flt(wip_map.get(pic, 0))
		p_open_po = flt(open_po_map.get(pic, 0))
		p_level = (p_stock + p_open_po) if p_sku in ["BOTO", "PTO", "TRMTO"] else (p_stock + p_wip)
		parent_details.append(
			{
				"item_code": pic,
				"sku_type": p_sku,
				"stock": math.ceil(p_stock),
				"wip": math.ceil(p_wip),
				"open_po": math.ceil(p_open_po),
				"level": math.ceil(p_level),
				"own_priority": _bd_priority_map.get(pic, ""),  # propagated priority of this parent
			}
		)

	# Final priority = worst of direct parents' propagated priorities; own if no parents
	final_priority = own_priority
	if parent_details:
		worst = 0
		for pd in parent_details:
			pc = pd["own_priority"]
			if pc:
				pv = _STATUS_PRIORITY.get(pc.upper(), 0)
				if pv > worst:
					worst = pv
		if worst > 0:
			final_priority = _PRIORITY_TO_COLOUR.get(worst, "")

	return {
		"item_code": item_code,
		"sku_type": sku_type,
		"stock": math.ceil(stock),
		"wip": math.ceil(wip),
		"open_po": math.ceil(open_po),
		"level": math.ceil(level),
		"level_formula": level_formula,
		"own_priority": own_priority,
		"fifo_detail": fifo_detail,
		"parent_details": parent_details,
		"final_priority": final_priority,
	}



@frappe.whitelist()
def get_on_hand_status_breakdown(item_code: str) -> dict:
	from frappe.utils import add_days, today
	if not frappe.has_permission("Item", "read"):
		frappe.throw("Not permitted to access on-hand breakdowns.", frappe.PermissionError)

	today_date = today()

	item = frappe.db.get_value(
		"Item", item_code,
		["name", "item_name", "safety_stock", "custom_buffer_flag", "custom_item_type",
		 "min_order_qty", "custom_batch_size"],
		as_dict=True,
	)
	if not item:
		frappe.throw(f"Item {item_code} not found")

	buffer_flag = item.custom_buffer_flag or "Non-Buffer"
	item_type   = item.custom_item_type or ""
	tog         = flt(item.safety_stock)

	stock_row = frappe.db.sql(
		"SELECT SUM(actual_qty) as stock FROM `tabBin` WHERE item_code = %s", item_code, as_dict=True
	)
	on_hand_stock = flt(stock_row[0].stock if stock_row else 0)

	till_today_rows = frappe.db.sql(
		"""
		SELECT SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as qty
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		  AND so.docstatus = 1 AND IFNULL(soi.custom_closed, 0) = 0
		  AND soi.item_code = %s AND IFNULL(soi.delivery_date,'1900-01-01') <= %s
		""",
		(item_code, today_date), as_dict=True,
	)
	till_today = flt(till_today_rows[0].qty if till_today_rows else 0)

	spike_config = frappe.db.get_value(
		"Spike Master", item_type, ["demand_horizon", "spike_threshold"], as_dict=True
	) if item_type else None

	demand_horizon      = flt(spike_config.demand_horizon) if spike_config else 0
	spike_threshold_pct = flt(spike_config.spike_threshold) if spike_config else 0
	spike_threshold_qty = tog * spike_threshold_pct / 100

	spike = 0.0
	spike_sos = []
	if buffer_flag == "Buffer" and demand_horizon > 0:
		end_date = add_days(today_date, int(demand_horizon))
		spike_rows = frappe.db.sql(
			"""
			SELECT so.name as so_name,
			       GREATEST(0, soi.qty - IFNULL(soi.delivered_qty,0)) as qty,
			       soi.delivery_date
			FROM `tabSales Order` so
			INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
			WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			  AND so.docstatus = 1 AND IFNULL(soi.custom_closed, 0) = 0
			  AND soi.item_code = %s
			  AND IFNULL(soi.delivery_date,'1900-01-01') > %s
			  AND IFNULL(soi.delivery_date,'1900-01-01') <= %s
			""",
			(item_code, today_date, end_date), as_dict=True,
		)
		for r in spike_rows:
			if flt(r.qty) > 0:
				spike += flt(r.qty)
				spike_sos.append({"so_name": r.so_name, "qty": flt(r.qty), "delivery_date": str(r.delivery_date)})

	raw_qualified = till_today + spike
	threshold_triggered = False
	qualified_demand = raw_qualified
	if buffer_flag == "Buffer" and spike_config and tog > 0:
		if raw_qualified < spike_threshold_qty:
			qualified_demand = 0.0
			threshold_triggered = True

	bom_parents = frappe.db.sql(
		"""
		SELECT b.item as parent_item, b.name as bom_name, b.quantity as bom_qty, bi.qty as child_qty
		FROM `tabBOM` b INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
		WHERE bi.item_code = %s AND b.is_active = 1 AND b.is_default = 1
		""",
		item_code, as_dict=True,
	)

	parent_details = []
	total_parent_demand = 0.0

	# ── Bulk-fetch all parent item data to avoid N+1 queries ───────────────
	parent_codes = list({p.parent_item for p in bom_parents})

	_pi_map = {}
	_p_stock_map = {}
	_p_wip_map = {}
	_p_open_po_map = {}
	_p_open_so_map = {}
	_p_qd_map = {}

	if parent_codes:
		# Item fields
		for row in frappe.db.get_all(
			"Item",
			filters={"name": ["in", parent_codes]},
			fields=["name", "custom_buffer_flag", "custom_item_type", "safety_stock", "min_order_qty", "custom_batch_size"],
		):
			_pi_map[row.name] = row

		# Stock
		for row in frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) as s FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(tuple(parent_codes),), as_dict=True,
		):
			_p_stock_map[row.item_code] = flt(row.s)

		# WIP
		for row in frappe.db.sql(
			"""SELECT production_item,
			          SUM(GREATEST(0, IFNULL(qty,0) - IFNULL(produced_qty,0))) as w
			   FROM `tabWork Order`
			   WHERE production_item IN %s
			     AND status NOT IN ('Completed','Stopped','Cancelled')
			     AND docstatus = 1
			   GROUP BY production_item""",
			(tuple(parent_codes),), as_dict=True,
		):
			_p_wip_map[row.production_item] = flt(row.w)

		# Open PO
		for row in frappe.db.sql(
			"""SELECT poi.item_code,
			          SUM(GREATEST(0, poi.qty - IFNULL(poi.received_qty, 0))) as po
			   FROM `tabPurchase Order` po
			   INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
			   WHERE po.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			     AND po.docstatus = 1
			     AND poi.item_code IN %s
			   GROUP BY poi.item_code""",
			(tuple(parent_codes),), as_dict=True,
		):
			_p_open_po_map[row.item_code] = flt(row.po)

		# Open SO (all-time, for non-buffer and for buffer display)
		for row in frappe.db.sql(
			"""SELECT soi.item_code,
			          SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as so
			   FROM `tabSales Order` so
			   INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
			   WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			     AND so.docstatus = 1
			     AND IFNULL(soi.custom_closed, 0) = 0
			     AND soi.item_code IN %s
			   GROUP BY soi.item_code""",
			(tuple(parent_codes),), as_dict=True,
		):
			_p_open_so_map[row.item_code] = flt(row.so)

		# Qualified demand (till-today, for buffer items)
		for row in frappe.db.sql(
			"""SELECT soi.item_code,
			          SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as qty
			   FROM `tabSales Order` so
			   INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
			   WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			     AND so.docstatus = 1
			     AND IFNULL(soi.custom_closed, 0) = 0
			     AND soi.item_code IN %s
			     AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
			   GROUP BY soi.item_code""",
			(tuple(parent_codes), today_date), as_dict=True,
		):
			_p_qd_map[row.item_code] = flt(row.qty)

	for p in bom_parents:
		parent_item = p.parent_item
		bom_qty = flt(p.bom_qty) or 1
		child_qty = flt(p.child_qty)
		ratio = child_qty / bom_qty

		pi = _pi_map.get(parent_item) or {}

		p_buffer = pi.get("custom_buffer_flag") or "Non-Buffer"
		p_type   = pi.get("custom_item_type") or ""
		p_tog    = flt(pi.get("safety_stock") or 0)
		p_moq    = flt(pi.get("min_order_qty") or 0)
		p_batch  = flt(pi.get("custom_batch_size") or 0)
		p_sku    = calculate_sku_type(p_buffer, p_type) or ""

		p_stock   = _p_stock_map.get(parent_item, 0.0)
		p_wip     = _p_wip_map.get(parent_item, 0.0)
		p_open_po = _p_open_po_map.get(parent_item, 0.0)
		p_open_so = _p_open_so_map.get(parent_item, 0.0)

		if p_buffer == "Buffer":
			p_qd = _p_qd_map.get(parent_item, 0.0)
			if p_sku in ["BOTA", "PTA"]:
				p_base = max(0, p_tog + p_qd - p_stock - p_wip - p_open_po)
			else:
				p_base = max(0, p_tog + p_qd - p_stock - p_wip)
			p_demand_label = f"TOG ({p_tog}) + QD ({p_qd}) - Stock ({p_stock}) - WIP ({p_wip})"
		else:
			p_qd = p_open_so
			if p_sku in ["BOTO", "PTO", "TRMTO"]:
				p_base = max(0, p_open_so - p_stock - p_wip - p_open_po)
				p_demand_label = f"Open SO ({p_open_so}) - Stock ({p_stock}) - WIP ({p_wip}) - Open PO ({p_open_po})"
			else:
				p_base = max(0, p_open_so - p_stock - p_wip)
				p_demand_label = f"Open SO ({p_open_so}) - Stock ({p_stock}) - WIP ({p_wip})"

		p_net = calculate_net_order_recommendation(p_base, p_moq, p_batch)
		demand_contributed = p_net * ratio
		total_parent_demand += demand_contributed

		parent_details.append({
			"parent_item": parent_item,
			"bom_name": p.bom_name,
			"buffer_flag": p_buffer,
			"sku_type": p_sku,
			"stock": p_stock,
			"wip": p_wip,
			"open_po": p_open_po,
			"open_so": p_open_so,
			"moq": p_moq,
			"batch_size": p_batch,
			"base_order_rec": round(p_base, 3),
			"net_order_rec": round(p_net, 3),
			"bom_qty": bom_qty,
			"child_qty": child_qty,
			"ratio": round(ratio, 4),
			"demand_contributed": round(demand_contributed, 3),
			"demand_label": p_demand_label,
		})

	total_demand = qualified_demand + total_parent_demand
	denominator  = tog + total_demand

	if buffer_flag == "Buffer" and denominator > 0:
		on_hand_pct = (on_hand_stock / denominator) * 100
		on_hand_pct_rounded = round(on_hand_pct, 2)
		if on_hand_pct_rounded == 0:
			colour = "BLACK"
		elif on_hand_pct_rounded <= 34:
			colour = "RED"
		elif on_hand_pct_rounded <= 67:
			colour = "YELLOW"
		elif on_hand_pct_rounded <= 100:
			colour = "GREEN"
		else:
			colour = "WHITE"
	else:
		on_hand_pct_rounded = None
		colour = None

	return {
		"item_code": item_code,
		"item_name": item.item_name,
		"buffer_flag": buffer_flag,
		"item_type": item_type,
		"tog": tog,
		"on_hand_stock": on_hand_stock,
		"till_today": till_today,
		"spike": spike,
		"spike_sos": spike_sos,
		"demand_horizon": demand_horizon,
		"spike_threshold_pct": spike_threshold_pct,
		"spike_threshold_qty": spike_threshold_qty,
		"raw_qualified": raw_qualified,
		"threshold_triggered": threshold_triggered,
		"qualified_demand": qualified_demand,
		"parent_details": parent_details,
		"total_parent_demand": round(total_parent_demand, 3),
		"total_demand": round(total_demand, 3),
		"denominator": round(denominator, 3),
		"on_hand_status": f"{on_hand_pct_rounded:.2f}%" if on_hand_pct_rounded is not None else "N/A",
		"on_hand_colour": colour,
	}


@frappe.whitelist()
def get_child_requirement_breakdown(item_code: str) -> dict:
	"""
	Return a step-by-step breakdown of how child requirements are computed
	for a given parent item in the PO Recommendation report.
	"""
	from frappe.utils import nowdate
	if not frappe.has_permission("Item", "read"):
		frappe.throw("Not permitted to access child requirement breakdowns.", frappe.PermissionError)

	today_date = nowdate()

	# ── Step 1: Parent item info ───────────────────────────────────────────
	item = frappe.db.get_value(
		"Item", item_code,
		["name", "item_name", "safety_stock", "custom_buffer_flag", "custom_item_type",
		 "min_order_qty", "custom_batch_size"],
		as_dict=True,
	)
	if not item:
		frappe.throw(f"Item {item_code} not found")

	buffer_flag  = item.custom_buffer_flag or "Non-Buffer"
	item_type    = item.custom_item_type or ""
	tog          = flt(item.safety_stock)
	moq          = flt(item.min_order_qty)
	batch_size   = flt(item.custom_batch_size)
	sku_type     = calculate_sku_type(buffer_flag, item_type) or ""

	# ── Step 2: Parent stock, WIP, open PO, open SO ────────────────────────
	stock_row = frappe.db.sql(
		"SELECT SUM(actual_qty) as stock FROM `tabBin` WHERE item_code = %s",
		item_code, as_dict=True,
	)
	stock = flt(stock_row[0].stock if stock_row else 0)

	wip_row = frappe.db.sql(
		"""SELECT SUM(GREATEST(0, IFNULL(qty,0) - IFNULL(produced_qty,0))) as w
		   FROM `tabWork Order`
		   WHERE production_item = %s AND status NOT IN ('Completed','Stopped','Cancelled') AND docstatus = 1""",
		item_code, as_dict=True,
	)
	wip = flt(wip_row[0].w if wip_row else 0)
	if sku_type in ["RBMTA", "RBMTO"]:
		wip = 0  # RBMTA/RBMTO do not count WIP

	open_po_row = frappe.db.sql(
		"""SELECT SUM(GREATEST(0, poi.qty - IFNULL(poi.received_qty,0))) as po
		   FROM `tabPurchase Order` po
		   INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		   WHERE po.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		     AND po.docstatus = 1 AND poi.item_code = %s""",
		item_code, as_dict=True,
	)
	open_po = flt(open_po_row[0].po if open_po_row else 0)

	open_so_row = frappe.db.sql(
		"""SELECT SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty,0))) as so
		   FROM `tabSales Order` so
		   INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		   WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		     AND so.docstatus = 1 AND IFNULL(soi.custom_closed,0) = 0
		     AND soi.item_code = %s""",
		item_code, as_dict=True,
	)
	open_so = flt(open_so_row[0].so if open_so_row else 0)

	# ── Step 3: Qualified demand ───────────────────────────────────────────
	till_today_row = frappe.db.sql(
		"""SELECT SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty,0))) as qty
		   FROM `tabSales Order` so
		   INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		   WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
		     AND so.docstatus = 1 AND IFNULL(soi.custom_closed,0) = 0
		     AND soi.item_code = %s AND IFNULL(soi.delivery_date,'1900-01-01') <= %s""",
		(item_code, today_date), as_dict=True,
	)
	till_today = flt(till_today_row[0].qty if till_today_row else 0)

	spike = 0.0
	demand_horizon = 0
	spike_threshold_pct = 0.0
	spike_threshold_qty = 0.0
	spike_sos = []
	threshold_triggered = False

	if buffer_flag == "Buffer" and item_type:
		spike_config = frappe.db.get_value(
			"Spike Master", item_type, ["demand_horizon", "spike_threshold"], as_dict=True
		)
		if spike_config:
			demand_horizon = flt(spike_config.demand_horizon)
			spike_threshold_pct = flt(spike_config.spike_threshold)
			spike_threshold_qty = tog * spike_threshold_pct / 100

			if demand_horizon > 0:
				from frappe.utils import add_days
				end_date = add_days(today_date, int(demand_horizon))
				spike_rows = frappe.db.sql(
					"""SELECT so.name as so_name,
					          GREATEST(0, soi.qty - IFNULL(soi.delivered_qty,0)) as qty,
					          soi.delivery_date
					   FROM `tabSales Order` so
					   INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
					   WHERE so.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
					     AND so.docstatus = 1 AND IFNULL(soi.custom_closed,0) = 0
					     AND soi.item_code = %s
					     AND IFNULL(soi.delivery_date,'1900-01-01') > %s
					     AND IFNULL(soi.delivery_date,'1900-01-01') <= %s""",
					(item_code, today_date, end_date), as_dict=True,
				)
				for r in spike_rows:
					if flt(r.qty) > 0:
						spike += flt(r.qty)
						spike_sos.append({"so_name": r.so_name, "qty": flt(r.qty), "delivery_date": str(r.delivery_date)})

	qualified_demand = till_today + spike
	if buffer_flag == "Buffer" and spike_threshold_qty > 0:
		if qualified_demand < spike_threshold_qty:
			qualified_demand = 0.0
			threshold_triggered = True

	# ── Step 4: Base & Net order recommendation ────────────────────────────
	if buffer_flag == "Buffer":
		if sku_type in ["BOTA", "PTA"]:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip - open_po)
			order_rec_formula = f"TOG ({tog}) + QD ({qualified_demand}) - Stock ({stock}) - WIP ({wip}) - Open PO ({open_po})"
		else:
			base_order_rec = max(0.0, tog + qualified_demand - stock - wip)
			order_rec_formula = f"TOG ({tog}) + QD ({qualified_demand}) - Stock ({stock}) - WIP ({wip})"
	else:
		if sku_type in ["BOTA", "PTA", "PTO", "BOTO", "TRMTO"]:
			base_order_rec = max(0.0, open_so - stock - wip - open_po)
			order_rec_formula = f"Open SO ({open_so}) - Stock ({stock}) - WIP ({wip}) - Open PO ({open_po})"
		else:
			base_order_rec = max(0.0, open_so - stock - wip)
			order_rec_formula = f"Open SO ({open_so}) - Stock ({stock}) - WIP ({wip})"

	net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

	if moq > 0:
		if moq < base_order_rec:
			moq_batch_note = f"MOQ ({moq}) < Base Rec ({round(base_order_rec,2)}) → use Base Rec"
		else:
			moq_batch_note = f"MOQ ({moq}) ≥ Base Rec ({round(base_order_rec,2)}) → use MOQ"
	elif batch_size > 0:
		moq_batch_note = f"Batch Size ({batch_size}) → ceil({round(base_order_rec,2)} / {batch_size}) × {batch_size} = {net_order_rec}"
	else:
		moq_batch_note = "No MOQ / Batch Size → use Base Rec as-is"

	or_with_moq_batch_size = math.ceil(flt(net_order_rec))

	# ── Step 5: BOM lookup ─────────────────────────────────────────────────
	bom_row = frappe.db.sql(
		"""SELECT b.name AS bom_name, b.quantity AS bom_quantity
		   FROM `tabBOM` b
		   WHERE b.item = %s AND b.is_default = 1 AND b.is_active = 1 AND b.docstatus = 1
		   LIMIT 1""",
		item_code, as_dict=True,
	)

	if not bom_row:
		return {
			"item_code": item_code,
			"item_name": item.item_name,
			"buffer_flag": buffer_flag,
			"sku_type": sku_type,
			"item_type": item_type,
			"tog": tog,
			"moq": moq,
			"batch_size": batch_size,
			"stock": stock,
			"wip": wip,
			"open_po": open_po,
			"open_so": open_so,
			"till_today": till_today,
			"spike": spike,
			"qualified_demand": round(qualified_demand, 3),
			"threshold_triggered": threshold_triggered,
			"spike_threshold_qty": round(spike_threshold_qty, 3),
			"demand_horizon": demand_horizon,
			"base_order_rec": round(base_order_rec, 3),
			"order_rec_formula": order_rec_formula,
			"moq_batch_note": moq_batch_note,
			"net_order_rec": round(net_order_rec, 3),
			"or_with_moq_batch_size": or_with_moq_batch_size,
			"bom_name": None,
			"bom_quantity": None,
			"child_items": [],
			"no_bom": True,
		}

	bom_name     = bom_row[0].bom_name
	bom_quantity = flt(bom_row[0].bom_quantity) or 1.0

	# ── Step 6: Child items ────────────────────────────────────────────────
	bom_items = frappe.db.sql(
		"""SELECT bi.item_code, bi.qty AS bom_qty, bi.item_name AS child_item_name
		   FROM `tabBOM Item` bi
		   WHERE bi.parent = %s AND bi.parenttype = 'BOM'""",
		bom_name, as_dict=True,
	)

	all_child_codes = [r.item_code for r in bom_items]
	child_detail_map = {}
	child_stock_map = {}
	child_wip_map = {}
	child_open_po_map = {}

	if all_child_codes:
		child_tuple = tuple(all_child_codes) if len(all_child_codes) > 1 else (all_child_codes[0],)

		# Child item types
		ci_rows = frappe.db.sql(
			"SELECT name, custom_item_type AS item_type, custom_buffer_flag AS buffer_flag FROM `tabItem` WHERE name IN %s",
			(child_tuple,), as_dict=True,
		)
		for ci in ci_rows:
			child_detail_map[ci.name] = {
				"item_type": ci.item_type,
				"buffer_flag": ci.buffer_flag or "Non-Buffer",
				"sku_type": calculate_sku_type(ci.buffer_flag or "Non-Buffer", ci.item_type),
			}

		# Child stock
		cs_rows = frappe.db.sql(
			"SELECT item_code, SUM(actual_qty) AS stock FROM `tabBin` WHERE item_code IN %s GROUP BY item_code",
			(child_tuple,), as_dict=True,
		)
		for cs in cs_rows:
			child_stock_map[cs.item_code] = math.ceil(flt(cs.stock))

		# Child WIP
		cw_rows = frappe.db.sql(
			"""SELECT production_item, SUM(GREATEST(0, IFNULL(qty,0) - IFNULL(produced_qty,0))) AS w
			   FROM `tabWork Order`
			   WHERE production_item IN %s AND status NOT IN ('Completed','Stopped','Cancelled') AND docstatus = 1
			   GROUP BY production_item""",
			(child_tuple,), as_dict=True,
		)
		for cw in cw_rows:
			child_wip_map[cw.production_item] = flt(cw.w)

		# Child open PO
		cp_rows = frappe.db.sql(
			"""SELECT poi.item_code, SUM(GREATEST(0, poi.qty - IFNULL(poi.received_qty,0))) AS po
			   FROM `tabPurchase Order` po
			   INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
			   WHERE po.status NOT IN ('Stopped','On Hold','Closed','Cancelled','Completed')
			     AND po.docstatus = 1 AND poi.item_code IN %s
			   GROUP BY poi.item_code""",
			(child_tuple,), as_dict=True,
		)
		for cp in cp_rows:
			child_open_po_map[cp.item_code] = flt(cp.po)

	child_items = []
	for bi in bom_items:
		child_code    = bi.item_code
		child_bom_qty = flt(bi.bom_qty)
		normalized    = child_bom_qty / bom_quantity if bom_quantity else 0
		child_req     = math.ceil(flt(or_with_moq_batch_size) * normalized)

		cd = child_detail_map.get(child_code, {})
		c_item_type  = cd.get("item_type") or ""
		c_buffer     = cd.get("buffer_flag") or "Non-Buffer"
		c_sku_type   = cd.get("sku_type") or ""

		c_stock   = child_stock_map.get(child_code, 0)
		c_wip     = 0 if c_sku_type in ["RBMTA", "RBMTO"] else child_wip_map.get(child_code, 0)
		c_open_po = child_open_po_map.get(child_code, 0)
		c_wip_open_po = math.ceil(flt(c_wip) + flt(c_open_po))

		stock_shortage      = max(0, child_req - c_stock)
		wip_po_shortage     = max(0, child_req - c_stock - c_wip_open_po)
		full_kit_stock      = "Full Kit" if stock_shortage == 0 else f"Short {stock_shortage}"
		full_kit_wip_po     = "Full Kit" if wip_po_shortage <= 0 else f"Short {math.ceil(wip_po_shortage)}"

		child_items.append({
			"child_item_code":  child_code,
			"child_item_name":  bi.child_item_name or "",
			"item_type":        c_item_type,
			"buffer_flag":      c_buffer,
			"sku_type":         c_sku_type,
			"bom_qty":          child_bom_qty,
			"bom_quantity":     bom_quantity,
			"normalized_ratio": round(normalized, 4),
			"child_requirement": child_req,
			"req_formula":      f"ceil({or_with_moq_batch_size} × {round(normalized,4)}) = {child_req}",
			"child_stock":      c_stock,
			"child_wip":        round(c_wip, 2),
			"child_open_po":    round(c_open_po, 2),
			"child_wip_open_po": c_wip_open_po,
			"stock_shortage":   stock_shortage,
			"wip_po_shortage":  math.ceil(wip_po_shortage) if wip_po_shortage > 0 else 0,
			"full_kit_stock":   full_kit_stock,
			"full_kit_wip_po":  full_kit_wip_po,
		})

	return {
		"item_code":             item_code,
		"item_name":             item.item_name,
		"buffer_flag":           buffer_flag,
		"sku_type":              sku_type,
		"item_type":             item_type,
		"tog":                   tog,
		"moq":                   moq,
		"batch_size":            batch_size,
		"stock":                 round(stock, 2),
		"wip":                   round(wip, 2),
		"open_po":               round(open_po, 2),
		"open_so":               round(open_so, 2),
		"till_today":            round(till_today, 2),
		"spike":                 round(spike, 2),
		"spike_sos":             spike_sos,
		"demand_horizon":        demand_horizon,
		"spike_threshold_pct":   spike_threshold_pct,
		"spike_threshold_qty":   round(spike_threshold_qty, 2),
		"threshold_triggered":   threshold_triggered,
		"qualified_demand":      round(qualified_demand, 3),
		"base_order_rec":        round(base_order_rec, 3),
		"order_rec_formula":     order_rec_formula,
		"moq_batch_note":        moq_batch_note,
		"net_order_rec":         round(net_order_rec, 3),
		"or_with_moq_batch_size": or_with_moq_batch_size,
		"bom_name":              bom_name,
		"bom_quantity":          bom_quantity,
		"child_items":           child_items,
		"no_bom":                False,
	}



