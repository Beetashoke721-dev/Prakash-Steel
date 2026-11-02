from collections import defaultdict

import frappe
from frappe.utils import add_days, flt, today

from .calculations import _STATUS_PRIORITY, _PRIORITY_TO_COLOUR, _compute_order_status


def get_stock_map(item_codes: list[str]) -> dict[str, float]:
	# Item stock for planning always comes from Planning Engine Warehouse Setup only.
	return get_planning_stock_map(item_codes)


def get_planning_engine_warehouses() -> list[str]:
	doc = frappe.get_single("Planning Engine Warehouse Setup")
	return [row.warehouse for row in doc.table_cmgr if row.warehouse]


def get_warehouse_stock_map(item_codes: list[str], warehouses: list[str]) -> dict[str, float]:
	if not item_codes or not warehouses:
		return {}

	bin_rows = frappe.db.sql(
		"""
		SELECT item_code, SUM(actual_qty) as stock
		FROM `tabBin`
		WHERE item_code IN %s AND warehouse IN %s
		GROUP BY item_code
		""",
		(tuple(item_codes), tuple(warehouses)),
		as_dict=True,
	)

	return {d.item_code: flt(d.stock) for d in bin_rows}


def get_planning_stock_map(item_codes: list[str]) -> dict[str, float]:
	return get_warehouse_stock_map(item_codes, get_planning_engine_warehouses())


