frappe.ui.form.on("Work Order", {
	refresh(frm) {
		patch_work_order_make_se();
		update_custom_wastage(frm);
		update_custom_cutting_weight(frm);
		update_custom_total_raw_material_pcs(frm);
		update_custom_burning_loss(frm);
	},

	produced_qty(frm) {
		update_custom_wastage(frm);
		update_custom_burning_loss(frm);
	},

	custom_bright_production(frm) {
		on_production_type_change(frm, "custom_bright_production");
	},

	custom_rolled_production(frm) {
		on_production_type_change(frm, "custom_rolled_production");
	},

	custom_annealing(frm) {
		on_production_type_change(frm, "custom_annealing");
	},

	custom_straightning(frm) {
		on_production_type_change(frm, "custom_straightning");
	},

	custom_cutting(frm) {
		on_production_type_change(frm, "custom_cutting");
	},

	custom_total_billet_cutting_pcs(frm) {
		update_custom_cutting_weight(frm);
		update_custom_total_raw_material_pcs(frm);
	},

	custom_miss_billet_pcs(frm) {
		update_custom_total_raw_material_pcs(frm);
	},

	custom_miss_billet_weight(frm) {
		update_custom_burning_loss(frm);
	},

	validate(frm) {
		const selected = get_selected_production_types(frm);

		if (!selected.length) {
			frappe.throw(
				__("Please select one production type: {0}.", [
					format_production_type_labels(
						PRODUCTION_TYPE_FIELDS.map((field) => field.label),
						__("or")
					),
				])
			);
		}

		if (selected.length > 1) {
			frappe.throw(
				__("Only one production type can be selected at a time. Currently selected: {0}.", [
					format_production_type_labels(
						selected.map((field) => field.label),
						__("and")
					),
				])
			);
		}
	},
});

frappe.ui.form.on("Work Order Item", {
	consumed_qty(frm) {
		update_custom_wastage(frm);
		update_custom_cutting_weight(frm);
		update_custom_burning_loss(frm);
	},
});

const PRODUCTION_TYPE_FIELDS = [
	{ fieldname: "custom_bright_production", label: "Bright Production" },
	{ fieldname: "custom_rolled_production", label: "Rolled Production" },
	{ fieldname: "custom_annealing", label: "Annealing" },
	{ fieldname: "custom_straightning", label: "Straightning" },
	{ fieldname: "custom_cutting", label: "Cutting" },
];

function get_selected_production_types(frm) {
	return PRODUCTION_TYPE_FIELDS.filter((field) => cint(frm.doc[field.fieldname]) === 1);
}

function format_production_type_labels(labels, separator) {
	const bold = labels.map((label) => `<b>${__(label)}</b>`);
	if (bold.length === 1) {
		return bold[0];
	}
	return `${bold.slice(0, -1).join(", ")} ${separator} ${bold[bold.length - 1]}`;
}

function on_production_type_change(frm, fieldname) {
	if (cint(frm.doc[fieldname]) === 1) {
		PRODUCTION_TYPE_FIELDS.forEach((field) => {
			if (field.fieldname !== fieldname && cint(frm.doc[field.fieldname]) === 1) {
				frm.set_value(field.fieldname, 0);
			}
		});
	}

	update_custom_wastage(frm);
	update_custom_cutting_weight(frm);
	update_custom_total_raw_material_pcs(frm);
	update_custom_burning_loss(frm);
}

function get_consumed_qty(frm) {
	return (frm.doc.required_items || []).reduce(
		(total, row) => total + flt(row.consumed_qty),
		0
	);
}

function set_calculated_value(frm, fieldname, value) {
	frm.doc[fieldname] = value;
	frm.refresh_field(fieldname);
}

function update_custom_wastage(frm) {
	const is_bright_production = cint(frm.doc.custom_bright_production) === 1;
	if (!is_bright_production) {
		set_calculated_value(frm, "custom_wastage", null);
		return;
	}

	const produced_qty = flt(frm.doc.produced_qty) || 0;
	const consumed_qty = get_consumed_qty(frm);

	if (
		frm.doc.produced_qty == null || frm.doc.produced_qty === "" ||
		consumed_qty === 0
	) {
		set_calculated_value(frm, "custom_wastage", null);
		return;
	}

	set_calculated_value(
		frm,
		"custom_wastage",
		Math.abs((produced_qty / consumed_qty) * 100 - 100)
	);
}

function update_custom_cutting_weight(frm) {
	const is_rolled_production = cint(frm.doc.custom_rolled_production) === 1;
	if (!is_rolled_production) {
		set_calculated_value(frm, "custom_cutting_weight", null);
		return;
	}

	const consumed_qty = get_consumed_qty(frm);
	const total_billet_cutting_pcs = flt(frm.doc.custom_total_billet_cutting_pcs) || 0;

	if (total_billet_cutting_pcs <= 0) {
		set_calculated_value(frm, "custom_cutting_weight", null);
		return;
	}

	set_calculated_value(frm, "custom_cutting_weight", consumed_qty / total_billet_cutting_pcs);
}

