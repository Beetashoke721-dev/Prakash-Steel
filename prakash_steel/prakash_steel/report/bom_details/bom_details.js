// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["BOM Details"] = {
	filters: [
		{
			fieldname: 'is_active',
			label: __('Is Active'),
			fieldtype: 'Select',
			options: '\nYes\nNo',
			default: ''
		},
		{
			fieldname: 'is_default',
			label: __('Is Default'),
			fieldtype: 'Select',
			options: '\nYes\nNo',
			default: ''
		},
		{
			fieldname: 'parent_item_code',
			label: __('Parent Item Code'),
			fieldtype: 'Link',
			options: 'Item',
			default: '',
			get_query: function() {
				return {
					query: 'prakash_steel.prakash_steel.report.bom_details.bom_details.get_bom_items_for_filter',
					filters: {
						is_active: frappe.query_report.get_filter_value('is_active'),
						is_default: frappe.query_report.get_filter_value('is_default')
					}
				};
			}
		},
		{
			fieldname: 'bom_name',
			label: __('BOM Name'),
			fieldtype: 'Link',
			options: 'BOM',
			default: '',
			get_query: function() {
				return {
					query: 'prakash_steel.prakash_steel.report.bom_details.bom_details.get_boms_for_filter',
					filters: {
						is_active: frappe.query_report.get_filter_value('is_active'),
						is_default: frappe.query_report.get_filter_value('is_default')
					}
				};
			}
		},
	],
};
