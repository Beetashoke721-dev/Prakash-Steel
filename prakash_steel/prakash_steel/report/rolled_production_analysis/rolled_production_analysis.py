# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import calendar
from collections import defaultdict
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

_MONTH_SHORT: dict[int, str] = {
	1: "Jan",
	2: "Feb",
	3: "Mar",
	4: "Apr",
	5: "May",
	6: "Jun",
	7: "Jul",
	8: "Aug",
	9: "Sep",
	10: "Oct",
	11: "Nov",
	12: "Dec",
}

# Fiscal year month order: April → March
_FISCAL_MONTH_ORDER: list[int] = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

# Maps view_by filter value → safe SQL column expression (never user-supplied input)
_METRIC_COL: dict[str, str] = {
	"Sale Quantity": "sii.qty",
	"Sale Value": "sii.amount",
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def execute(filters: dict | None = None) -> tuple[list[dict], list[dict]]:
	require_permission("Sales Invoice", "read")

	filters = filters or {}
	period_months = _get_period_months()
	columns = _get_columns(period_months)
	data = _get_data(filters, period_months)

	return columns, data


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------


def _get_period_months() -> list[tuple[int, int]]:
	"""Read HBT Period Settings and return an ordered list of (year, month) tuples.

	Months Apr-Dec map to the first calendar year of the fiscal year;
	Jan-Mar map to the second (e.g. FY 2025-2026: Apr 2025 ... Mar 2026).
	"""
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
	start_year: int = getdate(fy_doc.year_start_date).year  # e.g. 2025
	end_year: int = getdate(fy_doc.year_end_date).year  # e.g. 2026

	return [(start_year if m >= 4 else end_year, m) for m in _FISCAL_MONTH_ORDER[from_idx : to_idx + 1]]


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------


def _get_columns(period_months: list[tuple[int, int]]) -> list[dict]:
	columns: list[dict] = [
		{
			"label": _("Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 200,
		}
	]

	for year, month in period_months:
		columns.append(
			{
				"label": f"{_MONTH_SHORT[month]} {str(year)[-2:]}",
				"fieldname": _month_key(year, month),
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

	if view_by == "Throughput":
		# Throughput logic not implemented yet
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
			sii.item_code,
			YEAR(si.posting_date)  AS yr,
			MONTH(si.posting_date) AS mo,
			SUM({metric_col})      AS val
		FROM
			`tabSales Invoice` si
		INNER JOIN
			`tabSales Invoice Item` sii ON sii.parent = si.name
		INNER JOIN
			`tabItem` i ON i.name = sii.item_code
		WHERE
			si.docstatus = 1
			AND i.custom_item_type = 'RB'
			AND si.posting_date BETWEEN %(from_date)s AND %(to_date)s
		GROUP BY
			sii.item_code,
			YEAR(si.posting_date),
			MONTH(si.posting_date)
		ORDER BY
			sii.item_code
		""",
		{"from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	period_lookup: dict[tuple[int, int], str] = {(y, m): _month_key(y, m) for y, m in period_months}
	empty_row: dict[str, float] = {fn: 0.0 for fn in period_lookup.values()}

	item_data: dict[str, dict[str, float]] = defaultdict(lambda: dict(empty_row))

	for row in raw_rows:
		key = (int(row.yr), int(row.mo))
		fieldname = period_lookup.get(key)
		if fieldname:
			item_data[row.item_code][fieldname] += float(row.val or 0)

	return [{"item_code": item_code, **month_vals} for item_code, month_vals in sorted(item_data.items())]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _month_key(year: int, month: int) -> str:
	"""Fieldname key for a given year/month, e.g. ``m_2025_06``."""
	return f"m_{year}_{month:02d}"
