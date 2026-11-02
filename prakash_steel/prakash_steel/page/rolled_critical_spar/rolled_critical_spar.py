# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, nowdate

from prakash_steel.prakash_steel.report.rolled_critical_spares.rolled_critical_spares import execute
from prakash_steel.utils.whitelist_permissions import require_all_permissions

WAREHOUSE = "Rolling Mill - PSPL"
COMPANY = "Prakash Steel Products Pvt Ltd"


@frappe.whitelist()
def get_rolled_critical_spar_data():
	columns, data = execute()
	return {"columns": columns, "data": data}


@frappe.whitelist()
def execute_material_requests(rows) -> dict:
	require_all_permissions(
		[("Material Request", "create"), ("Material Request", "submit")],
		_("Not permitted to create Material Requests from Rolled Critical Spar."),
	)
	import json

	if isinstance(rows, str):
		rows = json.loads(rows)

	created = []
	errors = []

	for row in rows:
		item_code = row.get("item_code")
		qty = flt(row.get("net_order_recommendation"))

		if not item_code or qty <= 0:
			continue

		try:
			item_doc = frappe.get_doc("Item", item_code)
			stock_uom = item_doc.stock_uom
			transaction_date = nowdate()
			schedule_date = add_days(transaction_date, cint(item_doc.lead_time_days))

			mr = frappe.new_doc("Material Request")
			mr.company = COMPANY
			mr.material_request_type = "Purchase"
			mr.transaction_date = transaction_date
			mr.schedule_date = schedule_date
			mr.append(
				"items",
				{
					"item_code": item_code,
					"qty": qty,
					"uom": stock_uom,
					"stock_uom": stock_uom,
					"conversion_factor": 1.0,
					"warehouse": WAREHOUSE,
				},
			)
			mr.insert()
			mr.submit()
			created.append(mr.name)

		except Exception as e:
			errors.append(
				f"<b>{item_code}</b>: {frappe.get_traceback() if frappe.conf.developer_mode else str(e)}"
			)

	return {"created": created, "errors": errors}
