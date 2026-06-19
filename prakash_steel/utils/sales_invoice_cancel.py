import frappe
from frappe import _


@frappe.whitelist()
def cancel_sales_invoice_with_reason(name: str, reason: str) -> None:
    """Cancel a submitted Sales Invoice after capturing a Cancel Reason."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    doc = frappe.get_doc("Sales Invoice", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Sales Invoices can be cancelled."),
            title=_("Invalid Document Status"),
        )

    # Store the reason directly in the database to bypass update-after-submit validation
    frappe.db.set_value(
        "Sales Invoice",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    # Reload and perform the cancel; CustomSalesInvoice.before_cancel will still run
    doc = frappe.get_doc("Sales Invoice", name)
    doc.cancel()

    return {"name": doc.name, "docstatus": doc.docstatus}













