# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe

from prakash_steel.prakash_steel.report.customer_wise_otif.customer_wise_otif import (
	build_week_rows,
	get_week_columns,
)
from prakash_steel.prakash_steel.report.otif_report.otif_report import get_data as get_otif_data


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220,
		},
		*get_week_columns(),
	]


def get_data(filters) -> list[dict]:
	if not filters.get("fiscal_year"):
		return []

	year_start_date, year_end_date = frappe.db.get_value(
		"Fiscal Year", filters["fiscal_year"], ["year_start_date", "year_end_date"]
	)

	otif_filters = {"from_date": year_start_date, "to_date": year_end_date}
	for key in ("company", "item_code", "customer"):
		if filters.get(key):
			otif_filters[key] = filters[key]

	return build_week_rows(get_otif_data(otif_filters), group_by="item_code", label_field="item_name")
