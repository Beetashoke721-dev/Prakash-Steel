import math

import frappe
from frappe import _
from frappe.utils import cint, flt, today, add_days


def _get_horizon_days() -> int:
    """Return number of days to look back based on ADU Horizon.single DocType."""
    horizon = frappe.get_single("ADU Horizon")
    weeks_raw = getattr(horizon, "week", None) or 0
    weeks = cint(weeks_raw) or 0
    if weeks <= 0:
        return 0
    return weeks * 7


def _get_item_consumption(item_code: str, start_date=None, end_date=None) -> float:
    """Get total consumption for a single item within the date range."""
    if not item_code:
        return 0.0

    consumption = 0.0

    # Get item type to determine which consumption source to use
    item_type = frappe.db.get_value("Item", item_code, "custom_item_type")
    # Normalize to lowercase for case-insensitive comparison
    item_type_lower = (item_type or "").lower()

    if item_type_lower in ("rb", "bo"):
        # For items with item_type = "rb" or "bo": sum actual_rm_consumption from Bright Bar Production doctype
        # where this item is the raw_material
        query = """
            SELECT COALESCE(SUM(bbp.actual_rm_consumption), 0) AS total_rm_consumption
            FROM `tabBright Bar Production` bbp
            WHERE
                bbp.raw_material = %s
                AND bbp.docstatus = 1
        """
        params = [item_code]
        
        if start_date and end_date:
            query += " AND bbp.production_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        row = frappe.db.sql(query, tuple(params), as_dict=True)
        consumption = flt(row[0].get("total_rm_consumption", 0.0) if row else 0.0)

    elif item_type_lower in ("rm", "traded"):
        # For items with item_type = "rm" or "traded": sum billet_weight from Billet Cutting doctype
        query = """
            SELECT COALESCE(SUM(bc.billet_weight), 0) AS total_billet_weight
            FROM `tabBillet Cutting` bc
            WHERE
                bc.billet_size = %s
                AND bc.docstatus = 1
        """
        params = [item_code]
        
        if start_date and end_date:
            query += " AND bc.posting_date BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        
        row = frappe.db.sql(query, tuple(params), as_dict=True)
        consumption = flt(row[0].get("total_billet_weight", 0.0) if row else 0.0)

    return consumption


def _calculate_item_adu(item_code: str) -> int:
    """Calculate Average Daily Usage for a single item (ceiled to whole number)."""
    if not item_code:
        return 0

    days = _get_horizon_days()
    if days <= 0:
        return 0

    end_date = today()
    # Include "days" number of days including today
    start_date = add_days(end_date, -(days - 1))

    # Get sales quantity
    row = frappe.db.sql(
        """
        SELECT COALESCE(SUM(sii.qty), 0) AS total_qty
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        WHERE
            sii.item_code = %s
            AND si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
        """,
        (item_code, start_date, end_date),
        as_dict=True,
    )

    sales_qty = flt(row[0].get("total_qty") if row else 0.0)
    
    # Get consumption quantity (filtered by same date range as sales)
    # This matches the TOG calculation report logic
    consumption_qty = _get_item_consumption(item_code, start_date, end_date)
    
    # Total usage = sales + consumption (matching TOG calculation report)
    total_qty = sales_qty + consumption_qty
    
    if days <= 0:
        return 0

    # Ceil to whole number so 1000.12 → 1001, 2132.143 → 2133
    # This matches the TOG calculation report: math.ceil(adu_raw)
    if days > 0 and total_qty > 0:
        adu_raw = total_qty / days
        return int(math.ceil(adu_raw))
    else:
        return 0


def _update_item_adu(item_code: str) -> int:
    """Internal helper to calculate and write ADU back to the Item."""
    adu = _calculate_item_adu(item_code)

    # Only attempt to update if the Item exists
    if frappe.db.exists("Item", item_code):
        # custom_adu is expected to be a Float custom field on Item
        frappe.db.set_value("Item", item_code, "custom_adu", adu)

    return adu


@frappe.whitelist()
def update_item_adu(item_code: str) -> int:
    """
    Public/whitelisted API to recalculate ADU for a single Item.

    Usage (Python):
        from prakash_steel.api.adu import update_item_adu
        update_item_adu("ITEM-0001")

    Usage (JS):
        frappe.call('prakash_steel.api.adu.update_item_adu', { item_code: 'ITEM-0001' })
    """
    if not frappe.has_permission("Item", "write"):
        frappe.throw(_("Not permitted to update ADU for Items."), frappe.PermissionError)

    if not item_code:
        frappe.throw("Item Code is required to update ADU.")

    return _update_item_adu(item_code)


