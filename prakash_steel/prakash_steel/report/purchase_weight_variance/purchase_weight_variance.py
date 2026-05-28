# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 110},
		{
			"label": "PO No",
			"fieldname": "po_no",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 160,
		},
		{
			"label": "Item Code",
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 140,
		},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": "PO Qty", "fieldname": "po_qty", "fieldtype": "Float", "width": 100},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 120},
		{"label": "Weight Variation", "fieldname": "weight_variation", "fieldtype": "Float", "width": 140},
		{
			"label": "Weight Variation %",
			"fieldname": "weight_variation_pct",
			"fieldtype": "Percent",
			"width": 150,
		},
		{"label": "Status", "fieldname": "status", "fieldtype": "HTML", "width": 130},
	]


def get_data(filters):
	where = ["po.docstatus = 1", "po.workflow_state != 'Cancelled'"]
	params = {}

	if filters.get("from_date") and filters.get("to_date"):
		where.append("po.transaction_date BETWEEN %(from_date)s AND %(to_date)s")
		params.update(
			{
				"from_date": str(getdate(filters.get("from_date"))),
				"to_date": str(getdate(filters.get("to_date"))),
			}
		)

	if filters.get("supplier"):
		where.append("po.supplier = %(supplier)s")
		params["supplier"] = filters.get("supplier")

	if filters.get("item_code"):
		where.append("poi.item_code = %(item_code)s")
		params["item_code"] = filters.get("item_code")

	if filters.get("po_no"):
		where.append("po.name LIKE %(po_no_like)s")
		params["po_no_like"] = f"%{filters.get('po_no')}%"

	where_clause = " AND ".join(where)

	rows = frappe.db.sql(
		f"""
        SELECT
            po.transaction_date AS po_date,
            po.name AS po_no,
            poi.item_code,
            poi.item_name,
            poi.qty AS po_qty,
            IFNULL(poi.received_qty, 0) AS received_qty
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        WHERE {where_clause}
        ORDER BY po.transaction_date, po.name
        """,
		params,
		as_dict=True,
	)

	for r in rows:
		po_qty = float(r.get("po_qty") or 0)
		received_qty = float(r.get("received_qty") or 0)

		r["weight_variation"] = received_qty - po_qty
		r["weight_variation_pct"] = (r["weight_variation"] / po_qty * 100) if po_qty > 0 else 0

		pct = r["weight_variation_pct"]
		if -5 <= pct <= 5:
			r["status"] = "<span style='color:green'>● Acceptable</span>"
		elif pct > 5:
			r["status"] = "<span style='color:blue'>↑ +5% Up</span>"
		else:
			r["status"] = "<span style='color:red'>↓ -5% Down</span>"

	return rows
