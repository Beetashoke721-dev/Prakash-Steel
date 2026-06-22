# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _

from prakash_steel.utils.hbt_utils import (
	METRIC_COL,
	MONTH_SHORT,
	get_period_months,
	month_key,
	period_date_range,
)
from prakash_steel.utils.whitelist_permissions import require_permission


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	require_permission("Sales Invoice", "read")

	filters = filters or {}
	period_months = get_period_months()
	columns = _get_columns(period_months)
	data = _get_data(filters, period_months)

	return columns, data


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns(period_months: list[tuple[int, int]]) -> list[dict]:
	columns: list[dict] = [
		{
			"label": _("Customer / Group"),
			"fieldname": "group_name",
			"fieldtype": "Data",
			"width": 220,
		}
	]

	for year, month in period_months:
		columns.append(
			{
				"label": f"{MONTH_SHORT[month]} {str(year)[-2:]}",
				"fieldname": month_key(year, month),
				"fieldtype": "Float",
				"width": 110,
				"precision": 2,
			}
		)

	return columns


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(filters: dict, period_months: list[tuple[int, int]]) -> list[dict]:
	if not period_months:
		return []

	view_by: str = filters.get("view_by") or "Sale Quantity"

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
			YEAR(si.posting_date)  AS yr,
			MONTH(si.posting_date) AS mo,
			SUM({metric_col})      AS val
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		INNER JOIN `tabCustomer` cust ON cust.name = si.customer
		WHERE
			si.docstatus = 1
			AND i.custom_item_type IN ('BB', 'RB')
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer),
			YEAR(si.posting_date),
			MONTH(si.posting_date)
		ORDER BY group_name
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	period_lookup: dict[tuple[int, int], str] = {(y, m): month_key(y, m) for y, m in period_months}
	empty_row: dict[str, float] = {fn: 0.0 for fn in period_lookup.values()}
	group_data: dict[str, dict[str, float]] = defaultdict(lambda: dict(empty_row))

	for row in raw_rows:
		key = (int(row.yr), int(row.mo))
		fieldname = period_lookup.get(key)
		if fieldname:
			group_data[row.group_name][fieldname] += float(row.val or 0)

	return [{"group_name": gn, **month_vals} for gn, month_vals in sorted(group_data.items())]
