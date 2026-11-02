// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["BO Free Stock"] = {
	filters: [
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
			get_query() {
				return { filters: { custom_item_type: "BO" } };
			},
		},
		{
			fieldname: "include_zero_stock",
			label: __("Include Zero Stock"),
			fieldtype: "Check",
		},
	],

	// onload: function (report) {
	// 	report.page.add_inner_button(__("Bright Requirement Debugger"), function () {
	// 		const d = new frappe.ui.Dialog({
	// 			title: __("Bright Requirement Debugger"),
	// 			fields: [
	// 				{
	// 					label: __("BO Item Code"),
	// 					fieldname: "item_code",
	// 					fieldtype: "Link",
	// 					options: "Item",
	// 					reqd: 1,
	// 					get_query() {
	// 						return { filters: { custom_item_type: "BO" } };
	// 					},
	// 				},
	// 			],
	// 			primary_action_label: __("Show Breakdown"),
	// 			primary_action({ item_code }) {
	// 				if (!item_code) return;
	// 				d.disable_primary_action();
	// 				frappe.call({
	// 					method:
	// 						"prakash_steel.prakash_steel.report.bo_free_stock.bo_free_stock.get_bright_requirement_breakdown",
	// 					args: { item_code },
	// 					callback(r) {
	// 						d.enable_primary_action();
	// 						if (!r.message) {
	// 							frappe.msgprint(__("No data returned."));
	// 							return;
	// 						}
	// 						show_bright_requirement_dialog(r.message);
	// 					},
	// 					error() {
	// 						d.enable_primary_action();
	// 					},
	// 				});
	// 			},
	// 		});
	// 		d.show();
	// 	});
	// },
};

function show_bright_requirement_dialog(d) {
	const e = (v) => frappe.utils.escape_html(String(v ?? "—"));
	const n = (v) => (v === null || v === undefined || v === "" ? "—" : Number(v).toLocaleString());
	const row = (label, val, bold) => `
		<tr>
			<td style="padding:4px 10px;color:#888;font-size:12px;width:230px;white-space:nowrap;">${label}</td>
			<td style="padding:4px 10px;font-size:${bold ? "13" : "12"}px;font-weight:${bold ? "bold" : "normal"};">${val}</td>
		</tr>`;

	const header_html = `
		<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
			<table style="width:100%;border-collapse:collapse;">
				${row("BO Item", `<b>${e(d.item_code)}</b> — ${e(d.item_name)}`)}
				${row("SKU Type", e(d.sku_type))}
				${row(
					"Total Bright Requirement",
					`<b style="font-size:16px;color:#1d4ed8;">${n(d.total_bright_requirement)}</b> &nbsp;(ceil of sum below)`,
					true
				)}
			</table>
		</div>`;

	if (d.no_parents) {
		frappe.msgprint({
			title: __("Bright Requirement Debugger — {0}", [d.item_code]),
			message:
				header_html +
				`<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:12px 16px;">
					<p style="color:#c2410c;font-size:12px;margin:0;">⚠ No Bright Plan row has this item as its Child Item Code — Bright Requirement is 0.</p>
				</div>`,
			wide: true,
		});
		return;
	}

	const parent_rows_html = d.parents
		.map(
			(p, idx) => `
			<tr style="border-bottom:1px solid #f1f5f9;">
				<td style="padding:6px 8px;font-size:12px;">${idx + 1}</td>
				<td style="padding:6px 8px;font-size:12px;font-weight:600;">${e(p.parent_item)}</td>
				<td style="padding:6px 8px;font-size:11px;color:#666;">${e(p.machine)}</td>
				<td style="padding:6px 8px;font-size:11px;color:#666;">${e(p.sku_type)}</td>
				<td style="padding:6px 8px;font-size:12px;text-align:right;">${n(p.production_qty)}</td>
				<td style="padding:6px 8px;font-size:12px;text-align:right;">${n(p.child_requirement)}</td>
				<td style="padding:6px 8px;font-size:12px;text-align:right;">${n(p.child_stock)}</td>
				<td style="padding:6px 8px;font-size:12px;text-align:right;">${n(p.child_stock_soft_allocation_qty)}</td>
				<td style="padding:6px 8px;text-align:right;">
					<span style="background:#dbeafe;color:#1e40af;padding:2px 10px;border-radius:10px;font-weight:bold;font-size:13px;">${n(p.child_stock_shortage)}</span>
				</td>
			</tr>`
		)
		.join("");

	const parent_cards = `
		<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
			<h4 style="margin:0 0 8px;font-size:13px;color:#334155;">
				① Bright Plan rows where Child Item Code = ${e(d.item_code)}
			</h4>
			<div style="font-size:11px;color:#666;margin-bottom:8px;">
				One row per Bright Bar parent (and per MOQ/batch-size split of that parent) — sourced directly from the Bright Plan report.
			</div>
			<div style="overflow-x:auto;">
			<table style="border-collapse:collapse;width:100%;min-width:760px;">
				<thead>
					<tr style="background:#e9eef5;">
						<th style="padding:5px 8px;font-size:11px;text-align:left;">#</th>
						<th style="padding:5px 8px;font-size:11px;text-align:left;">Bright Bar Parent</th>
						<th style="padding:5px 8px;font-size:11px;text-align:left;">Machine</th>
						<th style="padding:5px 8px;font-size:11px;text-align:left;">SKU Type</th>
						<th style="padding:5px 8px;font-size:11px;text-align:right;">Production Qty</th>
						<th style="padding:5px 8px;font-size:11px;text-align:right;">Child Requirement</th>
						<th style="padding:5px 8px;font-size:11px;text-align:right;">Child Stock</th>
						<th style="padding:5px 8px;font-size:11px;text-align:right;">Stock Allocated</th>
						<th style="padding:5px 8px;font-size:11px;text-align:right;">Child Stock Shortage</th>
					</tr>
				</thead>
				<tbody>${parent_rows_html}</tbody>
			</table>
			</div>
		</div>`;

	const total_html = `
		<div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:6px;padding:12px 16px;">
			<h4 style="margin:0 0 6px;font-size:13px;color:#334155;">② Total Bright Requirement</h4>
			<div style="font-size:12px;color:#3730a3;">
				Sum of Child Stock Shortage across all ${d.parents.length} matching Bright Plan row(s), then ceil'd for display:
			</div>
			<div style="font-size:20px;font-weight:bold;color:#1d4ed8;margin-top:6px;">${n(d.total_bright_requirement)}</div>
		</div>`;

	frappe.msgprint({
		title: __("Bright Requirement Debugger — {0}", [d.item_code]),
		message: header_html + parent_cards + total_html,
		wide: true,
	});
}
