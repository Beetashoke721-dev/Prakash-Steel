import math
import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_all_permissions, require_permission


@frappe.whitelist()
def get_bright_plan_data() -> list[dict]:
	require_permission("Item", "report")
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
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import (
		calculate_sku_type,
		get_wip_map,
		get_open_po_map,
		get_planning_stock_map,
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


# Export column layout — mirrors the on-screen table in bright_plan_page.js
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
	("or_with_moq_batch_size", "Production Order Recommendation"),
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
_EXPORT_DATE_FIELDS = {"planned_start_date"}


@frappe.whitelist()
def export_bright_plan_xlsx(rows=None, summary=None):
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
		summary_data.append([
			srow.get("machine", ""),
			srow.get("no_of_machines", ""),
			srow.get("process_time", ""),
		])

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
