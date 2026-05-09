// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Planning Engine Sales Invoice"] = {
	onload: function (report) {
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "Sales Invoice",
				fields: ["place_of_supply"],
				filters: {
					docstatus: 1,
				},
				group_by: "place_of_supply",
				order_by: "place_of_supply asc",
				limit_page_length: 500,
			},
			callback: function (r) {
				const values = [""];
				(r.message || []).forEach((row) => {
					if (row.place_of_supply) values.push(row.place_of_supply);
				});

				const placeFilter = report.get_filter("place_of_supply");
				placeFilter.df.options = values.join("\n");
				placeFilter.refresh();
			},
		});
	},
	filters: [
		{
			fieldname: "financial_year",
			label: __("Financial Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			reqd: 1,
			default: frappe.defaults.get_user_default("fiscal_year"),
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: [
				"",
				"January",
				"February",
				"March",
				"April",
				"May",
				"June",
				"July",
				"August",
				"September",
				"October",
				"November",
				"December",
			].join("\n"),
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
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "category_name",
			label: __("Category Name"),
			fieldtype: "Link",
			options: "Item Category",
		},
		{
			fieldname: "place_of_supply",
			label: __("Place of Supply"),
			fieldtype: "Select",
			options: "",
		},
	],
};
