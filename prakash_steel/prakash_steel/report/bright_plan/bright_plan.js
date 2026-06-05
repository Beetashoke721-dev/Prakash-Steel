// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const BRIGHT_COLOUR_STYLES = {
	BLACK: { bg: "#000000", fg: "#FFFFFF" },
	RED: { bg: "#FF0000", fg: "#FFFFFF" },
	YELLOW: { bg: "#FFFF00", fg: "#000000" },
	GREEN: { bg: "#00FF00", fg: "#000000" },
	WHITE: { bg: "#FFFFFF", fg: "#000000" },
};

function bright_colour_badge(colour) {
	const key = (colour || "").toUpperCase();
	const s = BRIGHT_COLOUR_STYLES[key];
	if (!s) return frappe.utils.escape_html(colour || "&mdash;");
	return `<span style="background:${s.bg};color:${s.fg};padding:2px 10px;border-radius:3px;font-weight:bold;display:inline-block;">${frappe.utils.escape_html(colour)}</span>`;
}

function show_bright_breakdown(item_code, rows) {
	if (!rows || !rows.length) {
		frappe.msgprint(__("No rows returned for this item."));
		return;
	}

	const r0 = rows[0];
	const summary = `
		<div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:12px;font-size:13px;background:#f9f9f9;padding:10px;border-radius:6px;">
			<span><b>Item:</b> ${frappe.utils.escape_html(item_code)}</span>
			<span><b>SKU Type:</b> ${r0.sku_type}</span>
			<span><b>Stock:</b> ${r0.stock}</span>
			<span><b>WIP (Submitted WO):</b> ${r0.wip}</span>
			${r0.is_buffer ? `<span><b>Draft WO:</b> ${r0.draft_wo}</span>` : ""}
			<span><b>MRQ:</b> ${r0.mrq}</span>
			<span><b>Open SO:</b> ${r0.open_so}</span>
			${r0.is_buffer ? `<span><b>TOG:</b> ${r0.tog}</span>` : ""}
			<span><b>Qual. Demand:</b> ${r0.qualified_demand}</span>
			${r0.is_buffer ? `<span><b>Total (TOG+Demand):</b> ${r0.total}</span>` : ""}
			<span><b>Net Order Rec:</b> ${r0.net_order_rec}</span>
			<span><b>Batches:</b> ${r0.num_batches}</span>
			<span><b>MOQ:</b> ${r0.moq}</span>
			<span><b>Batch Size:</b> ${r0.batch_size}</span>
		</div>`;

	const hdrs = ["Row", "Qty", "Accum. Prev", "WIP (Sub WO)", "Draft WO", "Level (S+W+DW+P)", "On Hand Colour", "Reason", "Rem. SO before", "OP/CP", "Priority Colour"]
		.map(h => `<th style="padding:5px 8px;border-bottom:2px solid #ddd;text-align:left;font-size:12px;white-space:nowrap;">${h}</th>`)
		.join("");

	const tbody = rows.map(r => {
		const op_style = r.op_cp === "OP"
			? "background:#4dff88;color:#000;font-weight:bold;padding:1px 8px;border-radius:3px;"
			: r.op_cp === "CP"
				? "background:#add8e6;color:#000;font-weight:bold;padding:1px 8px;border-radius:3px;"
				: "";
		let pc_bg = "", pc_fg = "#000";
		for (const c of ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]) {
			if ((r.priority_colour || "").toUpperCase().endsWith(c)) {
				pc_bg = BRIGHT_COLOUR_STYLES[c].bg;
				pc_fg = BRIGHT_COLOUR_STYLES[c].fg;
				break;
			}
		}
		const pc_cell = pc_bg
			? `<span style="background:${pc_bg};color:${pc_fg};padding:2px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(r.priority_colour)}</span>`
			: frappe.utils.escape_html(r.priority_colour || "&mdash;");

		return `<tr style="border-bottom:1px solid #eee;">
			<td style="padding:4px 8px;font-size:12px;font-weight:bold;">${r.batch_no}</td>
			<td style="padding:4px 8px;font-size:12px;">${r.qty_per_row}</td>
			<td style="padding:4px 8px;font-size:12px;">${r.accumulated_batch_qty}</td>
			<td style="padding:4px 8px;font-size:12px;">${r.wip}</td>
			<td style="padding:4px 8px;font-size:12px;">${r.is_buffer ? r.draft_wo : "&mdash;"}</td>
			<td style="padding:4px 8px;font-size:12px;font-weight:bold;">${r.level}</td>
			<td style="padding:4px 8px;font-size:12px;">${bright_colour_badge(r.on_hand_colour)}</td>
			<td style="padding:4px 8px;font-size:12px;color:#555;">${frappe.utils.escape_html(r.colour_reason || "")}</td>
			<td style="padding:4px 8px;font-size:12px;">${r.remaining_so_before}</td>
			<td style="padding:4px 8px;font-size:12px;"><span style="${op_style}">${r.op_cp || "&mdash;"}</span></td>
			<td style="padding:4px 8px;font-size:12px;">${pc_cell}</td>
		</tr>`;
	}).join("");

	const html = summary + `
		<div style="overflow-x:auto;">
			<table style="width:100%;border-collapse:collapse;font-size:13px;">
				<thead><tr style="background:#f0f0f0;">${hdrs}</tr></thead>
				<tbody>${tbody}</tbody>
			</table>
		</div>`;

	frappe.msgprint({
		title: __("Bright Plan Debug — {0}", [item_code]),
		message: html,
		wide: true,
	});
}

