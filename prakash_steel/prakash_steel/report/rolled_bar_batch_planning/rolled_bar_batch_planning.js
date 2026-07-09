// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

frappe.query_reports["Rolled Bar Batch Planning"] = {
	filters: [
		{
			fieldname: "item_type",
			label: __("Item Type"),
			fieldtype: "Select",
			options: "\nRB\nBO\nTraded",
		},
		{
			fieldname: "sku_type",
			label: __("SKU Type"),
			fieldtype: "Select",
			options: "\nRBMTA\nRBMTO\nBOTA\nBOTO\nTRMTA\nTRMTO",
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Debug Item"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Debug Item Calculation"),
				fields: [
					{
						fieldname: "item_code",
						label: __("Item Code"),
						fieldtype: "Link",
						options: "Item",
						reqd: 1,
						filters: { custom_item_type: ["in", ["RB", "BO", "Traded"]], disabled: 0 },
					},
				],
				primary_action_label: __("Show Breakdown"),
				primary_action({ item_code }) {
					d.hide();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.rolled_bar_batch_planning.rolled_bar_batch_planning.get_item_debug_info",
						args: { item_code },
						freeze: true,
						freeze_message: __("Calculating…"),
						callback(r) {
							if (!r.message) return;
							show_debug_dialog(item_code, r.message);
						},
					});
				},
			});
			d.show();
		});
	},
};

function fmt_num(v) {
	if (v === null || v === undefined) return "—";
	return parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmt_str(v) {
	return (v === null || v === undefined || v === "") ? "—" : frappe.utils.escape_html(String(v));
}

function show_debug_dialog(item_code, info) {

	const section_hdr = (title, color) => `
		<tr>
			<td colspan="3" style="padding:8px 10px;font-weight:700;font-size:12px;
				background:${color};color:#333;letter-spacing:.4px;text-transform:uppercase;">
				${title}
			</td>
		</tr>`;

	const row = (label, value, source, is_str) => `
		<tr style="border-bottom:1px solid #f0f0f0;">
			<td style="padding:7px 10px;font-weight:600;width:170px;color:#444;">${label}</td>
			<td style="padding:7px 14px;font-weight:700;color:#1a73e8;width:130px;text-align:right;">
				${is_str ? fmt_str(value) : fmt_num(value)}
			</td>
			<td style="padding:7px 10px;color:#666;font-size:12px;">${source}</td>
		</tr>`;

	const sub_table = (headers, rows_data) => {
		if (!rows_data || !rows_data.length) return `
			<tr><td colspan="3" style="padding:4px 24px;color:#aaa;font-size:12px;font-style:italic;">
				No records found in period
			</td></tr>`;
		const head = headers.map(h =>
			`<th style="padding:4px 8px;background:#f8f9fa;color:#555;font-size:11px;font-weight:600;
				border-bottom:1px solid #e0e0e0;">${h}</th>`
		).join("");
		const body = rows_data.map(cells =>
			`<tr>${cells.map(c =>
				`<td style="padding:4px 8px;font-size:12px;border-bottom:1px solid #f5f5f5;
					${typeof c === "number" ? "text-align:right;" : ""}">${
				typeof c === "number" ? fmt_num(c) : fmt_str(c)}</td>`
			).join("")}</tr>`
		).join("");
		return `<tr><td colspan="3" style="padding:2px 24px 8px;">
			<table style="width:100%;border-collapse:collapse;">
				<thead><tr>${head}</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</td></tr>`;
	};

	const html = `
		<div style="font-family:var(--font-stack);font-size:13px;">
			<div style="margin-bottom:10px;padding:8px 10px;background:#f8f9fa;
				border-radius:4px;color:#555;line-height:1.8;">
				<strong>Item Code:</strong> ${fmt_str(item_code)}
				&nbsp;|&nbsp; <strong>Item Name:</strong> ${fmt_str(info.item_name)}
				&nbsp;|&nbsp; <strong>Period:</strong> ${fmt_str(info.period_label)}
			</div>
			<table style="width:100%;border-collapse:collapse;">

				${section_hdr("Item Info", "#e8f0fe")}
				${row("Item Type", info.item_type, "tabItem → custom_item_type", true)}
				${row("SKU Type",  info.sku_type,  "tabItem → custom_sku_type",  true)}

				${section_hdr("Sales Qty", "#e6f4ea")}
				${row("Sales Qty", info.sales_qty,
					`SUM(sii.qty) — ${(info.sales_records||[]).length} Sales Invoice(s) in period`)}
				${sub_table(
					["Sales Invoice", "Date", "Qty"],
					(info.sales_records||[]).map(r => [r.name, r.date, r.qty])
				)}

				${section_hdr("Consumption Qty", "#fff3e0")}
				${row("Consumption Qty", info.consumption_qty,
					`SUM(actual_rm_consumption) — ${(info.consumption_records||[]).length} Bright Bar Production record(s) where raw_material OR material = item_code`)}
				${sub_table(
					["BBP Name", "Date", "RM Consumption", "Matched Field"],
					(info.consumption_records||[]).map(r => [r.name, r.date, r.qty, r.matched_field])
				)}

				${section_hdr("Totals & Projection", "#fff8e1")}
				${row("Total",         info.total,        "Sales Qty + Consumption Qty")}
				${row("Projected Qty", info.projected_qty, "Total × 1.3")}

				${section_hdr("Production (Finish Weight)", "#fce8e6")}
				${row("Production Count", info.production_count,
					`COUNT(*) — ${info.production_count} Finish Weight record(s) where item_name = "${fmt_str(info.item_name)}" in period`)}
				${row("Production Qty", info.production_qty,
					`SUM(finish_weight) across all ${info.production_count} record(s)`)}
				${row("Batch Size", info.batch_size, "Projected Qty ÷ Production Count")}
				${sub_table(
					["Finish Weight Name", "Date", "Finish Weight"],
					(info.fw_records||[]).map(r => [r.name, r.date, r.weight])
				)}

			</table>
		</div>`;

	const result_d = new frappe.ui.Dialog({
		title: __("Calculation Breakdown — {0}", [item_code]),
		size: "large",
	});
	result_d.body.innerHTML = html;
	result_d.show();
}
