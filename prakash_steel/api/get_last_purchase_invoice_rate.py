import frappe


@frappe.whitelist()
def get_last_purchase_order_rate(item_code, company=None):
    if not item_code:
        return 0

    # Fetch the latest submitted Purchase Order Item rate.
    # If company is provided from Material Request, keep the result company-specific.
    conditions = ["poi.item_code = %s", "po.docstatus = 1"]
    values = [item_code]

    if company:
        conditions.append("po.company = %s")
        values.append(company)

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
    rate = frappe.db.get_value("Item", item_code, "last_purchase_rate")

    return rate or 0


@frappe.whitelist()
def get_last_purchase_invoice_rate(item_code, company=None):
    # Backward-compatible alias for any existing clients.
    return get_last_purchase_order_rate(item_code, company)
