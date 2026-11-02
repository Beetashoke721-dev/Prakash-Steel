# Copyright (c) 2026, Beetashoke Chakraborty and contributors
# For license information, please see license.txt

import frappe

from prakash_steel.prakash_steel.report.customer_hbt.customer_hbt import execute


@frappe.whitelist()
def get_customer_hbt_data(view_by: str = "Sale Quantity"):
	columns, data = execute({"view_by": view_by})
	return {"columns": columns, "data": data}
