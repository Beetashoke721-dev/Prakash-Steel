// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const COLOUR_STYLES = {
	Black: { bg: "#222", fg: "#fff" },
	Red: { bg: "#e74c3c", fg: "#fff" },
	Yellow: { bg: "#f1c40f", fg: "#333" },
	Green: { bg: "#27ae60", fg: "#fff" },
	White: { bg: "#f0f0f0", fg: "#333" },
};

frappe.query_reports["Rolled Plan"] = {
	filters: [],

	formatter(value, row, column, data, default_formatter) {
		if (["colour", "pipeline_priority"].includes(column.fieldname) && value) {
			// Colour can come from either the own-SO step (Title case, e.g. "Black")
			// or the parent-batch step (upper case, e.g. "BLACK") — normalize before
			// lookup so both render as a styled chip instead of one falling through
			// to plain text.
			const key = value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
			const style = COLOUR_STYLES[key];
			if (style) {
				const { bg, fg } = style;
				return `<span style="
					background:${bg};color:${fg};
					padding:2px 10px;border-radius:4px;
					font-weight:bold;display:inline-block;
				">${value}</span>`;
			}
		}
		if (column.fieldname === "on_hand_colour" && value) {
			const key = value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
			const style = COLOUR_STYLES[key];
			if (style) {
				const { bg, fg } = style;
				return `<div style="
					background-color:${bg};color:${fg};
					border-radius:0px;padding:4px;
					text-align:center;font-weight:bold;
				">${value}</div>`;
			}
		}
		return default_formatter(value, row, column, data);
	},

	onload(report) {
		// report.page.add_inner_button(__("Item Breakdown"), () => {
		// 	const d = new frappe.ui.Dialog({
		// 		title: __("Item Colour Breakdown"),
		// 		fields: [
		// 			{
		// 				label: __("Item Code"),
		// 				fieldname: "item_code",
		// 				fieldtype: "Link",
		// 				options: "Item",
		// 				reqd: 1,
		// 				get_query() {
		// 					return { filters: { custom_item_type: "RB" } };
		// 				},
		// 			},
		// 		],
		// 		primary_action_label: __("Show Breakdown"),
		// 		primary_action({ item_code }) {
		// 			if (!item_code) return;
		// 			d.disable_primary_action();
		// 			frappe.call({
		// 				method: "prakash_steel.prakash_steel.report.rolled_plan.rolled_plan.get_item_colour_breakdown",
		// 				args: { item_code },
		// 				callback(r) {
		// 					d.enable_primary_action();
		// 					if (!r.message) {
		// 						frappe.msgprint(__("No data returned."));
		// 						return;
		// 					}
		// 					show_breakdown_dialog(r.message);
		// 				},
		// 				error() { d.enable_primary_action(); },
		// 			});
		// 		},
		// 	});
		// 	d.show();
		// });
	},
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function colour_badge(label) {
	if (!label) return "";
	const s = COLOUR_STYLES[label] || COLOUR_STYLES[label.charAt(0).toUpperCase() + label.slice(1).toLowerCase()];
	if (!s) return frappe.utils.escape_html(label);
	return `<span style="background:${s.bg};color:${s.fg};padding:1px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(label)}</span>`;
}

function kv_table(rows) {
	const cells = rows.map(([k, v]) =>
		`<tr>
			<td style="padding:4px 10px;font-weight:600;color:#555;font-size:12px;white-space:nowrap;">${k}</td>
			<td style="padding:4px 10px;font-size:12px;">${v ?? ""}</td>
		</tr>`
	).join("");
	return `<table style="border-collapse:collapse;margin-bottom:8px;">${cells}</table>`;
}

function section_title(title) {
	return `<div style="font-weight:700;font-size:13px;margin:14px 0 6px;border-bottom:1px solid #ddd;padding-bottom:4px;">${title}</div>`;
}

function so_fifo_table(rows) {
	if (!rows || !rows.length)
		return `<em style="color:#aaa;font-size:11px;">No open SOs</em>`;

	const hdrs = ["Delivery Date", "Qty to Deliver", "Allocated", "Shortage", "Available After", "Order Status"]
		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");

	const trows = rows.map(r => {
		const sc = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
		return `<tr>
			<td style="padding:3px 8px;font-size:11px;">${r.delivery_date || ""}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.pending_qty}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
			<td style="padding:3px 8px;font-size:11px;${sc}">${r.shortage}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.available_after}</td>
			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.order_status)}</td>
		</tr>`;
	}).join("");

	return `<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table></div>`;
}

function parent_fifo_table(rows) {
	if (!rows || !rows.length)
		return `<em style="color:#aaa;font-size:11px;">No parent BOM batches</em>`;

	const hdrs = ["Priority Seq", "Priority Colour", "OP/CP", "Parent Item", "Level Before", "Batch Qty", "Child Req", "Allocated", "Shortage", "Available After", "Colour"]
		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");

	const trows = rows.map(r => {
		const sc = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
		return `<tr>
			<td style="padding:3px 8px;font-size:11px;">${r.priority_sequence === 999999 ? "—" : r.priority_sequence}</td>
			<td style="padding:3px 8px;font-size:11px;">${frappe.utils.escape_html(r.priority_colour || "")}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.op_cp || ""}</td>
			<td style="padding:3px 8px;font-size:11px;font-weight:600;">${frappe.utils.escape_html(r.parent_item)}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.level_before}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.batch_qty}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.child_req}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
			<td style="padding:3px 8px;font-size:11px;${sc}">${r.shortage}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.available_after}</td>
			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.order_status)}</td>
		</tr>`;
	}).join("");

	return `<div style="overflow-x:auto;"><table style="border-collapse:collapse;width:100%;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table></div>`;
}

function show_breakdown_dialog(d) {
	let html = "";

	// Header summary
	html += kv_table([
		["Item Code", `<b>${frappe.utils.escape_html(d.item_code)}</b> — ${frappe.utils.escape_html(d.item_name || "")}`],
		["SKU Type", d.sku_type],
		["Buffer Flag", d.buffer_flag],
		["Stock", d.stock],
		["Level (Stock)", `<b>${d.level}</b>`],
		["TOG", d.tog],
		["Colour", colour_badge(d.colour) || "<em>blank</em>"],
		["On Hand Colour", colour_badge(d.on_hand_colour) || "<em>blank</em>"],
	]);

	if (d.detail_type === "buffer") {
		// RBMTA — Colour and On Hand Colour are the exact same formula now
		html += section_title("Colour & On Hand Colour — same formula for RBMTA");
		const pct = (d.pct === null || d.pct === undefined) ? "N/A" : `${d.pct}%`;
		html += kv_table([
			["Total Demand (own qualified demand + BOM parent-cascaded demand)", d.total_demand],
			["Total (TOG + Total Demand)", d.total],
			["Level / Total", pct],
			["Bands", "0% → Black, ≤ 34% → Red, ≤ 67% → Yellow, ≤ 100% → Green, > 100% → White"],
		]);
	} else {
		// RBMTO — Colour: worst-shortage (else worst-no-shortage) FIFO walk.
		// Own SOs decide it whenever the item has any; parent batches are only
		// consulted as a fallback when there are no open SOs of its own at all.
		const usedOwnSo = (d.own_so_fifo || []).length > 0;
		html += section_title("Colour — Step 1: Own Open SOs (FIFO, sorted by Delivery Date)");
		html += so_fifo_table(d.own_so_fifo);
		if (usedOwnSo) {
			html += `<p style="font-size:12px;color:#888;">Own SOs exist, so this decides the result — Step 2 is not consulted.</p>`;
		}

		html += section_title("Colour — Step 2: Parent BOM FIFO (sorted by Priority Sequence ASC)");
		if (!usedOwnSo) {
			html += parent_fifo_table(d.parent_fifo);
		} else {
			html += `<p style="font-size:12px;color:#888;"><em>Not consulted — item has its own open SOs.</em></p>`;
		}

		html += section_title("Colour — Result");
		html += `<p style="font-size:13px;">Worst colour among shortage entries, else worst colour among covered entries (not blank just because covered): ${colour_badge(d.colour) || "<em>blank — nothing to check</em>"}</p>`;

		// On Hand Colour: ancestor-propagated priority
		html += section_title("On Hand Colour — Own Priority (FIFO through own SOs only)");
		html += `<p style="font-size:13px;">Own seed: ${colour_badge(d.own_priority_seed) || "<em>blank (no open SOs)</em>"}</p>`;

		html += section_title("On Hand Colour — Ancestor Propagation");
		const parentsList = (d.direct_parents || []).length
			? d.direct_parents.map(p => frappe.utils.escape_html(p)).join(", ")
			: "<em>none</em>";
		html += kv_table([
			["Direct parent(s)", parentsList],
			["Propagated from an ancestor?", d.propagated_from_ancestor
				? "Yes — some ancestor up the BOM chain (any depth, not just the direct parent) had a worse priority than this item's own"
				: "No — this item's own priority stands (or no ancestor had any priority)"],
		]);

		html += section_title("On Hand Colour — Result");
		html += `<p style="font-size:13px;">Final: ${colour_badge(d.on_hand_colour) || "<em>blank</em>"}</p>`;
	}

	frappe.msgprint({
		title: __("Colour Breakdown — {0}", [d.item_code]),
		message: `<div style="font-family:sans-serif;">${html}</div>`,
		wide: true,
	});
}
