import frappe
from frappe import _


def validate_cancel_reason(doc, method=None) -> None:
    """Server-side guard: block cancellation if Cancel Reason is missing.

    This runs for ALL cancellation paths, including list view bulk cancel.
    """
    reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
    if not reason:
        frappe.throw(
            _("Please enter Cancel Reason before cancelling this Sales Order."),
            title=_("Cancel Reason Required"),
        )


@frappe.whitelist()
def cancel_sales_order_with_reason(name: str, reason: str) -> None:
    """Cancel a Sales Order (and any linked Sales Invoices) after capturing a Cancel Reason."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    reason = reason.strip()

    if not frappe.has_permission("Sales Order", "cancel") or not frappe.has_permission("Sales Invoice", "cancel"):
        frappe.throw(
            _("Not permitted to cancel Sales Orders and linked Sales Invoices."),
            frappe.PermissionError,
        )

    so = frappe.get_doc("Sales Order", name)

    if so.docstatus != 1:
        frappe.throw(
            _("Only submitted Sales Orders can be cancelled."),
            title=_("Invalid Document Status"),
        )

    # Set reason on Sales Order first
    frappe.db.set_value(
        "Sales Order",
        name,
        "custom_cancel_reason",
        reason,
        update_modified=False,
    )

    # Cancel any linked Sales Invoices using the SAME reason
    linked_invoices = frappe.db.sql(
        """
        select distinct si.name
        from `tabSales Invoice` si
        inner join `tabSales Invoice Item` sii on si.name = sii.parent
        where sii.sales_order = %s and si.docstatus = 1
        """,
        name,
        as_dict=True,
    )

    from prakash_steel.utils.sales_invoice_cancel import (
        cancel_sales_invoice_with_reason,
    )

    for row in linked_invoices:
        cancel_sales_invoice_with_reason(row.name, reason)

    # Reload and cancel the Sales Order itself
    so = frappe.get_doc("Sales Order", name)
    so.cancel()

    return {"name": so.name, "docstatus": so.docstatus}


