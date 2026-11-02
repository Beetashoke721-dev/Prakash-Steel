// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Bright Free Stock"] = {
	filters: [
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
			get_query() {
				return { filters: { custom_item_type: "BB" } };
			},
		},
		{
			fieldname: "include_zero_stock",
			label: __("Include Zero Stock"),
			fieldtype: "Check",
		},
	],
};
