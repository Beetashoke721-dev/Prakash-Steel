frappe.ui.form.on("Payment Entry Reference", {
	reference_name(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) return;
		const row = locals[cdt][cdn];
		set_invoice_date(row);
	},
	reference_doctype(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) return;
		const row = locals[cdt][cdn];
		set_invoice_date(row);
	},
});

frappe.ui.form.on("Payment Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) return; // Do not touch submitted/cancelled docs

		// Ensure we also backfill values for rows that were populated programmatically
		// (e.g. via "Get References") without triggering child field change events.
		const rows = frm.doc.references || frm.doc.reference_details || [];
		(rows || []).forEach((row) => set_invoice_date(row));
	},
});

function set_invoice_date(row) {
	if (!row.reference_doctype || !row.reference_name) {
		frappe.model.set_value(
			row.doctype,
			row.name,
			"custom_invoice_date",
			null
		);
		return;
	}

	if (!["Sales Invoice", "Purchase Invoice"].includes(row.reference_doctype)) {
		frappe.model.set_value(
			row.doctype,
			row.name,
			"custom_invoice_date",
			null
		);
		return;
	}

	frappe.db
		.get_value(row.reference_doctype, row.reference_name, "posting_date")
		.then((response) => {
			const posting_date = response.message?.posting_date || null;
			frappe.model.set_value(
				row.doctype,
				row.name,
				"custom_invoice_date",
				posting_date
			);
		});
}
