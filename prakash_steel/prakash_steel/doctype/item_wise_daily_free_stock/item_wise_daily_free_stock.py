# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class ItemwiseDailyFreeStock(Document):
	pass


# (child table fieldname, report module) - each report's get_data() gives the
# same rows the Bright/Rolled/BO/Traded Free Stock reports show by default.
FREE_STOCK_REPORTS = (
	("bright_free_stock", "prakash_steel.prakash_steel.report.bright_free_stock.bright_free_stock"),
	("rolled_free_stock", "prakash_steel.prakash_steel.report.rolled_free_stock.rolled_free_stock"),
	("bo_free_stock", "prakash_steel.prakash_steel.report.bo_free_stock.bo_free_stock"),
	("traded_free_stock", "prakash_steel.prakash_steel.report.traded_free_stock.traded_free_stock"),
)


def save_daily_free_stock(posting_date: str | None = None) -> None:
	"""Save each item's Free Stock (item code, SKU type, free stock) from the
	Bright, Rolled, BO and Traded Free Stock reports for the day, one child
	table per report, so how much free stock was left on any past day can be
	read later.

	Runs daily from the scheduler. A day that's already saved is skipped. One
	report failing is logged and doesn't stop the others from being saved.
	"""
	posting_date = posting_date or nowdate()
	if frappe.db.exists("Item wise Daily Free Stock", posting_date):
		return

	rows_by_table = {}
	for table_field, module in FREE_STOCK_REPORTS:
		try:
			rows_by_table[table_field] = frappe.get_module(module).get_data()
		except Exception:
			frappe.log_error(title=f"Daily Free Stock (fetch {table_field})", message=frappe.get_traceback())

	if not any(rows_by_table.values()):
		return

	try:
		doc = frappe.new_doc("Item wise Daily Free Stock")
		doc.posting_date = posting_date
		for table_field, rows in rows_by_table.items():
			for row in rows or []:
				item_code = row.get("item_code")
				if not item_code:
					continue
				doc.append(
					table_field,
					{
						"item_code": item_code,
						"sku_type": row.get("sku_type") or "",
						"free_stock": flt(row.get("free_stock")),
					},
				)
		# System-only scheduler job; the doctype itself is System Manager-only.
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="Daily Free Stock (save)", message=frappe.get_traceback())
