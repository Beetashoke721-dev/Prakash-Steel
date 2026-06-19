import frappe
from frappe.utils import getdate


def execute(filters=None) -> tuple[list, list]:
	filters = filters or {}

	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns() -> list[dict]:
	return [
		{
			"label": "PO No",
			"fieldname": "po_no",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 160,
		},
		{"label": "Item Name", "fieldname": "item_name", "fieldtype": "Data", "width": 220},
		{"label": "Due Date", "fieldname": "required_by", "fieldtype": "Date", "width": 110},
		{"label": "Qty", "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": "UOM", "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 90},
		{"label": "Received Qty", "fieldname": "received_qty", "fieldtype": "Float", "width": 120},
		{"label": "Received %", "fieldname": "received_pct", "fieldtype": "Percent", "width": 120},
	]


def get_data(filters) -> list[dict]:
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
            po.name AS po_no,
            poi.item_name,
            po.schedule_date AS required_by,
            poi.qty,
            poi.uom,
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
		qty = float(r.get("qty") or 0)
		rec = float(r.get("received_qty") or 0)
		r["received_pct"] = (rec / qty * 100) if qty > 0 else 0

	return rows





