# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class BilletCuttingRateCalculation(Document):
	def validate(self):
		self.set_fields_from_work_order_required_items()
		self.calculate_amount()

	def set_fields_from_work_order_required_items(self):
		values = get_required_item_values(self.work_order)
		self.raw_material_item = values.get("raw_material_item")
		self.billet_weight = values.get("billet_weight")

	def calculate_amount(self):
		self.amount = flt(self.billet_weight) * flt(self.rate)


@frappe.whitelist()
def get_required_item_values(work_order=None):
	"""Return first Required Item item_code and total consumed_qty for a Work Order."""
	if not work_order:
		return {"raw_material_item": None, "billet_weight": None}

	frappe.has_permission("Work Order", "read", throw=True)

	rows = frappe.get_all(
		"Work Order Item",
		filters={"parent": work_order, "parenttype": "Work Order"},
		fields=["item_code", "consumed_qty"],
		order_by="idx asc",
	)

	if not rows:
		return {"raw_material_item": None, "billet_weight": 0}

	return {
		"raw_material_item": rows[0].item_code,
		"billet_weight": cint(sum(flt(row.consumed_qty) for row in rows)),
	}
