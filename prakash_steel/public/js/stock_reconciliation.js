// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

function update_stock_reconciliation_totals(frm) {
	// The server-side `validate` hook is the source of truth for these totals.
	// Only keep them live while the document is an editable draft, otherwise
	// re-summing on load/refresh writes the field and leaves a submitted doc
	// permanently marked "Not Saved" (the fields are allow_on_submit).
	if (frm.doc.docstatus !== 0) {
		return;
	}

	const total_qty = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.qty), 0);
	const total_amount = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.amount), 0);

	if (flt(frm.doc.custom_total_quantity, 6) !== flt(total_qty, 6)) {
		frm.set_value("custom_total_quantity", total_qty);
	}
	if (flt(frm.doc.custom_total_amount, 6) !== flt(total_amount, 6)) {
		frm.set_value("custom_total_amount", total_amount);
	}
}

frappe.ui.form.on("Stock Reconciliation", {
	onload(frm) {
		update_stock_reconciliation_totals(frm);
	},

	refresh(frm) {
		update_stock_reconciliation_totals(frm);
	},

	validate(frm) {
		update_stock_reconciliation_totals(frm);
	},

	items_add(frm) {
		update_stock_reconciliation_totals(frm);
	},

	items_remove(frm) {
		update_stock_reconciliation_totals(frm);
	},
});

frappe.ui.form.on("Stock Reconciliation Item", {
	qty(frm) {
		update_stock_reconciliation_totals(frm);
	},

	valuation_rate(frm) {
		update_stock_reconciliation_totals(frm);
	},

	amount(frm) {
		update_stock_reconciliation_totals(frm);
	},
});
