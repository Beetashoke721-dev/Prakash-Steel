# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import IfNull
from frappe.utils import date_diff, flt, getdate

from prakash_steel.utils.whitelist_permissions import require_permission

GST_RATE = 18.0


def _build_rows(entries) -> list[dict]:
	"""Map raw Payment Entry references to Late Payment Charges rows."""
	rows = []
	for entry in entries:
		due_date = entry.get("due_date")
		bill_date = entry.get("bill_date")
		deposit_date = entry.get("deposit_date")
		amount = flt(entry.get("amount"))

		grace_period = date_diff(due_date, bill_date) if due_date and bill_date else None
		delay_of_payment = date_diff(deposit_date, due_date) if due_date and deposit_date else None

		if not delay_of_payment or delay_of_payment <= 0:
			continue

		rate = flt(entry.get("rate"))
		interest = round((amount * (rate/100) * delay_of_payment) / 365, 2)
		gst = round(flt(interest) * GST_RATE / 100.0, 2)
		total = round(flt(interest) + flt(gst), 2)

		rows.append(
			{
				"bill_no": entry.get("bill_no"),
				"customer": entry.get("customer"),
				"bill_date": entry.get("bill_date"),
				"due_date": due_date,
				"grace_period": grace_period,
				"deposit_date": deposit_date,
				"amount": amount,
				"delay_of_payment": delay_of_payment,
				"rate": rate if rate else None,
				"interest": interest,
				"gst": gst,
				"total": total,
				"late_payment_issued": entry.get("late_payment_issued") or 0,
			}
		)
	return rows


@frappe.whitelist()
def get_data(from_date=None, to_date=None, customer=None):
	require_permission("Sales Invoice", "read")
	require_permission("Payment Entry", "read")
	require_permission("Customer", "read")

	if not from_date or not to_date:
		frappe.throw(_("From Date and To Date are required."))

	start = getdate(from_date)
	end = getdate(to_date)
	if start > end:
		frappe.throw(_("From Date cannot be after To Date."))

	payment_entry = frappe.qb.DocType("Payment Entry")
	reference = frappe.qb.DocType("Payment Entry Reference")
	sales_invoice = frappe.qb.DocType("Sales Invoice")
	customer_doc = frappe.qb.DocType("Customer")

	query = (
		frappe.qb.from_(reference)
		.inner_join(payment_entry)
		.on(reference.parent == payment_entry.name)
		.inner_join(sales_invoice)
		.on(reference.reference_name == sales_invoice.name)
		.left_join(customer_doc)
		.on(sales_invoice.customer == customer_doc.name)
		.select(
			reference.reference_name.as_("bill_no"),
			sales_invoice.customer.as_("customer"),
			sales_invoice.posting_date.as_("bill_date"),
			sales_invoice.due_date.as_("due_date"),
			payment_entry.posting_date.as_("deposit_date"),
			reference.allocated_amount.as_("amount"),
			customer_doc.custom_rate.as_("rate"),
			sales_invoice.custom_late_payment_issued.as_("late_payment_issued"),
		)
		.where(reference.reference_doctype == "Sales Invoice")
		.where(reference.allocated_amount > 0)
		.where(payment_entry.docstatus == 1)
		.where(payment_entry.payment_type == "Receive")
		.where(payment_entry.posting_date.between(from_date, to_date))
		.where(IfNull(sales_invoice.custom_late_payment_issued, 0) == 0)
		.orderby(sales_invoice.name)
	)

	if customer:
		query = query.where(sales_invoice.customer == customer)

	return _build_rows(query.run(as_dict=True))


@frappe.whitelist()
def mark_issued(invoices):
	require_permission("Sales Invoice", "write")

	if isinstance(invoices, str):
		invoices = frappe.parse_json(invoices)

	if not isinstance(invoices, (list, tuple)) or not invoices:
		frappe.throw(_("Please select at least one row to save."))

	for name in invoices:
		if not isinstance(name, str) or not frappe.db.exists("Sales Invoice", name):
			frappe.throw(_("Sales Invoice {0} does not exist.").format(name))
		frappe.db.set_value("Sales Invoice", name, "custom_late_payment_issued", 1)

	return len(invoices)
