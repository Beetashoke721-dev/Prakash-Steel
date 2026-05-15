import math

import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
	calculate_net_order_recommendation,
	calculate_sku_type,
	calculate_spike_map,
	get_mrq_map,
	get_open_po_map,
	get_qualified_demand_for_item,
	get_qualified_demand_map,
	get_sales_order_qty_map,
	get_stock_map,
)


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Colour"),
			"fieldname": "colour",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Net Order Recommendation"),
			"fieldname": "net_order_recommendation",
			"fieldtype": "Int",
			"width": 200,
		},
		{
			"label": _("SKU Type"),
			"fieldname": "sku_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Item Type"),
			"fieldname": "item_type",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("TOG"),
			"fieldname": "tog",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Last Rolled Date"),
			"fieldname": "last_rolled_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": _("Last Rolled Qty"),
			"fieldname": "last_rolled_qty",
			"fieldtype": "Float",
			"width": 130,
		},
		{
			"label": _("Last 3 Months Sale"),
			"fieldname": "last_3_months_sale",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Last 3 Months Consumption"),
			"fieldname": "last_3_months_consumption",
			"fieldtype": "Float",
			"width": 180,
		},
		{
			"label": _("Last 1 Month Sale"),
			"fieldname": "last_1_month_sale",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Last 1 Month Consumption"),
			"fieldname": "last_1_month_consumption",
			"fieldtype": "Float",
			"width": 170,
		},
		{
			"label": _("On Hand Stock"),
			"fieldname": "on_hand_stock",
			"fieldtype": "Float",
			"precision": 2,
			"width": 130,
		},
		{
			"label": _("Net Qty"),
			"fieldname": "net_qty",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": _("Sub Grp"),
			"fieldname": "sub_grp",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Shape"),
			"fieldname": "shape",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Subgrp+Shape"),
			"fieldname": "subgrp_shape",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Subgrp Weightage"),
			"fieldname": "subgrp_weightage",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Prod Qty Based on Child Stock"),
			"fieldname": "prod_qty_based_on_child_stock",
			"fieldtype": "Float",
			"width": 200,
		},
		{
			"label": _("Prod Qty Based on Child Stock+WIP/Open PO"),
			"fieldname": "prod_qty_based_on_child_stock_wip_open_po",
			"fieldtype": "Float",
			"width": 260,
		},
		{
			"label": _("Child Item Code"),
			"fieldname": "child_item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Child Requirement"),
			"fieldname": "child_requirement",
			"fieldtype": "Float",
			"width": 150,
		},
		{
			"label": _("Child Stock"),
			"fieldname": "child_stock",
			"fieldtype": "Float",
			"width": 110,
		},
		{
			"label": _("Child Stock Allocation"),
			"fieldname": "child_stock_allocation",
			"fieldtype": "Float",
			"width": 160,
		},
		{
			"label": _("Child Shortage"),
			"fieldname": "child_shortage",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Child Item Open PO"),
			"fieldname": "child_item_open_po",
			"fieldtype": "Float",
			"width": 150,
		},
	]