frappe.query_reports["Bright Plan"] = {
	filters: [],

	onload(report) {
		report.page.add_inner_button(__("Debug Item Breakdown"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Debug Item Breakdown"),
				fields: [
					{
						label: __("Item Code"),
						fieldname: "item_code",
						fieldtype: "Link",
						options: "Item",
						reqd: 1,
						get_query() {
							return { filters: { custom_item_type: "BB" } };
						},
					},
				],
				primary_action_label: __("Show Breakdown"),
				primary_action({ item_code }) {
					if (!item_code) return;
					d.disable_primary_action();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.bright_plan.bright_plan.get_item_breakdown",
						args: { item_code },
						callback(r) {
							d.enable_primary_action();
							show_bright_breakdown(item_code, r.message || []);
						},
						error() {
							d.enable_primary_action();
						},
					});
				},
			});
			d.show();
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "on_hand_colour_priority" && data && data.on_hand_colour_priority) {
			let colour = (data.on_hand_colour_priority || "").toUpperCase();
			let bg = "";
			let textColor = "#000000";

			if (colour === "BLACK") {
				bg = "#000000";
				textColor = "#FFFFFF";
			} else if (colour === "RED") {
				bg = "#FF0000";
				textColor = "#FFFFFF";
			} else if (colour === "YELLOW") {
				bg = "#FFFF00";
				textColor = "#000000";
			} else if (colour === "GREEN") {
				bg = "#00FF00";
				textColor = "#000000";
			} else if (colour === "WHITE") {
				bg = "#FFFFFF";
				textColor = "#000000";
			}

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${data.on_hand_colour_priority}
				</div>`;
			}
		}

		if (column.fieldname === "priority_colour" && data && data.priority_colour) {
			let val = data.priority_colour;
			let bg = "";
			let textColor = "#000000";

			// Extract colour suffix dynamically
			for (let colour of ["BLACK", "RED", "YELLOW", "GREEN", "WHITE"]) {
				if (val.endsWith(colour)) {
					if (colour === "BLACK") { bg = "#000000"; textColor = "#FFFFFF"; }
					else if (colour === "RED") { bg = "#FF0000"; textColor = "#FFFFFF"; }
					else if (colour === "YELLOW") { bg = "#FFFF00"; textColor = "#000000"; }
					else if (colour === "GREEN") { bg = "#00FF00"; textColor = "#000000"; }
					else if (colour === "WHITE") { bg = "#FFFFFF"; textColor = "#000000"; }
					break;
				}
			}

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${val}
				</div>`;
			}
		}

		if (column.fieldname === "op_cp" && data && data.op_cp) {
			let val = data.op_cp;
			let bg = "";
			let textColor = "#000000";

			if (val === "OP") {
				bg = "#4dff88";   // green — serving open SO
			} else if (val === "CP") {
				bg = "#add8e6";   // light blue — going to stock
			}

			if (bg) {
				return `<div style="
					background-color:${bg};
					border-radius:0px;
					padding:4px;
					text-align:center;
					font-weight:bold;
					color:${textColor};
				">
					${val}
				</div>`;
			}
		}

		return value;
	},
};
