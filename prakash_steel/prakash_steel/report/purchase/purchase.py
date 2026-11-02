# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe


def execute(filters: dict | None = None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "Date",
			"fieldname": "date",
			"fieldtype": "Date",
			"width": 100,
		},
		{
			"label": "ID",
			"fieldname": "id",
			"fieldtype": "Link",
			"options": "Purchase Receipt",
			"width": 150,
		},
		{
			"label": "Vendor Name",
			"fieldname": "vendor_name",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 150,
		},
		{
			"label": "Item Name",
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": "Qty",
			"fieldname": "qty",
			"fieldtype": "Float",
			"width": 100,
		},
		{
			"label": "Rate",
			"fieldname": "rate",
			"fieldtype": "Currency",
			"width": 100,
		},
		{
			"label": "Amount",
			"fieldname": "amount",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "Category",
			"fieldname": "category",
			"fieldtype": "Link",
			"options": "Item Category",
			"width": 120,
		},
		{
			"label": "Month",
			"fieldname": "month",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": "Net Value",
			"fieldname": "net_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": "Avg Rate",
			"fieldname": "avg_rate",
			"fieldtype": "Currency",
			"width": 100,
		},
	]


def get_data(filters: dict) -> list[dict]:
	if not filters.get("from_date"):
		filters["from_date"] = "2020-01-01"
	if not filters.get("to_date"):
		filters["to_date"] = "2030-12-31"

	conditions = "pr.docstatus = 1 AND pr.posting_date BETWEEN %(from_date)s AND %(to_date)s"

	if filters.get("supplier"):
		conditions += " AND pr.supplier = %(supplier)s"

	if filters.get("item_code"):
		conditions += " AND pri.item_code = %(item_code)s"

	query = f"""
		SELECT
			pr.posting_date AS date,
			pr.name AS id,
			pr.supplier AS vendor_name,
			pri.item_name AS item_name,
			pri.qty AS qty,
			pri.rate AS rate,
			pri.amount AS amount,
			item.custom_category_name AS category,
			DATE_FORMAT(pr.posting_date, '%%c-%%y') AS month

		FROM
			`tabPurchase Receipt` pr
		INNER JOIN
			`tabPurchase Receipt Item` pri ON pri.parent = pr.name
		LEFT JOIN
			`tabItem` item ON item.name = pri.item_code

		WHERE {conditions}

		ORDER BY pr.posting_date DESC, pr.name
	"""

	data = frappe.db.sql(query, filters, as_dict=True)

	group_totals = {}
	for row in data:
		row["net_value"] = row["amount"] / row["qty"] if row["qty"] else 0
		if row["category"]:
			key = (row["month"], row["category"])
			totals = group_totals.setdefault(key, {"sum": 0, "count": 0})
			totals["sum"] += row["net_value"]
			totals["count"] += 1

	group_avg = {key: totals["sum"] / totals["count"] for key, totals in group_totals.items()}

	for row in data:
		row["avg_rate"] = group_avg.get((row["month"], row["category"]))

	return data
