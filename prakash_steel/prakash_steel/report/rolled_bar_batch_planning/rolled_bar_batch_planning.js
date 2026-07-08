// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Rolled Bar Batch Planning"] = {
	filters: [
		{
			fieldname: "item_type",
			label: __("Item Type"),
			fieldtype: "Select",
			options: "\nRB\nBO\nTraded",
		},
		{
			fieldname: "sku_type",
			label: __("SKU Type"),
			fieldtype: "Select",
			options: "\nRBMTA\nRBMTO\nBOTA\nBOTO\nTRMTA\nTRMTO",
		},
	],
};
