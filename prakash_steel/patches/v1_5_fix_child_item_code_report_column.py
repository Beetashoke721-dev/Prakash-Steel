"""Saved views of "PO Recomendation for PSP" pin a snapshot of column defs
(fieldname, fieldtype, options, ...) in Report.json at save time. The report's
child_item_code column used to be fieldtype "Link" (options "Item"), which
made the grid render "item_code: item_name" instead of just the item code.
columns.py now defines it as "Data", but existing saved Report docs still
carry the old Link snapshot — this backfills those.
"""

import json

import frappe


def execute() -> None:
	reports = frappe.get_all("Report", filters={"json": ["is", "set"]}, fields=["name", "json"])

	for report in reports:
		try:
			data = json.loads(report.json)
		except (TypeError, ValueError):
			continue

		columns = data.get("columns")
		if not columns:
			continue

		changed = False
		for col in columns:
			if not isinstance(col, dict):
				# Report Builder-style columns store [fieldname, label, fieldtype, width]
				# lists instead of dicts — not relevant to this fix, skip them.
				continue
			if col.get("fieldname") == "child_item_code" and (
				col.get("fieldtype") != "Data" or "options" in col
			):
				col["fieldtype"] = "Data"
				col.pop("options", None)
				changed = True

		if changed:
			frappe.db.set_value("Report", report.name, "json", json.dumps(data), update_modified=False)

	frappe.db.commit()
