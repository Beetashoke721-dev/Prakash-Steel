import frappe
from frappe import _
from frappe.utils import getdate

from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def get_grade_wise_avg_rate(from_date=None, to_date=None):
	require_permission("Purchase Order", "read")

	where = [
		"po.docstatus = 1",
		"po.workflow_state != 'Cancelled'",
		"i.custom_grade IS NOT NULL",
		"i.custom_grade != ''",
	]
	params = {}

	if from_date:
		where.append("po.transaction_date >= %(from_date)s")
		params["from_date"] = str(getdate(from_date))
	if to_date:
		where.append("po.transaction_date <= %(to_date)s")
		params["to_date"] = str(getdate(to_date))

	where_clause = " AND ".join(where)

	return frappe.db.sql(
		f"""
		SELECT
			i.custom_grade AS grade,
			AVG(poi.rate) AS avg_rate
		FROM `tabPurchase Order` po
		INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		INNER JOIN `tabItem` i ON i.name = poi.item_code
		WHERE {where_clause}
		GROUP BY i.custom_grade
		ORDER BY i.custom_grade
		""",
		params,
		as_dict=True,
	)


@frappe.whitelist()
def export_grade_wise_xlsx(from_date=None, to_date=None):
	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Purchase Order", "read")
	data = get_grade_wise_avg_rate(from_date=from_date, to_date=to_date)

	rows = [["Grade", "Avg Rate (₹)"]]
	for r in data:
		rows.append([r.get("grade", ""), round(float(r.get("avg_rate") or 0), 2)])

	xlsx_file = make_xlsx(rows, "Grade Wise Summary")
	frappe.response["filename"] = "Grade Wise Summary.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def export_details_xlsx(from_date=None, to_date=None, item_code=None, grade=None):
	from frappe.utils.xlsxutils import make_xlsx

	require_permission("Purchase Order", "read")

	filters = {}
	if from_date:
		filters["from_date"] = from_date
	if to_date:
		filters["to_date"] = to_date
	if item_code:
		filters["item_code"] = item_code
	if grade:
		filters["grade"] = grade

	from prakash_steel.prakash_steel.report.average_purchase_rate_report.average_purchase_rate_report import (
		get_data,
	)

	report_data = get_data(filters)
	grade_avg_map = {
		r["grade"]: float(r["avg_rate"] or 0)
		for r in get_grade_wise_avg_rate(from_date=from_date, to_date=to_date)
	}

	rows = [["PO Date", "Supplier", "Item Name", "Grade", "Rate (₹)", "Avg Rate (₹)", "Purchase Order"]]
	for r in report_data:
		po_date = r.get("po_date")
		if po_date:
			parts = str(po_date).split("-")
			po_date = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else str(po_date)
		rows.append([
			po_date or "",
			r.get("party_name", ""),
			r.get("item_name", ""),
			r.get("item_grade", ""),
			round(float(r.get("rate") or 0), 2),
			round(grade_avg_map.get(r.get("item_grade", ""), 0), 2),
			r.get("purchase_order_no", ""),
		])

	xlsx_file = make_xlsx(rows, "Average Purchase Rate")
	frappe.response["filename"] = "Average Purchase Rate.xlsx"
	frappe.response["filecontent"] = xlsx_file.getvalue()
	frappe.response["type"] = "binary"
