frappe.ui.form.on("Work Order", {
	refresh(frm) {
		update_custom_wastage(frm);
		update_custom_cutting_weight(frm);
	},

	produced_qty(frm) {
		update_custom_wastage(frm);
	},

	custom_bright_production(frm) {
		if (frm.doc.custom_bright_production) {
			frm.set_value("custom_rolled_production", 0);
		}
	},

	custom_rolled_production(frm) {
		if (frm.doc.custom_rolled_production) {
			frm.set_value("custom_bright_production", 0);
		}
		update_custom_cutting_weight(frm);
	},

	custom_total_billet_cutting_pcs(frm) {
		update_custom_cutting_weight(frm);
	},

	validate(frm) {
		if (!frm.doc.custom_bright_production && !frm.doc.custom_rolled_production) {
			frappe.throw(
				__("Please select one production type: <b>Bright Production</b> or <b>Rolled Production</b>.")
			);
		}
	},
});

frappe.ui.form.on("Work Order Item", {
	consumed_qty(frm) {
		update_custom_wastage(frm);
		update_custom_cutting_weight(frm);
	},
});

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
