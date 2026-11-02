import frappe
from frappe.utils import cint


def is_manual_item_row_addition_restricted() -> bool:
	"""Feature flag controlled by `Item Row Restriction Setting` single doctype."""
	try:
		return (
			cint(
				frappe.db.get_single_value(
					"Item Row Restriction Setting",
					"restrict_manual_item_row_addition",
				)
			)
			== 1
		)
	except Exception:
		# If the setting DocType isn't installed/migrated yet, keep default behaviour.
		return False


@frappe.whitelist()
def get_item_row_restriction_setting() -> dict:
	"""Used by Delivery Note / Sales Invoice JS to decide whether to disable manual item row addition."""
	return {"enabled": is_manual_item_row_addition_restricted()}
