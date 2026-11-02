# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from frappe.utils import flt


def set_total_quantity_and_amount(doc, method=None):
	"""Set parent Total Quantity / Total Amount from Stock Reconciliation Item rows."""
	total_qty = 0.0
	total_amount = 0.0

	for row in doc.get("items") or []:
		total_qty += flt(row.qty)
		total_amount += flt(row.amount)

	doc.custom_total_quantity = flt(total_qty, doc.precision("custom_total_quantity"))
	doc.custom_total_amount = flt(total_amount, doc.precision("custom_total_amount"))
