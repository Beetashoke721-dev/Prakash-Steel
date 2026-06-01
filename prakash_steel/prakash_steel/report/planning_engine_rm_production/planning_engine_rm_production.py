import frappe


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
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
			"label": "Production Planning",
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


def get_data(filters):
	conditions = ["fw.docstatus = 1"]

	if filters.get("from_date"):
		conditions.append("fw.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("fw.posting_date <= %(to_date)s")

	if filters.get("item_code"):
		conditions.append("fw.item_code = %(item_code)s")

	if filters.get("category_name"):
		conditions.append("item.custom_category_name = %(category_name)s")

	if filters.get("production_plan"):
		conditions.append("fw.production_plan = %(production_plan)s")

	if filters.get("production_planning"):
		conditions.append("fw.production_planning = %(production_planning)s")

	if filters.get("company"):
		conditions.append("COALESCE(pp.company, pln.company) = %(company)s")

	query = f"""
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
		WHERE {" AND ".join(conditions)}
		ORDER BY fw.posting_date DESC, fw.name DESC
	"""

	return frappe.db.sql(query, filters, as_dict=True)
