# Copyright (c) 2026, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate


class ItemwiseDailyBrightMachineLoad(Document):
	pass


def save_daily_bright_machine_load(posting_date: str | None = None) -> None:
	"""Save each Bright Machine's Net Order Load (days) for the day, so past load can be
	read later for the weekly register (Bright Machine Net SO Load rows).

	Uses the Bright Machine Load report's own numbers. Runs daily from the scheduler.
	A day that's already saved is skipped.
	"""
	from prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load import get_data

	posting_date = posting_date or nowdate()
	if frappe.db.exists("Item wise Daily Bright Machine Load", posting_date):
		return

	try:
		rows = get_data()
	except Exception:
		frappe.log_error(title="Bright Machine Load daily status (fetch)", message=frappe.get_traceback())
		return

	if not rows:
		return

	try:
		doc = frappe.new_doc("Item wise Daily Bright Machine Load")
		doc.posting_date = posting_date
		for row in rows:
			machine_name = row.get("machine_name")
			if not machine_name:
				continue
			doc.append(
				"machine_load_status",
				{
					"machine_name": machine_name,
					"net_order_load": row.get("net_order_load"),
				},
			)
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(title="Bright Machine Load daily status (save)", message=frappe.get_traceback())
