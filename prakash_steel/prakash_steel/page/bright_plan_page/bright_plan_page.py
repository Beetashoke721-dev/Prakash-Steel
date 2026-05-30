import math
import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_bright_plan_data():
	from prakash_steel.prakash_steel.report.bright_plan.bright_plan import execute

	columns, data = execute()

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

	# Build child options for all parent items
	parent_items = list(set(r.get("item_code") for r in data if r.get("item_code")))
	child_options = _build_child_options(parent_items)

	return {
		"columns": columns,
		"data": data,
		"machine_groups": machine_groups,
		"child_options": child_options,
	}


def _build_child_options(parent_items):
	"""Return {parent_item_code: [{child_item_code, child_bom_qty, child_bom_quantity,
	child_stock, child_wip_open_po, child_sku_type}, ...]} for all active BOMs."""
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
		calculate_sku_type,
		get_wip_map,
		get_open_po_map,
	)

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
		stock_rows = frappe.db.sql(
			"""
			SELECT item_code, CEIL(SUM(actual_qty)) AS stock
			FROM `tabBin`
			WHERE item_code IN %(items)s
			GROUP BY item_code
			""",
			{"items": child_items},
			as_dict=True,
		)
		stock_map = {r.item_code: flt(r.stock) for r in stock_rows}
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


@frappe.whitelist()
def execute_work_orders(rows):

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

		try:
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

			wo = frappe.new_doc("Work Order")
			wo.production_item = item_code
			wo.bom_no = bom_no
			wo.qty = qty
			wo.company = "Prakash Steel Products Pvt Ltd"
			wo.wip_warehouse = "Work In Progress - PSPL"
			wo.fg_warehouse = "Bright Bar Unit - PSPL"
			wo.source_warehouse = "Bright Bar Unit - PSPL"
			wo.update_consumed_material_cost_in_project = 1
			wo.insert()
			# wo.submit()
			created.append(wo.name)

		except Exception as e:
			errors.append(
				f"<b>{item_code}</b>: {frappe.get_traceback() if frappe.conf.developer_mode else str(e)}"
			)

	return {"created": created, "errors": errors}
