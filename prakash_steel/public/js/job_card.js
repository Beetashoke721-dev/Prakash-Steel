frappe.ui.form.on("Job Card", {
	refresh(frm) {
		(frm.doc.time_logs || []).forEach((row) => {
			calculate_time_log_total(frm, row.doctype, row.name);
		});
	},

	validate(frm) {
		validate_time_log_miss_fields(frm);
	},
});

frappe.ui.form.on("Job Card Time Log", {
	form_render(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
	},

	custom_finish_item(frm, cdt, cdn) {
		calculate_time_log_total(frm, cdt, cdn);
	},

	custom_miss_roll(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
	},

	custom_miss_ingot_or_billet(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
	},
});

function toggle_time_log_miss_fields(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const grid_row = frm.fields_dict.time_logs?.grid?.get_row(cdn);

	if (!grid_row) {
		return;
	}

	const has_miss_roll = cint(row.custom_miss_roll) > 0;
	const has_miss_ingot = cint(row.custom_miss_ingot_or_billet) > 0;

	grid_row.toggle_reqd("custom_miss_roll_weight", has_miss_roll);
	grid_row.toggle_reqd("custom_summary_remarks", has_miss_roll);
	grid_row.toggle_reqd("custom_miss_ingot_or_billet_weight", has_miss_ingot);
	grid_row.toggle_reqd("custom_reason_for_miss_ingot_or_billet", has_miss_ingot);

	if (!has_miss_roll) {
		frappe.model.set_value(cdt, cdn, "custom_miss_roll_weight", null);
	}

	if (!has_miss_ingot) {
		frappe.model.set_value(cdt, cdn, {
			custom_miss_ingot_or_billet_weight: null,
			custom_reason_for_miss_ingot_or_billet: null,
		});
	}
}

function calculate_time_log_total(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const finish = parseFloat(row.custom_finish_item) || 0;
	const miss_roll = parseFloat(row.custom_miss_roll) || 0;
	const miss_ingot = parseFloat(row.custom_miss_ingot_or_billet) || 0;

	frappe.model.set_value(cdt, cdn, "custom_total", finish + miss_roll + miss_ingot);
}

function validate_time_log_miss_fields(frm) {
	(frm.doc.time_logs || []).forEach((row, index) => {
		const row_label = __("Row {0}", [index + 1]);

		if (cint(row.custom_miss_roll) > 0) {
			if (!row.custom_miss_roll_weight) {
				frappe.throw(
					__("{0}: Miss Roll Weight is mandatory when Miss Roll (Pcs) is greater than 0.", [row_label])
				);
			}
			if (!row.custom_summary_remarks) {
				frappe.throw(
					__("{0}: Summary Remarks is mandatory when Miss Roll (Pcs) is greater than 0.", [row_label])
				);
			}
		}

		if (cint(row.custom_miss_ingot_or_billet) > 0) {
			if (!row.custom_miss_ingot_or_billet_weight) {
				frappe.throw(
					__(
						"{0}: Miss Ingot / Billet Weight is mandatory when Miss Ingot / Billet (Pcs) is greater than 0.",
						[row_label]
					)
				);
			}
			if (!row.custom_reason_for_miss_ingot_or_billet) {
				frappe.throw(
					__(
						"{0}: Reason for Miss Ingot / Billet is mandatory when Miss Ingot / Billet (Pcs) is greater than 0.",
						[row_label]
					)
				);
			}
		}
	});
}
