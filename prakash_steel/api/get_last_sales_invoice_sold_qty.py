import frappe
from frappe import _


@frappe.whitelist()
def get_last_sales_invoice_sold_qty(item_code) -> float:
	if not frappe.has_permission("Sales Invoice", "read"):
		frappe.throw(_("Not permitted to access Sales Invoice data."), frappe.PermissionError)

	result = frappe.db.sql(
		"""
        SELECT sii.qty
        FROM `tabSales Invoice Item` sii
        JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE sii.item_code = %s
          AND si.docstatus = 1
        ORDER BY si.posting_date DESC, si.posting_time DESC
        LIMIT 1
    """,
		(item_code),
		as_dict=True,
	)

	if result:
		return result[0].qty
	else:
		return 0
