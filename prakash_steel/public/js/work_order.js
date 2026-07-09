frappe.ui.form.on("Work Order", {
	refresh(frm) {
		update_custom_wastage(frm);
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
	},
});

function get_consumed_qty(frm) {
	return (frm.doc.required_items || []).reduce(
		(total, row) => total + flt(row.consumed_qty),
		0
	);
}

function update_custom_wastage(frm) {
	const produced_qty = flt(frm.doc.produced_qty) || 0;
	const consumed_qty = get_consumed_qty(frm);

	if (
		frm.doc.produced_qty == null || frm.doc.produced_qty === "" ||
		consumed_qty === 0
	) {
		frm.set_value("custom_wastage", null);
		return;
	}

	frm.set_value("custom_wastage", (produced_qty / consumed_qty) * 100 - 100);
}
