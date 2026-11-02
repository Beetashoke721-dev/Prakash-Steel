# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


@frappe.whitelist()
def export_otif_xlsx(rows=None, summary=None):
	"""Download the current OTIF page as a single .xlsx with two sheets:
	"OTIF Summary" (the Business Measures / Percentage table) and
	"OTIF Report" (the main order-lines table, as shown on screen)."""
	import json
	from io import BytesIO

	import xlsxwriter
	from frappe.utils.xlsxutils import make_xlsx

	from prakash_steel.prakash_steel.report.otif_report.otif_report import get_columns

	frappe.has_permission("Sales Order", "read", throw=True)

	if isinstance(rows, str):
		rows = json.loads(rows or "[]")
	rows = rows or []

	if isinstance(summary, str):
		summary = json.loads(summary or "[]")
	summary = summary or []

	# Same visible columns as the page's main table (hidden report columns dropped).
	columns = [c for c in get_columns() if not c.get("hidden")]

	summary_data = [["Business Measures", "Percentage"]]
	for srow in summary:
		summary_data.append([srow.get("label", ""), srow.get("percentage", "")])

	report_data = [[c["label"] for c in columns]]
	for row in rows:
		report_data.append([row.get(c["fieldname"], "") for c in columns])

	xlsx_file = BytesIO()
	wb = xlsxwriter.Workbook(xlsx_file, {"constant_memory": True})
	make_xlsx(summary_data, "OTIF Summary", wb=wb)
	make_xlsx(report_data, "OTIF Report", wb=wb)
	wb.close()
	xlsx_file.seek(0)

	frappe.response["filename"] = "OTIF Report.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
