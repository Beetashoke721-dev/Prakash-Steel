// Copyright (c) 2026, Prakash Steel and contributors
// For license information, please see license.txt

frappe.query_reports["Custom General Ledger Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Autocomplete",
			options: Object.keys(frappe.boot.party_account_types),
			on_change: function () {
				frappe.query_report.set_filter_value("party_name", []);
			},
		},
		{
			fieldname: "party_name",
			label: __("Party Name"),
			fieldtype: "MultiSelectList",
			depends_on: "party_type",
			get_data: function (txt) {
				let party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return;

				return frappe
					.xcall(
						"prakash_steel.prakash_steel.report.custom_general_ledger_report.custom_general_ledger_report.get_party_name_options",
						{ txt: txt || "", party_type: party_type }
					)
					.then((data) => data || []);
			},
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: function (txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.defaults.get_user_default("Company"),
				});
			},
		},
		{
			fieldname: "categorize_by",
			label: __("Categorize by"),
			fieldtype: "Select",
			options: [
				"",
				{
					label: __("Categorize by Voucher"),
					value: "Categorize by Voucher",
				},
				{
					label: __("Categorize by Voucher (Consolidated)"),
					value: "Categorize by Voucher (Consolidated)",
				},
				{
					label: __("Categorize by Account"),
					value: "Categorize by Account",
				},
				{
					label: __("Categorize by Party"),
					value: "Categorize by Party",
				},
			],
			default: "Categorize by Voucher (Consolidated)",
		},
	],
};
