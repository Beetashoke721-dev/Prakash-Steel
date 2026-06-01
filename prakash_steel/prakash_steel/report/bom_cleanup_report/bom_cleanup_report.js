// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Bom Cleanup report"] = {
	"filters": [
		{
			fieldname: "item",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "is_default",
			label: __("Default"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
		{
			fieldname: "is_active",
			label: __("Active"),
			fieldtype: "Select",
			options: "\nYes\nNo",
		},
	]
};
