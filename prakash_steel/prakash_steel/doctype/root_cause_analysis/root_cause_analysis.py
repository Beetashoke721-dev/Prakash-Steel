# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RootCauseAnalysis(Document):
	pass


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_invoice_items(doctype, txt, searchfield, start, page_len, filters):
	sales_invoice = filters.get("sales_invoice")
	if not sales_invoice:
		return []

	return frappe.db.sql(
		"""
		SELECT DISTINCT si_item.item_code, item.item_name
		FROM `tabSales Invoice Item` si_item
		LEFT JOIN `tabItem` item ON item.name = si_item.item_code
		WHERE si_item.parent = %(sales_invoice)s
			AND (si_item.item_code LIKE %(txt)s OR IFNULL(item.item_name, '') LIKE %(txt)s)
		ORDER BY si_item.idx
		LIMIT %(start)s, %(page_len)s
		""",
		{
			"sales_invoice": sales_invoice,
			"txt": f"%{txt}%",
			"start": start,
			"page_len": page_len,
		},
	)
