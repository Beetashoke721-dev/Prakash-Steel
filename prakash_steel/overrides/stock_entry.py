# Copyright (c) 2025, beetashoke chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from erpnext.stock.doctype.stock_entry.stock_entry import StockEntry
from frappe.utils import flt, formatdate, format_time
from erpnext.stock.stock_ledger import (
    NegativeStockError,
    get_previous_sle,
    is_negative_stock_allowed,
)


class CustomStockEntry(StockEntry):
    """Custom Stock Entry that aggregates *all* insufficient stock errors.

    ERPNext's core `set_actual_qty` throws on the first row that goes
    negative. Here we override that method and collect errors for all
    rows, then throw once with a combined message.
    """

    def validate(self):
        """Override validate to check stock availability on save (docstatus 0) as well."""
        print("=" * 80)
        print("[CONSOLE] CustomStockEntry.validate() called")
        print(f"[CONSOLE] Document name: {self.name}")
        print(f"[CONSOLE] Document status: {self.docstatus}")
        print(f"[CONSOLE] Number of items: {len(self.items) if self.items else 0}")
        print("=" * 80)
        
        # Call parent validate first
        super().validate()

        # For Manufacture entries: if ERPNext calculated a negative basic_rate for the FG
        # item (happens when RM has zero cost and scrap item has an existing valuation),
        # zero out the scrap item rates and recalculate FG rate so validation passes.
        if self.purpose in ("Manufacture", "Repack"):
            has_negative_fg = any(
                flt(item.basic_rate) < 0 and item.is_finished_item
                for item in self.items
            )
            if has_negative_fg:
                # Zero scrap/by-product output items (have t_warehouse, no s_warehouse, not FG)
                for item in self.items:
                    if not item.is_finished_item and item.t_warehouse and not item.s_warehouse:
                        item.basic_rate = 0
                        item.basic_amount = 0
                # Recalculate FG basic_rate from RM cost only (scrap now = 0)
                rm_cost = sum(
                    flt(item.basic_amount)
                    for item in self.items
                    if item.s_warehouse and not item.t_warehouse
                )
                for item in self.items:
                    if item.is_finished_item and flt(item.qty):
                        item.basic_rate = rm_cost / flt(item.qty)
                        item.basic_amount = flt(item.basic_rate) * flt(item.qty)

        # Check stock availability during save (docstatus 0) and submit (docstatus 1)
        print("[CONSOLE] Calling validate_stock_availability()...")
        self.validate_stock_availability()
        print("[CONSOLE] validate_stock_availability() completed")
        print("=" * 80)

    def get_basic_rate_for_manufactured_item(self, finished_item_qty, outgoing_items_cost=0) -> float:
        """Prevent negative FG rate when RM cost is zero but scrap has existing valuation.

        ERPNext formula: (outgoing_items_cost - scrap_items_cost) / finished_item_qty
        When RM cost = 0 and scrap has value, the result goes negative.
        We zero the scrap cost so FG rate = RM cost / FG qty, floored at 0.
        """
        scrap_items_cost = sum(
            flt(d.basic_amount) for d in self.get("items") if d.is_legacy_scrap_item
        )
        rate = super().get_basic_rate_for_manufactured_item(finished_item_qty, outgoing_items_cost)
        if rate < 0:
            # Recalculate ignoring scrap so FG rate is never negative
            rate = flt((outgoing_items_cost) / finished_item_qty) if finished_item_qty else 0
        return max(flt(rate), 0.0)

    def validate_stock_availability(self):
        """Validate stock availability for all items and collect all errors."""
        print("[CONSOLE] validate_stock_availability() started")
        errors = []

        if not self.items:
            print("[CONSOLE] No items found, skipping validation")
            return

        for d in self.get("items"):
            print(f"[CONSOLE] Checking item row {d.idx}: {d.item_code}")
            
            # Skip if no item code
            if not d.item_code:
                print(f"[CONSOLE] Row {d.idx}: No item_code, skipping")
                continue
            
            # Only validate if there's a source warehouse
            if not d.s_warehouse:
                print(f"[CONSOLE] Row {d.idx}: No source warehouse, skipping")
                continue
            
            allow_negative_stock = is_negative_stock_allowed(item_code=d.item_code)
            print(f"[CONSOLE] Row {d.idx}: Allow negative stock: {allow_negative_stock}")

            previous_sle = get_previous_sle(
                {
                    "item_code": d.item_code,
                    "warehouse": d.s_warehouse,
                    "posting_date": self.posting_date,
                    "posting_time": self.posting_time,
                }
            )

            # Get actual stock at warehouse
            actual_qty = previous_sle.get("qty_after_transaction") or 0
            transfer_qty = flt(d.transfer_qty, d.precision("transfer_qty"))
            
            print(f"[CONSOLE] Row {d.idx}: Actual Qty: {actual_qty}, Transfer Qty: {transfer_qty}")

            # Check stock availability (for both save and submit)
            # During save (docstatus 0), we still want to validate
            if (
                d.s_warehouse
                and not allow_negative_stock
                and flt(actual_qty, d.precision("actual_qty"))
                < flt(transfer_qty, d.precision("transfer_qty"))
            ):
                # Calculate shortage quantity
                shortage_qty = flt(transfer_qty - actual_qty, d.precision("transfer_qty"))
                actual_qty_formatted = flt(actual_qty, d.precision("actual_qty"))
                transfer_qty_formatted = flt(transfer_qty, d.precision("transfer_qty"))
                
                msg = (
                    _("Row {0}: {1} Quantity not available for {2} in warehouse {3}").format(
                        d.idx,
                        frappe.bold(shortage_qty),
                        frappe.bold(d.item_code),
                        frappe.bold(d.s_warehouse),
                    )
                    + "<br>"
                    + _("Available quantity is {0}, you need {1}").format(
                        frappe.bold(actual_qty_formatted),
                        frappe.bold(transfer_qty_formatted),
                    )
                )
                errors.append(msg)
                print(f"[CONSOLE] Row {d.idx}: INSUFFICIENT STOCK ERROR added - Shortage: {shortage_qty}")

        # After checking all rows, if any errors were found, throw them together
        if errors:
            print(f"[CONSOLE] Found {len(errors)} stock validation errors")
            combined = "<br><br>".join(errors)
            print("[CONSOLE] Throwing validation error...")
            frappe.throw(combined, NegativeStockError, title=_("Insufficient Stock"))
        else:
            print("[CONSOLE] No stock validation errors found")

    def set_actual_qty(self):
        """Copy of core `set_actual_qty`, but collect errors instead of early-throwing."""
        print("[CONSOLE] set_actual_qty() called")
        
        errors = []

        for d in self.get("items"):
            allow_negative_stock = is_negative_stock_allowed(item_code=d.item_code)

            previous_sle = get_previous_sle(
                {
                    "item_code": d.item_code,
                    "warehouse": d.s_warehouse or d.t_warehouse,
                    "posting_date": self.posting_date,
                    "posting_time": self.posting_time,
                }
            )

            # Same as core: set actual stock at warehouse
            d.actual_qty = previous_sle.get("qty_after_transaction") or 0

            # Our change: don't throw immediately, just record the error
            if (
                d.docstatus == 1
                and d.s_warehouse
                and not allow_negative_stock
                and flt(d.actual_qty, d.precision("actual_qty"))
                < flt(d.transfer_qty, d.precision("actual_qty"))
            ):
                # Calculate shortage quantity
                shortage_qty = flt(d.transfer_qty - d.actual_qty, d.precision("transfer_qty"))
                actual_qty_formatted = flt(d.actual_qty, d.precision("actual_qty"))
                transfer_qty_formatted = flt(d.transfer_qty, d.precision("transfer_qty"))
                
                msg = (
                    _("Row {0}: {1} Quantity not available for {2} in warehouse {3}").format(
                        d.idx,
                        frappe.bold(shortage_qty),
                        frappe.bold(d.item_code),
                        frappe.bold(d.s_warehouse),
                    )
                    + "<br>"
                    + _("Available quantity is {0}, you need {1}").format(
                        frappe.bold(actual_qty_formatted),
                        frappe.bold(transfer_qty_formatted),
                    )
                )
                errors.append(msg)

        # After checking all rows, if any errors were found, throw them together
        if errors:
            combined = "<br><br>".join(errors)
            frappe.throw(combined, NegativeStockError, title=_("Insufficient Stock"))
