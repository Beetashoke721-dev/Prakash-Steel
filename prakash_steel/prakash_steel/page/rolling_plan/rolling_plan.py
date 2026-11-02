import json

import frappe
from frappe import _
from frappe.utils import flt, format_datetime

from prakash_steel.prakash_steel.report.rolled_plan.rolled_plan import execute, get_columns
from prakash_steel.prakash_steel.report.rolling_machine_load.rolling_machine_load import get_machine
from prakash_steel.utils.whitelist_permissions import require_all_permissions, require_permission

# Defaults taken from the submitted rolled Work Orders already in the system.
COMPANY = "Prakash Steel Products Pvt Ltd"
WIP_WAREHOUSE = "Work In Progress - PSPL"
ROLLING_MILL_WAREHOUSE = "Rolling Mill - PSPL"


@frappe.whitelist()
def get_rolling_plan_data(filters=None) -> dict:
	"""Thin wrapper around the Rolled Plan report — same columns, same logic.
	The page just renders the report output as a colourful grid. `machine` is the
	Rolling Machine single (name / no of machines / runtime) for the
	"Tomorrow's Plan" machine-load panel."""
	require_permission("Item", "report")

	if isinstance(filters, str):
		filters = json.loads(filters) if filters else {}

	columns, data = execute(filters or {})
	machine = get_machine()
	return {
		"columns": columns,
		"data": data,
		"machine": {
			"machine_name": machine["machine_name"],
			"no_of_machines": machine["no_of_machines"],
			"runtime": machine["runtime"],
		},
	}


@frappe.whitelist()
def export_rolling_plan_xlsx(rows=None):
	"""Download the currently-displayed Rolling Plan rows as a single-sheet .xlsx.
	Column layout mirrors the on-screen table (the report's own get_columns(),
	hidden columns dropped); `rows` is the client's filtered view so the file
	matches exactly what the user sees."""
	from io import BytesIO

	import xlsxwriter

	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Item", "report")

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	rows = rows or []

	export_columns = [c for c in get_columns() if not c.get("hidden")]

	def _fmt(col, value):
		if value is None or value == "":
			return ""
		if col.get("fieldtype") == "Date":
			return format_datetime(value, "dd-MM-yyyy")
		return value

	sheet = [[c["label"] for c in export_columns]]
	for row in rows:
		sheet.append([_fmt(c, row.get(c["fieldname"])) for c in export_columns])

	xlsx_file = BytesIO()
	wb = xlsxwriter.Workbook(xlsx_file, {"constant_memory": True})
	make_xlsx(sheet, "Rolling Plan", wb=wb)
	wb.close()
	xlsx_file.seek(0)

	frappe.response["filename"] = "Rolling Plan.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


def _get_bom_for_row(item_code, child_item_code):
	"""BOM to produce `item_code`: prefer the active BOM containing the row's child
	item (a Rolled Plan row is one parent x one BOM child), else the default BOM."""
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
			ORDER BY b.is_default DESC
			LIMIT 1
			""",
			(item_code, child_item_code),
		)
		if result:
			return result[0][0]

	return frappe.db.get_value(
		"BOM",
		{"item": item_code, "is_default": 1, "is_active": 1, "docstatus": 1},
		"name",
	)


@frappe.whitelist()
def execute_work_orders(rows) -> dict:
	"""Create one draft rolled Work Order per selected Rolling Plan row, for the
	row's planned qty (`plan_qty`), on the Rolling Machine workstation. Left as
	draft on purpose — the user reviews and submits each one."""
	require_all_permissions(
		[("Work Order", "create"), ("Work Order", "write")],
		_("Not permitted to create Work Orders from Rolling Plan."),
	)

	if isinstance(rows, str):
		rows = json.loads(rows)

	machine_name = get_machine()["machine_name"]
	workstation = machine_name if frappe.db.exists("Workstation", machine_name) else None

	created = []
	errors = []

	for row in rows or []:
		item_code = row.get("item_code")
		qty = flt(row.get("plan_qty"))

		if not item_code or qty <= 0:
			continue

		bom_no = _get_bom_for_row(item_code, row.get("child_item_code"))
		if not bom_no:
			errors.append(f"No active BOM found for <b>{item_code}</b>")
			continue

		# Wrap each Work Order in a savepoint: if the save fails, roll the
		# insert back too so a failed row never leaves an orphan draft behind.
		savepoint = "rp_wo_" + frappe.generate_hash(length=8)
		frappe.db.savepoint(savepoint)
		try:
			wo = frappe.new_doc("Work Order")
			wo.production_item = item_code
			wo.bom_no = bom_no
			wo.qty = qty
			wo.company = COMPANY
			wo.wip_warehouse = WIP_WAREHOUSE
			wo.fg_warehouse = ROLLING_MILL_WAREHOUSE
			wo.source_warehouse = ROLLING_MILL_WAREHOUSE
			wo.update_consumed_material_cost_in_project = 1
			wo.custom_rolled_production = 1
			wo.custom_shift_type = row.get("shift_type") or ""
			wo.custom_machine_name = machine_name

			planned_start_date = row.get("planned_start_date")
			if planned_start_date:
				wo.planned_start_date = planned_start_date

			wo.insert()
			# Operations are only fetched by this call (normally the form's JS).
			wo.set_work_order_operations()
			# required_items come in with each item's own default warehouse —
			# rolled production always consumes from the Rolling Mill.
			for item in wo.required_items:
				item.source_warehouse = ROLLING_MILL_WAREHOUSE
			if workstation:
				for operation in wo.operations:
					operation.workstation = workstation
			wo.save()
			created.append(wo.name)

		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			errors.append(
				f"<b>{item_code}</b>: {frappe.get_traceback() if frappe.conf.developer_mode else str(e)}"
			)

	return {"created": created, "errors": errors}
