// // Copyright (c) 2026, Beetashoke Chakraborty and contributors
// // For license information, please see license.txt

// const COLOUR_STYLES = {
// 	Black: { bg: "#222", fg: "#fff" },
// 	Red: { bg: "#e74c3c", fg: "#fff" },
// 	Yellow: { bg: "#f1c40f", fg: "#333" },
// 	Green: { bg: "#27ae60", fg: "#fff" },
// 	White: { bg: "#f0f0f0", fg: "#333" },
// };

// frappe.query_reports["Rolled Plan"] = {
// 	filters: [],

// 	formatter(value, row, column, data, default_formatter) {
// 		if (column.fieldname === "colour" && value && COLOUR_STYLES[value]) {
// 			const { bg, fg } = COLOUR_STYLES[value];
// 			return `<span style="
// 				background:${bg};color:${fg};
// 				padding:2px 10px;border-radius:4px;
// 				font-weight:bold;display:inline-block;
// 			">${value}</span>`;
// 		}
// 		if (column.fieldname === "on_hand_colour" && value) {
// 			const key = value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
// 			const style = COLOUR_STYLES[key];
// 			if (style) {
// 				const { bg, fg } = style;
// 				return `<div style="
// 					background-color:${bg};color:${fg};
// 					border-radius:0px;padding:4px;
// 					text-align:center;font-weight:bold;
// 				">${value}</div>`;
// 			}
// 		}
// 		return default_formatter(value, row, column, data);
// 	},

// 	onload(report) {
// 		report.page.add_inner_button(__("Final Allocated Qty Breakdown"), () => {
// 			const d = new frappe.ui.Dialog({
// 				title: __("Final Allocated Qty Breakdown"),
// 				fields: [
// 					{
// 						label: __("Item Code"),
// 						fieldname: "item_code",
// 						fieldtype: "Link",
// 						options: "Item",
// 						reqd: 1,
// 						get_query() {
// 							return { filters: { custom_item_type: "RB" } };
// 						},
// 					},
// 				],
// 				primary_action_label: __("Show Breakdown"),
// 				primary_action({ item_code }) {
// 					if (!item_code) return;
// 					d.disable_primary_action();
// 					frappe.call({
// 						method: "prakash_steel.prakash_steel.report.rolled_plan.rolled_plan.get_final_allocated_qty_breakdown",
// 						args: { item_code },
// 						callback(r) {
// 							d.enable_primary_action();
// 							if (!r.message) {
// 								frappe.msgprint(__("No data returned."));
// 								return;
// 							}
// 							if (r.message.error) {
// 								frappe.msgprint(r.message.error);
// 								return;
// 							}
// 							show_final_allocated_breakdown(r.message);
// 						},
// 						error() { d.enable_primary_action(); },
// 					});
// 				},
// 			});
// 			d.show();
// 		});

// 		report.page.add_inner_button(__("Item Breakdown"), () => {
// 			const d = new frappe.ui.Dialog({
// 				title: __("Item Colour Breakdown"),
// 				fields: [
// 					{
// 						label: __("Item Code"),
// 						fieldname: "item_code",
// 						fieldtype: "Link",
// 						options: "Item",
// 						reqd: 1,
// 						get_query() {
// 							return { filters: { custom_item_type: "RB" } };
// 						},
// 					},
// 				],
// 				primary_action_label: __("Show Breakdown"),
// 				primary_action({ item_code }) {
// 					if (!item_code) return;
// 					d.disable_primary_action();
// 					frappe.call({
// 						method: "prakash_steel.prakash_steel.report.rolled_plan.rolled_plan.get_item_colour_breakdown",
// 						args: { item_code },
// 						callback(r) {
// 							d.enable_primary_action();
// 							if (!r.message) {
// 								frappe.msgprint(__("No data returned."));
// 								return;
// 							}
// 							show_breakdown_dialog(r.message);
// 						},
// 						error() { d.enable_primary_action(); },
// 					});
// 				},
// 			});
// 			d.show();
// 		});
// 	},
// };

