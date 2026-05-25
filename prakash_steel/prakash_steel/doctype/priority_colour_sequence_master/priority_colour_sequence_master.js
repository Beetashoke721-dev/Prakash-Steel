// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Priority Colour Sequence Master", {
	validate(frm) {
		validate_priority_colour_sequence_rows(frm);
	},
});

frappe.ui.form.on("Priority Colour Seq Master Table", {
	priority_colour(frm, cdt, cdn) {
		validate_unique_priority_colours(frm, cdt, cdn);
	},

	sequence(frm, cdt, cdn) {
		validate_sequence_not_zero(frm, cdt, cdn);
		validate_unique_sequences(frm, cdt, cdn);
	},
});

function validate_priority_colour_sequence_rows(frm) {
	validate_sequence_not_zero(frm);
	validate_unique_priority_colours(frm);
	validate_unique_sequences(frm);
}

function validate_sequence_not_zero(frm, cdt, cdn) {
	for (const row of frm.doc.table_avyc || []) {
		if (cint(row.sequence) === 0) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "sequence", null);
			}
			frappe.throw(__("Sequence cannot be 0."));
		}
	}
}

function validate_unique_priority_colours(frm, cdt, cdn) {
	const seen = new Set();

	for (const row of frm.doc.table_avyc || []) {
		const priority_colour = (row.priority_colour || "").trim();
		if (!priority_colour) {
			continue;
		}
		if (seen.has(priority_colour)) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "priority_colour", "");
			}
			frappe.throw(
				__(
					"Priority Colour {0} cannot appear in more than one row.",
					[priority_colour]
				)
			);
		}
		seen.add(priority_colour);
	}
}

function validate_unique_sequences(frm, cdt, cdn) {
	const seen = new Set();

	for (const row of frm.doc.table_avyc || []) {
		if (row.sequence === null || row.sequence === undefined || row.sequence === "") {
			continue;
		}
		const sequence = cint(row.sequence);
		if (seen.has(sequence)) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "sequence", null);
			}
			frappe.throw(
				__(
					"Sequence {0} cannot appear in more than one row.",
					[sequence]
				)
			);
		}
		seen.add(sequence);
	}
}
