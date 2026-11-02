# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from prakash_steel.utils.whitelist_permissions import require_permission


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	require_permission("Bright Bar Production", "read")

	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Production Date"),
			"fieldname": "production_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("RM Code"),
			"fieldname": "rm_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("RM Name"),
			"fieldname": "rm_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("RM Category Name"),
			"fieldname": "rm_category_name",
			"fieldtype": "Link",
			"options": "Item Category",
			"width": 220,
		},
		{
			"label": _("Actual RM Consumption"),
			"fieldname": "actual_rm_consumption",
			"fieldtype": "Int",
			"width": 150,
		},
	]


def get_data(filters: dict) -> list[dict]:
	"""Return data for the report.

	Two sources are unioned:

	* `Bright Bar Production` entries (the original source) — one row per
	  submitted entry, ``actual_rm_consumption`` is the RM used in Kg.
	* `Work Order` (flagged ``custom_bright_production``) — one row per
	  ``required_items`` line, ``consumed_qty`` is the RM actually consumed
	  against the order, dated on the Work Order's ``actual_start_date``.
	"""
	bbp_conditions = ["bbp.docstatus = 1"]
	wo_conditions = ["wo.docstatus = 1", "wo.custom_bright_production = 1"]
	values = {}

	if filters.get("from_date"):
		bbp_conditions.append("bbp.production_date >= %(from_date)s")
		wo_conditions.append("date(wo.actual_start_date) >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		bbp_conditions.append("bbp.production_date <= %(to_date)s")
		wo_conditions.append("date(wo.actual_start_date) <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("rm_code"):
		bbp_conditions.append("coalesce(bbp.material, bbp.raw_material) = %(rm_code)s")
		wo_conditions.append("woi.item_code = %(rm_code)s")
		values["rm_code"] = filters["rm_code"]

	bbp_where_clause = " and ".join(bbp_conditions)
	wo_where_clause = " and ".join(wo_conditions)

	data = frappe.db.sql(
		f"""
		select * from (
			select
				bbp.production_date as production_date,
				coalesce(bbp.material, bbp.raw_material) as rm_code,
				i.item_name as rm_name,
				i.custom_category_name as rm_category_name,
				bbp.actual_rm_consumption as actual_rm_consumption
			from `tabBright Bar Production` bbp
			left join `tabItem` i on i.name = coalesce(bbp.material, bbp.raw_material)
			where {bbp_where_clause}

			union all

			select
				date(wo.actual_start_date) as production_date,
				woi.item_code as rm_code,
				i.item_name as rm_name,
				i.custom_category_name as rm_category_name,
				woi.consumed_qty as actual_rm_consumption
			from `tabWork Order Item` woi
			inner join `tabWork Order` wo on wo.name = woi.parent
			left join `tabItem` i on i.name = woi.item_code
			where {wo_where_clause} and woi.consumed_qty > 0
		) rm_consumption
		order by production_date asc, rm_code asc
		""",
		values,
		as_dict=True,
	)

	for row in data:
		row["actual_rm_consumption"] = int(flt(row.get("actual_rm_consumption", 0)))

	return data
