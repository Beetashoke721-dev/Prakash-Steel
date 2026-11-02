// Copyright (c) 2026, beetashoke chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Root Cause Analysis", {
	setup(frm) {
		frm.set_query("sales_invoice", () => {
			return {
				filters: {
					customer: frm.doc.customer,
					docstatus: 1,
				},
			};
		});

		frm.set_query("item", () => {
			return {
				query: "prakash_steel.prakash_steel.doctype.root_cause_analysis.root_cause_analysis.get_sales_invoice_items",
				filters: {
					sales_invoice: frm.doc.sales_invoice,
				},
			};
		});
	},

	customer(frm) {
		frm.set_value("sales_invoice", "");
		frm.set_value("item", "");
	},

	sales_invoice(frm) {
		frm.set_value("item", "");
	},
});
