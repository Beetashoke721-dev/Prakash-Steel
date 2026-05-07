// Invoice posting date on each Payment Entry Reference row (`custom_invoice_date`).
//
// - Manual row / reference picker: ERPNext fills `due_date` via `get_reference_details`;
//   we also set `custom_invoice_date` here with a lightweight `get_value` and force a
//   grid refresh so the date column updates immediately (same moment as due_date).
// - "Get Outstanding Invoices/Orders": due_date is copied from `get_outstanding_reference_documents`
//   and never calls `get_reference_details`; we patch that flow to fill posting dates after allocation.

frappe.ui.form.on("Payment Entry Reference", {
	reference_doctype(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) return;
		const row = locals[cdt][cdn];
		if (
			!row.reference_doctype ||
			!["Sales Invoice", "Purchase Invoice"].includes(row.reference_doctype)
		) {
			frappe.model.set_value(cdt, cdn, "custom_invoice_date", null);
			frm.refresh_field("references");
		}
	},

	reference_name(frm, cdt, cdn) {
		if (frm.doc.docstatus !== 0) return;
		const row = locals[cdt][cdn];

		if (!row.reference_doctype || !row.reference_name) {
			frappe.model.set_value(cdt, cdn, "custom_invoice_date", null);
			frm.refresh_field("references");
			return;
		}

		if (!["Sales Invoice", "Purchase Invoice"].includes(row.reference_doctype)) {
			frappe.model.set_value(cdt, cdn, "custom_invoice_date", null);
			frm.refresh_field("references");
			return;
		}

		frappe.db
			.get_value(row.reference_doctype, row.reference_name, "posting_date")
			.then((response) => {
				const posting_date = response.message?.posting_date || null;
				frappe.model.set_value(cdt, cdn, "custom_invoice_date", posting_date);
				frm.refresh_field("references");
			});
	},
});

frappe.ui.form.on("Payment Entry", {
	onload(frm) {
		if (frm.__ps_payment_ref_invoice_date_patched) return;
		frm.__ps_payment_ref_invoice_date_patched = true;

		const orig_get_outstanding_documents = frm.events.get_outstanding_documents;
		frm.events.get_outstanding_documents = function (
			frm_inner,
			filters,
			get_outstanding_invoices,
			get_orders_to_be_billed
		) {
			const orig_frappe_call = frappe.call.bind(frappe);
			frappe.call = function (opts) {
				if (
					opts &&
					opts.method ===
						"erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents"
				) {
					const orig_cb = opts.callback;
					opts.callback = function (r, rt) {
						const posting_map = {};
						(r.message || []).forEach((d) => {
							if (
								["Sales Invoice", "Purchase Invoice"].includes(d.voucher_type) &&
								d.posting_date
							) {
								posting_map[`${d.voucher_type}::${d.voucher_no}`] = d.posting_date;
							}
						});
						frm_inner._ps_invoice_posting_map = posting_map;
						return orig_cb.apply(this, arguments);
					};
				}
				try {
					return orig_frappe_call(opts);
				} finally {
					frappe.call = orig_frappe_call;
				}
			};
			return orig_get_outstanding_documents.call(
				this,
				frm_inner,
				filters,
				get_outstanding_invoices,
				get_orders_to_be_billed
			);
		};

		const orig_allocate = frm.events.allocate_party_amount_against_ref_docs;
		frm.events.allocate_party_amount_against_ref_docs = async function (
			frm_inner,
			paid_amount,
			paid_amount_change
		) {
			await orig_allocate.call(this, frm_inner, paid_amount, paid_amount_change);
			const map = frm_inner._ps_invoice_posting_map;
			if (map && Object.keys(map).length) {
				(frm_inner.doc.references || []).forEach((row) => {
					const k = `${row.reference_doctype}::${row.reference_name}`;
					if (map[k]) {
						frappe.model.set_value(
							row.doctype,
							row.name,
							"custom_invoice_date",
							map[k]
						);
					}
				});
				frm_inner._ps_invoice_posting_map = null;
			}
			frm_inner.refresh_field("references");
		};
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;

		(frm.doc.references || []).forEach((row) => {
			if (row.custom_invoice_date) return;
			if (!row.reference_doctype || !row.reference_name) return;
			if (!["Sales Invoice", "Purchase Invoice"].includes(row.reference_doctype)) return;

			frappe.db
				.get_value(row.reference_doctype, row.reference_name, "posting_date")
				.then((response) => {
					const posting_date = response.message?.posting_date || null;
					if (!posting_date) return;
					frappe.model.set_value(
						row.doctype,
						row.name,
						"custom_invoice_date",
						posting_date
					);
					frm.refresh_field("references");
				});
		});
	},
});
