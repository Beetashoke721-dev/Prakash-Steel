// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Scorecard Sales Invoice"] = {
	formatter: function (value, row, column, data, default_formatter) {
		const fname = column.fieldname || column.id;
		// Int/Currency formatters wrap in text-align:right; inline skips that wrapper.
		if (
			["qty_ordered", "qty_invoiced", "invoice_qty", "pending_qty", "book_value"].includes(
				fname
			)
		) {
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
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 0,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 0,
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "sales_order",
			label: __("Sales Order"),
			fieldtype: "Link",
			options: "Sales Order",
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
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
		},
	],
};