def get_data(filters=None):
	if not filters:
		filters = {}

	# Fetch all RB items
	rb_items = frappe.db.sql(
		"""
		SELECT
			i.name as item_code,
			i.item_name,
			i.custom_item_type as item_type,
			i.custom_buffer_flag as buffer_flag,
			i.safety_stock as tog,
			i.min_order_qty as moq,
			i.custom_batch_size as batch_size,
			i.custom_sub_group_new_name as sub_grp,
			i.custom_shape as shape
		FROM `tabItem` i
		WHERE i.custom_item_type = 'RB'
		""",
		as_dict=True,
	)

	if not rb_items:
		return []

	item_codes = set(item.item_code for item in rb_items)
	item_codes_tuple = tuple(item_codes) if len(item_codes) > 1 else (next(iter(item_codes)),)

	# Build lookup maps
	item_buffer_map = {}
	item_type_map = {}
	item_tog_map = {}
	item_info_map = {}
	for item in rb_items:
		item_buffer_map[item.item_code] = item.buffer_flag or "Non-Buffer"
		item_type_map[item.item_code] = item.item_type
		item_tog_map[item.item_code] = flt(item.tog or 0)
		item_info_map[item.item_code] = item

	stock_map = get_stock_map(item_codes)
	mrq_map = get_mrq_map()

	# Last rolled date and qty from most recent submitted Finish Weight doc per item
	last_rolled_rows = frappe.db.sql(
		"""
		SELECT fw.item_code, fw.posting_date, fw.finish_weight
		FROM `tabFinish Weight` fw
		INNER JOIN (
			SELECT item_code, MAX(posting_date) AS max_date
			FROM `tabFinish Weight`
			WHERE docstatus = 1 AND item_code IN %s
			GROUP BY item_code
		) latest ON fw.item_code = latest.item_code AND fw.posting_date = latest.max_date
		WHERE fw.docstatus = 1
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_rolled_map = {}
	for r in last_rolled_rows:
		existing = last_rolled_map.get(r.item_code)
		if not existing or r.posting_date > existing["last_rolled_date"]:
			last_rolled_map[r.item_code] = {
				"last_rolled_date": r.posting_date,
				"last_rolled_qty": flt(r.finish_weight),
			}
	open_po_map = get_open_po_map()
	so_qty_map = get_sales_order_qty_map(filters)

	# Last 3 months consumption (90 days) from Bright Bar Production
	last_3month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			bbp.raw_material AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND bbp.raw_material IN %s
		GROUP BY bbp.raw_material
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_3month_consumption_map = {r.item_code: flt(r.consumption_qty) for r in last_3month_consumption_rows}

	# Last 1 month consumption (30 days) from Bright Bar Production
	last_1month_consumption_rows = frappe.db.sql(
		"""
		SELECT
			bbp.raw_material AS item_code,
			SUM(bbp.actual_rm_consumption) AS consumption_qty
		FROM `tabBright Bar Production` bbp
		WHERE bbp.docstatus = 1
			AND bbp.production_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND bbp.raw_material IN %s
		GROUP BY bbp.raw_material
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_1month_consumption_map = {r.item_code: flt(r.consumption_qty) for r in last_1month_consumption_rows}

	# Last 3 months sale (90 days) — same logic as bright_plan
	last_3month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(sii.qty) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
			AND sii.item_code IN %s
		GROUP BY sii.item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_3month_sale_map = {r.item_code: flt(r.sale_qty) for r in last_3month_rows}

	# Last 1 month sale (30 days) — same query, shorter interval
	last_1month_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			SUM(sii.qty) AS sale_qty
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		WHERE si.docstatus = 1
			AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
			AND sii.item_code IN %s
		GROUP BY sii.item_code
		""",
		(item_codes_tuple,),
		as_dict=True,
	)
	last_1month_sale_map = {r.item_code: flt(r.sale_qty) for r in last_1month_rows}

	till_today_map, spike_map_base = get_qualified_demand_map()
	calculated_spike_map = calculate_spike_map(item_codes, item_buffer_map, item_type_map, item_tog_map)
	spike_map_base.update(calculated_spike_map)

	spike_master_records = frappe.get_all(
		"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
	)
	spike_master_map = {
		sm.item_type: {"demand_horizon": flt(sm.demand_horizon), "spike_threshold": flt(sm.spike_threshold)}
		for sm in spike_master_records
	}

	qualified_demand_map = {}
	for item_code in item_codes:
		qualified_demand, _, _ = get_qualified_demand_for_item(
			item_code,
			till_today_map,
			spike_map_base,
			item_buffer_map,
			item_tog_map,
			item_type_map,
			spike_master_map,
		)
		qualified_demand_map[item_code] = qualified_demand

	data = []
	for item_code in sorted(item_codes):
		item = item_info_map[item_code]
		buffer_flag = item_buffer_map[item_code]
		sku_type = calculate_sku_type(buffer_flag, item_type_map[item_code])

		# Only include RBMTA and RBMTO
		if sku_type not in ("RBMTA", "RBMTO"):
			continue

		is_buffer = buffer_flag == "Buffer"
		tog = item_tog_map[item_code]
		stock = flt(stock_map.get(item_code, 0))
		mrq = flt(mrq_map.get(item_code, 0))
		moq = flt(item.moq or 0)
		batch_size = flt(item.batch_size or 0)

		# WIP is excluded for RBMTA and RBMTO

		if is_buffer:
			# RBMTA: TOG + qualified_demand - stock - MRQ
			qualified_demand = flt(qualified_demand_map.get(item_code, 0))
			base_order_rec = tog + qualified_demand - stock - mrq
		else:
			# RBMTO: open_so - stock - MRQ
			open_so = flt(so_qty_map.get(item_code, 0))
			base_order_rec = open_so - stock - mrq

		base_order_rec = max(0, base_order_rec)
		net_order_rec = calculate_net_order_recommendation(base_order_rec, moq, batch_size)

		data.append(
			{
				"item_code": item_code,
				"item_name": item.item_name,
				"colour": None,  # TODO: colour logic TBD
				"net_order_recommendation": math.ceil(flt(net_order_rec)),
				"sku_type": sku_type,
				"item_type": item_type_map[item_code],
				"tog": math.ceil(flt(tog)),
				"last_rolled_date": last_rolled_map.get(item_code, {}).get("last_rolled_date"),
				"last_rolled_qty": last_rolled_map.get(item_code, {}).get("last_rolled_qty"),
				"last_3_months_sale": last_3month_sale_map.get(item_code, 0),
				"last_3_months_consumption": last_3month_consumption_map.get(item_code, 0),
				"last_1_month_sale": last_1month_sale_map.get(item_code, 0),
				"last_1_month_consumption": last_1month_consumption_map.get(item_code, 0),
				"on_hand_stock": flt(stock),
				"net_qty": None,
				"sub_grp": item.sub_grp or "",
				"shape": item.shape or "",
				"subgrp_shape": " ".join(filter(None, [item.sub_grp, item.shape])),
				"subgrp_weightage": None,
				"prod_qty_based_on_child_stock": None,
				"prod_qty_based_on_child_stock_wip_open_po": None,
				"child_item_code": None,
				"child_requirement": None,
				"child_stock": None,
				"child_stock_allocation": None,
				"child_shortage": None,
				"child_item_open_po": None,
			}
		)

	return data
