import frappe
from frappe import _


def validate_cancel_reason(doc, method=None):
    """Server-side guard: block cancellation if Cancel Reason is missing.

    This runs for ALL cancellation paths, including list view bulk cancel.
    """
    reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
    if not reason:
        frappe.throw(
            _("Please enter Cancel Reason before cancelling this Purchase Order."),
            title=_("Cancel Reason Required"),
        )


@frappe.whitelist()
def set_purchase_order_cancel_reason(name: str, reason: str):
    """Set cancel reason on Purchase Order before running standard cancel flow."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    if not frappe.has_permission("Purchase Order", "cancel"):
        frappe.throw(
            _("Not permitted to cancel Purchase Orders."),
            frappe.PermissionError,
        )

    doc = frappe.get_doc("Purchase Order", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Purchase Orders can be cancelled."),
            title=_("Invalid Document Status"),
        )

    frappe.db.set_value(
        "Purchase Order",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    return {"name": doc.name}













