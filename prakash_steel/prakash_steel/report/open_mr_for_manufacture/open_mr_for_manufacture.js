// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const COLOUR_STYLES = {
	Black: { bg: "#222", fg: "#fff" },
	Red: { bg: "#e74c3c", fg: "#fff" },
	Yellow: { bg: "#f1c40f", fg: "#333" },
	Green: { bg: "#27ae60", fg: "#fff" },
	White: { bg: "#f0f0f0", fg: "#333" },
};

frappe.query_reports["Open MR for Manufacture"] = {
	filters: [],

	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "colour" && value && COLOUR_STYLES[value]) {
			const { bg, fg } = COLOUR_STYLES[value];
			return `<span style="
				background:${bg};
				color:${fg};
				padding:2px 10px;
				border-radius:4px;
				font-weight:bold;
				display:inline-block;
			">${value}</span>`;
		}
		return default_formatter(value, row, column, data);
	},

	onload(report) {
		// report.page.add_inner_button(__("Debug Item Breakdown"), () => {
		// 	const d = new frappe.ui.Dialog({
		// 		title: __("Item Breakdown Debug"),
		// 		fields: [
		// 			{
		// 				label: __("Material Request"),
		// 				fieldname: "mr_name",
		// 				fieldtype: "Link",
		// 				options: "Material Request",
		// 				reqd: 1,
		// 				get_query() {
		// 					return {
		// 						filters: {
		// 							material_request_type: "Manufacture",
		// 							docstatus: 1,
		// 						},
		// 					};
		// 				},
		// 			},
		// 		],
		// 		primary_action_label: __("Show Breakdown"),
		// 		primary_action({ mr_name }) {
		// 			if (!mr_name) return;
		// 			d.disable_primary_action();

		// 			frappe.call({
		// 				method: "prakash_steel.prakash_steel.report.open_mr_for_manufacture.open_mr_for_manufacture.get_item_breakdown",
		// 				args: { mr_name },
		// 				callback(r) {
		// 					d.enable_primary_action();
		// 					if (!r.message || !r.message.length) {
		// 						frappe.msgprint(__("No items found for this MR."));
		// 						return;
		// 					}
		// 					show_breakdown_dialog(mr_name, r.message);
		// 				},
		// 				error() {
		// 					d.enable_primary_action();
		// 				},
		// 			});
		// 		},
		// 	});
		// 	d.show();
		// });
	},
};

// ---------------------------------------------------------------------------
// Debug breakdown dialog
// ---------------------------------------------------------------------------

const SO_STATUS_STYLE = {
	BLACK: { bg: "#222", fg: "#fff" },
	RED: { bg: "#e74c3c", fg: "#fff" },
	YELLOW: { bg: "#f1c40f", fg: "#333" },
	GREEN: { bg: "#27ae60", fg: "#fff" },
	WHITE: { bg: "#f0f0f0", fg: "#333" },
};

function colour_badge(label) {
	const key = (label || "").toUpperCase();
	const s = SO_STATUS_STYLE[key] || COLOUR_STYLES[label];
	if (!s) return frappe.utils.escape_html(label || "");
	return `<span style="background:${s.bg};color:${s.fg};padding:1px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(label)}</span>`;
}

