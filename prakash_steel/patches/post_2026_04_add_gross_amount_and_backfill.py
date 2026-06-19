import frappe
from frappe.utils import flt


def _compute_gross(item: dict) -> float:
    """Compute gross amount for a child row with fallbacks."""
    taxable_value = flt(
        item.get("taxable_value") or item.get("net_amount") or item.get("amount") or 0
    )
    igst = flt(item.get("igst_amount") or 0)
    cgst = flt(item.get("cgst_amount") or 0)
    sgst = flt(item.get("sgst_amount") or 0)
    gst_component = igst if igst else (cgst + sgst)
    return taxable_value + gst_component


def _backfill_existing() -> None:
    """Populate custom_gross_amount for all Sales Invoice Items across all invoices.

    - Works for submitted, draft and cancelled by writing directly to child rows.
    - Avoids modified timestamps on parents.
    """
    item_rows = frappe.db.sql(
        """
		SELECT name, taxable_value, net_amount, amount, igst_amount, cgst_amount, sgst_amount
		FROM `tabSales Invoice Item`
		""",
        as_dict=True,
    )

    if not item_rows:
        return

    for row in item_rows:
        gross = _compute_gross(row)
        frappe.db.set_value(
            "Sales Invoice Item",
            row["name"],
            "custom_gross_amount",
            gross,
            update_modified=False,
        )

    frappe.db.commit()


def execute() -> tuple[list, list]:
    _backfill_existing()
