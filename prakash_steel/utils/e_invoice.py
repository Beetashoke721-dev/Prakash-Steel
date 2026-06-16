import frappe
from frappe import _

from prakash_steel.utils.whitelist_permissions import require_permission


@frappe.whitelist()
def cancel_e_invoice(docname, values):
    """
    Override for `india_compliance.gst_india.utils.e_invoice.cancel_e_invoice`.

    India Compliance cancels the Sales Invoice after cancelling IRN/e-Waybill.
    Our Sales Invoice override enforces `custom_cancel_reason` in `before_cancel`,
    so we must persist a reason *before* calling the original flow.
    """
    require_permission("Sales Invoice", "cancel", _("Not permitted to cancel Sales Invoice."))
    try:
        from india_compliance.gst_india.utils import e_invoice as ic_e_invoice
    except Exception:
        # If India Compliance isn't installed/enabled, fail loudly (otherwise cancellation would be inconsistent)
        frappe.throw(
            _("e-Invoice app is not available. Please contact System Administrator."),
            title=_("Missing App"),
        )

    values = frappe.parse_json(values)

    reason = (values.get("reason") or "").strip()
    remark = (values.get("remark") or "").strip()
    custom_cancel_reason = (values.get("custom_cancel_reason") or "").strip()

    if not reason:
        # Keep behavior consistent with the e-Invoice dialog which requires a reason
        frappe.throw(_("Cancel Reason is required."), title=_("Cancel Reason Required"))

    # Store internal cancel reason so our CustomSalesInvoice.before_cancel doesn't block cancellation.
    # This should come from *your* internal dropdown (not the NIC reason).
    if not custom_cancel_reason:
        frappe.throw(
            _("Please select Internal Cancel Reason before cancelling this Sales Invoice."),
            title=_("Cancel Reason Required"),
        )

    doc = ic_e_invoice.load_doc("Sales Invoice", docname, "cancel")

    internal_reason = custom_cancel_reason
    frappe.db.set_value(
        "Sales Invoice",
        doc.name,
        "custom_cancel_reason",
        internal_reason,
        update_modified=False,
    )

    doc.reload()
    ic_e_invoice._cancel_e_invoice(doc, values)
    return ic_e_invoice.send_updated_doc(doc)

