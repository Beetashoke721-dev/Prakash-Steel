import frappe
from frappe import _


def validate_cancel_reason(doc, method=None) -> None:
    """Server-side guard: block cancellation if Cancel Reason is missing.

    This runs for ALL cancellation paths, including list view bulk cancel.
    """
    reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
    if not reason:
        frappe.throw(
            _("Please enter Cancel Reason before cancelling this Material Request."),
            title=_("Cancel Reason Required"),
        )
    # pass


@frappe.whitelist()
def cancel_material_request_with_reason(name: str, reason: str) -> dict:
    """Cancel a submitted Material Request after capturing a Cancel Reason (form Cancel button)."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    doc = frappe.get_doc("Material Request", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Material Requests can be cancelled."),
            title=_("Invalid Document Status"),
        )

    # Store the reason directly in the database to bypass update-after-submit validation
    frappe.db.set_value(
        "Material Request",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    # Reload and perform the cancel (standard ERPNext before_cancel/on_cancel will run),
    # and validate_cancel_reason will pass because we just saved the reason.
    doc = frappe.get_doc("Material Request", name)
    doc.cancel()

    return {"name": doc.name, "docstatus": doc.docstatus}














