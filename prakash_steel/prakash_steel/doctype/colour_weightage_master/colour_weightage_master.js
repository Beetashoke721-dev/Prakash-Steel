// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Colour Weightage Master", {
	validate(frm) {
		validate_colour_weightage_rows(frm);
	},
});

frappe.ui.form.on("Colour Weightage Master Table", {
	colour(frm, cdt, cdn) {
		validate_unique_colours(frm, cdt, cdn);
	},

	weightage(frm, cdt, cdn) {
		validate_weightage_not_zero(frm, cdt, cdn);
		validate_unique_weightages(frm, cdt, cdn);
	},
});

function validate_colour_weightage_rows(frm) {
	validate_weightage_not_zero(frm);
	validate_unique_colours(frm);
	validate_unique_weightages(frm);
}

function validate_weightage_not_zero(frm, cdt, cdn) {
	for (const row of frm.doc.table_zdau || []) {
		if (cint(row.weightage) === 0) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "weightage", null);
			}
			frappe.throw(__("Weightage cannot be 0."));
		}
	}
}

function validate_unique_colours(frm, cdt, cdn) {
	const seen = new Set();

	for (const row of frm.doc.table_zdau || []) {
		const colour = (row.colour || "").trim();
		if (!colour) {
			continue;
		}
		if (seen.has(colour)) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "colour", "");
			}
			frappe.throw(
				__("Colour {0} cannot appear in more than one row.", [colour])
			);
		}
		seen.add(colour);
	}
}

function validate_unique_weightages(frm, cdt, cdn) {
	const seen = new Set();

	for (const row of frm.doc.table_zdau || []) {
		const weightage = row.weightage;
		if (weightage === null || weightage === undefined || weightage === "") {
			continue;
		}
		const weightage_key = cint(weightage);
		if (seen.has(weightage_key)) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "weightage", null);
			}
			frappe.throw(
				__(
					"Weightage {0} cannot appear in more than one row.",
					[weightage_key]
				)
			);
		}
		seen.add(weightage_key);
	}
}
