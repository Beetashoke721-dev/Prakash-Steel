// Copyright (c) 2026, beetashoke chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Test Certificate", {
	setup(frm) {
		frm.set_query("sales_invoice", () => ({ filters: { docstatus: 1, is_return: 0 } }));

		frm.set_query("items", () => ({
			query: "prakash_steel.prakash_steel.doctype.test_certificate.test_certificate.get_sales_invoice_items",
			filters: { sales_invoice: frm.doc.sales_invoice },
		}));
	},

	sales_invoice(frm) {
		// Items belong to the previous invoice, so start fresh
		frm.set_value("items", []);
		frm.set_value("quantity", 0);
		frm.set_value("colour_code", "");
	},

	items(frm) {
		const items = (frm.doc.items || []).map((d) => d.item_code).filter(Boolean);
		if (!frm.doc.sales_invoice || !items.length) {
			frm.set_value("quantity", 0);
			frm.set_value("colour_code", "");
			return;
		}

		frappe.call({
			method: "prakash_steel.prakash_steel.doctype.test_certificate.test_certificate.get_colour_code",
			args: { items },
			callback(r) {
				frm.set_value("colour_code", r.message || "");
			},
		});

		frappe.call({
			method: "prakash_steel.prakash_steel.doctype.test_certificate.test_certificate.get_quantity_in_mt",
			args: { sales_invoice: frm.doc.sales_invoice, items },
			callback(r) {
				frm.set_value("quantity", r.message || 0);
			},
		});
	},

	quality_inspection_template(frm) {
		if (!frm.doc.quality_inspection_template) return;

		frm.call({
			method: "get_item_specification_details",
			doc: frm.doc,
			callback() {
				frm.refresh_field("readings");
			},
		});
	},
});
