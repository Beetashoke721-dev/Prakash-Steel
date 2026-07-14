frappe.ui.form.on("Job Card", {
	refresh(frm) {
		calculate_total_completed_qty(frm, true);

		if (frm.doc.docstatus === 1) {
			return;
		}

		(frm.doc.time_logs || []).forEach((row) => {
			calculate_time_log_total(frm, row.doctype, row.name, true);
		});
		calculate_finish_pcs(frm, true);
		calculate_miss_pcs(frm, true);
		fetch_colour_code_from_production_item(frm, true);
		set_billet_weight_from_work_order(frm, true);
		refresh_time_log_billet_cutting_remaining(frm, true);
	},

	work_order(frm) {
		if (frm.doc.docstatus === 1) {
			return;
		}

		set_billet_weight_from_work_order(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	production_item(frm) {
		if (frm.doc.docstatus === 1) {
			return;
		}

		fetch_colour_code_from_production_item(frm);
	},

	total_completed_qty(frm) {
		calculate_fg_per_pcs_weight(frm);
	},

	time_logs_add(frm) {
		calculate_finish_pcs(frm);
		calculate_miss_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	time_logs_remove(frm) {
		calculate_finish_pcs(frm);
		calculate_miss_pcs(frm);
		calculate_total_completed_qty(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	validate(frm) {
		flush_time_logs_grid(frm);
		calculate_total_completed_qty(frm);
		calculate_finish_pcs(frm);
		calculate_miss_pcs(frm);
		calculate_fg_per_pcs_weight(frm);
		validate_time_log_miss_fields(frm);
		validate_time_log_billet_cutting_remaining(frm);
	},
});

frappe.ui.form.on("Job Card Time Log", {
	form_render(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn, frm.doc.docstatus !== 1);
		calculate_time_log_total(frm, cdt, cdn, frm.doc.docstatus !== 1);
		if (frm.doc.docstatus !== 1) {
			refresh_time_log_billet_cutting_remaining(frm, true);
		}
	},

	completed_qty(frm) {
		calculate_total_completed_qty(frm);
	},

	custom_finish_item(frm, cdt, cdn) {
		calculate_time_log_total(frm, cdt, cdn);
		calculate_finish_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_miss_roll(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
		calculate_miss_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_miss_roll_weight(frm) {
		calculate_miss_pcs(frm);
	},

	custom_miss_ingot_or_billet(frm, cdt, cdn) {
		toggle_time_log_miss_fields(frm, cdt, cdn);
		calculate_time_log_total(frm, cdt, cdn);
		calculate_miss_pcs(frm);
		refresh_time_log_billet_cutting_remaining(frm);
	},

	custom_miss_ingot_or_billet_weight(frm) {
		calculate_miss_pcs(frm);
	},
});

function set_form_value(frm, fieldname, value, quiet = false) {
	if (frm.doc[fieldname] === value) {
		return Promise.resolve();
	}

	if (quiet) {
		frm.doc[fieldname] = value;
		frm.refresh_field(fieldname);
		return Promise.resolve();
	}

	return frm.set_value(fieldname, value);
}

function set_child_value(cdt, cdn, values, quiet = false) {
	const row = locals[cdt][cdn];
	const updates = {};

	Object.entries(values).forEach(([fieldname, value]) => {
		if (row[fieldname] !== value) {
			updates[fieldname] = value;
		}
	});

	if (!Object.keys(updates).length) {
		return;
	}

	if (quiet) {
		Object.assign(row, updates);
		return;
	}

	frappe.model.set_value(cdt, cdn, updates);
}

function toggle_time_log_miss_fields(frm, cdt, cdn, quiet = false) {
	const row = locals[cdt][cdn];
	const grid_row = frm.fields_dict.time_logs?.grid?.get_row(cdn);

	if (!grid_row) {
		return;
	}

	const has_miss_roll = cint(row.custom_miss_roll) > 0;
	const has_miss_ingot = cint(row.custom_miss_ingot_or_billet) > 0;

	grid_row.toggle_reqd("custom_miss_roll_weight", has_miss_roll);
	grid_row.toggle_reqd("custom_reason_for_miss_roll", has_miss_roll);
	grid_row.toggle_reqd("custom_miss_ingot_or_billet_weight", has_miss_ingot);
	grid_row.toggle_reqd("custom_reason_for_miss_ingot_or_billet", has_miss_ingot);

	if (!has_miss_roll && (row.custom_miss_roll_weight || row.custom_reason_for_miss_roll)) {
		set_child_value(
			cdt,
			cdn,
			{
				custom_miss_roll_weight: null,
				custom_reason_for_miss_roll: null,
			},
			quiet
		);
	}

	if (
		!has_miss_ingot &&
		(row.custom_miss_ingot_or_billet_weight || row.custom_reason_for_miss_ingot_or_billet)
	) {
		set_child_value(
			cdt,
			cdn,
			{
				custom_miss_ingot_or_billet_weight: null,
				custom_reason_for_miss_ingot_or_billet: null,
			},
			quiet
		);
	}
}

function calculate_time_log_total(frm, cdt, cdn, quiet = false) {
	const row = locals[cdt][cdn];
	const finish = parseFloat(row.custom_finish_item) || 0;
	const miss_roll = parseFloat(row.custom_miss_roll) || 0;
	const miss_ingot = parseFloat(row.custom_miss_ingot_or_billet) || 0;
	const total = finish + miss_roll + miss_ingot;

	if (flt(row.custom_total) !== total) {
		set_child_value(cdt, cdn, { custom_total: total }, quiet);
	}
}

function flush_time_logs_grid(frm) {
	const grid = frm.fields_dict.time_logs?.grid;
	if (!grid) {
		return;
	}

	const editable_row = frappe.ui.form.editable_row;
	if (editable_row?.on_grid_fields) {
		editable_row.on_grid_fields.forEach((field) => {
			field.parse_validate_and_set_in_model?.(field.get_value());
		});
	}

	const open_form = frappe.ui.form.get_open_grid_form?.();
	if (open_form?.layout?.fields) {
		open_form.layout.fields.forEach((field) => {
			field.parse_validate_and_set_in_model?.(field.get_value());
		});
	}

	frappe.ui.form.close_grid_form?.();
}

function calculate_total_completed_qty(frm, quiet = false) {
	let total = 0;
	(frm.doc.time_logs || []).forEach((row) => {
		total += flt(row.completed_qty);
	});

	set_form_value(frm, "total_completed_qty", total, quiet);
	calculate_fg_per_pcs_weight(frm, quiet);
}

function calculate_finish_pcs(frm, quiet = false) {
	let total = 0;
	(frm.doc.time_logs || []).forEach((row) => {
		total += cint(row.custom_finish_item) || 0;
	});

	const apply_fg = () => calculate_fg_per_pcs_weight(frm, quiet);

	if (cint(frm.doc.custom_finish_pcs) !== total) {
		set_form_value(frm, "custom_finish_pcs", total, quiet).then(apply_fg);
	} else {
		apply_fg();
	}
}

function calculate_miss_pcs(frm, quiet = false) {
	let total_miss_roll = 0;
	let total_miss_ingot = 0;
	let total_miss_roll_weight = 0;
	let total_miss_ingot_weight = 0;

	(frm.doc.time_logs || []).forEach((row) => {
		total_miss_roll += cint(row.custom_miss_roll) || 0;
		total_miss_ingot += cint(row.custom_miss_ingot_or_billet) || 0;
		total_miss_roll_weight += cint(row.custom_miss_roll_weight) || 0;
		total_miss_ingot_weight += cint(row.custom_miss_ingot_or_billet_weight) || 0;
	});

	set_form_value(frm, "custom_total_miss_roll", total_miss_roll, quiet);
	set_form_value(frm, "custom_total_miss_ingot_or_billet", total_miss_ingot, quiet);
	set_form_value(frm, "custom_total_miss_roll_weight", total_miss_roll_weight, quiet);
	set_form_value(frm, "custom_total_miss_ingot_or_billet_weight", total_miss_ingot_weight, quiet);
}

function calculate_fg_per_pcs_weight(frm, quiet = false) {
	const finish_pcs = cint(frm.doc.custom_finish_pcs);
	const completed_qty = flt(frm.doc.total_completed_qty);
	let value = 0;

	if (finish_pcs > 0 && completed_qty) {
		value = Math.round((completed_qty / finish_pcs) * 100) / 100;
	}

	set_form_value(frm, "custom_fg_per_pcs_weight", value, quiet);
}

function fetch_colour_code_from_production_item(frm, quiet = false) {
	if (!frm.doc.production_item) {
		if (frm.doc.custom_colour_code) {
			set_form_value(frm, "custom_colour_code", null, quiet);
		}
		return;
	}

	frappe.db.get_value("Item", frm.doc.production_item, "custom_grade").then((r) => {
		const grade = r && r.message ? r.message.custom_grade : null;
		if (!grade) {
			if (frm.doc.custom_colour_code) {
				set_form_value(frm, "custom_colour_code", null, quiet);
			}
			return;
		}

		frappe.db
			.get_list("Item Grade wise Colour Code", {
				filters: { item_grade: grade },
				fields: ["colour_code"],
				limit: 1,
			})
			.then((docs) => {
				const colour = docs && docs.length > 0 ? docs[0].colour_code : null;
				if (frm.doc.custom_colour_code !== colour) {
					set_form_value(frm, "custom_colour_code", colour, quiet);
				}
			});
	});
}

function set_billet_weight_from_work_order(frm, quiet = false) {
	if (frm.doc.docstatus === 1) {
		return;
	}

	if (!frm.doc.work_order) {
		if (cint(frm.doc.custom_billet_weight)) {
			set_form_value(frm, "custom_billet_weight", 0, quiet);
		}
		return;
	}

	frappe.db.get_doc("Work Order", frm.doc.work_order).then((wo) => {
		const miss_billet_weight = flt(wo.custom_miss_billet_weight);
		const consumed_qty = (wo.required_items || []).reduce(
			(sum, row) => sum + flt(row.consumed_qty),
			0
		);
		const total = cint(miss_billet_weight + consumed_qty);

		if (cint(frm.doc.custom_billet_weight) !== total) {
			set_form_value(frm, "custom_billet_weight", total, quiet);
		}
	});
}

function get_time_log_used_pcs(row) {
	return (
		(parseFloat(row.custom_finish_item) || 0) +
		(parseFloat(row.custom_miss_roll) || 0) +
		(parseFloat(row.custom_miss_ingot_or_billet) || 0)
	);
}

function set_time_log_value(row, fieldname, value, quiet = false) {
	if (value == null) {
		if (row[fieldname] != null && row[fieldname] !== "") {
			if (quiet) {
				row[fieldname] = null;
			} else {
				frappe.model.set_value(row.doctype, row.name, fieldname, null);
			}
		}
		return;
	}

	if (flt(row[fieldname]) !== flt(value)) {
		if (quiet) {
			row[fieldname] = value;
		} else {
			frappe.model.set_value(row.doctype, row.name, fieldname, value);
		}
	}
}

function clear_time_log_billet_cutting(frm, quiet = false) {
	(frm.doc.time_logs || []).forEach((row) => {
		set_time_log_value(row, "custom_total_billet_cutting", null, quiet);
	});
}

function apply_time_log_billet_cutting_remaining(frm, pool, other_used, quiet = false) {
	let running_used = 0;

	(frm.doc.time_logs || []).forEach((row) => {
		const remaining = pool - other_used - running_used;
		set_time_log_value(row, "custom_total_billet_cutting", remaining, quiet);
		running_used += get_time_log_used_pcs(row);
	});

	if (quiet && frm.fields_dict.time_logs?.grid) {
		frm.fields_dict.time_logs.grid.refresh();
	}
}

function refresh_time_log_billet_cutting_remaining(frm, quiet = false) {
	if (!frm.doc.work_order) {
		clear_time_log_billet_cutting(frm, quiet);
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
				clear_time_log_billet_cutting(frm, quiet);
				return;
			}

			apply_time_log_billet_cutting_remaining(frm, flt(ctx.pool), flt(ctx.other_used), quiet);
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
			if (!row.custom_reason_for_miss_roll) {
				frappe.throw(
					__("{0}: Reason for Miss Roll is mandatory when Miss Roll (Pcs) is greater than 0.", [row_label])
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
