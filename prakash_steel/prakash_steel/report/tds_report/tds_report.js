// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

frappe.query_reports["TDS Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Select",
			options: "\nPurchase Invoice\nSales Invoice",
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Data",
		},
		{
			fieldname: "include_cancelled",
			label: __("Include Cancelled"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		// Total row must stay blank for % (disable_total alone still formats as 0.00).
		if (column.fieldname === "tds_tcs_percent" && (!data || data.is_total_row)) {
			return "";
		}
		return default_formatter(value, row, column, data);
	},
};