def update_adu_for_sales_invoice(doc) -> None:
    """
    Convenience helper to be called from Sales Invoice hooks/overrides.
    Recalculates ADU for all unique items present in the given Sales Invoice doc.
    """
    if not getattr(doc, "items", None):
        return

    processed: set[str] = set()
    for row in doc.items:
        item_code = getattr(row, "item_code", None)
        if not item_code or item_code in processed:
            continue
        processed.add(item_code)
        try:
            _update_item_adu(item_code)
        except Exception:
            frappe.log_error(
                title="Failed to update ADU for Item {0}".format(item_code),
                message=frappe.get_traceback(),
            )


@frappe.whitelist()
def recalculate_adu_for_all_items() -> None:
    """
    Recalculate ADU for all stock items so that Item.custom_adu matches
    the same horizon logic used in reports.

    Intended to be called from a daily scheduler event.
    """
    if not frappe.has_permission("Item", "write"):
        frappe.throw(_("Not permitted to recalculate ADU for Items."), frappe.PermissionError)

    days = _get_horizon_days()
    if days <= 0:
        return

    end_date = today()
    start_date = add_days(end_date, -(days - 1))

    # Get total sales qty per item in the horizon
    rows = frappe.db.sql(
        """
        SELECT
            sii.item_code,
            COALESCE(SUM(sii.qty), 0) AS total_qty
        FROM `tabSales Invoice Item` sii
        INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
        INNER JOIN `tabItem` i ON i.name = sii.item_code
        WHERE
            si.docstatus = 1
            AND si.posting_date BETWEEN %s AND %s
            AND i.is_stock_item = 1
        GROUP BY sii.item_code
        """,
        (start_date, end_date),
        as_dict=True,
    )

    sales_map = {row.item_code: flt(row.total_qty) for row in rows}

    # Get consumption for all items (filtered by same date range as sales)
    consumption_map = {}
    
    # Get consumption from Bright Bar Production for items with item_type = "rb" or "bo"
    # where the item is consumed as raw_material
    bright_bar_rows = frappe.db.sql(
        """
        SELECT
            bbp.raw_material AS item_code,
            COALESCE(SUM(bbp.actual_rm_consumption), 0) AS total_rm_consumption
        FROM `tabBright Bar Production` bbp
        INNER JOIN `tabItem` i ON i.name = bbp.raw_material
        WHERE
            bbp.docstatus = 1
            AND LOWER(i.custom_item_type) IN ('rb', 'bo')
            AND i.is_stock_item = 1
            AND bbp.production_date BETWEEN %s AND %s
        GROUP BY bbp.raw_material
        """,
        (start_date, end_date),
        as_dict=True,
    )

    for row in bright_bar_rows:
        item_code = row.get("item_code")
        if item_code:
            consumption_map[item_code] = flt(row.get("total_rm_consumption", 0.0))

    # Get consumption from Billet Cutting for items with item_type = "rm" or "traded"
    billet_cutting_rows = frappe.db.sql(
        """
        SELECT
            bc.billet_size AS item_code,
            COALESCE(SUM(bc.billet_weight), 0) AS total_billet_weight
        FROM `tabBillet Cutting` bc
        INNER JOIN `tabItem` i ON i.name = bc.billet_size
        WHERE
            bc.docstatus = 1
            AND LOWER(i.custom_item_type) IN ('rm', 'traded')
            AND i.is_stock_item = 1
            AND bc.posting_date BETWEEN %s AND %s
        GROUP BY bc.billet_size
        """,
        (start_date, end_date),
        as_dict=True,
    )

    for row in billet_cutting_rows:
        item_code = row.get("item_code")
        if item_code:
            # If item already has consumption from Bright Bar Production, add to it
            # Otherwise, set it
            current_consumption = consumption_map.get(item_code, 0.0)
            consumption_map[item_code] = current_consumption + flt(row.get("total_billet_weight", 0.0))

    # Get all stock items so we also reset ADU to 0 when there is no sales/consumption in horizon
    all_items = frappe.get_all(
        "Item",
        filters={"is_stock_item": 1},
        pluck="name",
    )

    for item_code in all_items:
        sales_qty = sales_map.get(item_code, 0.0)
        consumption_qty = consumption_map.get(item_code, 0.0)
        total_qty = sales_qty + consumption_qty
        
        # Ceil to whole number so 1000.12 → 1001, matching TOG calculation report
        if days > 0 and total_qty > 0:
            adu_raw = total_qty / days
            adu_ceiled = int(math.ceil(adu_raw))
        else:
            adu_ceiled = 0

        frappe.db.set_value("Item", item_code, "custom_adu", adu_ceiled)