// // ---------------------------------------------------------------------------
// // Helpers
// // ---------------------------------------------------------------------------

// function colour_badge(label) {
// 	if (!label) return "";
// 	const s = COLOUR_STYLES[label] || COLOUR_STYLES[label.charAt(0).toUpperCase() + label.slice(1).toLowerCase()];
// 	if (!s) return frappe.utils.escape_html(label);
// 	return `<span style="background:${s.bg};color:${s.fg};padding:1px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(label)}</span>`;
// }

// function kv_table(rows) {
// 	const cells = rows.map(([k, v]) =>
// 		`<tr>
// 			<td style="padding:4px 10px;font-weight:600;color:#555;font-size:12px;white-space:nowrap;">${k}</td>
// 			<td style="padding:4px 10px;font-size:12px;">${v ?? ""}</td>
// 		</tr>`
// 	).join("");
// 	return `<table style="border-collapse:collapse;margin-bottom:8px;">${cells}</table>`;
// }

// function section_title(title) {
// 	return `<div style="font-weight:700;font-size:13px;margin:14px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px;">${title}</div>`;
// }

// function so_fifo_table(rows) {
// 	if (!rows || !rows.length)
// 		return `<em style="color:#aaa;font-size:11px;">No open SOs</em>`;

// 	const hdrs = ["Delivery Date", "Qty to Deliver", "Allocated", "Shortage", "Available After", "Order Status"]
// 		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
// 		.join("");

// 	const trows = rows.map(r => {
// 		const sc = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
// 		return `<tr>
// 			<td style="padding:3px 8px;font-size:11px;">${r.delivery_date || ""}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.pending_qty}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
// 			<td style="padding:3px 8px;font-size:11px;${sc}">${r.shortage}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.available_after}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.order_status)}</td>
// 		</tr>`;
// 	}).join("");

// 	return `<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;background:#fafafa;">
// 		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
// 		<tbody>${trows}</tbody>
// 	</table></div>`;
// }

// function parent_fifo_table(rows) {
// 	if (!rows || !rows.length)
// 		return `<em style="color:#aaa;font-size:11px;">No parent BOM batches</em>`;

// 	const hdrs = ["Priority Seq", "Priority Colour", "OP/CP", "Parent Item", "Level Before", "Batch Qty", "Child Req", "Allocated", "Shortage", "Available After", "Colour"]
// 		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
// 		.join("");

// 	const trows = rows.map(r => {
// 		const sc = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
// 		return `<tr>
// 			<td style="padding:3px 8px;font-size:11px;">${r.priority_sequence === 999999 ? "—" : r.priority_sequence}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${frappe.utils.escape_html(r.priority_colour || "")}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.op_cp || ""}</td>
// 			<td style="padding:3px 8px;font-size:11px;font-weight:600;">${frappe.utils.escape_html(r.parent_item)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.level_before}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.batch_qty}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.child_req}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
// 			<td style="padding:3px 8px;font-size:11px;${sc}">${r.shortage}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${r.available_after}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.order_status)}</td>
// 		</tr>`;
// 	}).join("");

// 	return `<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;background:#fafafa;">
// 		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
// 		<tbody>${trows}</tbody>
// 	</table></div>`;
// }

// function show_breakdown_dialog(d) {
// 	let html = "";

// 	// Header summary
// 	html += kv_table([
// 		["Item Code", `<b>${frappe.utils.escape_html(d.item_code)}</b> — ${frappe.utils.escape_html(d.item_name || "")}`],
// 		["SKU Type", d.sku_type],
// 		["Buffer Flag", d.buffer_flag],
// 		["Stock", d.stock],
// 		["Level (Stock)", `<b>${d.level}</b>`],
// 		["TOG", d.tog],
// 		["Final Colour", colour_badge(d.colour)],
// 	]);

