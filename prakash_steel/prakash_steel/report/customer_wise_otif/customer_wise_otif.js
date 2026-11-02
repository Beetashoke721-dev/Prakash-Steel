// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Customer wise OTIF"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			width: "80",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_default("company"),
		},
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			width: "80",
			options: "Fiscal Year",
			reqd: 1,
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			width: "80",
		},
	],
};
