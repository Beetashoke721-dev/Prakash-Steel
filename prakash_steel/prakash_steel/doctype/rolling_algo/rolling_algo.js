// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Rolling Algo", {
	refresh(frm) {
		update_final_sub_group_fields(frm);
	},

	item_code(frm) {
		frappe.after_ajax(() => update_final_sub_group_fields(frm));
	},

	item_sub_group(frm) {
		update_final_sub_group_fields(frm);
	},

	shape(frm) {
		update_final_sub_group_fields(frm);
	},

	planning_sub_group(frm) {
		frappe.after_ajax(() => update_final_sub_group_fields(frm));
	},

	planning_sub_group_name(frm) {
		update_final_sub_group_fields(frm);
	},

	planned_hrs(frm) {
		frm.set_value("final_planned_hrs", frm.doc.planned_hrs);
	},
});

function update_final_sub_group_fields(frm) {
	const custom_shape = (frm.doc.shape || "").trim();
	let sub_group_name = "";

	if (frm.doc.planning_sub_group) {
		sub_group_name = (frm.doc.planning_sub_group_name || "").trim();
	} else {
		sub_group_name = (frm.doc.item_sub_group || "").trim();
	}

	const final_sub_group_shape =
		sub_group_name || custom_shape
			? `${sub_group_name}${custom_shape}`
			: "";

	frm.set_value("final_sub_group", sub_group_name);
	frm.set_value("final_sub_group_shape", final_sub_group_shape);
}
