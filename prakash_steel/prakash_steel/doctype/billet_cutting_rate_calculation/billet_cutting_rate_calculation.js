// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Billet Cutting Rate Calculation", {
	work_order(frm) {
		set_fields_from_work_order_required_items(frm);
	},
	billet_weight(frm) {
		calculate_amount(frm);
	},
	rate(frm) {
		calculate_amount(frm);
	},
	cutting_category(frm) {
		calculate_amount(frm);
	},
});

function calculate_amount(frm) {
	const amount = flt(frm.doc.billet_weight) * flt(frm.doc.rate);
	frm.set_value("amount", amount);
}

function set_fields_from_work_order_required_items(frm) {
	if (!frm.doc.work_order) {
		frm.set_value("raw_material_item", null);
		frm.set_value("billet_weight", null);
		calculate_amount(frm);
		return;
	}

	frappe.call({
		method:
			"prakash_steel.prakash_steel.doctype.billet_cutting_rate_calculation.billet_cutting_rate_calculation.get_required_item_values",
		args: { work_order: frm.doc.work_order },
		callback(r) {
			if (!r.message) {
				return;
			}
			frm.set_value("raw_material_item", r.message.raw_material_item || null);
			frm.set_value("billet_weight", r.message.billet_weight || 0);
		},
	});
}
