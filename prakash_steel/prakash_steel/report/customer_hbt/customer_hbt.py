# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from prakash_steel.utils.hbt_utils import (
	METRIC_COL,
	assign_hbt_labels,
	get_period_months,
	period_date_range,
)
from prakash_steel.utils.whitelist_permissions import require_permission


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	require_permission("Sales Invoice", "read")

	filters = filters or {}
	view_by: str = filters.get("view_by") or "Sale Quantity"

	period_months = get_period_months()
	columns = _get_columns(view_by)
	data = _get_data(period_months, view_by)

	return columns, data


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns(view_by: str) -> list[dict]:
	# Sale Value temporarily hidden — _get_data returns [] for it; use Sale Quantity columns as placeholder
	if view_by == "Sale Value":
		view_by = "Sale Quantity"

	if view_by not in METRIC_COL:
		frappe.throw(_("{0} is not yet implemented for this report.").format(view_by))

	# Uncomment when Sale Value is ready to expose:
	# if view_by == "Sale Value":
	#     total_label = _("Total Sale Value")
	#     total_fieldtype = "Currency"
	# else:
	total_label = _("Total Sale Quantity")
	total_fieldtype = "Int"

	return [
		{"label": _("Customer / Group"), "fieldname": "group_name", "fieldtype": "Data", "width": 220},
		{"label": total_label, "fieldname": "total", "fieldtype": total_fieldtype, "width": 160},
		{"label": _("Contr%"), "fieldname": "contr_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
		{"label": _("Cumu%"), "fieldname": "cumu_pct", "fieldtype": "Percent", "width": 100, "precision": 1},
		{"label": _("HBT"), "fieldname": "hbt", "fieldtype": "Data", "width": 60},
		{"label": _("Frequency"), "fieldname": "frequency", "fieldtype": "Int", "width": 100},
	]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(period_months: list[tuple[int, int]], view_by: str) -> list[dict]:
	if not period_months:
		return []

	# Sale Value is implemented but temporarily hidden from users
	if view_by == "Sale Value":
		return []

	if view_by not in METRIC_COL:
		frappe.throw(_("{0} is not yet implemented for this report.").format(view_by))

	metric_col = METRIC_COL[view_by]
	from_date, to_date = period_date_range(period_months)

	# metric_col is sourced from METRIC_COL (internal constant) — safe to interpolate
	raw_rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer) AS group_name,
			SUM({metric_col}) AS total,
			COUNT(DISTINCT YEAR(si.posting_date) * 100 + MONTH(si.posting_date)) AS frequency
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		INNER JOIN `tabCustomer` cust ON cust.name = si.customer
		WHERE
			si.docstatus = 1
			AND i.custom_item_type IN ('BB', 'RB', 'Traded', 'BO')
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer)
		ORDER BY total DESC
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	assign_hbt_labels(raw_rows)

	return [
		{
			"group_name": row["group_name"],
			"total": int(row["total"] or 0),
			"contr_pct": row["contr_pct"],
			"cumu_pct": row["cumu_pct"],
			"hbt": row["hbt"],
			"frequency": int(row["frequency"] or 0),
		}
		for row in raw_rows
	]
