# import frappe
# from frappe import _


# def validate_cancel_reason(doc, method=None):
#     """Server-side guard: block cancellation if Cancel Reason is missing.

#     This runs for ALL cancellation paths, including list view bulk cancel.
#     """
#     reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
#     if not reason:
#         frappe.throw(
#             _("Please enter Cancel Reason before cancelling this Purchase Invoice."),
#             title=_("Cancel Reason Required"),
#         )


# @frappe.whitelist()
# def cancel_purchase_invoice_with_reason(name: str, reason: str):
#     """Cancel a submitted Purchase Invoice after capturing a Cancel Reason."""
#     if not reason or not str(reason).strip():
#         frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

#     doc = frappe.get_doc("Purchase Invoice", name)

#     if doc.docstatus != 1:
#         frappe.throw(
#             _("Only submitted Purchase Invoices can be cancelled."),
#             title=_("Invalid Document Status"),
#         )

#     # Store the reason directly in the database to bypass update-after-submit validation
#     frappe.db.set_value(
#         "Purchase Invoice",
#         name,
#         "custom_cancel_reason",
#         reason.strip(),
#         update_modified=False,
#     )

#     # Reload and perform the cancel; standard ERPNext on_cancel will run
#     doc = frappe.get_doc("Purchase Invoice", name)
#     doc.cancel()

#     return {"name": doc.name, "docstatus": doc.docstatus}




import frappe
from frappe import _
from frappe.utils import cint, flt


def clear_cancel_reason_on_amend(doc, method=None) -> None:
    """Clear cancel reason on an amended (draft) Purchase Invoice."""
    if doc.amended_from and doc.docstatus == 0 and doc.custom_cancel_reason:
        doc.custom_cancel_reason = ""

def update_gross_amount_on_items(doc, method=None) -> None:
    """Compute custom_gross_amount on each Purchase Invoice Item row.

    Formula:
      gross = taxable_value + (igst_amount if igst_amount else (cgst_amount + sgst_amount))
    """
    if not getattr(doc, "items", None):
        return

    for item in doc.get("items"):
        taxable_value = flt(item.get("taxable_value") or item.get("net_amount") or item.get("amount") or 0)
        igst_amount = flt(item.get("igst_amount") or 0)
        cgst_amount = flt(item.get("cgst_amount") or 0)
        sgst_amount = flt(item.get("sgst_amount") or 0)

        gst_component = igst_amount if igst_amount else (cgst_amount + sgst_amount)
        item.custom_gross_amount = taxable_value + gst_component


def update_total_weight_slip_qty(doc, method=None) -> None:
    """Sum weight slip qty from items; shortage = total_qty - total weight slip qty."""
    doc.custom_total_weight_slip_qty = sum(
        flt(item.get("custom_weight_slip_qty") or 0) for item in (doc.get("items") or [])
    )
    doc.custom_shortage_qty = cint(
        flt(doc.get("total_qty") or 0) - flt(doc.custom_total_weight_slip_qty or 0)
    )


def validate_cancel_reason(doc, method=None) -> None:
    """Server-side guard: block cancellation if Cancel Reason is missing.

    This runs for ALL cancellation paths, including list view bulk cancel.
    """
    reason = (getattr(doc, "custom_cancel_reason", "") or "").strip()
    if not reason:
        frappe.throw(
            _("Please enter Cancel Reason before cancelling this Purchase Invoice."),
            title=_("Cancel Reason Required"),
        )


@frappe.whitelist()
def set_purchase_invoice_cancel_reason(name: str, reason: str) -> None:
    """Set cancel reason on Purchase Invoice before running standard cancel flow."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    doc = frappe.get_doc("Purchase Invoice", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Purchase Invoices can have a cancel reason set."),
            title=_("Invalid Document Status"),
        )

    frappe.db.set_value(
        "Purchase Invoice",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    return {"name": doc.name}


@frappe.whitelist()
def cancel_purchase_invoice_with_reason(name: str, reason: str) -> None:
    """Cancel a submitted Purchase Invoice after capturing a Cancel Reason."""
    if not reason or not str(reason).strip():
        frappe.throw(_("Cancel Reason is required."), title=_("Missing Cancel Reason"))

    doc = frappe.get_doc("Purchase Invoice", name)

    if doc.docstatus != 1:
        frappe.throw(
            _("Only submitted Purchase Invoices can be cancelled."),
            title=_("Invalid Document Status"),
        )

    # Store the reason directly in the database to bypass update-after-submit validation
    frappe.db.set_value(
        "Purchase Invoice",
        name,
        "custom_cancel_reason",
        reason.strip(),
        update_modified=False,
    )

    # Reload and perform the cancel; standard ERPNext on_cancel will run
    doc = frappe.get_doc("Purchase Invoice", name)
    doc.cancel()

    return {"name": doc.name, "docstatus": doc.docstatus}








