frappe.ui.form.on("Work Order", {
	custom_bright_production(frm) {
		if (frm.doc.custom_bright_production) {
			frm.set_value("custom_rolled_production", 0);
		}
	},

	custom_rolled_production(frm) {
		if (frm.doc.custom_rolled_production) {
			frm.set_value("custom_bright_production", 0);
		}
	},

	validate(frm) {
		if (!frm.doc.custom_bright_production && !frm.doc.custom_rolled_production) {
			frappe.throw(
				__("Please select one production type: <b>Bright Production</b> or <b>Rolled Production</b>.")
			);
		}
	},
});
