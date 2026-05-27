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

	return {"columns": columns, "data": data, "machine_groups": machine_groups}


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
			bom_no = frappe.db.get_value(
				"BOM",
				{"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
				"name",
			)
			if not bom_no:
				errors.append(f"No default active BOM found for <b>{item_code}</b>")
				continue

			wo = frappe.new_doc("Work Order")
			wo.production_item = item_code
			wo.bom_no = bom_no
			wo.qty = qty
			wo.company = "Prakash Steel Products Pvt Ltd"
			wo.wip_warehouse = "Work In Progress - PSPL"
			wo.fg_warehouse = "Bright Bar Unit - PSPL"
			wo.source_warehouse = "New Godown - PSPL"
			wo.update_consumed_material_cost_in_project = 1
			wo.insert()
			wo.submit()
			created.append(wo.name)

		except Exception as e:
			errors.append(
				f"<b>{item_code}</b>: {frappe.get_traceback() if frappe.conf.developer_mode else str(e)}"
			)

	return {"created": created, "errors": errors}
