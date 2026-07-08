import frappe
from frappe import _


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
