// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const MACHINE_LOAD_COLOUR_CHAIN = ["Black", "Red", "Yellow", "Green", "White"];

frappe.ui.form.on("Machine Load Colour Master", {
	after_save(frm) {
		frappe.after_ajax(() => {
			frm.doc.__unsaved = 0;
			frm.toolbar && frm.toolbar.show_title_as_dirty();
		});
	},
});

frappe.ui.form.on("Machine Load Colour Table", {
	colour(frm) {
		apply_colour_day_chain(frm);
		frm.refresh_field("table_iobk");
	},

	to_days(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.colour) {
			return;
		}

		if (row.colour === "Black" || row.colour === "White") {
			sync_fixed_colour_days(frm);
			if (row.colour === "Black") {
				propagate_from_days_from(frm, "Black");
			}
			frm.refresh_field("table_iobk");
			return;
		}

		propagate_from_days_from(frm, row.colour);
		sync_fixed_colour_days(frm);
		frm.refresh_field("table_iobk");
	},
});

function get_colour_row(frm, colour) {
	return (frm.doc.table_iobk || []).find((row) => row.colour === colour);
}

function set_child_field(row, fieldname, value) {
	if (cint(row[fieldname]) === cint(value)) {
		return;
	}
	row[fieldname] = cint(value);
}

function sync_fixed_colour_days(frm) {
	const black = get_colour_row(frm, "Black");
	if (black) {
		set_child_field(black, "from_days", 0);
		set_child_field(black, "to_days", 0);
	}

	const white = get_colour_row(frm, "White");
	if (white) {
		set_child_field(white, "to_days", 0);
	}
}

function propagate_from_days_from(frm, colour) {
	const idx = MACHINE_LOAD_COLOUR_CHAIN.indexOf(colour);
	if (idx < 0 || idx >= MACHINE_LOAD_COLOUR_CHAIN.length - 1) {
		return;
	}

	const current = get_colour_row(frm, colour);
	const next = get_colour_row(frm, MACHINE_LOAD_COLOUR_CHAIN[idx + 1]);
	if (!current || !next) {
		return;
	}

	set_child_field(next, "from_days", cint(current.to_days));
}

function apply_colour_day_chain(frm) {
	sync_fixed_colour_days(frm);
	for (let i = 0; i < MACHINE_LOAD_COLOUR_CHAIN.length - 1; i++) {
		propagate_from_days_from(frm, MACHINE_LOAD_COLOUR_CHAIN[i]);
	}
}
