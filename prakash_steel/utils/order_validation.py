import frappe
from frappe import _


def validate_no_zero_rate_items(doc, event=None) -> None:
	"""
	Raise an error if any item in the order has rate = 0.
	Applies to both Sales Order and Purchase Order.
	Works for normal save (validate) and Update Items (before_update_after_submit).
	"""
	zero_rate_rows = []

	for row in doc.get("items") or []:
		rate = frappe.utils.flt(row.get("rate"))
		if rate == 0:
			zero_rate_rows.append(
				_("Row {0}: Item {1} has Rate 0. Please set a valid rate before saving.").format(
					row.idx, frappe.bold(row.item_code or row.item_name or "")
				)
			)

	if zero_rate_rows:
		frappe.throw(
			"<br>".join(zero_rate_rows),
			title=_("Zero Rate Not Allowed"),
		)
