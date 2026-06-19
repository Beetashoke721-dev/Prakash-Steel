import frappe
from frappe import _


@frappe.whitelist()
def get_last_purchase_or_production(item_code: str) -> dict | None:
    """
    Fetch the latest *either* production or purchase transaction for the item.

    Logic:
    - Check the latest **production** for this item from:
        - `Finish Weight` (rolled production)
        - `Bright Bar Production` (bright bar production)
    - Check the latest **Purchase Order** for this item.
    - Compare the dates:
        - If latest production date > latest PO date → return production date & qty
        - Else → return purchase order date & qty

    Returns:
        dict with keys:
            - date: date of the latest relevant transaction (production or PO)
            - qty: corresponding quantity
    """
    if not frappe.has_permission("Item", "read"):
        frappe.throw(_("Not permitted to access last purchase/production data."), frappe.PermissionError)

    if not item_code:
        return {"date": None, "qty": 0}

    # ── Latest production (Finish Weight + Bright Bar Production) ─────────────────
    prod_rows = frappe.db.sql(
        """
        SELECT posting_date AS tx_date, finish_weight AS qty
        FROM `tabFinish Weight`
        WHERE item_code = %s AND docstatus = 1

        UNION ALL

        SELECT production_date AS tx_date, fg_weight AS qty
        FROM `tabBright Bar Production`
        WHERE finished_good = %s AND docstatus = 1

        ORDER BY tx_date DESC
        LIMIT 1
        """,
        (item_code, item_code),
        as_dict=True,
    )

    latest_prod_date = None
    latest_prod_qty = 0
    if prod_rows:
        latest_prod_date = prod_rows[0].get("tx_date")
        latest_prod_qty = prod_rows[0].get("qty") or 0

    # ── Latest purchase (Purchase Order) ─────────────────────────────────────────
    po_rows = frappe.db.sql(
        """
        SELECT poi.qty, po.transaction_date
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po ON poi.parent = po.name
        WHERE poi.item_code = %s
          AND po.docstatus = 1
        ORDER BY po.transaction_date DESC, po.creation DESC
        LIMIT 1
        """,
        (item_code,),
        as_dict=True,
    )

    latest_po_date = None
    latest_po_qty = 0
    if po_rows:
        latest_po_date = po_rows[0].get("transaction_date")
        latest_po_qty = po_rows[0].get("qty") or 0

    # ── Decide which one is latest ───────────────────────────────────────────────
    if latest_prod_date and (not latest_po_date or latest_prod_date > latest_po_date):
        # Latest is production (either Finish Weight or Bright Bar Production)
        return {"date": latest_prod_date, "qty": latest_prod_qty}
    elif latest_po_date:
        # Latest is Purchase Order
        return {"date": latest_po_date, "qty": latest_po_qty}

    # No production or purchase found
    return {"date": None, "qty": 0}