def get_sales_order_qty_map(filters: dict) -> dict[str, float]:
	so_rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as so_qty
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.custom_closed, 0) = 0
		GROUP BY
			soi.item_code
		""",
		as_dict=True,
	)

	return {d.item_code: flt(d.so_qty) for d in so_rows}


def get_qualified_demand_map() -> tuple[dict[str, float], dict[str, float]]:
	today_date = today()

	so_rows = frappe.db.sql(
		"""
		SELECT
			soi.item_code,
			SUM(GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0))) as so_qty
		FROM
			`tabSales Order` so
		INNER JOIN
			`tabSales Order Item` soi ON soi.parent = so.name
		WHERE
			so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
			AND so.docstatus = 1
			AND IFNULL(soi.custom_closed, 0) = 0
			AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
		GROUP BY
			soi.item_code
		""",
		(today_date,),
		as_dict=True,
	)

	till_today_map = {d.item_code: flt(d.so_qty) for d in so_rows}
	spike_map = {item_code: 0.0 for item_code in till_today_map}

	return till_today_map, spike_map


def get_draft_wo_map() -> dict[str, float]:
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


def get_wip_map() -> dict[str, float]:
	try:
		settings = frappe.get_single("Production planning settings")
	except Exception:
		settings = frappe._dict(
			{"from_work_order": 1, "from_production_plan": 0, "from_production_planning": 0}
		)

	wip_map = {}

	if settings.get("from_work_order"):
		wip_rows_wo = frappe.db.sql(
			"""
			SELECT
				wo.production_item as item_code,
				SUM(GREATEST(0, IFNULL(wo.qty, 0) - IFNULL(wo.produced_qty, 0))) as wip_qty
			FROM
				`tabWork Order` wo
			WHERE
				wo.status NOT IN ('Completed', 'Cancelled')
				AND wo.docstatus = 1
			GROUP BY
				wo.production_item
			""",
			as_dict=True,
		)

		for row in wip_rows_wo:
			wip_map[row.item_code] = flt(row.wip_qty)

	elif settings.get("from_production_plan"):
		pp_filters = {"docstatus": 1}
		production_plans = frappe.get_all("Production Plan", filters=pp_filters, fields=["name"])

		for pp in production_plans:
			pp_name = pp["name"]

			try:
				pp_doc = frappe.get_doc("Production Plan", pp_name)

				if hasattr(pp_doc, "po_items") and pp_doc.po_items:
					for po_item in pp_doc.po_items:
						item_code = po_item.item_code
						planned_qty = flt(po_item.planned_qty) if po_item.planned_qty else 0

						if not item_code:
							continue

						finished_weight_docs = frappe.db.sql(
							"""
							SELECT name, finish_weight
							FROM `tabFinish Weight`
							WHERE production_plan = %s
							AND docstatus = 1
							AND item_code = %s
							ORDER BY name
							""",
							(pp_name, item_code),
							as_dict=True,
						)

						total_finished_from_fw = sum(flt(doc.finish_weight) for doc in finished_weight_docs)

						bright_bar_production_docs = frappe.db.sql(
							"""
							SELECT name, fg_weight
							FROM `tabBright Bar Production`
							WHERE production_plan = %s
							AND docstatus = 1
							AND finished_good = %s
							ORDER BY name
							""",
							(pp_name, item_code),
							as_dict=True,
						)

						total_finished_from_bbp = sum(
							flt(doc.fg_weight) for doc in bright_bar_production_docs
						)

						total_finished = total_finished_from_fw + total_finished_from_bbp
						wip_qty = max(0, planned_qty - total_finished)

						if item_code in wip_map:
							wip_map[item_code] += wip_qty
						else:
							wip_map[item_code] = wip_qty

			except Exception:
				continue

	elif settings.get("from_production_planning"):
		wip_rows_pp = frappe.db.sql(
			"""
			SELECT
				fg.fg_item as item_code,
				SUM(
					CASE
						WHEN IFNULL(fg.closed, 0) = 1 THEN 0
						ELSE GREATEST(0, IFNULL(fg.fg_production_qty, 0) - IFNULL(fg.produced_qty, 0))
					END
				) as wip_qty
			FROM
				`tabProduction Planning FG Table` fg
			INNER JOIN
				`tabProduction Planning` pp ON pp.name = fg.parent
			WHERE
				pp.docstatus = 1
				AND fg.fg_item IS NOT NULL
			GROUP BY
				fg.fg_item
			""",
			as_dict=True,
		)

		for row in wip_rows_pp:
			wip_map[row.item_code] = flt(row.wip_qty)

	return wip_map


def get_mrq_map() -> dict[str, float]:
	mrq_rows = frappe.db.sql(
		"""
		SELECT
			mri.item_code,
			SUM(GREATEST(0, mri.qty - IFNULL(mri.ordered_qty, 0))) as mrq_qty
		FROM
			`tabMaterial Request` mr
		INNER JOIN
			`tabMaterial Request Item` mri ON mri.parent = mr.name
		WHERE
			mr.docstatus = 1
			AND mr.status IN ('Pending', 'Partially Ordered')
		GROUP BY
			mri.item_code
		""",
		as_dict=True,
	)

	mrq_map = {d.item_code: flt(d.mrq_qty) for d in mrq_rows}

	wo_rows = frappe.db.sql(
		"""
		SELECT
			production_item as item_code,
			SUM(GREATEST(0, qty - IFNULL(produced_qty, 0))) as wo_qty
		FROM
			`tabWork Order`
		WHERE
			docstatus = 0
		GROUP BY
			production_item
		""",
		as_dict=True,
	)

	for d in wo_rows:
		mrq_map[d.item_code] = mrq_map.get(d.item_code, 0) + flt(d.wo_qty)

	return mrq_map


def get_open_po_map() -> dict[str, float]:
	po_rows = frappe.db.sql(
		"""
		SELECT
			poi.item_code,
			poi.qty,
			IFNULL(poi.received_qty, 0) as received_qty
		FROM
			`tabPurchase Order` po
		INNER JOIN
			`tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE
			po.docstatus = 1
			AND po.status NOT IN ('Cancelled', 'Closed')
			AND IFNULL(poi.custom_closed, 0) = 0
		""",
		as_dict=True,
	)

	open_po_map = {}
	for row in po_rows:
		item_code = row.item_code
		open_qty = max(0, flt(row.qty) - flt(row.received_qty))
		if item_code in open_po_map:
			open_po_map[item_code] += open_qty
		else:
			open_po_map[item_code] = open_qty

	return open_po_map


def get_open_subcon_po_map() -> dict[str, float]:
	"""Open subcontracted PO qty per finished-good item.

	For every submitted, open subcontracted Purchase Order, the child row's
	``fg_item`` (not ``item_code``, which is the subcontracting service/raw
	material line) identifies the finished good being subcontracted. For
	each such row we take ``fg_item_qty - received_qty``, floored at 0 per
	row (a doc with received_qty > fg_item_qty contributes 0, not a
	negative), and sum across docs for that fg_item.
	"""
	po_rows = frappe.db.sql(
		"""
		SELECT
			poi.fg_item as item_code,
			poi.fg_item_qty,
			IFNULL(poi.received_qty, 0) as received_qty
		FROM
			`tabPurchase Order` po
		INNER JOIN
			`tabPurchase Order Item` poi ON poi.parent = po.name
		WHERE
			po.is_subcontracted = 1
			AND po.docstatus = 1
			AND po.status NOT IN ('Cancelled', 'Closed')
			AND IFNULL(poi.custom_closed, 0) = 0
			AND poi.fg_item IS NOT NULL
		""",
		as_dict=True,
	)

	open_subcon_po_map = {}
	for row in po_rows:
		item_code = row.item_code
		open_qty = max(0, flt(row.fg_item_qty) - flt(row.received_qty))
		if item_code in open_subcon_po_map:
			open_subcon_po_map[item_code] += open_qty
		else:
			open_subcon_po_map[item_code] = open_qty

	return open_subcon_po_map


def get_open_so_map_for_priority(item_codes: list[str]) -> dict[str, list[dict]]:
	if not item_codes:
		return {}
	items_tuple = tuple(item_codes)
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
		(items_tuple,),
		as_dict=True,
	)
	so_map = defaultdict(list)
	for r in result:
		so_map[r.item_code].append(
			{
				"pending_qty": flt(r.pending_qty),
				"order_status": _compute_order_status(r.delivery_date, r.transaction_date),
			}
		)
	return so_map


def calculate_spike_map(
	item_codes: list[str],
	item_buffer_map: dict[str, str],
	item_type_map: dict[str, str],
	item_tog_map: dict[str, float],
	spike_master_map: dict[str, dict] | None = None,
) -> dict[str, float]:
	today_date = today()
	spike_map = {}

	if spike_master_map is None:
		spike_master_records = frappe.get_all(
			"Spike Master", fields=["item_type", "demand_horizon", "spike_threshold"]
		)
		spike_master_map = {}
		for sm in spike_master_records:
			spike_master_map[sm.item_type] = {
				"demand_horizon": flt(sm.demand_horizon),
				"spike_threshold": flt(sm.spike_threshold),
			}

	buffer_items = [
		item_code for item_code in item_codes if item_buffer_map.get(item_code, "Non-Buffer") == "Buffer"
	]

	if not buffer_items:
		return spike_map

	buffer_items_with_details = []
	for item_code in buffer_items:
		item_type = item_type_map.get(item_code)
		tog = flt(item_tog_map.get(item_code, 0))
		if item_type and tog > 0:
			buffer_items_with_details.append(
				{"item_code": item_code, "item_type": item_type, "tog": tog}
			)

	items_by_type = {}
	for item_info in buffer_items_with_details:
		item_type = item_info["item_type"]
		if item_type not in items_by_type:
			items_by_type[item_type] = []
		items_by_type[item_type].append(item_info)

	for item_type, items_list in items_by_type.items():
		spike_config = spike_master_map.get(item_type)
		if not spike_config:
			for item_info in items_list:
				spike_map[item_info["item_code"]] = 0.0
			continue

		demand_horizon = spike_config["demand_horizon"]

		if not demand_horizon or demand_horizon <= 0:
			for item_info in items_list:
				spike_map[item_info["item_code"]] = 0.0
			continue

		start_date = add_days(today_date, 1)
		end_date = add_days(today_date, demand_horizon)
		item_codes_for_type = [item["item_code"] for item in items_list]
		item_codes_tuple = tuple(item_codes_for_type)

		if end_date:
			so_rows = frappe.db.sql(
				"""
				SELECT
					soi.item_code,
					GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) as so_qty,
					IFNULL(soi.delivery_date, '1900-01-01') as delivery_date,
					so.name as sales_order_name
				FROM
					`tabSales Order` so
				INNER JOIN
					`tabSales Order Item` soi ON soi.parent = so.name
				WHERE
					so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
					AND so.docstatus = 1
					AND IFNULL(soi.custom_closed, 0) = 0
					AND soi.item_code IN %s
					AND IFNULL(soi.delivery_date, '1900-01-01') >= %s
					AND IFNULL(soi.delivery_date, '1900-01-01') <= %s
				""",
				(item_codes_tuple, start_date, end_date),
				as_dict=True,
			)
		else:
			so_rows = frappe.db.sql(
				"""
				SELECT
					soi.item_code,
					GREATEST(0, soi.qty - IFNULL(soi.delivered_qty, 0)) as so_qty,
					IFNULL(soi.delivery_date, '1900-01-01') as delivery_date,
					so.name as sales_order_name
				FROM
					`tabSales Order` so
				INNER JOIN
					`tabSales Order Item` soi ON soi.parent = so.name
				WHERE
					so.status NOT IN ('Stopped', 'On Hold', 'Closed', 'Cancelled', 'Completed')
					AND so.docstatus = 1
					AND IFNULL(soi.custom_closed, 0) = 0
					AND soi.item_code IN %s
					AND IFNULL(soi.delivery_date, '1900-01-01') > %s
				""",
				(item_codes_tuple, today_date),
				as_dict=True,
			)

		so_by_item = {}
		for row in so_rows:
			item_code = row.item_code
			so_qty = flt(row.so_qty)
			if so_qty > 0:
				if item_code not in so_by_item:
					so_by_item[item_code] = []
				so_by_item[item_code].append(
					{
						"qty": so_qty,
						"delivery_date": row.delivery_date,
						"sales_order": row.sales_order_name,
					}
				)

		for item_info in items_list:
			item_code = item_info["item_code"]
			so_data_list = so_by_item.get(item_code, [])
			if not so_data_list:
				spike_map[item_code] = 0.0
				continue
			total_future_qty = sum(so_data["qty"] for so_data in so_data_list)
			spike_map[item_code] = total_future_qty

	for item_code in item_codes:
		if item_buffer_map.get(item_code, "Non-Buffer") != "Buffer":
			spike_map[item_code] = 0.0

	return spike_map
