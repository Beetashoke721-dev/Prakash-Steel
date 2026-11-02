# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from erpnext.stock.doctype.quality_inspection_template.quality_inspection_template import (
	get_template_details,
)

# Factor to convert a stock UOM into Metric Tonnes (MT)
UOM_TO_MT = {"Kg": 0.001, "MT": 1, "Tonne": 1}


class TestCertificate(Document):
	def validate(self):
		self.validate_items_belong_to_invoice()
		if self.sales_invoice and self.items:
			self.quantity = get_quantity_in_mt(self.sales_invoice, [d.item_code for d in self.items])
		self.colour_code = get_colour_code([d.item_code for d in self.items])
		self.inspect_readings()

	def inspect_readings(self):
		"""Set each reading's Accepted/Rejected status the same way Quality Inspection does."""
		if not self.readings:
			return

		# Reuse ERPNext's per-reading checks (min/max, value match, acceptance formula)
		qi = frappe.new_doc("Quality Inspection")
		for reading in self.readings:
			if reading.manual_inspection:
				continue
			if reading.formula_based_criteria:
				qi.set_status_based_on_acceptance_formula(reading)
			else:
				qi.set_status_based_on_acceptance_values(reading)

	@frappe.whitelist()
	def get_item_specification_details(self):
		"""Fill Readings from the selected Quality Inspection Template."""
		self.set("readings", [])
		for d in get_template_details(self.quality_inspection_template):
			child = self.append("readings", {})
			child.update(d)
			child.status = "Accepted"
			child.parameter_group = frappe.get_value(
				"Quality Inspection Parameter", d.specification, "parameter_group"
			)

	def validate_items_belong_to_invoice(self):
		if not self.items:
			return
		if not self.sales_invoice:
			frappe.throw(_("Select a Sales Invoice before selecting Items"))

		invoice_items = set(
			frappe.get_all("Sales Invoice Item", filters={"parent": self.sales_invoice}, pluck="item_code")
		)
		invalid = [d.item_code for d in self.items if d.item_code not in invoice_items]
		if invalid:
			frappe.throw(
				_("Items {0} are not in Sales Invoice {1}").format(", ".join(invalid), self.sales_invoice)
			)


@frappe.whitelist()
def get_colour_code(items):
	"""Colour(s) of the items' Grade via Item Grade wise Colour Code, e.g. "Red+White"."""
	items = frappe.parse_json(items) if isinstance(items, str) else items
	if not items:
		return ""

	grades = frappe.get_all("Item", filters={"name": ["in", items]}, pluck="custom_grade", distinct=True)
	grades = [g for g in grades if g]
	if not grades:
		return ""

	colours = frappe.get_all(
		"Item Grade wise Colour Code",
		filters={"item_grade": ["in", grades]},
		pluck="colour_code",
		distinct=True,
		order_by="colour_code",
	)
	return ", ".join(c for c in colours if c)


@frappe.whitelist()
def get_quantity_in_mt(sales_invoice, items):
	"""Total stock qty of the given items in the Sales Invoice, converted to MT."""
	frappe.has_permission("Sales Invoice", "read", sales_invoice, throw=True)

	items = frappe.parse_json(items) if isinstance(items, str) else items
	if not items:
		return 0

	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": sales_invoice, "parenttype": "Sales Invoice", "item_code": ["in", items]},
		fields=["item_code", "stock_qty", "stock_uom"],
	)

	total, unconverted = 0.0, set()
	for row in rows:
		factor = UOM_TO_MT.get(row.stock_uom)
		if factor is None:
			unconverted.add(f"{row.item_code} ({row.stock_uom})")
			continue
		total += flt(row.stock_qty) * factor

	if unconverted:
		frappe.msgprint(
			_("Could not convert to MT, excluded from Quantity: {0}").format(", ".join(sorted(unconverted))),
			indicator="orange",
			alert=True,
		)

	return flt(total, 3)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_sales_invoice_items(doctype, txt, searchfield, start, page_len, filters):
	"""Link search for Items that are present in the given Sales Invoice."""
	sales_invoice = (filters or {}).get("sales_invoice")
	if not sales_invoice:
		return []
	frappe.has_permission("Sales Invoice", "read", sales_invoice, throw=True)

	sii = frappe.qb.DocType("Sales Invoice Item")
	query = (
		frappe.qb.from_(sii)
		.select(sii.item_code, sii.item_name)
		.where((sii.parent == sales_invoice) & (sii.parenttype == "Sales Invoice"))
		.groupby(sii.item_code, sii.item_name)
		.orderby(sii.item_code)
		.limit(page_len)
		.offset(start)
	)
	if txt:
		query = query.where(sii.item_code.like(f"%{txt}%") | sii.item_name.like(f"%{txt}%"))

	return query.run()
