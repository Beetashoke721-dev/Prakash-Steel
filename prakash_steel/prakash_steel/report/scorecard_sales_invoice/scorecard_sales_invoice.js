// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Scorecard Sales Invoice"] = {
	formatter: function (value, row, column, data, default_formatter) {
		const fname = column.fieldname || column.id;
		// Int/Currency formatters wrap in text-align:right; inline skips that wrapper.
		if (fname === "qty" || fname === "item_price") {
			const formatted = frappe.format(value, column, {
				for_print: false,
				always_show_decimals: true,
				inline: true,
			}, data);
			return `<div style="text-align:left;width:100%">${formatted ?? ""}</div>`;
		}
		if (fname === "sales_order_number") {
			const formatted = default_formatter(value, row, column, data);
			return `<div style="text-align:left;width:100%">${formatted ?? ""}</div>`;
		}
		return default_formatter(value, row, column, data);
	},
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
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "sales_invoice",
			label: __("Sales Invoice"),
			fieldtype: "Link",
			options: "Sales Invoice",
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "customer_group_name",
			label: __("Customer Group Name"),
			fieldtype: "Data",
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
