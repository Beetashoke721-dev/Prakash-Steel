import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt


def _compute_gross(item: dict) -> float:
    taxable_value = flt(
        item.get("taxable_value") or item.get("net_amount") or item.get("amount") or 0
    )
    igst = flt(item.get("igst_amount") or 0)
    cgst = flt(item.get("cgst_amount") or 0)
    sgst = flt(item.get("sgst_amount") or 0)

    gst_component = igst if igst else (cgst + sgst)
    return taxable_value + gst_component


def _ensure_custom_field() -> None:
    if frappe.db.exists("Custom Field", "Purchase Invoice Item-custom_gross_amount"):
        return

    create_custom_fields(
        {
            "Purchase Invoice Item": [
                {
                    "fieldname": "custom_gross_amount",
                    "fieldtype": "Currency",
                    "label": "Gross Amount",
                    "insert_after": "amount",
                    "read_only": 1,
                }
            ]
        },
        update=True,
    )


def _backfill_existing() -> None:
    rows = frappe.db.sql(
        """
        SELECT
            name, taxable_value, net_amount, amount, igst_amount, cgst_amount, sgst_amount
        FROM `tabPurchase Invoice Item`
        """,
        as_dict=True,
    )

    for row in rows:
        frappe.db.set_value(
            "Purchase Invoice Item",
            row["name"],
            "custom_gross_amount",
            _compute_gross(row),
            update_modified=False,
        )


def execute() -> tuple[list, list]:
    _ensure_custom_field()
    _backfill_existing()