// 	if (d.detail_type === "buffer") {
// 		// RBMTA
// 		html += section_title("Buffer Colour Calculation");
// 		const pct = d.total > 0 ? `${Math.round(d.level / d.total * 100)}%` : "N/A";
// 		html += kv_table([
// 			["Till Today Demand", d.till_today],
// 			["Spike", d.spike],
// 			["Qualified Demand", d.qualified_demand],
// 			["Total (TOG + QD)", d.total],
// 			["Level / Total", pct],
// 			["≤ 1/3 → Red, ≤ 2/3 → Yellow, ≤ 1 → Green, > 1 → White", ""],
// 		]);
// 	} else {
// 		// RBMTO
// 		html += section_title("Step 1 — Own Open SOs (FIFO, sorted by Delivery Date)");
// 		html += so_fifo_table(d.own_so_fifo);

// 		html += section_title("Step 2 — Parent BOM FIFO (sorted by Priority Sequence ASC)");
// 		html += parent_fifo_table(d.parent_fifo);

// 		html += section_title("Result");
// 		html += `<p style="font-size:13px;">First shortage colour: ${colour_badge(d.colour) || "<em>No shortage — no colour</em>"}</p>`;
// 	}

// 	frappe.msgprint({
// 		title: __("Colour Breakdown — {0}", [d.item_code]),
// 		message: `<div style="font-family:sans-serif;">${html}</div>`,
// 		wide: true,
// 	});
// }

// function show_final_allocated_breakdown(d) {
// 	const fmt = v => (v === null || v === undefined) ? "—" : parseFloat(v).toFixed(3);
// 	let html = "";

// 	// Step 1: Item base
// 	html += section_title("Step 1 — Item Base Values");
// 	html += kv_table([
// 		["Item Code", `<b>${frappe.utils.escape_html(d.item_code)}</b> — ${frappe.utils.escape_html(d.item_name || "")}`],
// 		["SKU Type", d.sku_type],
// 		["Subgrp+Shape", frappe.utils.escape_html(d.subgrp_shape || "")],
// 		["Sub Grp", frappe.utils.escape_html(d.sub_grp || "")],
// 		["TOG (effective)", fmt(d.tog)],
// 		["Per Hour Qty", fmt(d.per_hour_qty)],
// 		["Net Order Recommendation", fmt(d.net_order_rec)],
// 		["Hrs Work (NOR / Per Hour Qty)", fmt(d.hrs_work)],
// 		["TOG %", fmt(d.tog_pct)],
// 	]);

// 	// Step 2: Subgroup hours shortage
// 	html += section_title("Step 2 — Subgroup Hours Shortage (grouped by Sub Grp)");
// 	html += kv_table([
// 		["Subgrp Hours+Setup (sum of hrs_work in sub grp)", fmt(d.subgrp_hrs_setup)],
// 		["Subgrp Hours Shortage (final_planned_hrs − setup)", fmt(d.subgrp_hours_shortage)],
// 	]);

// 	// Step 3: Extra hours & qty
// 	html += section_title("Step 3 — Extra Hours & Qty");
// 	html += kv_table([
// 		["Formula", "TOG% × Subgrp Hours Shortage / 100"],
// 		["Extra Hours", `${fmt(d.tog_pct)} × ${fmt(d.subgrp_hours_shortage)} / 100 = <b>${fmt(d.extra_hours)}</b>`],
// 		["Extra Qty (Extra Hours × Per Hour Qty)", fmt(d.extra_qty)],
// 	]);

// 	// Step 4: On hand colour & excess qty
// 	html += section_title("Step 4 — On Hand Colour & Excess Qty");
// 	html += kv_table([
// 		["On Hand Stock", fmt(d.on_hand_stock)],
// 		["On Hand Colour", colour_badge(d.on_hand_colour) || "—"],
// 		["Excess Qty", `${d.on_hand_colour === "WHITE"
// 			? `WHITE → stock − tog − qd = <b>${fmt(d.excess_qty)}</b>`
// 			: `Not WHITE → Excess Qty = Extra Qty = <b>${fmt(d.excess_qty)}</b>`}`],
// 		["Excess Qty / TOG %", fmt(d.excess_qty_tog)],
// 	]);

