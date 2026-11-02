# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class ItemwiseDailyCSColour(Document):
	pass


def save_daily_cs_colour(posting_date: str | None = None) -> None:
	"""Save each Bright and Rolled Critical Spares item's On Hand Colour for the day, in one
	uniform doctype (child rows tagged by cs_type), so past Bright/Rolled CS
	Availability/Black/Red/White % can be read later for the weekly register.

	Uses the Bright/Rolled Critical Spares reports' own rows. Runs daily from the
	scheduler. A day that's already saved is skipped.
	"""
	from prakash_steel.prakash_steel.report.bright_critical_spares.bright_critical_spares import (
		get_data as get_bright_cs_rows,
	)
	from prakash_steel.prakash_steel.report.rolled_critical_spares.rolled_critical_spares import (
		get_data as get_rolled_cs_rows,
	)

	posting_date = posting_date or nowdate()
	if frappe.db.exists("Item wise Daily CS Colour", posting_date):
		return

	rows_by_type = {}
	for cs_type, get_rows in (("Bright", get_bright_cs_rows), ("Rolled", get_rolled_cs_rows)):
		try:
			rows_by_type[cs_type] = get_rows()
		except Exception:
			frappe.log_error(title=f"CS Colour daily status (fetch {cs_type})", message=frappe.get_traceback())

	if not any(rows_by_type.values()):
		return

	try:
		doc = frappe.new_doc("Item wise Daily CS Colour")
		doc.posting_date = posting_date
		for cs_type, rows in rows_by_type.items():
			for row in rows or []:
				item_code = row.get("item_code")
				if not item_code:
					continue
				doc.append(
					"cs_colour_status",
					{
						"item_code": item_code,
						"cs_type": cs_type,
						"on_hand_colour": row.get("on_hand_colour") or "",
					},
				)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="CS Colour daily status (save)", message=frappe.get_traceback())
