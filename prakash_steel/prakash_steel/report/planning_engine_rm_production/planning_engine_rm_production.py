import frappe


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Production Date",
			"fieldname": "production_date",
			"fieldtype": "Date",
			"width": 130,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": "Category Name",
			"fieldname": "category_name",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": "Actual Qty",
			"fieldname": "actual_qty",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": "Usage Unit",
			"fieldname": "usage_unit",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": "Production Planning/Work Order",
			"fieldname": "production_planning",
			"fieldtype": "Dynamic Link",
			"options": "plan_doctype",
			"width": 220,
		},
		{
			"fieldname": "plan_doctype",
			"fieldtype": "Data",
			"hidden": 1,
		},
	]


def get_data(filters) -> list[dict]:
	"""Return data for the report.

	Work Order (flagged custom_rolled_production) is the default source of
	production data. Finish Weight entries linked to a Production Plan or
	Production Planning are unioned in alongside it.
	"""
	wo_conditions = ["wo.docstatus = 1", "wo.custom_rolled_production = 1"]
	fw_conditions = ["fw.docstatus = 1"]

	if filters.get("from_date"):
		wo_conditions.append("DATE(wo.actual_start_date) >= %(from_date)s")
		fw_conditions.append("fw.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		wo_conditions.append("DATE(wo.actual_start_date) <= %(to_date)s")
		fw_conditions.append("fw.posting_date <= %(to_date)s")

	if filters.get("item_code"):
		wo_conditions.append("wo.production_item = %(item_code)s")
		fw_conditions.append("fw.item_code = %(item_code)s")

	if filters.get("category_name"):
		wo_conditions.append("wo_item.custom_category_name = %(category_name)s")
		fw_conditions.append("item.custom_category_name = %(category_name)s")

	if filters.get("production_plan"):
		wo_conditions.append("wo.production_plan = %(production_plan)s")
		fw_conditions.append("fw.production_plan = %(production_plan)s")

	if filters.get("production_planning"):
		# Work Orders carry no Production Planning link, so exclude them.
		wo_conditions.append("1 = 0")
		fw_conditions.append("fw.production_planning = %(production_planning)s")

	if filters.get("company"):
		wo_conditions.append("wo.company = %(company)s")
		fw_conditions.append("COALESCE(pp.company, pln.company) = %(company)s")

	query = f"""
		SELECT
			DATE(wo.actual_start_date) AS production_date,
			wo_item.item_name AS item_name,
			wo_item.custom_category_name AS category_name,
			ROUND(wo.produced_qty, 0) AS actual_qty,
			wo_item.stock_uom AS usage_unit,
			wo.name AS production_planning,
			'Work Order' AS plan_doctype
		FROM `tabWork Order` wo
		LEFT JOIN `tabItem` wo_item ON wo_item.name = wo.production_item
		WHERE {" AND ".join(wo_conditions)}

		UNION ALL

		SELECT
			fw.posting_date AS production_date,
			fw.item_name AS item_name,
			item.custom_category_name AS category_name,
			ROUND(fw.finish_weight, 0) AS actual_qty,
			item.stock_uom AS usage_unit,
			COALESCE(NULLIF(fw.production_planning, ''), NULLIF(fw.production_plan, '')) AS production_planning,
			CASE
				WHEN IFNULL(fw.production_planning, '') != '' THEN 'Production Planning'
				WHEN IFNULL(fw.production_plan, '') != '' THEN 'Production Plan'
				ELSE NULL
			END AS plan_doctype
		FROM `tabFinish Weight` fw
		LEFT JOIN `tabItem` item ON item.name = fw.item_code
		LEFT JOIN `tabProduction Plan` pp ON pp.name = fw.production_plan
		LEFT JOIN `tabProduction Planning` pln ON pln.name = fw.production_planning
		WHERE {" AND ".join(fw_conditions)}

		ORDER BY production_date ASC, plan_doctype = 'Work Order' DESC
	"""

	return frappe.db.sql(query, filters, as_dict=True)
