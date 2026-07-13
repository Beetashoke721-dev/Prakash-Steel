import frappe
from frappe import _
from frappe.utils import cint, flt


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
	"""Set custom_wastage from produced_qty and total consumed raw material (Bright only)."""
	if not bool(doc.custom_bright_production):
		doc.custom_wastage = None
		return

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


def calculate_burning_loss_for_rolled_production(doc, method=None):
	"""Set custom_burning_loss for rolled production work orders."""
	if not bool(doc.custom_rolled_production):
		doc.custom_burning_loss = None
		return

	consumed_qty = get_total_consumed_qty(doc)
	if consumed_qty <= 0:
		doc.custom_burning_loss = None
		return

	miss_billet_weight = flt(doc.custom_miss_billet_weight) or 0
	produced_qty = flt(doc.produced_qty) or 0

	doc.custom_burning_loss = flt(
		abs(((consumed_qty - miss_billet_weight - produced_qty) / consumed_qty) * 100),
		frappe.get_precision("Work Order", "custom_burning_loss") or 2,
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
	"""Persist calculated Work Order fields after stock entries update quantities."""
	if not doc.work_order:
		return

	wo = frappe.get_doc("Work Order", doc.work_order)
	calculate_custom_wastage(wo)
	calculate_cutting_weight_for_rolled_production(wo)
	calculate_burning_loss_for_rolled_production(wo)
	frappe.db.set_value(
		"Work Order",
		doc.work_order,
		{
			"custom_wastage": wo.custom_wastage,
			"custom_cutting_weight": wo.custom_cutting_weight,
			"custom_burning_loss": wo.custom_burning_loss,
		},
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


def _time_log_used_pcs(row) -> float:
	return flt(row.custom_finish_item) + flt(row.custom_miss_roll) + flt(row.custom_miss_ingot_or_billet)


def get_submitted_job_card_used_pcs(work_order: str, exclude_job_card: str | None = None) -> float:
	"""Sum used pcs from submitted Job Card time logs for a Work Order."""
	if not work_order:
		return 0.0

	conditions = ["jc.work_order = %(work_order)s", "jc.docstatus = 1"]
	values = {"work_order": work_order}

	if exclude_job_card:
		conditions.append("jc.name != %(exclude_job_card)s")
		values["exclude_job_card"] = exclude_job_card

	used = frappe.db.sql(
		f"""
		SELECT SUM(
			IFNULL(tl.custom_finish_item, 0)
			+ IFNULL(tl.custom_miss_roll, 0)
			+ IFNULL(tl.custom_miss_ingot_or_billet, 0)
		)
		FROM `tabJob Card Time Log` tl
		INNER JOIN `tabJob Card` jc ON jc.name = tl.parent
		WHERE {" AND ".join(conditions)}
		""",
		values,
	)

	return flt(used[0][0]) if used and used[0][0] is not None else 0.0


@frappe.whitelist()
def get_job_card_billet_cutting_context(work_order: str, exclude_job_card: str | None = None) -> dict:
	"""Return Work Order pool and already-used pcs for Job Card remaining calculation."""
	if not work_order:
		return {"pool": None, "other_used": 0, "is_rolled": 0}

	wo = frappe.db.get_value(
		"Work Order",
		work_order,
		["custom_rolled_production", "custom_total_raw_material_pcs"],
		as_dict=True,
	)
	if not wo or not wo.custom_rolled_production:
		return {"pool": None, "other_used": 0, "is_rolled": 0}

	return {
		"pool": flt(wo.custom_total_raw_material_pcs),
		"other_used": get_submitted_job_card_used_pcs(work_order, exclude_job_card),
		"is_rolled": 1,
	}


def calculate_job_card_time_log_billet_cutting(doc, method=None):
	"""
	Set custom_total_billet_cutting per time log as remaining pcs before that row.

	remaining = WO.custom_total_raw_material_pcs
	           - submitted Job Card usage (same WO, excluding this Job Card)
	           - earlier rows' custom_total on this Job Card
	"""
	is_rolled = bool(doc.custom_rolled_production)
	if not is_rolled and doc.work_order:
		is_rolled = bool(
			frappe.db.get_value("Work Order", doc.work_order, "custom_rolled_production")
		)

	if not doc.work_order or not is_rolled:
		for row in doc.time_logs or []:
			row.custom_total_billet_cutting = None
		return

	pool = flt(
		frappe.db.get_value("Work Order", doc.work_order, "custom_total_raw_material_pcs")
	)
	other_used = get_submitted_job_card_used_pcs(
		doc.work_order, None if doc.is_new() else doc.name
	)

	running_used = 0.0
	for index, row in enumerate(doc.time_logs or [], start=1):
		row.custom_total = _time_log_used_pcs(row)
		remaining = pool - other_used - running_used
		row.custom_total_billet_cutting = remaining

		row_used = flt(row.custom_total)
		if remaining < 0 or row_used > remaining:
			over_by = abs(remaining) if remaining < 0 else (row_used - remaining)
			frappe.throw(
				_(
					"Row {0}: No pieces left! You are trying to use {1} more pieces than available. "
					"Please reduce the quantities."
				).format(index, flt(over_by, 0)),
				title=_("Billet Cutting Pcs Exceeded"),
			)

		running_used += row_used


def calculate_job_card_finish_pcs(doc, method=None):
	"""Set custom_finish_pcs as the sum of custom_finish_item across time_logs."""
	doc.custom_finish_pcs = sum(cint(row.custom_finish_item) for row in (doc.time_logs or []))


def calculate_job_card_miss_pcs(doc, method=None):
	"""Set Job Card miss totals from time log miss pcs fields."""
	doc.custom_total_miss_roll = sum(cint(row.custom_miss_roll) for row in (doc.time_logs or []))
	doc.custom_total_miss_ingot_or_billet = sum(
		cint(row.custom_miss_ingot_or_billet) for row in (doc.time_logs or [])
	)


def calculate_job_card_fg_per_pcs_weight(doc, method=None):
	"""Set custom_fg_per_pcs_weight = round(total_completed_qty / custom_finish_pcs, 2)."""
	finish_pcs = cint(doc.custom_finish_pcs)
	if finish_pcs > 0 and flt(doc.total_completed_qty):
		doc.custom_fg_per_pcs_weight = flt(flt(doc.total_completed_qty) / finish_pcs, 2)
	else:
		doc.custom_fg_per_pcs_weight = 0


def set_job_card_colour_code(doc, method=None):
	"""Set custom_colour_code from production_item grade via Item Grade wise Colour Code."""
	if not doc.production_item:
		doc.custom_colour_code = None
		return

	grade = frappe.db.get_value("Item", doc.production_item, "custom_grade")
	if not grade:
		doc.custom_colour_code = None
		return

	doc.custom_colour_code = frappe.db.get_value(
		"Item Grade wise Colour Code",
		{"item_grade": grade},
		"colour_code",
	)


def calculate_job_card_billet_weight(doc, method=None):
	"""Set custom_billet_weight from linked Work Order miss billet weight + consumed qty.

	Skip after submit so WO consumption growth cannot change a locked Job Card field.
	"""
	if doc.docstatus == 1:
		return

	if not doc.work_order:
		doc.custom_billet_weight = 0
		return

	miss_billet_weight = flt(
		frappe.db.get_value("Work Order", doc.work_order, "custom_miss_billet_weight")
	)
	consumed_qty = flt(
		frappe.db.sql(
			"""
			SELECT SUM(IFNULL(consumed_qty, 0))
			FROM `tabWork Order Item`
			WHERE parent = %s
			""",
			doc.work_order,
		)[0][0]
	)
	doc.custom_billet_weight = cint(miss_billet_weight + consumed_qty)


def validate_job_card_time_log_miss_fields(doc, method=None):
	"""Enforce miss-roll and miss-ingot dependent fields on Job Card time logs."""
	for index, row in enumerate(doc.time_logs or [], start=1):
		row.custom_total = _time_log_used_pcs(row)

		row_label = _("Row {0}").format(index)

		if flt(row.custom_miss_roll) > 0:
			if not row.custom_miss_roll_weight:
				frappe.throw(
					_("{0}: Miss Roll Weight is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
			if not row.custom_reason_for_miss_roll:
				frappe.throw(
					_("{0}: Reason for Miss Roll is mandatory when Miss Roll (Pcs) is greater than 0.").format(
						row_label
					)
				)
		else:
			row.custom_miss_roll_weight = None
			row.custom_reason_for_miss_roll = None

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
