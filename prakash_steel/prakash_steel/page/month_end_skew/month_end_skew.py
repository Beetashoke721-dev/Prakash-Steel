# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, getdate

DAY_BUCKETS = [
	("bucket_1_7", 1, 7),
	("bucket_8_14", 8, 14),
	("bucket_15_21", 15, 21),
	("bucket_22_31", 22, 31),
]


def get_month_list(from_date, to_date):
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	months = []
	cur = date(from_date.year, from_date.month, 1)
	end = date(to_date.year, to_date.month, 1)
	while cur <= end:
		months.append(cur)
		if cur.month == 12:
			cur = date(cur.year + 1, 1, 1)
		else:
			cur = date(cur.year, cur.month + 1, 1)
	return months


def get_item_type_amount_sum(item_type, start, end):
	if start > end:
		return 0

	conditions = (
		"si.docstatus = 1 AND si.is_return = 0 AND si.naming_series != 'DN/.####./.FY.'"
		" AND si.posting_date BETWEEN %(start)s AND %(end)s"
	)
	if item_type:
		conditions += " AND i.custom_item_type = %(item_type)s"

	result = frappe.db.sql(
		f"""
		SELECT SUM(sii.amount) AS amount
		FROM `tabSales Invoice Item` sii
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
		INNER JOIN `tabItem` i ON i.name = sii.item_code
		WHERE {conditions}
		""",
		{"item_type": item_type, "start": start, "end": end},
	)
	return round(flt(result[0][0])) if result and result[0][0] else 0


def get_month_end_skew_columns():
	return [
		{"label": _("Month"), "fieldname": "month", "fieldtype": "Data", "width": 110},
		{"label": _("1st-7th"), "fieldname": "bucket_1_7", "fieldtype": "Int", "width": 120},
		{"label": _("8th-14th"), "fieldname": "bucket_8_14", "fieldtype": "Int", "width": 120},
		{"label": _("15th-21st"), "fieldname": "bucket_15_21", "fieldtype": "Int", "width": 120},
		{"label": _("22nd-31st"), "fieldname": "bucket_22_31", "fieldtype": "Int", "width": 120},
	]


def build_month_end_skew_table(item_type, from_date, to_date):
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	months = get_month_list(from_date, to_date)

	data = []
	totals = {key: 0 for key, _f, _t in DAY_BUCKETS}

	for month_start in months:
		last_day = calendar.monthrange(month_start.year, month_start.month)[1]
		row = {"month": month_start.strftime("%b-%y")}
		for key, day_from, day_to in DAY_BUCKETS:
			if day_from > last_day:
				row[key] = 0
				continue
			day_to = min(day_to, last_day)
			bucket_start = date(month_start.year, month_start.month, day_from)
			bucket_end = date(month_start.year, month_start.month, day_to)
			clipped_start = max(bucket_start, from_date)
			clipped_end = min(bucket_end, to_date)
			amount = (
				get_item_type_amount_sum(item_type, clipped_start, clipped_end)
				if clipped_start <= clipped_end
				else 0
			)
			row[key] = amount
			totals[key] += amount
		data.append(row)

	total_row = {"month": _("Total")}
	total_row.update(totals)
	data.append(total_row)

	return get_month_end_skew_columns(), data


def build_percentage_table(month_rows):
	bucket_keys = [key for key, _f, _t in DAY_BUCKETS]

	data = []
	totals = {key: 0 for key in bucket_keys}

	for row in month_rows:
		row_total = sum(flt(row.get(key)) for key in bucket_keys)
		pct_row = {"month": row["month"]}
		for key in bucket_keys:
			pct = (flt(row.get(key)) / row_total * 100) if row_total else 0
			pct_row[key] = pct
			totals[key] += pct
		data.append(pct_row)

	num_rows = len(month_rows) or 1
	avg_row = {"month": _("Avg")}
	for key in bucket_keys:
		avg_row[key] = totals[key] / num_rows
	data.append(avg_row)

	return get_month_end_skew_columns(), data


def get_settings_date_range():
	settings = frappe.get_single("Month End Skew Settings")
	if not settings.from_date or not settings.to_date:
		frappe.throw(_("Please set From Date and To Date in Month End Skew Settings."))
	return settings.from_date, settings.to_date


def get_month_end_skew_and_percentage(item_type):
	from_date, to_date = get_settings_date_range()
	skew_columns, skew_data = build_month_end_skew_table(item_type, from_date, to_date)
	month_rows = skew_data[:-1]  # exclude the skew table's own Total row
	pct_columns, pct_data = build_percentage_table(month_rows)
	return {
		"skew": {"columns": skew_columns, "data": skew_data},
		"percentage": {"columns": pct_columns, "data": pct_data},
	}


@frappe.whitelist()
def get_bright_month_end_skew():
	return get_month_end_skew_and_percentage("BB")


@frappe.whitelist()
def get_rolling_month_end_skew():
	return get_month_end_skew_and_percentage("RB")


@frappe.whitelist()
def get_total_month_end_skew():
	return get_month_end_skew_and_percentage(None)