function update_custom_total_raw_material_pcs(frm) {
	const is_rolled_production = cint(frm.doc.custom_rolled_production) === 1;
	if (!is_rolled_production) {
		set_calculated_value(frm, "custom_total_raw_material_pcs", null);
		return;
	}

	const total_billet_cutting_pcs = flt(frm.doc.custom_total_billet_cutting_pcs) || 0;
	const miss_billet_pcs = flt(frm.doc.custom_miss_billet_pcs) || 0;

	set_calculated_value(
		frm,
		"custom_total_raw_material_pcs",
		total_billet_cutting_pcs + miss_billet_pcs
	);
}

function update_custom_burning_loss(frm) {
	const is_rolled_production = cint(frm.doc.custom_rolled_production) === 1;
	if (!is_rolled_production) {
		set_calculated_value(frm, "custom_burning_loss", null);
		return;
	}

	const consumed_qty = get_consumed_qty(frm);
	if (consumed_qty <= 0) {
		set_calculated_value(frm, "custom_burning_loss", null);
		return;
	}

	const miss_billet_weight = flt(frm.doc.custom_miss_billet_weight) || 0;
	const produced_qty = flt(frm.doc.produced_qty) || 0;

	set_calculated_value(
		frm,
		"custom_burning_loss",
		Math.abs(((consumed_qty - miss_billet_weight - produced_qty) / consumed_qty) * 100)
	);
}

function patch_work_order_make_se() {
	if (!erpnext.work_order || erpnext.work_order.__prakash_steel_manufacture_patched) return;

	frappe.call({
		method: "prakash_steel.utils.work_order.get_stock_entry_setting_auto_manufacture_enabled",
		args: {},
		callback: function (r) {
			if (!r || !r.message || !r.message.enabled) {
				return;
			}

			erpnext.work_order.__prakash_steel_manufacture_patched = true;
			const original_make_se = erpnext.work_order.make_se.bind(erpnext.work_order);

			erpnext.work_order.make_se = function (frm, purpose, qty, is_additional_transfer_entry) {
				if (purpose !== "Manufacture") {
					return original_make_se(frm, purpose, qty, is_additional_transfer_entry);
				}
				return finish_work_order_with_process_loss(frm, qty);
			};
		},
	});
}

function finish_work_order_with_process_loss(frm, qty) {
	return frappe
		.call({
			method: "prakash_steel.utils.work_order.get_work_order_finish_defaults",
			args: { work_order_id: frm.doc.name },
		})
		.then((r) => {
			const defaults = r.message || {};
			if (qty) {
				return submit_auto_manufacture_stock_entry(frm, qty, defaults, true);
			}
			return show_finish_qty_prompt(frm, defaults).then((data) =>
				submit_auto_manufacture_stock_entry(
					frm,
					data.qty,
					defaults,
					cint(data.consider_process_loss)
				)
			);
		});
}

function show_finish_qty_prompt(frm, defaults) {
	const max = erpnext.work_order.get_max_transferable_qty(frm, "Manufacture");
	const process_loss = flt(defaults.process_loss_qty);
	const base_qty = flt(defaults.total_completed_qty) || max;
	const qty_with_loss = base_qty + process_loss;
	const overproduction =
		(flt(frm.doc.qty) * flt((frm.doc.__onload && frm.doc.__onload.overproduction_percentage) || 0)) /
		100;
	const allowed_max = Math.max(max + process_loss, qty_with_loss) + overproduction;

	const fields = [
		{
			fieldtype: "Float",
			label: __("Qty for {0}", [__("Manufacture")]),
			fieldname: "qty",
			description: __("Includes process loss {0}. Max: {1}", [process_loss, allowed_max]),
			default: qty_with_loss,
		},
		{
			fieldtype: "Check",
			label: __("Consider Process Loss"),
			fieldname: "consider_process_loss",
			default: 1,
			onchange: function () {
				if (!frm.qty_prompt) {
					return;
				}
				if (this.value) {
					frm.qty_prompt.set_value("qty", qty_with_loss);
				} else {
					frm.qty_prompt.set_value("qty", base_qty);
				}
			},
		},
	];

	return new Promise((resolve, reject) => {
		frm.qty_prompt = frappe.prompt(
			fields,
			(data) => {
				if (flt(data.qty) > allowed_max) {
					frappe.msgprint(__("Quantity must not be more than {0}", [allowed_max]));
					reject();
					return;
				}
				data.purpose = "Manufacture";
				resolve(data);
			},
			__("Select Quantity"),
			__("Create")
		);
	});
}

function submit_auto_manufacture_stock_entry(frm, qty, defaults, consider_process_loss) {
	const process_loss = consider_process_loss ? flt(defaults.process_loss_qty) : 0;
	const args = {
		work_order_id: frm.doc.name,
		qty: flt(qty),
		process_loss_qty: process_loss,
		finished_good_qty: flt(qty) - process_loss,
	};

	if (defaults.job_card) {
		args.job_card = defaults.job_card;
		args.actual_rm_consumption = flt(defaults.actual_rm_consumption);
	}

	return frappe
		.call({
			method: "prakash_steel.utils.work_order.submit_manufacture_stock_entry",
			args: args,
			freeze: true,
			freeze_message: __("Creating Stock Entry..."),
		})
		.then((r) => {
			if (!r.message) {
				return;
			}
			frappe.set_route("Form", "Stock Entry", r.message.name);
		});
}
