// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Weekly Register"] = {
	filters: [
		{
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: frappe.defaults.get_user_default("fiscal_year"),
			reqd: 1,
		},
	],
	tree: true,
	name_field: "business_measure",
	parent_field: "parent_measure",
	initial_depth: 0,
	formatter: function (value, row, column, data, default_formatter) {
		// A week column with no value for this row is `undefined` (the key is simply
		// absent from the row, e.g. a heading, or a week before data exists). Frappe's
		// Float formatter only blanks a strict `null`, so an absent value falls through
		// and renders as "0.00" instead of blank - skip it ourselves before that happens.
		if (column.fieldname && column.fieldname.startsWith("week_") && (value === undefined || value === null || value === "")) {
			return "";
		}
		value = default_formatter(value, row, column, data);
		if (data && column.fieldname === "business_measure" && data.is_group) {
			value = `<b>${value}</b>`;
		}
		return value;
	},
};
