"""Backfill Work Order MFG-WO-2026-00113's actual_start_date.

The linked Job Card's time log rows had no from_time/to_time recorded, so the
Work Order's actual_start_date was never set even though it's Completed with a
submitted Manufacture Stock Entry. The Production Dashboard's Bright Production
query filters/derives its date from actual_start_date, so a NULL value silently
drops this Work Order from the "Bright Production" tab regardless of date range.
"""

import frappe


def execute() -> None:
	wo_name = "MFG-WO-2026-00113"

	if not frappe.db.exists("Work Order", wo_name):
		return

	posting_datetime = frappe.db.sql(
		"""
		SELECT TIMESTAMP(posting_date, posting_time)
		FROM `tabStock Entry`
		WHERE work_order = %(wo_name)s
			AND stock_entry_type = 'Manufacture'
			AND docstatus = 1
		LIMIT 1
		""",
		{"wo_name": wo_name},
	)
	if not posting_datetime or not posting_datetime[0][0]:
		return
	posting_datetime = posting_datetime[0][0]

	frappe.db.set_value(
		"Work Order",
		wo_name,
		"actual_start_date",
		posting_datetime,
		update_modified=False,
	)
	frappe.db.commit()
