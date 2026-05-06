// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

const COLOUR_STYLES = {
	Black: { bg: "#222", fg: "#fff" },
	Red: { bg: "#e74c3c", fg: "#fff" },
	Yellow: { bg: "#f1c40f", fg: "#333" },
	Green: { bg: "#27ae60", fg: "#fff" },
	White: { bg: "#e8e8e8", fg: "#333" },
};

frappe.query_reports["Open MR for Purchase"] = {
	filters: [],

	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "colour" && value && COLOUR_STYLES[value]) {
			const { bg, fg, border } = COLOUR_STYLES[value];
			return `<span style="
				background:${bg};
				color:${fg};
				padding:2px 10px;
				border-radius:4px;
				font-weight:bold;
				display:inline-block;
				${border ? `border:${border};` : ""}
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
		// 							material_request_type: "Purchase",
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
		// 				method: "prakash_steel.prakash_steel.report.open_mr_for_purchase.open_mr_for_purchase.get_item_breakdown",
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
	WHITE: { bg: "#ffffff", fg: "#333", border: "1px solid #aaa" },
};

function colour_badge(label) {
	const key = (label || "").toUpperCase();
	const s = SO_STATUS_STYLE[key] || COLOUR_STYLES[label];
	if (!s) return frappe.utils.escape_html(label || "");
	const borderStyle = s.border ? `border:${s.border};` : "";
	return `<span style="background:${s.bg};color:${s.fg};${borderStyle}padding:1px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(label)}</span>`;
}

function so_fifo_table(fifo_rows) {
	if (!fifo_rows || !fifo_rows.length) {
		return `<em style="color:#aaa;">No open SOs</em>`;
	}
	const hdrs = ["Delivery Date", "Qty to Deliver", "Allocated", "Shortage", "Order Status"]
		.map((h) => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");

	const trows = fifo_rows.map((r) => {
		const shortageStyle = r.shortage > 0
			? "color:#c0392b;font-weight:bold;"
			: "color:#27ae60;";
		return `<tr>
			<td style="padding:3px 8px;font-size:11px;">${r.delivery_date || ""}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.pending_qty}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
			<td style="padding:3px 8px;font-size:11px;${shortageStyle}">${r.shortage}</td>
			<td style="padding:3px 8px;font-size:11px;">${colour_badge(r.order_status)}</td>
		</tr>`;
	}).join("");

	return `<table style="border-collapse:collapse;width:100%;margin-top:4px;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table>`;
}

function show_breakdown_dialog(mr_name, rows) {
	const columns = [
		{ label: "Item Code", width: "150px" },
		{ label: "SKU Type", width: "90px" },
		{ label: "Buffer", width: "90px" },
		{ label: "Stock", width: "80px" },
		{ label: "Open PO", width: "80px" },
		{ label: "Prev MR Qty", width: "100px" },
		{ label: "Level (S+PO+P)", width: "110px" },
		{ label: "TOG", width: "80px" },
		{ label: "Qual. Demand", width: "110px" },
		{ label: "Colour", width: "90px" },
		{ label: "SO FIFO Detail", width: "360px" },
	];

	const header = columns
		.map((c) => `<th style="min-width:${c.width};padding:6px 8px;border-bottom:2px solid #ddd;text-align:left;">${c.label}</th>`)
		.join("");

	const body = rows.map((row) => {
		const bufferCell = row.buffer_flag === "Buffer"
			? `<span style="color:green;font-weight:bold;">Buffer</span>`
			: `<span style="color:#888;">Non-Buffer</span>`;

		const soDetail = row.buffer_flag === "Buffer"
			? `<em style="color:#aaa;font-size:11px;">N/A (Buffer)</em>`
			: so_fifo_table(row.so_fifo_detail);

		const cells = [
			`<b>${frappe.utils.escape_html(row.item_code)}</b><br>
			 <small style="color:#888;">${frappe.utils.escape_html(row.description || "")}</small>`,
			frappe.utils.escape_html(row.sku_type || ""),
			bufferCell,
			row.stock,
			row.open_po,
			row.previous_mr_qty,
			`<b>${row.level}</b>`,
			row.tog,
			row.qualified_demand,
			colour_badge(row.colour),
			soDetail,
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
