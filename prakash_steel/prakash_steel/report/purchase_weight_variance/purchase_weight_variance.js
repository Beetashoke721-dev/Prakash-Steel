// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Weight Variance"] = {
	"filters": [
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "po_no",
			"label": __("PO No"),
			"fieldtype": "Link",
			"options": "Purchase Order",
		},
	]
};
