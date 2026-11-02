import frappe
from frappe import _
from frappe.utils import flt, getdate

from prakash_steel.prakash_steel.page.basic_rate.basic_rate import (
	component_rate,
	submitted_rate_doc_asof,
)


def _bypassed_users() -> set:
	"""Users listed in Rate Permission Settings who may submit below the floor."""
	settings = frappe.get_cached_doc("Rate Permission Settings")
	return {row.user for row in settings.get("table_nhsr") or []}


def _rate_floor_violations(doc) -> list:
	"""Item rows on `doc` priced below the floor, as formatted messages.

	The floor for each item is computed from the most recent *submitted* Basic
	Rate Structure dated on or before the Sales Order's transaction date - a
	draft rate structure created for today (or a future date) is ignored, so the
	check falls back to the previous submitted day, and the one before that, etc.

	For every item we read ``custom_grade`` + ``custom_shape`` (to pick the rate
	rule) and ``custom_rate_component`` (to pick the offset within that rule).
	Items without a rate component, or whose grade/shape/component is not part of
	the rate structure, are left alone. Pure read - never throws or prompts.
	"""
	items = doc.get("items") or []
	if not items:
		return []

	rate_doc = submitted_rate_doc_asof(getdate(doc.transaction_date))
	if not rate_doc:
		return []

	item_codes = list({row.item_code for row in items if row.item_code})
	if not item_codes:
		return []

	item_meta = {
		d.name: d
		for d in frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=["name", "custom_grade", "custom_shape", "custom_rate_component"],
		)
	}

	violations = []
	for row in items:
		meta = item_meta.get(row.item_code)
		if not meta or not meta.custom_rate_component:
			continue

		floor = component_rate(
			rate_doc, meta.custom_grade, meta.custom_shape, meta.custom_rate_component
		)
		if floor is None:
			continue

		# small tolerance so precision-2 float noise never trips the check
		if flt(row.rate) < flt(floor) - 0.005:
			violations.append(
				_(
					"Row {0}: {1} rate {2} is below the minimum {3} "
					"(Basic Rate Structure dated {4})."
				).format(
					row.idx,
					frappe.bold(row.item_code or row.item_name or ""),
					flt(row.rate),
					flt(floor),
					frappe.format(rate_doc.date, {"fieldtype": "Date"}),
				)
			)

	return violations


def validate_item_rate_floor(doc, event=None) -> None:
	"""Block Sales Order items priced below the last approved Basic Rate Structure.

	Runs at submit time (before_submit / before_update_after_submit), not on a
	plain save - anyone can save a Sales Order with any rate, but submitting it
	is blocked unless the rate meets the floor. Users listed in the "Rate Bypass
	table" of the (single) Rate Permission Settings doctype skip this check
	entirely - the client shows them a confirmation dialog before the submit
	request is even sent (see get_rate_floor_warnings + sales_order.js).
	"""
	if frappe.session.user in _bypassed_users():
		return

	violations = _rate_floor_violations(doc)
	if violations:
		frappe.throw("<br>".join(violations), title=_("Rate Below Minimum"))


@frappe.whitelist()
def get_rate_floor_warnings(sales_order):
	"""Below-floor rows for a not-yet-submitted Sales Order, for the bypass-user
	confirmation dialog shown client-side right before submit.

	Returns an empty list for anyone not in the bypass list - those users are
	hard blocked by validate_item_rate_floor regardless, so no prompt is needed.
	"""
	if frappe.session.user not in _bypassed_users():
		return {"warnings": []}

	if isinstance(sales_order, str):
		sales_order = frappe.parse_json(sales_order)

	doc = frappe.get_doc(sales_order)
	return {"warnings": _rate_floor_violations(doc)}
