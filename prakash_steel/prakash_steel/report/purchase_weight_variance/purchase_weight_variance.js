// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Weight Variance"] = {
	"filters": [
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
		},
		{
			"fieldname": "po_no",
			"label": __("PO No"),
			"fieldtype": "Link",
			"options": "Purchase Order",
		},
		{
			"fieldname": "po_status",
			"label": __("PO Status"),
			"fieldtype": "MultiSelectList",
			get_data: function(txt) {
				const statuses = [
					"Draft",
					"To Receive and Bill",
					"To Bill",
					"To Receive",
					"Completed",
					"Closed",
				];
				return statuses
					.filter(s => !txt || s.toLowerCase().includes(txt.toLowerCase()))
					.map(s => ({ value: s, description: "" }));
			},
		},
	]
};
