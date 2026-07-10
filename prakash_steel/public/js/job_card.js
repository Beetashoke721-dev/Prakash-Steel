frappe.ui.form.on("Job Card", {
	refresh(frm) {
		(frm.doc.time_logs || []).forEach((row) => {
			calculate_time_log_total(frm, row.doctype, row.name);
		});
		calculate_finish_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	work_order(frm) {
		refresh_time_log_billet_cutting_remaining(frm);
	},

	total_completed_qty(frm) {
		calculate_fg_per_pcs_weight(frm);
	},

	time_logs_add(frm) {
		calculate_finish_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	time_logs_remove(frm) {
		calculate_finish_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	validate(frm) {
		calculate_finish_pcs(frm);
		validate_time_log_miss_fields(frm);
		validate_time_log_billet_cutting_remaining(frm);
	},
});

frappe.ui.form.on("Job Card Time Log", {
	form_render(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_finish_item(frm, cdt, cdn) {
		calculate_time_log_total(frm, cdt, cdn);
		calculate_finish_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_miss_roll(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_miss_ingot_or_billet(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
		refresh_time_log_billet_cutting_remaining(frm);
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
	const total = finish + miss_roll + miss_ingot;

	if (flt(row.custom_total) !== total) {
		frappe.model.set_value(cdt, cdn, "custom_total", total);
	}
}

function calculate_finish_pcs(frm) {
	let total = 0;
	(frm.doc.time_logs || []).forEach((row) => {
		total += cint(row.custom_finish_item) || 0;
	});

	const apply_fg = () => calculate_fg_per_pcs_weight(frm);

	if (cint(frm.doc.custom_finish_pcs) !== total) {
		frm.set_value("custom_finish_pcs", total).then(apply_fg);
	} else {
		apply_fg();
	}
}

function calculate_fg_per_pcs_weight(frm) {
	const finish_pcs = cint(frm.doc.custom_finish_pcs);
	const completed_qty = flt(frm.doc.total_completed_qty);
	let value = 0;

	if (finish_pcs > 0 && completed_qty) {
		value = Math.round((completed_qty / finish_pcs) * 100) / 100;
	}

	if (flt(frm.doc.custom_fg_per_pcs_weight) !== value) {
		frm.set_value("custom_fg_per_pcs_weight", value);
	}
}

function get_time_log_used_pcs(row) {
	return (
		(parseFloat(row.custom_finish_item) || 0) +
		(parseFloat(row.custom_miss_roll) || 0) +
		(parseFloat(row.custom_miss_ingot_or_billet) || 0)
	);
}

function set_time_log_value(row, fieldname, value) {
	if (value == null) {
		if (row[fieldname] != null && row[fieldname] !== "") {
			frappe.model.set_value(row.doctype, row.name, fieldname, null);
		}
		return;
	}

	if (flt(row[fieldname]) !== flt(value)) {
		frappe.model.set_value(row.doctype, row.name, fieldname, value);
	}
}

function clear_time_log_billet_cutting(frm) {
	(frm.doc.time_logs || []).forEach((row) => {
		set_time_log_value(row, "custom_total_billet_cutting", null);
	});
}

function apply_time_log_billet_cutting_remaining(frm, pool, other_used) {
	let running_used = 0;

	(frm.doc.time_logs || []).forEach((row) => {
		const remaining = pool - other_used - running_used;
		set_time_log_value(row, "custom_total_billet_cutting", remaining);
		running_used += get_time_log_used_pcs(row);
	});
}

function refresh_time_log_billet_cutting_remaining(frm) {
	if (!frm.doc.work_order) {
		clear_time_log_billet_cutting(frm);
		return;
	}

	frappe.call({
		method: "prakash_steel.utils.work_order.get_job_card_billet_cutting_context",
		args: {
			work_order: frm.doc.work_order,
			exclude_job_card: frm.is_new() ? null : frm.doc.name,
		},
		callback(r) {
			const ctx = r.message || {};
			if (!cint(ctx.is_rolled) || ctx.pool == null) {
				clear_time_log_billet_cutting(frm);
				return;
			}

			apply_time_log_billet_cutting_remaining(frm, flt(ctx.pool), flt(ctx.other_used));
		},
	});
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

function validate_time_log_billet_cutting_remaining(frm) {
	if (!frm.doc.work_order) {
		return;
	}

	(frm.doc.time_logs || []).forEach((row, index) => {
		const remaining = parseFloat(row.custom_total_billet_cutting);
		const used = get_time_log_used_pcs(row);

		if (remaining == null || isNaN(remaining)) {
			return;
		}

		if (remaining < 0 || used > remaining) {
			const over_by = remaining < 0 ? Math.abs(remaining) : used - remaining;
			frappe.throw(
				__(
					"Row {0}: No pieces left! You are trying to use {1} more pieces than available. Please reduce the quantities.",
					[index + 1, over_by]
				)
			);
		}
	});
}
