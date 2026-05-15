// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.ui.form.on("pr fc solver", {
	fc_solver(frm) {
		if (!frm.doc.items || !frm.doc.items.length) {
			frappe.msgprint(__("Add at least one Purchase Receipt row."));
			return;
		}

		const missing = frm.doc.items.filter((row) => !row.purchase_receipt || !row.freight_payable_by);
		if (missing.length) {
			frappe.msgprint(__("Each row must have Purchase Receipt and Freight Payable By."));
			return;
		}

		frappe.confirm(
			__(
				"Update <b>Freight Payable By</b> on {0} Purchase Receipt(s)? Submitted documents will be updated directly.",
				[frm.doc.items.length]
			),
			() => {
				frm.save().then(() => {
					frappe.call({
						method:
							"prakash_steel.prakash_steel.doctype.pr_fc_solver.pr_fc_solver.apply_freight_payable_by",
						freeze: true,
						freeze_message: __("Updating Purchase Receipts..."),
						callback(r) {
							if (r.exc) {
								return;
							}
							show_apply_result(r.message);
							frm.reload_doc();
						},
					});
				});
			}
		);
	},
});

function show_apply_result(result) {
	if (!result) {
		return;
	}

	let html = `<p><strong>${result.summary}</strong></p>`;

	const sections = [
		["updated", __("Updated"), "green"],
		["skipped", __("Skipped"), "orange"],
		["failed", __("Failed"), "red"],
	];

	for (const [key, title, indicator] of sections) {
		const rows = result[key] || [];
		if (!rows.length) {
			continue;
		}
		html += `<p class="text-${indicator === "green" ? "success" : indicator === "red" ? "danger" : "warning"}"><strong>${title}</strong></p><ul>`;
		for (const row of rows) {
			if (key === "updated") {
				html += `<li>${frappe.utils.escape_html(row.purchase_receipt)}: ${frappe.utils.escape_html(row.from || "—")} → ${frappe.utils.escape_html(row.to)}</li>`;
			} else {
				html += `<li>${frappe.utils.escape_html(row.purchase_receipt)} — ${frappe.utils.escape_html(row.reason)}</li>`;
			}
		}
		html += "</ul>";
	}

	frappe.msgprint({
		title: __("Freight Payable By Corrections"),
		message: html,
		indicator: result.failed?.length ? "orange" : "green",
	});
}
