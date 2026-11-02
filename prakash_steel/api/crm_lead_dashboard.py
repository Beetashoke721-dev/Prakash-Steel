# Copyright (c) 2026, Prakash Steel and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_crm_lead_dashboard_data(
	lead=None,
	lead_owner=None,
	status=None,
	from_date=None,
	to_date=None,
) -> dict:
	"""
	Fetch CRM Lead rows for the CRM Lead Dashboard page.

	Respects CRM Lead read permissions.
	"""
	if not frappe.has_permission("CRM Lead", "read"):
		frappe.throw(_("Not permitted to access CRM Lead dashboard data."), frappe.PermissionError)

	conditions, params = _build_conditions(lead, lead_owner, status, from_date, to_date)

	return {
		"recent_leads": _get_recent_leads(conditions, params),
	}


def _build_conditions(lead, lead_owner, status, from_date=None, to_date=None):
	conditions = ["1=1"]
	params = {}

	if lead:
		conditions.append("l.name = %(lead)s")
		params["lead"] = lead
	if lead_owner:
		conditions.append("l.lead_owner = %(lead_owner)s")
		params["lead_owner"] = lead_owner
	if status:
		conditions.append("l.status = %(status)s")
		params["status"] = status
	if from_date:
		conditions.append("DATE(l.creation) >= %(from_date)s")
		params["from_date"] = from_date
	if to_date:
		conditions.append("DATE(l.creation) <= %(to_date)s")
		params["to_date"] = to_date

	return " AND ".join(conditions), params


def _get_recent_leads(conditions: str, params: dict) -> list:
	rows = frappe.db.sql(
		f"""
		SELECT
			l.name,
			l.lead_name,
			l.organization,
			l.status,
			l.lead_owner,
			IFNULL(u.full_name, l.lead_owner) AS assigned_to,
			p.products AS product,
			l.converted,
			IFNULL(l.net_total, 0) AS net_total,
			DATE(l.creation) AS lead_date,
			l.creation
		FROM `tabCRM Lead` l
		LEFT JOIN `tabUser` u ON u.name = l.lead_owner
		LEFT JOIN (
			SELECT
				parent,
				GROUP_CONCAT(
					DISTINCT IFNULL(NULLIF(product_name, ''), product_code)
					ORDER BY idx
					SEPARATOR ', '
				) AS products
			FROM `tabCRM Products`
			WHERE parenttype = 'CRM Lead'
			GROUP BY parent
		) p ON p.parent = l.name
		WHERE {conditions}
		ORDER BY l.creation DESC
		LIMIT 25
		""",
		params,
		as_dict=True,
	)
	for r in rows:
		r["converted"] = int(r.converted or 0)
		r["net_total"] = float(r.net_total or 0)
		r["product"] = r.product or ""
		r["lead_date"] = str(r.lead_date) if r.lead_date else None
		r.pop("creation", None)
	return rows
