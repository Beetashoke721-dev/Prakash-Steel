import frappe
from frappe import _
from frappe.utils import flt


def validate_production_type(doc, method=None):
	"""Exactly one of Bright Production or Rolled Production must be checked."""
	bright = bool(doc.custom_bright_production)
	rolled = bool(doc.custom_rolled_production)

	if not bright and not rolled:
		frappe.throw(
			_("Please select one production type: <b>Bright Production</b> or <b>Rolled Production</b>."),
			title=_("Production Type Required"),
		)

	if bright and rolled:
		frappe.throw(
			_("Only one production type can be selected at a time: either <b>Bright Production</b> or <b>Rolled Production</b>, not both."),
			title=_("Production Type Conflict"),
		)


def get_total_consumed_qty(doc):
	return sum(flt(row.consumed_qty) for row in (doc.required_items or []))


def calculate_custom_wastage(doc, method=None):
	"""Set custom_wastage from produced_qty and total consumed raw material."""
	consumed_qty = get_total_consumed_qty(doc)
	produced_qty = flt(doc.produced_qty)

	if doc.produced_qty in (None, "") or consumed_qty == 0:
		doc.custom_wastage = None
		return

	doc.custom_wastage = flt(
		abs((produced_qty / consumed_qty) * 100 - 100),
		frappe.get_precision("Work Order", "custom_wastage") or 2,
	)


def calculate_cutting_weight_for_rolled_production(doc, method=None):
	"""Set custom_cutting_weight for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_cutting_weight = None
		return

	total_billet_cutting_pcs = flt(doc.custom_total_billet_cutting_pcs) or 0
	if total_billet_cutting_pcs <= 0:
		doc.custom_cutting_weight = None
		return

	consumed_qty = get_total_consumed_qty(doc)
	doc.custom_cutting_weight = consumed_qty / total_billet_cutting_pcs


def calculate_total_raw_material_pcs(doc, method=None):
	"""Set custom_total_raw_material_pcs for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_total_raw_material_pcs = None
		return

	doc.custom_total_raw_material_pcs = (
		flt(doc.custom_total_billet_cutting_pcs) + flt(doc.custom_miss_billet_pcs)
	)


def validate_miss_billet_weight(doc, method=None):
	"""Require custom_miss_billet_weight when custom_miss_billet_pcs > 0."""
	miss_billet_pcs = flt(doc.custom_miss_billet_pcs) or 0
	miss_billet_weight = flt(doc.custom_miss_billet_weight) or 0

	if miss_billet_pcs > 0 and miss_billet_weight <= 0:
		frappe.throw(
			_("Miss Billet Weight is mandatory when Miss Billet Pcs is greater than 0."),
			title=_("Validation Error"),
		)


def update_custom_wastage_after_stock_entry(doc, method=None):
	"""Persist custom_wastage after stock entries update Work Order quantities."""
	if not doc.work_order:
		return

	wo = frappe.get_doc("Work Order", doc.work_order)
	calculate_custom_wastage(wo)
	frappe.db.set_value(
		"Work Order",
		doc.work_order,
		"custom_wastage",
		wo.custom_wastage,
		update_modified=False,
	)


def copy_production_type_to_job_card(doc, method=None):
	"""Copy production type checkboxes from the parent Work Order to this Job Card."""
	if not doc.work_order:
		return

	wo = frappe.db.get_value(
		"Work Order",
		doc.work_order,
		["custom_bright_production", "custom_rolled_production"],
		as_dict=True,
	)

	if not wo:
		return

	frappe.db.set_value(
		"Job Card",
		doc.name,
		{
			"custom_bright_production": wo.custom_bright_production,
			"custom_rolled_production": wo.custom_rolled_production,
		},
		update_modified=False,
	)


def lock_production_type_from_work_order(doc, method=None):
	"""Keep Job Card production type in sync with the linked Work Order."""
	if not doc.work_order:
		return

	wo = frappe.db.get_value(
		"Work Order",
		doc.work_order,
		["custom_bright_production", "custom_rolled_production"],
		as_dict=True,
	)

	if not wo:
		return

	doc.custom_bright_production = wo.custom_bright_production
	doc.custom_rolled_production = wo.custom_rolled_production


def validate_job_card_time_log_miss_fields(doc, method=None):
	"""Enforce miss-roll and miss-ingot dependent fields on Job Card time logs."""
	for index, row in enumerate(doc.time_logs or [], start=1):
		row.custom_total = (
			flt(row.custom_finish_item) + flt(row.custom_miss_roll) + flt(row.custom_miss_ingot_or_billet)
		)

		row_label = _("Row {0}").format(index)

		if flt(row.custom_miss_roll) > 0:
			if not row.custom_miss_roll_weight:
				frappe.throw(
					_("{0}: Miss Roll Weight is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
			if not row.custom_summary_remarks:
				frappe.throw(
					_("{0}: Summary Remarks is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
		else:
			row.custom_miss_roll_weight = None

		if flt(row.custom_miss_ingot_or_billet) > 0:
			if not row.custom_miss_ingot_or_billet_weight:
				frappe.throw(
					_(
						"{0}: Miss Ingot / Billet Weight is mandatory when Miss Ingot / Billet (Pcs) is greater than 0."
					).format(row_label)
				)
			if not row.custom_reason_for_miss_ingot_or_billet:
				frappe.throw(
					_(
						"{0}: Reason for Miss Ingot / Billet is mandatory when Miss Ingot / Billet (Pcs) is greater than 0."
					).format(row_label)
				)
		else:
			row.custom_miss_ingot_or_billet_weight = None
			row.custom_reason_for_miss_ingot_or_billet = None
