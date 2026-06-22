import frappe
from frappe import _


def validate_cancel_reason(doc, method=None) -> None:
    """Server-side guard: block cancellation if Cancel Reason is missing.

    This runs for ALL cancellation paths, including list view bulk cancel.
    """
    reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
    if not reason:
        frappe.throw(
            _("Please enter Cancel Reason before cancelling this Purchase Receipt."),
            title=_("Cancel Reason Required"),
        )


@frappe.whitelist()
def cancel_purchase_receipt_with_reason(name: str, reason: str) -> dict:
    """Cancel a submitted Purchase Receipt after capturing a Cancel Reason."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    doc = frappe.get_doc("Purchase Receipt", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Purchase Receipts can be cancelled."),
            title=_("Invalid Document Status"),
        )

    # Store the reason directly in the database to bypass update-after-submit validation
    frappe.db.set_value(
        "Purchase Receipt",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    # Reload and perform the cancel; standard ERPNext on_cancel will run
    doc = frappe.get_doc("Purchase Receipt", name)
    doc.cancel()

    return {"name": doc.name, "docstatus": doc.docstatus}

