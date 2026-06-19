# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, flt

class UnsecuredLoansandTransaction(Document): 
    def validate(self) -> None:
        # Set the dates based on the Fiscal Year selected
        self.set_from_to_dates()
        
        # We no longer call populate_interest_details() or calculate_totals() 
        # as the child table logic has been removed.

    def set_from_to_dates(self) -> None:
        """Sets From and To dates based on the selected Fiscal Year."""
        if self.financial_year:
            fy = frappe.get_doc("Fiscal Year", self.financial_year)
            self.from_date = fy.year_start_date
            self.to_date = fy.year_end_date

# ----------------------------------------------------------------------
# Helpers (Modified to remove child table dependencies)
# ----------------------------------------------------------------------

def get_closing_balance(account, date) -> float:
    """
    Fetches the closing balance for a specific account up to a certain date.
    """
    if not account:
        return 0.0
    try:
        result = frappe.db.sql("""
            SELECT SUM(credit) - SUM(debit) AS balance
            FROM `tabGL Entry`
            WHERE account      = %(account)s
              AND posting_date <= %(date)s
              AND is_cancelled  = 0
              AND docstatus     = 1
        """, {"account": account, "date": str(date)}, as_dict=True)
        
        if result and result[0].get("balance") is not None:
            # Using abs() assuming unsecured loans are usually credit balances
            return abs(flt(result[0]["balance"]))
        return 0.0
    except Exception:
        frappe.log_error(
            message=frappe.get_traceback(),
            title=f"GL Balance Fetch Error: {account} on {date}"
        )
        return 0.0

# Note: The scheduled job 'fetch_daily_interest_for_all_active_docs' 
# has been removed as it relied entirely on updating the child table.