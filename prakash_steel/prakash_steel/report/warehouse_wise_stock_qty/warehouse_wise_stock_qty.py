# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Warehouse Name",
			"fieldname": "warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"width": 300,
		},
		{
			"label": "Stock Qty",
			"fieldname": "stock_qty",
			"fieldtype": "Float",
			"width": 150,
		},
	]


def get_data(filters) -> list[dict]:
	where_conditions = []
	params = {}

	# Apply warehouse filter if provided
	if filters.get("warehouse"):
		where_conditions.append("b.warehouse = %(warehouse)s")
		params["warehouse"] = filters.get("warehouse")

	# Join with Item to ensure we only count active items
	# This matches the Stock Balance report logic
	where_conditions.append("i.disabled = 0")

	where_clause = " AND ".join(where_conditions)

	# Query to get sum of actual_qty from Bin table grouped by warehouse
	# actual_qty from Bin should match bal_qty from Stock Balance report
	# Only include active items to match Stock Balance behavior
	having_clause = ""
	if not filters.get("include_zero_stock"):
		having_clause = "HAVING SUM(b.actual_qty) != 0"

	rows = frappe.db.sql(
		f"""
		SELECT
			b.warehouse,
			SUM(b.actual_qty) AS stock_qty
		FROM `tabBin` b
		INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE {where_clause}
		GROUP BY b.warehouse
		{having_clause}
		ORDER BY b.warehouse
		""",
		params,
		as_dict=True,
	)

	# Format the data
	for row in rows:
		row["stock_qty"] = float(row.get("stock_qty") or 0)

	return rows
