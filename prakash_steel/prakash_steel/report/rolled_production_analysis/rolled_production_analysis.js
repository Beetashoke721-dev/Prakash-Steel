// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Rolled Production Analysis"] = {
	filters: [
		{
			fieldname: "view_by",
			label: __("View By"),
			fieldtype: "Select",
			options: "Sale Quantity\nSale Value\nThroughput",
			default: "Sale Quantity",
			reqd: 1,
		},
	],
};
