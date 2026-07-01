// Copyright (c) 2026, beetashoke chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production planning settings", {
	refresh(frm) {
		// Ensure only one checkbox is selected on refresh
		ensure_single_checkbox_selection(frm);
	},

	from_work_order(frm) {
		// If from_work_order is checked, uncheck the others
		if (frm.doc.from_work_order) {
			frm.set_value("from_production_plan", 0);
			frm.set_value("from_production_planning", 0);
		}
	},

	from_production_plan(frm) {
		// If from_production_plan is checked, uncheck the others
		if (frm.doc.from_production_plan) {
			frm.set_value("from_work_order", 0);
			frm.set_value("from_production_planning", 0);
		}
	},

	from_production_planning(frm) {
		// If from_production_planning is checked, uncheck the others
		if (frm.doc.from_production_planning) {
			frm.set_value("from_work_order", 0);
			frm.set_value("from_production_plan", 0);
		}
	},
});

function ensure_single_checkbox_selection(frm) {
	// Enforce that at most one source is selected. Priority: Work Order,
	// then Production Plan, then Production Planning.
	if (frm.doc.from_work_order) {
		if (frm.doc.from_production_plan) frm.set_value("from_production_plan", 0);
		if (frm.doc.from_production_planning) frm.set_value("from_production_planning", 0);
	} else if (frm.doc.from_production_plan && frm.doc.from_production_planning) {
		frm.set_value("from_production_planning", 0);
	}
}
