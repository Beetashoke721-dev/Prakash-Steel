// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Bright Production HBT"] = {
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

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "hbt" && data) {
			if (data.hbt === "H") {
				value = `<span style="background-color:#1a7a3f; color:#ffffff; font-weight:bold; padding:2px 8px; border-radius:4px;">${value}</span>`;
			} else if (data.hbt === "B") {
				value = `<span style="background-color:#d4a000; color:#ffffff; font-weight:bold; padding:2px 8px; border-radius:4px;">${value}</span>`;
			} else if (data.hbt === "T") {
				value = `<span style="background-color:#c0152a; color:#ffffff; font-weight:bold; padding:2px 8px; border-radius:4px;">${value}</span>`;
			}
		}

		return value;
	},
};
