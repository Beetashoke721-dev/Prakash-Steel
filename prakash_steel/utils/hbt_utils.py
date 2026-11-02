# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

"""
Shared utilities for HBT (High-Buyer / Buffer / Tail) period reports.

All month-to-number mappings, fiscal-year period resolution, and HBT label
assignment logic live here so individual reports don't duplicate ~60 lines each.
"""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import cint, getdate

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTH_TO_NUM: dict[str, int] = {
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

MONTH_SHORT: dict[int, str] = {
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

# Indian fiscal year: April → March
FISCAL_MONTH_ORDER: list[int] = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]

# Safe SQL column expressions keyed by view_by filter value.
# Only "Sale Quantity" is fully implemented; "Sale Value" is available but
# Throughput is not yet defined — reports should guard against unsupported values.
METRIC_COL: dict[str, str] = {
	"Sale Quantity": "sii.qty",
	"Sale Value": "sii.amount",
}

# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------


def get_period_months(settings_doctype: str) -> list[tuple[int, int]]:
	"""Read a period-settings Single doctype and return an ordered list of (year, month) tuples.

	Months Apr-Dec map to the first calendar year of the fiscal year;
	Jan-Mar map to the second (e.g. FY 2025-2026: Apr 2025 → Mar 2026).

	Raises ``frappe.ValidationError`` if settings are incomplete or invalid.
	"""
	settings = frappe.get_single(settings_doctype)

	fiscal_year: str | None = settings.fiscal_year
	from_month: str | None = settings.from_month
	to_month: str | None = settings.to_month

	if not fiscal_year or not from_month or not to_month:
		frappe.throw(
			_("Please configure Fiscal Year, From Month, and To Month in {0}.").format(settings_doctype),
			title=_("Incomplete Period Settings"),
		)

	from_num = MONTH_TO_NUM.get(from_month)
	to_num = MONTH_TO_NUM.get(to_month)

	if from_num is None or to_num is None:
		frappe.throw(
			_("Invalid month value in {0}.").format(settings_doctype),
			title=_("Invalid Period Settings"),
		)

	from_idx = FISCAL_MONTH_ORDER.index(from_num)
	to_idx = FISCAL_MONTH_ORDER.index(to_num)

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

	return [(start_year if m >= 4 else end_year, m) for m in FISCAL_MONTH_ORDER[from_idx : to_idx + 1]]


def get_period_range(settings_doctype: str = "HBT Period Setting") -> tuple[date, date]:
	"""Read a period-settings Single doctype with ``from_date``/``to_date`` fields and
	return the configured ``(from_date, to_date)`` range.

	Unlike ``get_period_months``, these doctypes store an exact date range (not a
	fiscal-year/month selection), so the returned dates are used as-is — never
	rounded out to full calendar months.

	Raises ``frappe.ValidationError`` if the range is incomplete or invalid.
	"""
	settings = frappe.get_single(settings_doctype)

	from_date = settings.from_date
	to_date = settings.to_date

	if not from_date or not to_date:
		frappe.throw(
			_("Please configure From Date and To Date in {0}.").format(settings_doctype),
			title=_("Incomplete Period Settings"),
		)

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	if from_date > to_date:
		frappe.throw(
			_("From Date ({0}) must come before To Date ({1}) in {2}.").format(from_date, to_date, settings_doctype),
			title=_("Invalid Period Range"),
		)

	return from_date, to_date


def months_spanning(from_date: date, to_date: date) -> list[tuple[int, int]]:
	"""Return an ordered list of (year, month) tuples for every calendar month
	touched by ``[from_date, to_date]`` — used to build per-month report columns
	against an arbitrary date range."""
	months: list[tuple[int, int]] = []
	year, month = from_date.year, from_date.month
	while (year, month) <= (to_date.year, to_date.month):
		months.append((year, month))
		month += 1
		if month > 12:
			month = 1
			year += 1
	return months


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# TOG Horizon Setting keeps a separate From/To Date and Last/Updated FOS per
# item type, in fields prefixed with the lower-cased item type (bb_from_date …).
TOG_HORIZON_ITEM_TYPES = ("BB", "RB", "BO", "RM", "Traded", "CS")


def _tog_field(item_type: str, field: str) -> str:
	if item_type not in TOG_HORIZON_ITEM_TYPES:
		frappe.throw(_("Unsupported item type {0} for TOG Horizon Setting.").format(item_type))
	return f"{item_type.lower()}_{field}"


def get_tog_horizon_range(item_type: str) -> tuple[date, date]:
	"""Read TOG Horizon Setting and return the ``(from_date, to_date)`` range
	configured for ``item_type``.

	Raises ``frappe.ValidationError`` if the range is incomplete or invalid.
	"""
	settings = frappe.get_single("TOG Horizon Setting")

	from_date = settings.get(_tog_field(item_type, "from_date"))
	to_date = settings.get(_tog_field(item_type, "to_date"))

	if not from_date or not to_date:
		frappe.throw(
			_("Please configure {0} From Date and {0} To Date in TOG Horizon Setting.").format(item_type),
			title=_("Incomplete TOG Horizon Setting"),
		)

	from_date = getdate(from_date)
	to_date = getdate(to_date)

	if from_date > to_date:
		frappe.throw(
			_("{0} From Date ({1}) must come before {0} To Date ({2}) in TOG Horizon Setting.").format(
				item_type, from_date, to_date
			),
			title=_("Invalid Period Range"),
		)

	return from_date, to_date


def get_default_fos(item_type: str) -> int:
	"""FOS% to prefill a TOG page with: the item type's last saved ``updated_fos``,
	falling back to its baseline ``last_fos``, falling back to 30.

	Blank Int fields are stored as 0 in a Single, so 0 is treated as "not set".
	"""
	settings = frappe.get_single("TOG Horizon Setting")
	return cint(settings.get(_tog_field(item_type, "updated_fos"))) or get_last_fos(item_type, settings)


def get_last_fos(item_type: str, settings=None) -> int:
	"""Baseline FOS% for ``item_type`` that the Reset button reverts to."""
	settings = settings or frappe.get_single("TOG Horizon Setting")
	return cint(settings.get(_tog_field(item_type, "last_fos"))) or 30


def set_updated_fos(item_type: str, value) -> int:
	"""Persist the FOS% for ``item_type`` now in effect after a Save/Update/Reset action.

	When the FOS% changes, the one it replaces moves into ``last_fos`` so the
	Reset button can go back to it. Returns the resulting ``last_fos``.
	"""
	value = cint(value)
	previous = get_default_fos(item_type)
	if value == previous:
		return get_last_fos(item_type)
	frappe.db.set_single_value(
		"TOG Horizon Setting",
		{_tog_field(item_type, "last_fos"): previous, _tog_field(item_type, "updated_fos"): value},
	)
	return previous


def month_key(year: int, month: int) -> str:
	"""Fieldname-safe key for a year/month pair, e.g. ``m_2025_06``."""
	return f"m_{year}_{month:02d}"


def period_date_range(period_months: list[tuple[int, int]]) -> tuple[date, date]:
	"""Return ``(from_date, to_date)`` covering the full span of *period_months*."""
	first_year, first_month = period_months[0]
	last_year, last_month = period_months[-1]
	from_date = date(first_year, first_month, 1)
	last_day = calendar.monthrange(last_year, last_month)[1]
	to_date = date(last_year, last_month, last_day)
	return from_date, to_date


def assign_hbt_labels(rows: list[dict], total_key: str = "total") -> list[dict]:
	"""Assign ``hbt``, ``contr_pct``, and ``cumu_pct`` fields to each row in-place.

	Rows must already be sorted descending by *total_key*.
	H = top 50 % of cumulative contribution, B = next 40 % (up to 90 %), T = rest.
	Rows with a non-positive *total_key* (no sale) are labelled ``NS`` and take no
	part in the H/B/T ranking.

	Returns *rows* for convenience.
	"""
	grand = sum(float(r.get(total_key) or 0) for r in rows)
	running = 0.0
	h_done = False
	b_done = False
	for row in rows:
		val = float(row.get(total_key) or 0)
		if val <= 0:
			row["hbt"] = "NS"
			row["contr_pct"] = 0.0
			row["cumu_pct"] = running
			continue

		contr = (val / grand * 100) if grand else 0.0
		running += contr

		if not h_done:
			row["hbt"] = "H"
			if running >= 50:
				h_done = True
		elif not b_done:
			row["hbt"] = "B"
			if running >= 90:
				b_done = True
		else:
			row["hbt"] = "T"

		row["contr_pct"] = contr
		row["cumu_pct"] = running

	return rows


# ---------------------------------------------------------------------------
# Customer HBT map
# ---------------------------------------------------------------------------


def get_customer_hbt_map(
	from_date: date,
	to_date: date,
	metric_col: str,
) -> dict[str, str]:
	"""Return ``{group_name: 'H'|'B'|'T'}`` for all customer groups.

	Uses all item types (BB, RB, Traded, BO) for a consistent company-wide
	customer ranking — the same baseline used by the Customer HBT report.

	*metric_col* must be a value from ``METRIC_COL`` (never user-supplied).
	"""
	rows: list[dict] = frappe.db.sql(
		f"""
		SELECT
			COALESCE(NULLIF(cust.custom_customer_group_name, ''), si.customer) AS group_name,
			SUM({metric_col}) AS total
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

	# Drop non-positive rows (e.g. net returns) before ranking — this map's
	# contract is strictly H/B/T, and callers fall back to "T" for any
	# customer group missing from it.
	rows = [r for r in rows if float(r.get("total") or 0) > 0]

	# Assign HBT using the shared label function
	assign_hbt_labels(rows)
	return {r["group_name"]: r["hbt"] for r in rows}
