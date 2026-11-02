// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

function payment_terms_surcharge(payment_terms) {
	// IF(C6=15, 0.5, IF(C6=30, 1, 0))
	if (payment_terms === 15) return 0.5;
	if (payment_terms === 30) return 1;
	return 0;
}

function calculate_rates(frm) {
	const billet_basic_ms = flt(frm.doc.billet_basic_ms);
	const rolling_charges = flt(frm.doc.rolling_charges);
	const surcharge = payment_terms_surcharge(cint(frm.doc.payment_terms));

	// MS Round Basic Rate = billet_basic_ms + rolling_charges + payment terms surcharge
	const ms_round_basic_rate = billet_basic_ms + rolling_charges + surcharge;
	frm.set_value("ms_round_basic_rate", ms_round_basic_rate);

	// MS Square Rate = MS Round Basic Rate + MS Square
	frm.set_value("ms_square_rate", ms_round_basic_rate + flt(frm.doc.ms_square));

	// C4 Round Rate = C4 Round + MS Round Basic Rate
	const c4_round_rate = flt(frm.doc.c4_round) + ms_round_basic_rate;
	frm.set_value("c4_round_rate", c4_round_rate);

	// C4 Flat & Square Rate = C4 Flat & Square + C4 Round Rate
	frm.set_value("c4_flat_square_rate", flt(frm.doc.c4_flat_square) + c4_round_rate);

	// Bright Round C4 Rate = C4 Round Rate + Bright Round C4 Difference
	frm.set_value("round_bright_c4_rate", c4_round_rate + flt(frm.doc.round_bright_c4_difference));

	// Bright Round Basic = Billet Basic MS + 8.5 + Bright Round Basic Difference
	const bright_round_basic = billet_basic_ms + 8.5 + flt(frm.doc.bright_round_basic_difference);
	frm.set_value("bright_round_basic", bright_round_basic);

	// Bright Flat Basic = Bright Round Basic + 5 + Bright Flat Basic Difference
	frm.set_value(
		"bright_flat_basic",
		bright_round_basic + 5 + flt(frm.doc.bright_flat_basic_difference)
	);
}

frappe.ui.form.on("Basic Rate Structure", {
	billet_basic_ms: calculate_rates,
	rolling_charges: calculate_rates,
	payment_terms: calculate_rates,
	ms_square: calculate_rates,
	c4_round: calculate_rates,
	c4_flat_square: calculate_rates,
	round_bright_c4_difference: calculate_rates,
	bright_round_basic_difference: calculate_rates,
	bright_flat_basic_difference: calculate_rates,
});
