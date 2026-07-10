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
