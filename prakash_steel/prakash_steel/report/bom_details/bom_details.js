// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["BOM Details"] = {
	filters: [
		{
			fieldname: 'is_active',
			label: __('isActive'),
			fieldtype: 'Select',
			options: '\nYes\nNo',
			default: ''
		},
		{
			fieldname: 'is_default',
			label: __('isDefault'),
			fieldtype: 'Select',
			options: '\nYes\nNo',
			default: ''
		},
	],
};