// 	// Step 5: Allocated hours
// 	html += section_title("Step 5 — Allocated Hours (grouped by Subgrp+Shape)");
// 	html += kv_table([
// 		["Sum of Extra Hours in Subgrp+Shape", fmt(d.subgrp_extra_hrs_sum)],
// 		["Formula", "Sum × TOG% / 100"],
// 		["Allocated Hours", `${fmt(d.subgrp_extra_hrs_sum)} × ${fmt(d.tog_pct)} / 100 = <b>${fmt(d.allocated_hours)}</b>`],
// 		["Total Allocated Qty (Alloc Hours × Per Hour Qty)", `<b>${fmt(d.total_allocated_qty)}</b>`],
// 	]);

// 	// Step 6: Final allocated qty
// 	html += section_title("Step 6 — Final Allocated Qty");
// 	const isWhite = d.on_hand_colour === "WHITE";
// 	html += kv_table([
// 		["On Hand Colour", colour_badge(d.on_hand_colour) || "—"],
// 		["WHITE deduction", isWhite
// 			? `Total Alloc Qty − Excess Qty = ${fmt(d.total_allocated_qty)} − ${fmt(d.excess_qty)} = <b>${fmt(Math.max(0, (d.total_allocated_qty || 0) - (d.excess_qty || 0)))}</b>`
// 			: "Not WHITE — no deduction"],
// 		["Lost Hours from WHITE items in Subgrp+Shape", fmt(d.subgrp_lost_hrs)],
// 		["Eligible TOG Sum (non-WHITE, final > 0)", fmt(d.eligible_tog_sum)],
// 		["Redistribution added", d.subgrp_lost_hrs > 0 && !isWhite && d.eligible_tog_sum > 0
// 			? `${fmt(d.subgrp_lost_hrs)} × (${fmt(d.tog_pct)} / ${fmt(d.eligible_tog_sum)}) × ${fmt(d.per_hour_qty)}`
// 			: "None"],
// 		["Final Allocated Qty", `<b style="font-size:14px;">${fmt(d.final_allocated_qty)}</b>`],
// 	]);

// 	// Subgroup context table
// 	html += section_title("Subgrp+Shape Context — All Items");
// 	const hdrs = ["Item Code", "TOG%", "Extra Hrs", "On Hand", "Excess Qty", "Alloc Hrs", "Total Alloc Qty", "Final Alloc Qty"]
// 		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`).join("");
// 	const trows = (d.subgrp_rows || []).map(r => {
// 		const highlight = r.item_code === d.item_code ? "background:#fffbe6;" : "";
// 		return `<tr style="${highlight}">
// 			<td style="padding:3px 8px;font-size:11px;font-weight:600;">${frappe.utils.escape_html(r.item_code)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${fmt(r.tog_pct)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${fmt(r.extra_hours)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.on_hand_colour)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${fmt(r.excess_qty)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${fmt(r.allocated_hours)}</td>
// 			<td style="padding:3px 8px;font-size:11px;">${fmt(r.total_allocated_qty)}</td>
// 			<td style="padding:3px 8px;font-size:11px;font-weight:bold;">${fmt(r.final_allocated_qty)}</td>
// 		</tr>`;
// 	}).join("");
// 	html += `<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;background:#fafafa;">
// 		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
// 		<tbody>${trows}</tbody>
// 	</table></div>`;

// 	frappe.msgprint({
// 		title: __("Final Allocated Qty Breakdown — {0}", [d.item_code]),
// 		message: `<div style="font-family:sans-serif;">${html}</div>`,
// 		wide: true,
// 	});
// }
