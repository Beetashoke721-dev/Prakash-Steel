# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe

from prakash_steel.prakash_steel.report.otif_report.otif_report import _week_totals
from prakash_steel.prakash_steel.report.otif_report.otif_report import get_data as get_otif_data

MAX_WEEKS = 53


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Customer Name",
			"fieldname": "customer_name",
			"fieldtype": "Data",
			"width": 220,
		},
		*get_week_columns(),
	]


def get_week_columns() -> list[dict]:
	return [
		{
			"label": f"Week {week}",
			"fieldname": f"week_{week}",
			"fieldtype": "Percent",
			"width": 90,
		}
		for week in range(1, MAX_WEEKS + 1)
	]


def get_data(filters) -> list[dict]:
	if not filters.get("fiscal_year"):
		return []

	year_start_date, year_end_date = frappe.db.get_value(
		"Fiscal Year", filters["fiscal_year"], ["year_start_date", "year_end_date"]
	)

	otif_filters = {"from_date": year_start_date, "to_date": year_end_date}
	for key in ("company", "customer"):
		if filters.get(key):
			otif_filters[key] = filters[key]

	return build_customer_rows(get_otif_data(otif_filters))


def build_customer_rows(lines: list[dict]) -> list[dict]:
	return build_week_rows(lines, group_by="customer", label_field="customer_name")


def build_week_rows(lines: list[dict], group_by: str, label_field: str) -> list[dict]:
	# Same Line Percentage as the OTIF Report, but per group (customer / item) instead of
	# across everything: sales value of Line-OTIF-100 lines / book value of all lines, per delivery week.
	lines_by_group: dict = {}
	for line in lines:
		if not line.get("week"):
			continue
		key = line.get(group_by) or line.get(label_field)
		lines_by_group.setdefault(key, []).append(line)

	data = []
	for group_lines in lines_by_group.values():
		row = {label_field: group_lines[0].get(label_field)}
		# Weeks with no lines due must be an explicit None: Frappe's Percent formatter
		# renders a missing (undefined) value as "0%" and only blanks out null.
		row.update({f"week_{week}": None for week in range(1, MAX_WEEKS + 1)})
		for week_label, bucket in _week_totals(group_lines).items():
			total = bucket["all"]
			row[f"week_{_week_number(week_label)}"] = round(bucket["line"] / total * 100, 2) if total else 0
		data.append(row)

	data.sort(key=lambda row: (row[label_field] or "").lower())
	return data


def _week_number(week_label: str) -> int:
	# get_week_label returns "<week>-<yy>", e.g. "12-26"
	return int(week_label.split("-")[0])
