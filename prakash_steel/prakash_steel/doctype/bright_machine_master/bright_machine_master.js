// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bright Machine Master", {
	validate(frm) {
		ensure_one_default_machine_row(frm);
		ensure_unique_machine_group_names(frm);
	},
});

frappe.ui.form.on("Bright Machine Master Table", {
	machine_group_name(frm, cdt, cdn) {
		ensure_unique_machine_group_names(frm, cdt, cdn);
	},

	is_default(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.is_default) {
			return;
		}

		(frm.doc.machine_details || []).forEach((machine_row) => {
			if (machine_row.name !== row.name) {
				frappe.model.set_value(
					machine_row.doctype,
					machine_row.name,
					"is_default",
					0
				);
			}
		});
	},
});

function ensure_unique_machine_group_names(frm, cdt, cdn) {
	const rows = frm.doc.machine_details || [];
	const seen = new Set();

	for (const row of rows) {
		const machine_group = (row.machine_group_name || "").trim();
		if (!machine_group) {
			continue;
		}
		if (seen.has(machine_group)) {
			if (cdt && cdn) {
				frappe.model.set_value(cdt, cdn, "machine_group_name", "");
			}
			frappe.throw(
				__(
					"Machine Group Name {0} cannot appear in more than one row.",
					[machine_group]
				)
			);
		}
		seen.add(machine_group);
	}
}

function ensure_one_default_machine_row(frm) {
	const rows = frm.doc.machine_details || [];
	const default_rows = rows.filter((row) => row.is_default);

	if (default_rows.length !== 1) {
		frappe.throw(
			__(
				"Please mark exactly one row in Machine Details as Default (Is Default)."
			)
		);
	}
}
