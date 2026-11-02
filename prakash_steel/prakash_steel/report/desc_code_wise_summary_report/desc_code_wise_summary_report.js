// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Desc Code Wise Summary Report"] = {
	filters: [
		{
			fieldname: "transaction_type",
			label: __("Sale/Purchase"),
			fieldtype: "Select",
			options: "Sale\nPurchase",
			default: "Sale",
			reqd: 1,
		},
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
	],
};
