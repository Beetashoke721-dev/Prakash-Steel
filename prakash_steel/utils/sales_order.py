import frappe
from frappe import _


@frappe.whitelist()
def make_delivery_note(source_name, target_doc=None, kwargs=None):
    from erpnext.selling.doctype.sales_order.sales_order import (
        make_delivery_note as _make_delivery_note,
    )

    doc = _make_delivery_note(source_name, target_doc=target_doc, kwargs=kwargs)

    if not (doc and doc.items):
        return doc

    original_count = len(doc.items)

    doc.items = [
        item
        for item in doc.items
        if not (
            item.get("so_detail")
            and frappe.db.get_value(
                "Sales Order Item",
                item.so_detail,
                "custom_closed",
            )
        )
    ]

    for idx, item in enumerate(doc.items, 1):
        item.idx = idx

    so_detail_names = [item.so_detail for item in doc.items if item.get("so_detail")]
    delivery_dates = {}
    if so_detail_names:
        delivery_dates = frappe.db.get_values(
            "Sales Order Item",
            {"name": ["in", so_detail_names]},
            ["name", "delivery_date"],
            as_dict=False,
        )
        delivery_dates = dict(delivery_dates)

    for item in doc.items:
        if item.get("so_detail") and delivery_dates.get(item.so_detail):
            item.custom_expexted_delivery_date = delivery_dates[item.so_detail]

    closed_count = original_count - len(doc.items)

    if closed_count:
        frappe.msgprint(
            _("{0} closed item(s) were excluded from the Delivery Note.").format(
                closed_count
            ),
            indicator="orange",
            alert=True,
        )

    return doc


@frappe.whitelist()
def make_sales_invoice(
    source_name,
    target_doc=None,
    ignore_permissions=False,
    args=None,
):
    from erpnext.selling.doctype.sales_order.sales_order import (
        make_sales_invoice as _make_sales_invoice,
    )

    doc = _make_sales_invoice(
        source_name,
        target_doc=target_doc,
        ignore_permissions=ignore_permissions,
        args=args,
    )

    if not (doc and doc.items):
        return doc

    original_count = len(doc.items)

    doc.items = [
        item
        for item in doc.items
        if not (
            item.get("so_detail")
            and frappe.db.get_value(
                "Sales Order Item",
                item.so_detail,
                "custom_closed",
            )
        )
    ]

    for idx, item in enumerate(doc.items, 1):
        item.idx = idx

    so_detail_names = [item.so_detail for item in doc.items if item.get("so_detail")]
    delivery_dates = {}
    if so_detail_names:
        delivery_dates = frappe.db.get_values(
            "Sales Order Item",
            {"name": ["in", so_detail_names]},
            ["name", "delivery_date"],
            as_dict=False,
        )
        delivery_dates = dict(delivery_dates)

    for item in doc.items:
        if item.get("so_detail") and delivery_dates.get(item.so_detail):
            item.expected_delivery_date = delivery_dates[item.so_detail]

    closed_count = original_count - len(doc.items)

    if closed_count:
        frappe.msgprint(
            _("{0} closed item(s) were excluded from the Sales Invoice.").format(
                closed_count
            ),
            indicator="orange",
            alert=True,
        )

    return doc