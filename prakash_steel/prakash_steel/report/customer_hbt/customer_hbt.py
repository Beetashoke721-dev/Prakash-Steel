# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import getdate

from prakash_steel.utils.whitelist_permissions import require_permission

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MONTH_TO_NUM: dict[str, int] = {
	"January": 1,
	"February": 2,
	"March": 3,
	"April": 4,
	"May": 5,
	"June": 6,
	"July": 7,
	"August": 8,
	"September": 9,
	"October": 10,
	"November": 11,
	"December": 12,
}

_FISCAL_MONTH_ORDER: list[int] = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

# Maps view_by → safe SQL expression (never user-supplied)
_METRIC_COL: dict[str, str] = {
	"Sale Quantity": "sii.qty",
	"Sale Value": "sii.amount",
	"Throughput": "sii.amount",  # placeholder until throughput logic is defined
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	require_permission("Sales Invoice", "read")

	filters = filters or {}
	view_by: str = filters.get("view_by") or "Sale Quantity"

	period_months = _get_period_months()
	columns = _get_columns(view_by)
	data = _get_data(filters, period_months, view_by)

	return columns, data


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------


def _get_period_months() -> list[tuple[int, int]]:
	"""Return ordered (year, month) tuples from HBT Period Settings."""
	settings = frappe.get_single("HBT Period Settings")

	fiscal_year: str | None = settings.fiscal_year
	from_month: str | None = settings.from_month
	to_month: str | None = settings.to_month

	if not fiscal_year or not from_month or not to_month:
		frappe.throw(
			_("Please configure Fiscal Year, From Month, and To Month in HBT Period Settings."),
			title=_("Incomplete Period Settings"),
		)

	from_num = _MONTH_TO_NUM.get(from_month)
	to_num = _MONTH_TO_NUM.get(to_month)

	if from_num is None or to_num is None:
		frappe.throw(
			_("Invalid month value in HBT Period Settings."),
			title=_("Invalid Period Settings"),
		)

	from_idx = _FISCAL_MONTH_ORDER.index(from_num)
	to_idx = _FISCAL_MONTH_ORDER.index(to_num)

	if from_idx > to_idx:
		frappe.throw(
			_("From Month ({0}) must come before To Month ({1}) in the fiscal year.").format(
				from_month, to_month
			),
			title=_("Invalid Period Range"),
		)

	fy_doc = frappe.get_doc("Fiscal Year", fiscal_year)
	start_year: int = getdate(fy_doc.year_start_date).year
	end_year: int = getdate(fy_doc.year_end_date).year

	return [(start_year if m >= 4 else end_year, m) for m in _FISCAL_MONTH_ORDER[from_idx : to_idx + 1]]


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns(view_by: str) -> list[dict]:
	if view_by == "Sale Value":
		total_label = _("Total Sale Value")
		total_fieldtype = "Currency"
	elif view_by == "Sale Quantity":
		total_label = _("Total Sale Quantity")
		total_fieldtype = "Float"
	else:  # Throughput
		total_label = _("Total Throughput")
		total_fieldtype = "Currency"

	return [
		{
			"label": _("Customer / Group"),
			"fieldname": "group_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": total_label,
			"fieldname": "total",
			"fieldtype": total_fieldtype,
			"width": 160,
			"precision": 2,
		},
		{
			"label": _("Contr%"),
			"fieldname": "contr_pct",
			"fieldtype": "Percent",
			"width": 100,
			"precision": 1,
		},
		{
			"label": _("Cumu%"),
			"fieldname": "cumu_pct",
			"fieldtype": "Percent",
			"width": 100,
			"precision": 1,
		},
		{
			"label": _("HBT"),
			"fieldname": "hbt",
			"fieldtype": "Data",
			"width": 60,
		},
		{
			"label": _("Frequency"),
			"fieldname": "frequency",
			"fieldtype": "Int",
			"width": 100,
		},
	]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def _get_data(filters: dict, period_months: list[tuple[int, int]], view_by: str) -> list[dict]:
	if not period_months:
		return []

	# TODO: Sale Value and Throughput not implemented yet
	if view_by != "Sale Quantity":
		return []

	metric_col = _METRIC_COL.get(view_by)
	if not metric_col:
		frappe.throw(_("Unknown view option: {0}").format(view_by))

	first_year, first_month = period_months[0]
	last_year, last_month = period_months[-1]

	from_date = date(first_year, first_month, 1)
	last_day = calendar.monthrange(last_year, last_month)[1]
	to_date = date(last_year, last_month, last_day)

	# metric_col is sourced from _METRIC_COL (internal constant) — safe to interpolate
	raw_rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer) AS group_name,
			SUM({metric_col}) AS total,
			COUNT(DISTINCT YEAR(si.posting_date) * 100 + MONTH(si.posting_date)) AS frequency
		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN
			`tabItem` i ON i.name = sii.item_code
		INNER JOIN
			`tabCustomer` cust ON cust.name = si.customer
		WHERE
			si.docstatus = 1
			AND i.custom_item_type IN ('BB', 'RB', 'Traded', 'BO')
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer)
		ORDER BY
			total DESC
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	grand_total = sum(float(row.total or 0) for row in raw_rows)

	result = []
	running = 0.0
	h_done = False
	b_done = False
	for row in raw_rows:
		contr = (float(row.total or 0) / grand_total * 100) if grand_total else 0.0
		running += contr

		if not h_done:
			hbt = "H"
			if running >= 50:
				h_done = True
		elif not b_done:
			hbt = "B"
			if running >= 90:
				b_done = True
		else:
			hbt = "T"

		result.append(
			{
				"group_name": row.group_name,
				"total": float(row.total or 0),
				"contr_pct": contr,
				"cumu_pct": running,
				"hbt": hbt,
				"frequency": int(row.frequency or 0),
			}
		)
	return result