function own_so_table(rows) {
	if (!rows || !rows.length) {
		return `<em style="color:#aaa;font-size:11px;">No own SOs</em>`;
	}
	const hdrs = ["Pending Qty", "Allocated", "Shortage", "Colour"]
		.map((h) => `<th style="padding:3px 6px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");
	const trows = rows.map((r) => {
		const shortageStyle = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
		return `<tr>
			<td style="padding:2px 6px;font-size:11px;">${r.pending_qty}</td>
			<td style="padding:2px 6px;font-size:11px;">${r.allocated}</td>
			<td style="padding:2px 6px;font-size:11px;${shortageStyle}">${r.shortage}</td>
			<td style="padding:2px 6px;font-size:11px;">${colour_badge(r.colour)}</td>
		</tr>`;
	}).join("");
	return `<table style="border-collapse:collapse;width:100%;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table>`;
}

function parent_fifo_table(rows) {
	if (!rows || !rows.length) {
		return `<em style="color:#aaa;font-size:11px;">No parent batches</em>`;
	}
	const hdrs = ["Parent Item", "Parent SO Qty", "Child Req", "Allocated", "Shortage", "Colour", "Priority"]
		.map((h) => `<th style="padding:3px 6px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");
	const trows = rows.map((r) => {
		const shortageStyle = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
		return `<tr>
			<td style="padding:2px 6px;font-size:11px;">${frappe.utils.escape_html(r.parent_item || "")}</td>
			<td style="padding:2px 6px;font-size:11px;">${r.parent_so_pending ?? r.child_req}</td>
			<td style="padding:2px 6px;font-size:11px;">${r.child_req}</td>
			<td style="padding:2px 6px;font-size:11px;">${r.allocated}</td>
			<td style="padding:2px 6px;font-size:11px;${shortageStyle}">${r.shortage}</td>
			<td style="padding:2px 6px;font-size:11px;">${colour_badge(r.colour)}</td>
			<td style="padding:2px 6px;font-size:11px;">${frappe.utils.escape_html(r.priority_colour || "")}</td>
		</tr>`;
	}).join("");
	return `<table style="border-collapse:collapse;width:100%;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table>`;
}

function debug_bom_table(bom_parents) {
	if (!bom_parents || !bom_parents.length) {
		return `<em style="color:#c0392b;font-size:11px;">No parent BOM found (BOM not default/active/submitted?)</em>`;
	}
	const rows = bom_parents.map((p) => {
		const soStyle = p.open_so_count > 0 ? "color:#27ae60;font-weight:bold;" : "color:#c0392b;font-weight:bold;";
		return `<tr>
			<td style="padding:2px 6px;font-size:11px;">${frappe.utils.escape_html(p.parent_item)}</td>
			<td style="padding:2px 6px;font-size:11px;">${p.bom_qty} / ${p.bom_quantity}</td>
			<td style="padding:2px 6px;font-size:11px;${soStyle}">${p.open_so_count} open SO(s)</td>
		</tr>`;
	}).join("");
	return `<table style="border-collapse:collapse;background:#fffbe6;">
		<thead><tr style="background:#fef3c7;">
			<th style="padding:3px 6px;font-size:11px;text-align:left;">Parent Item</th>
			<th style="padding:3px 6px;font-size:11px;text-align:left;">BOM Qty / BOM Qty (parent)</th>
			<th style="padding:3px 6px;font-size:11px;text-align:left;">Open SOs</th>
		</tr></thead>
		<tbody>${rows}</tbody>
	</table>`;
}

function non_buffer_detail(own_so_rows, parent_rows, debug_parent_bom) {
	return `
		<div style="margin-bottom:6px;">
			<b style="font-size:11px;color:#555;">BOM Parents</b>
			${debug_bom_table(debug_parent_bom)}
		</div>
		<div style="margin-bottom:6px;">
			<b style="font-size:11px;color:#555;">Own SOs</b>
			${own_so_table(own_so_rows)}
		</div>
		<div>
			<b style="font-size:11px;color:#555;">Parent SO FIFO</b>
			${parent_fifo_table(parent_rows)}
		</div>`;
}

function show_breakdown_dialog(mr_name, rows) {
	const columns = [
		{ label: "Item Code", width: "150px" },
		{ label: "SKU Type", width: "90px" },
		{ label: "Buffer", width: "90px" },
		{ label: "Stock", width: "80px" },
		{ label: "WIP", width: "60px" },
		{ label: "Prev MR Qty", width: "100px" },
		{ label: "Level (S+W+P)", width: "110px" },
		{ label: "TOG", width: "80px" },
		{ label: "Qual. Demand", width: "110px" },
		{ label: "Colour", width: "90px" },
		{ label: "FIFO Detail", width: "400px" },
	];

	const header = columns
		.map((c) => `<th style="min-width:${c.width};padding:6px 8px;border-bottom:2px solid #ddd;text-align:left;">${c.label}</th>`)
		.join("");

	const body = rows.map((row) => {
		const bufferCell = row.buffer_flag === "Buffer"
			? `<span style="color:green;font-weight:bold;">Buffer</span>`
			: `<span style="color:#888;">Non-Buffer</span>`;

		const fifoDetail = row.buffer_flag === "Buffer"
			? `<em style="color:#aaa;font-size:11px;">N/A (Buffer)</em>`
			: non_buffer_detail(row.own_so_detail, row.parent_fifo_detail, row.debug_parent_bom);

		const cells = [
			`<b>${frappe.utils.escape_html(row.item_code)}</b><br>
			 <small style="color:#888;">${frappe.utils.escape_html(row.description || "")}</small>`,
			frappe.utils.escape_html(row.sku_type || ""),
			bufferCell,
			row.stock,
			row.wip,
			row.previous_mr_qty,
			`<b>${row.level}</b>`,
			row.tog,
			row.qualified_demand,
			colour_badge(row.colour),
			fifoDetail,
		].map((v) => `<td style="padding:5px 8px;border-bottom:1px solid #eee;vertical-align:top;">${v ?? ""}</td>`).join("");

		return `<tr>${cells}</tr>`;
	}).join("");

	const html = `
		<p style="color:#888;margin-bottom:8px;">MR: <b>${frappe.utils.escape_html(mr_name)}</b></p>
		<div style="overflow-x:auto;">
			<table style="width:100%;border-collapse:collapse;font-size:13px;">
				<thead><tr style="background:#f5f5f5;">${header}</tr></thead>
				<tbody>${body}</tbody>
			</table>
		</div>`;

	frappe.msgprint({
		title: __("Item Breakdown - {0}", [mr_name]),
		message: html,
		wide: true,
	});
}
