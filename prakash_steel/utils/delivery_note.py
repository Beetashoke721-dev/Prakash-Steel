import frappe


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None, args=None):
    from erpnext.stock.doctype.delivery_note.delivery_note import (
        make_sales_invoice as _make_sales_invoice,
    )

    doc = _make_sales_invoice(source_name, target_doc=target_doc, args=args)

    if not (doc and doc.items):
        return doc

    dn_detail_names = [item.dn_detail for item in doc.items if item.get("dn_detail")]
    dn_expected_dates = {}
    if dn_detail_names:
        dn_expected_dates = dict(
            frappe.db.get_values(
                "Delivery Note Item",
                {"name": ["in", dn_detail_names]},
                ["name", "custom_expexted_delivery_date"],
                as_dict=False,
            )
        )

    # Fallback to the linked Sales Order Item's delivery_date for Delivery Note
    # Items that predate the custom_expexted_delivery_date field or were never
    # created through the Sales Order -> Delivery Note flow.
    so_detail_names = [
        item.so_detail
        for item in doc.items
        if item.get("so_detail") and not dn_expected_dates.get(item.get("dn_detail"))
    ]
    so_delivery_dates = {}
    if so_detail_names:
        so_delivery_dates = dict(
            frappe.db.get_values(
                "Sales Order Item",
                {"name": ["in", so_detail_names]},
                ["name", "delivery_date"],
                as_dict=False,
            )
        )

    for item in doc.items:
        expected_date = dn_expected_dates.get(item.get("dn_detail")) or so_delivery_dates.get(
            item.get("so_detail")
        )
        if expected_date:
            item.expected_delivery_date = expected_date

    return doc
