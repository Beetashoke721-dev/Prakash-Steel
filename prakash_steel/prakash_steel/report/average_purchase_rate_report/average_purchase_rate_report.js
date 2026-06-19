// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

frappe.query_reports["Average Purchase Rate Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "grade",
			label: __("Grade"),
			fieldtype: "Link",
			options: "Item Grade",
		},
	],
};
