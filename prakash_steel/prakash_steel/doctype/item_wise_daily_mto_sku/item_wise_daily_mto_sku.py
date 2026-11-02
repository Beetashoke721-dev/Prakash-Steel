# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

MTO_SKU_TYPES = ("BBMTO", "RBMTO", "BOTO", "PTO")


class ItemwiseDailyMTOSKU(Document):
	pass


def save_daily_mto_sku(posting_date: str | None = None) -> None:
	"""Save each Non-Buffer (MTO) item's SKU type and Priority colour for the day.

	Uses the PO Recommendation rows for non-buffer items (the same source as the daily
	On hand colour snapshot does for buffer items). A day that's already saved is skipped.
	"""
	from prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp import execute

	posting_date = posting_date or nowdate()
	if frappe.db.exists("Item wise Daily MTO SKU", posting_date):
		return

	seen_item_codes = {}
	for filters in ({"sell": 1, "buffer_flag": 0}, {"purchase": 1, "buffer_flag": 0}):
		try:
			_, rows = execute(filters)
		except Exception:
			frappe.log_error(title="MTO SKU daily status (fetch)", message=frappe.get_traceback())
			continue
		for row in rows or []:
			item_code = row.get("item_code")
			if item_code and row.get("sku_type") in MTO_SKU_TYPES and item_code not in seen_item_codes:
				seen_item_codes[item_code] = row

	if not seen_item_codes:
		return

	try:
		doc = frappe.new_doc("Item wise Daily MTO SKU")
		doc.posting_date = posting_date
		for row in seen_item_codes.values():
			doc.append(
				"mto_sku_status",
				{
					"item_code": row["item_code"],
					"sku_type": row["sku_type"],
					"priority_colour": row.get("priority") or "",
				},
			)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="MTO SKU daily status (save)", message=frappe.get_traceback())
