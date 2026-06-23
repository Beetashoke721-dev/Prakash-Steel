"""Create Repost Item Valuation entries for all SLEs with negative incoming_rate.

These were created by Manufacture stock entries where RM cost was zero but scrap
had existing valuation, causing ERPNext formula (RM - scrap) / qty to go negative.
The CustomStockEntry override now prevents this going forward; this patch fixes
historical SLEs by triggering ERPNext's standard repost mechanism.
"""

import frappe


def execute():
    bad_sles = frappe.db.sql(
        """
        SELECT DISTINCT voucher_no, posting_date, posting_time
        FROM `tabStock Ledger Entry`
        WHERE incoming_rate < 0
          AND is_cancelled = 0
        ORDER BY posting_date ASC, posting_time ASC
        """,
        as_dict=True,
    )

    if not bad_sles:
        frappe.msgprint("No negative incoming_rate SLEs found — nothing to fix.")
        return

    for row in bad_sles:
        # Skip if a repost entry already exists for this voucher
        if frappe.db.exists(
            "Repost Item Valuation",
            {"voucher_type": "Stock Entry", "voucher_no": row.voucher_no, "docstatus": ("!=", 2)},
        ):
            continue

        riv = frappe.new_doc("Repost Item Valuation")
        riv.based_on = "Transaction"
        riv.voucher_type = "Stock Entry"
        riv.voucher_no = row.voucher_no
        riv.posting_date = row.posting_date
        riv.posting_time = row.posting_time
        riv.allow_negative_stock = 0
        riv.flags.ignore_permissions = True
        riv.insert()
        riv.submit()

    frappe.db.commit()
    frappe.msgprint(
        f"Created and submitted Repost Item Valuation for {len(bad_sles)} voucher(s). "
        "Check the Repost Item Valuation list to confirm status."
    )
