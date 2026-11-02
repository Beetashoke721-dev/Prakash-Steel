# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import json

import frappe

from prakash_steel.prakash_steel.report.rolled_bar_batch_recommendation.rolled_bar_batch_recommendation import (
	execute as _execute_report,
)
from prakash_steel.utils.hbt_utils import get_period_range
from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_rolled_bar_batch_rec_data(item_code: str | None = None, item_type: str | None = None, sku_type: str | None = None) -> dict:
	require_permission("Item", "read")

	filters = {}
	if item_code:
		filters["item_code"] = item_code
	if item_type:
		filters["item_type"] = item_type
	if sku_type:
		filters["sku_type"] = sku_type

	columns, data = _execute_report(filters)

	from_date, to_date = get_period_range("RB Batch Planning Setting")
	period_label = f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')}"

	fos = frappe.db.get_single_value("RB Batch Planning Setting", "fos") or 0

	return {"columns": columns, "data": data, "period_label": period_label, "fos": fos}


@frappe.whitelist()
def export_rolled_bar_batch_rec_xlsx(data, columns, filename="Rolled_Bar_Batch_Recommendation"):
	from frappe.utils.xlsxutils import build_xlsx_response

	rows_data = json.loads(data) if isinstance(data, str) else data
	cols = json.loads(columns) if isinstance(columns, str) else columns

	headers = [c.get("label") for c in cols]
	rows = [headers] + [
		[r.get(c.get("fieldname")) for c in cols]
		for r in rows_data
	]
	build_xlsx_response(rows, filename)
