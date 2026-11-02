# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, flt, today

from prakash_steel.utils.whitelist_permissions import require_permission


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	require_permission("Finish Weight", "read")

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
			"label": _("Finished Item Code"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 150,
		},
		{
			"label": _("Item Name"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Finished Item Category Name"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Category",
			"width": 220,
		},
		{
			"label": _("Actual Qty"),
			"fieldname": "actual_qty",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("UOM"),
			"fieldname": "uom",
			"fieldtype": "Link",
			"options": "UOM",
			"width": 90,
		},
		{
			"label": _("Production Plan/Work Order"),
			"fieldname": "production_plan",
			"fieldtype": "Dynamic Link",
			"options": "production_plan_type",
			"width": 180,
		},
		{
			"label": _("Vendor Name"),
			"fieldname": "vendor_name",
			"fieldtype": "Data",
			"width": 150,
		},
	]


def get_data(filters: dict) -> list[dict]:
	"""Return data for the report.

	Work Order (flagged custom_rolled_production) is the default source of
	production data. Finish Weight entries linked to a Rolled Production
	Plan or Production Planning are unioned in alongside it.
	"""
	from_date = filters.get("from_date") or add_days(today(), -6)
	to_date = filters.get("to_date") or today()

	values = {"from_date": from_date, "to_date": to_date}

	wo_conditions = [
		"wo.docstatus = 1",
		"wo.custom_rolled_production = 1",
		"date(wo.actual_start_date) between %(from_date)s and %(to_date)s",
	]
	fw_conditions = [
		"fw.docstatus = 1",
		"fw.posting_date between %(from_date)s and %(to_date)s",
		"(fw.production_planning like 'Rolled%%' or fw.production_plan like 'Rolled%%')",
	]

	if filters.get("item_code"):
		values["item_code"] = filters["item_code"]
		wo_conditions.append("wo.production_item = %(item_code)s")
		fw_conditions.append("fw.item_code = %(item_code)s")

	wo_where_clause = " and ".join(wo_conditions)
	fw_where_clause = " and ".join(fw_conditions)

	data = frappe.db.sql(
		f"""
		select
			date(wo.actual_start_date) as production_date,
			wo.production_item as item_code,
			i.item_name as item_name,
			i.custom_category_name as item_group,
			wo.produced_qty as actual_qty,
			i.stock_uom as uom,
			wo.name as production_plan,
			'Work Order' as production_plan_type,
			coalesce(so.customer_name, '') as vendor_name
		from `tabWork Order` wo
		left join `tabItem` i on i.name = wo.production_item
		left join `tabSales Order` so on so.name = wo.sales_order
		where {wo_where_clause}

		union all

		select
			fw.posting_date as production_date,
			fw.item_code as item_code,
			fw.item_name as item_name,
			i.custom_category_name as item_group,
			fw.finish_weight as actual_qty,
			i.stock_uom as uom,
			coalesce(fw.production_planning, fw.production_plan) as production_plan,
			case
				when fw.production_planning is not null then 'Production Planning'
				else 'Production Plan'
			end as production_plan_type,
			'Rolling Mill Production' as vendor_name
		from `tabFinish Weight` fw
		left join `tabItem` i on i.name = fw.item_code
		where {fw_where_clause}

		order by production_date asc, production_plan_type = 'Work Order' desc
		""",
		values,
		as_dict=True,
	)

	for row in data:
		row["actual_qty"] = int(flt(row.get("actual_qty", 0)))

	return data
