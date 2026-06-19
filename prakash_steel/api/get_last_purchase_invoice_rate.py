import frappe
from frappe import _


@frappe.whitelist()
def get_last_purchase_order_rate(item_code, company=None) -> float:
    if not frappe.has_permission("Purchase Order", "read") and not frappe.has_permission("Item", "read"):
        frappe.throw(_("Not permitted to access purchase order rate data."), frappe.PermissionError)

    if not item_code:
        return 0

    # Fetch the latest submitted Purchase Order Item rate.
    # If company is provided from Material Request, keep the result company-specific.
    conditions = ["poi.item_code = %s", "po.docstatus = 1"]
    values = [item_code]

    if company:
        conditions.append("po.company = %s")
        values.append(company)

    result = 0
    if frappe.has_permission("Purchase Order", "read"):
        result = frappe.db.sql(
            f"""
            SELECT poi.rate
            FROM `tabPurchase Order Item` poi
            INNER JOIN `tabPurchase Order` po
                ON po.name = poi.parent
            WHERE {' AND '.join(conditions)}
            ORDER BY po.transaction_date DESC, poi.creation DESC
            LIMIT 1
            """,
            values=values,
            as_dict=True,
        )

        if result and result[0].get("rate") is not None:
            return result[0]["rate"]

    # Fallback to Item master value if there is no submitted PI row.
    if not frappe.has_permission("Item", "read"):
        return 0

    rate = frappe.db.get_value("Item", item_code, "last_purchase_rate")
    return rate or 0


@frappe.whitelist()
def get_last_purchase_invoice_rate(item_code, company=None) -> float:
    # Backward-compatible alias for any existing clients.
    if not frappe.has_permission("Purchase Order", "read") and not frappe.has_permission("Item", "read"):
        frappe.throw(
            _("Not permitted to access purchase order rate data."),
            frappe.PermissionError,
        )
    return get_last_purchase_order_rate(item_code, company)
