

frappe.query_reports["PO Recomendation for PSP"] = {
	filters: [
		{
			fieldname: "purchase",
			label: __("Purchase"),
			fieldtype: "Check",
			default: 0,
			width: "80",
		},
		{
			fieldname: "sell",
			label: __("Manufacture"),
			fieldtype: "Check",
			default: 0,
			width: "80",
		},
		{
			fieldname: "buffer_flag",
			label: __("Buffer Flag"),
			fieldtype: "Check",
			default: 0,
			width: "80",
		},
		{
			fieldname: "sku_type",
			label: __("SKU Type"),
			fieldtype: "MultiSelectList",
			width: "80",
			get_data: function (txt) {
				// This will be overridden in onload to access report filter values
				return [];
			},
		},
		{
			fieldname: "item_code",
			label: __("Item Code"),
			fieldtype: "Link",
			options: "Item",
			width: "80",
		},
		// {
		// 	fieldname: "from_date",
		// 	label: __("From Date"),
		// 	fieldtype: "Date",
		// 	width: "80",
		// },
		// {
		// 	fieldname: "to_date",
		// 	label: __("To Date"),
		// 	fieldtype: "Date",
		// 	width: "80",
		// },
	],

	onload: function (report) {
		// Store report reference for SKU type filter
		let report_ref = report;

		// Update SKU type filter's get_data to use report reference
		if (report.page.fields_dict.sku_type) {
			let original_get_data = report.page.fields_dict.sku_type.df.get_data;
			report.page.fields_dict.sku_type.df.get_data = function (txt) {
				// Get current filter values from report
				let filter_values = report_ref.get_filter_values ? report_ref.get_filter_values() : {};

				let purchase = filter_values.purchase || 0;
				let sell = filter_values.sell || 0;
				let buffer_flag = filter_values.buffer_flag || 0;

				// Determine which SKU types to show based on Purchase/Sell and Buffer Flag selection
				let sku_types = [];
				if (purchase) {
					if (buffer_flag) {
						// Purchase + Buffer: PTA, BOTA, TRMTA
						sku_types = ["PTA", "BOTA", "TRMTA"];
					} else {
						// Purchase + Non-Buffer: PTO, BOTO, TRMTO
						sku_types = ["PTO", "BOTO", "TRMTO"];
					}
				} else if (sell) {
					if (buffer_flag) {
						// Sell + Buffer: BBMTA, RBMTA
						sku_types = ["BBMTA", "RBMTA"];
					} else {
						// Sell + Non-Buffer: BBMTO, RBMTO
						sku_types = ["BBMTO", "RBMTO"];
					}
				} else {
					// No selection: return empty array
					return [];
				}

				let options = [];
				for (let sku of sku_types) {
					if (!txt || sku.toLowerCase().includes(txt.toLowerCase())) {
						options.push({
							value: sku,
							label: __(sku),
							description: "",
						});
					}
				}
				return options;
			};
		}

		// Make Purchase and Sell mutually exclusive
		report.page.fields_dict.purchase.$input.on("change", function () {
			if (report.page.fields_dict.purchase.get_value()) {
				report.page.fields_dict.sell.set_value(0);
			}
			// Refresh SKU type filter
			if (report.page.fields_dict.sku_type) {
				report.page.fields_dict.sku_type.refresh();
			}
		});

		report.page.fields_dict.sell.$input.on("change", function () {
			if (report.page.fields_dict.sell.get_value()) {
				report.page.fields_dict.purchase.set_value(0);
			}
			// Refresh SKU type filter
			if (report.page.fields_dict.sku_type) {
				report.page.fields_dict.sku_type.refresh();
			}
		});

		// Refresh SKU type filter when Buffer Flag changes
		report.page.fields_dict.buffer_flag.$input.on("change", function () {
			if (report.page.fields_dict.sku_type) {
				report.page.fields_dict.sku_type.refresh();
			}
		});
		function logCalculationBreakdowns() {
			setTimeout(function () {
				try {
					// Get report data
					let data = report.data || [];

					if (data && data.length > 0) {
						console.log("\n" + "=".repeat(100));
						console.log("PO RECOMMENDATION FOR PSP - CALCULATION BREAKDOWN");
						console.log("=".repeat(100) + "\n");

						// Track items we've already logged (to avoid duplicates from child rows)
						let logged_items = new Set();

						data.forEach(function (row, index) {
							if (row && row.item_code && !logged_items.has(row.item_code)) {
								logged_items.add(row.item_code);

								// Log the breakdown if available
								if (row.calculation_breakdown) {
									console.log(row.calculation_breakdown);
									console.log("-".repeat(100));
								}
							}
						});

						console.log("\n" + "=".repeat(100));
						console.log("END OF CALCULATION BREAKDOWN");
						console.log("=".repeat(100) + "\n");
					}
				} catch (e) {
					console.error("Error logging calculation breakdown:", e);
				}
			}, 2000); // Wait for data to load
		}

		// Log when report loads
		logCalculationBreakdowns();

		// Also log when report refreshes
		if (report.refresh) {
			let originalRefresh = report.refresh;
			report.refresh = function () {
				let result = originalRefresh.apply(this, arguments);
				setTimeout(logCalculationBreakdowns, 2000);
				return result;
			};
		}

		// ── On Hand Status Calculator button ─────────────────────────────

		// report.page.add_inner_button(__("On Hand Status Calculator"), function () {
		// 		const d = new frappe.ui.Dialog({
		// 			title: __("On Hand Status Calculator"),
		// 			fields: [
		// 				{
		// 					label: __("Item Code"),
		// 					fieldname: "item_code",
		// 					fieldtype: "Link",
		// 					options: "Item",
		// 					reqd: 1,
		// 				},
		// 			],
		// 			primary_action_label: __("Calculate"),
		// 			primary_action({ item_code }) {
		// 				if (!item_code) return;
		// 				d.disable_primary_action();
		// 				frappe.call({
		// 					method: "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.get_on_hand_status_breakdown",
		// 					args: { item_code },
		// 					callback(r) {
		// 						d.enable_primary_action();
		// 						if (!r.message) {
		// 							frappe.msgprint(__("No data returned."));
		// 							return;
		// 						}
		// 						show_on_hand_status_dialog(r.message);
		// 					},
		// 					error() { d.enable_primary_action(); },
		// 				});
		// 			},
		// 		});
		// 		d.show();
		// 	});
		// ── Priority Breakdown button ──────────────────────────────────────
		// report.page.add_inner_button(__("Priority Breakdown"), function () {
		// 	const d = new frappe.ui.Dialog({
		// 		title: __("Priority Breakdown"),
		// 		fields: [
		// 			{
		// 				label: __("Item Code"),
		// 				fieldname: "item_code",
		// 				fieldtype: "Link",
		// 				options: "Item",
		// 				reqd: 1,
		// 			},
		// 		],
		// 		primary_action_label: __("Show"),
		// 		primary_action({ item_code }) {
		// 			if (!item_code) return;
		// 			d.disable_primary_action();
		// 			frappe.call({
		// 				method: "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.get_priority_breakdown",
		// 				args: { item_code },
		// 				callback(r) {
		// 					d.enable_primary_action();
		// 					if (!r.message) {
		// 						frappe.msgprint(__("No data returned."));
		// 						return;
		// 					}
		// 					show_priority_breakdown_dialog(r.message);
		// 				},
		// 				error() { d.enable_primary_action(); },
		// 			});
		// 		},
		// 	});
		// 	d.show();
		// });
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// Background colors for On Hand Colour status
		if (column.fieldname === "on_hand_colour" && data && data.on_hand_colour) {
			let colour = data.on_hand_colour;
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
					${colour}
				</div>`;
			}
		}

		// Background colors for Priority (non-buffer FIFO colour)
		if (column.fieldname === "priority" && data && data.priority) {
			let colour = data.priority.toLowerCase();
			let bg = "";
			let textColor = "#000000";

			if (colour === "black") {
				bg = "#000000";
				textColor = "#FFFFFF";
			} else if (colour === "red") {
				bg = "#FF0000";
				textColor = "#FFFFFF";
			} else if (colour === "yellow") {
				bg = "#FFFF00";
				textColor = "#000000";
			} else if (colour === "green") {
				bg = "#00FF00";
				textColor = "#000000";
			} else if (colour === "white") {
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
					${data.priority}
				</div>`;
			}
		}

		// Background colors for Child full-kit status
		if (column.fieldname === "child_full_kit_status" && data && data.child_full_kit_status) {
			let fullkitRaw = data.child_full_kit_status || "";
			let fullkit = fullkitRaw.toLowerCase();

			if (!fullkit) {
				return value;
			}

			let bg = "";
			let textColor = "#000000";
			let fullkitText = fullkitRaw;

			if (fullkit === "full-kit") {
				bg = "#4dff88"; // Green
				textColor = "#000000";
			} else if (fullkit === "partial") {
				bg = "#ffff99"; // Yellow
				textColor = "#000000";
			} else if (fullkit === "pending") {
				bg = "#ff9999"; // Red
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
					${fullkitText}
				</div>`;
			}
		}

		// Background colors for Child WIP/Open PO full-kit status
		if (column.fieldname === "child_wip_open_po_full_kit_status" && data && data.child_wip_open_po_full_kit_status) {
			let fullkitRaw = data.child_wip_open_po_full_kit_status || "";
			let fullkit = fullkitRaw.toLowerCase();

			if (!fullkit) {
				return value;
			}

			let bg = "";
			let textColor = "#000000";
			let fullkitText = fullkitRaw;

			if (fullkit === "full-kit") {
				bg = "#4dff88"; // Green
				textColor = "#000000";
			} else if (fullkit === "partial") {
				bg = "#ffff99"; // Yellow
				textColor = "#000000";
			} else if (fullkit === "pending") {
				bg = "#ff9999"; // Red
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
					${fullkitText}
				</div>`;
			}
		}

		return value;
	},
};
// ---------------------------------------------------------------------------
// Priority Breakdown dialog helpers
// ---------------------------------------------------------------------------

const _PRIORITY_STYLES = {
	black: { bg: "#000000", fg: "#ffffff" },
	red: { bg: "#FF0000", fg: "#ffffff" },
	yellow: { bg: "#FFFF00", fg: "#000000" },
	green: { bg: "#00FF00", fg: "#000000" },
	white: { bg: "#FFFFFF", fg: "#000000" },
};

function _priority_badge(val) {
	if (!val) return '<span style="color:#aaa;">—</span>';
	const s = _PRIORITY_STYLES[(val || "").toLowerCase()];
	if (!s) return frappe.utils.escape_html(val);
	return `<span style="background:${s.bg};color:${s.fg};padding:2px 10px;border-radius:4px;font-weight:bold;font-size:12px;display:inline-block;">${frappe.utils.escape_html(val)}</span>`;
}

function _so_status_badge(val) {
	if (!val) return '<span style="color:#aaa;">—</span>';
	const s = _PRIORITY_STYLES[(val || "").toLowerCase()];
	if (!s) return frappe.utils.escape_html(val);
	return `<span style="background:${s.bg};color:${s.fg};padding:1px 8px;border-radius:3px;font-weight:bold;font-size:11px;">${frappe.utils.escape_html(val)}</span>`;
}

function _fifo_table(rows) {
	if (!rows || !rows.length)
		return `<em style="color:#aaa;">No open Sales Orders</em>`;
	const hdrs = ["Delivery Date", "Qty to Deliver", "Allocated", "Shortage", "Order Status"]
		.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
		.join("");
	const trows = rows.map(r => {
		const ss = r.shortage > 0 ? "color:#c0392b;font-weight:bold;" : "color:#27ae60;";
		return `<tr>
			<td style="padding:3px 8px;font-size:11px;">${r.delivery_date || ""}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.pending_qty}</td>
			<td style="padding:3px 8px;font-size:11px;">${r.allocated}</td>
			<td style="padding:3px 8px;font-size:11px;${ss}">${r.shortage}</td>
			<td style="padding:3px 8px;font-size:11px;">${_so_status_badge(r.order_status)}</td>
		</tr>`;
	}).join("");
	return `<table style="border-collapse:collapse;width:100%;margin-top:4px;background:#fafafa;">
		<thead><tr style="background:#eee;">${hdrs}</tr></thead>
		<tbody>${trows}</tbody>
	</table>`;
}

function show_on_hand_status_dialog(d) {
	const e = v => frappe.utils.escape_html(String(v ?? "—"));
	const n = v => (v === null || v === undefined) ? "—" : Number(v).toLocaleString();

	const colour_badge = (colour) => {
		if (!colour) return "—";
		const map = { BLACK: ["#000", "#fff"], RED: ["#FF0000", "#fff"], YELLOW: ["#FFFF00", "#000"], GREEN: ["#00FF00", "#000"], WHITE: ["#fff", "#000"] };
		const [bg, fg] = map[colour] || ["#eee", "#000"];
		return `<span style="background:${bg};color:${fg};padding:2px 12px;border-radius:4px;font-weight:bold;font-size:13px;border:1px solid #ccc;">${colour}</span>`;
	};

	// ── Section 1: Item info ──────────────────────────────────────────────
	const info_html = `
		<table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
			<tr><td style="padding:4px 10px;color:#888;font-size:12px;width:180px;">Item Code</td><td style="padding:4px 10px;font-size:13px;font-weight:bold;">${e(d.item_code)} — ${e(d.item_name)}</td></tr>
			<tr><td style="padding:4px 10px;color:#888;font-size:12px;">Buffer Flag</td><td style="padding:4px 10px;font-size:12px;">${e(d.buffer_flag)} &nbsp;|&nbsp; Type: <b>${e(d.item_type)}</b></td></tr>
		</table>`;

	if (d.buffer_flag !== "Buffer") {
		frappe.msgprint({ title: __("On Hand Status Calculator"), message: info_html + `<p style="color:#888;">On Hand Status is only calculated for <b>Buffer</b> items.</p>`, wide: true });
		return;
	}

	// ── Section 2: Qualified Demand ───────────────────────────────────────
	const threshold_note = d.threshold_triggered
		? `<span style="color:#c0392b;font-size:11px;">⚠ Raw QD (${n(d.raw_qualified)}) &lt; Threshold (${n(d.spike_threshold_qty)}) → set to 0</span>`
		: `<span style="color:#27ae60;font-size:11px;">✓ Raw QD (${n(d.raw_qualified)}) ≥ Threshold (${n(d.spike_threshold_qty)})</span>`;

	const spike_rows_html = d.spike_sos && d.spike_sos.length
		? d.spike_sos.map(s => `<tr><td style="padding:2px 8px;font-size:11px;">${e(s.so_name)}</td><td style="padding:2px 8px;font-size:11px;">${e(s.delivery_date)}</td><td style="padding:2px 8px;font-size:11px;">${n(s.qty)}</td></tr>`).join("")
		: `<tr><td colspan="3" style="padding:4px 8px;font-size:11px;color:#aaa;">No spike SOs</td></tr>`;

	const qd_html = `
		<div style="background:#f9f9f9;border:1px solid #e0e0e0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
			<h4 style="margin:0 0 8px;font-size:13px;color:#333;">① Qualified Demand</h4>
			<table style="width:100%;border-collapse:collapse;">
				<tr><td style="padding:3px 8px;color:#666;font-size:12px;width:220px;">Till Today (SO ≤ today)</td><td style="padding:3px 8px;font-size:12px;font-weight:bold;">${n(d.till_today)}</td></tr>
				<tr><td style="padding:3px 8px;color:#666;font-size:12px;">Spike (next ${n(d.demand_horizon)} days)</td><td style="padding:3px 8px;font-size:12px;font-weight:bold;">${n(d.spike)}</td></tr>
				<tr><td style="padding:3px 8px;color:#666;font-size:12px;">Raw QD (Till Today + Spike)</td><td style="padding:3px 8px;font-size:12px;">${n(d.raw_qualified)}</td></tr>
				<tr><td style="padding:3px 8px;color:#666;font-size:12px;">Threshold (TOG ${n(d.tog)} × ${n(d.spike_threshold_pct)}%)</td><td style="padding:3px 8px;font-size:12px;">${n(d.spike_threshold_qty)}</td></tr>
				<tr><td style="padding:3px 8px;color:#666;font-size:12px;">Threshold check</td><td style="padding:3px 8px;font-size:12px;">${threshold_note}</td></tr>
				<tr style="background:#eef;"><td style="padding:4px 8px;font-size:13px;font-weight:bold;color:#333;">Qualified Demand</td><td style="padding:4px 8px;font-size:14px;font-weight:bold;color:#1a1aff;">${n(d.qualified_demand)}</td></tr>
			</table>
			${d.spike_sos && d.spike_sos.length ? `
			<details style="margin-top:8px;"><summary style="font-size:11px;color:#555;cursor:pointer;">Spike SO Details</summary>
			<table style="border-collapse:collapse;width:100%;margin-top:4px;">
				<thead><tr style="background:#eee;"><th style="padding:2px 8px;font-size:11px;text-align:left;">SO</th><th style="padding:2px 8px;font-size:11px;text-align:left;">Delivery Date</th><th style="padding:2px 8px;font-size:11px;text-align:left;">Qty</th></tr></thead>
				<tbody>${spike_rows_html}</tbody>
			</table></details>` : ""}
		</div>`;

	// ── Section 3: Parent Demand ──────────────────────────────────────────
	let parent_html = "";
	if (d.parent_details && d.parent_details.length) {
		const p_rows = d.parent_details.map(p => `
			<tr style="border-bottom:1px solid #eee;">
				<td style="padding:5px 8px;font-size:12px;font-weight:bold;">${e(p.parent_item)}</td>
				<td style="padding:5px 8px;font-size:11px;color:#666;">${e(p.buffer_flag)}</td>
				<td style="padding:5px 8px;font-size:11px;">${e(p.demand_label)}</td>
				<td style="padding:5px 8px;font-size:11px;text-align:right;">${n(p.base_order_rec)}</td>
				<td style="padding:5px 8px;font-size:11px;text-align:right;">${p.moq > 0 ? `MOQ=${n(p.moq)}` : p.batch_size > 0 ? `Batch=${n(p.batch_size)}` : "—"}</td>
				<td style="padding:5px 8px;font-size:11px;font-weight:bold;text-align:right;">${n(p.net_order_rec)}</td>
				<td style="padding:5px 8px;font-size:11px;text-align:right;">${n(p.child_qty)} / ${n(p.bom_qty)} = ${n(p.ratio)}</td>
				<td style="padding:5px 8px;font-size:12px;font-weight:bold;color:#c0392b;text-align:right;">${n(p.demand_contributed)}</td>
			</tr>`).join("");

		parent_html = `
			<div style="background:#f9f9f9;border:1px solid #e0e0e0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
				<h4 style="margin:0 0 8px;font-size:13px;color:#333;">② Parent Demand (via BOM)</h4>
				<div style="overflow-x:auto;">
				<table style="border-collapse:collapse;width:100%;min-width:700px;">
					<thead><tr style="background:#eee;">
						<th style="padding:4px 8px;font-size:11px;text-align:left;">Parent Item</th>
						<th style="padding:4px 8px;font-size:11px;text-align:left;">Type</th>
						<th style="padding:4px 8px;font-size:11px;text-align:left;">Order Rec Formula</th>
						<th style="padding:4px 8px;font-size:11px;text-align:right;">Base Rec</th>
						<th style="padding:4px 8px;font-size:11px;text-align:right;">MOQ/Batch</th>
						<th style="padding:4px 8px;font-size:11px;text-align:right;">Net Rec</th>
						<th style="padding:4px 8px;font-size:11px;text-align:right;">BOM Ratio</th>
						<th style="padding:4px 8px;font-size:11px;text-align:right;">Demand →</th>
					</tr></thead>
					<tbody>${p_rows}</tbody>
					<tfoot><tr style="background:#eef;">
						<td colspan="7" style="padding:4px 8px;font-size:13px;font-weight:bold;text-align:right;">Total Parent Demand</td>
						<td style="padding:4px 8px;font-size:14px;font-weight:bold;color:#c0392b;text-align:right;">${n(d.total_parent_demand)}</td>
					</tr></tfoot>
				</table></div>
			</div>`;
	} else {
		parent_html = `
			<div style="background:#f9f9f9;border:1px solid #e0e0e0;border-radius:6px;padding:10px 16px;margin-bottom:12px;">
				<h4 style="margin:0 0 4px;font-size:13px;color:#333;">② Parent Demand</h4>
				<p style="color:#aaa;font-size:12px;margin:0;">No active BOMs use this item — parent demand = 0</p>
			</div>`;
	}

	// ── Section 4: Final calculation ──────────────────────────────────────
	const final_html = `
		<div style="background:#f0f8ff;border:2px solid #aad4f5;border-radius:6px;padding:14px 16px;">
			<h4 style="margin:0 0 10px;font-size:13px;color:#333;">③ On Hand Status Calculation</h4>
			<table style="width:100%;border-collapse:collapse;">
				<tr><td style="padding:3px 8px;color:#555;font-size:12px;width:260px;">TOG</td><td style="padding:3px 8px;font-size:13px;font-weight:bold;">${n(d.tog)}</td></tr>
				<tr><td style="padding:3px 8px;color:#555;font-size:12px;">Qualified Demand</td><td style="padding:3px 8px;font-size:12px;">${n(d.qualified_demand)}</td></tr>
				<tr><td style="padding:3px 8px;color:#555;font-size:12px;">Total Parent Demand</td><td style="padding:3px 8px;font-size:12px;">${n(d.total_parent_demand)}</td></tr>
				<tr style="border-top:1px solid #ccc;"><td style="padding:4px 8px;color:#555;font-size:12px;">Denominator (TOG + QD + Parent)</td><td style="padding:4px 8px;font-size:13px;font-weight:bold;">${n(d.denominator)}</td></tr>
				<tr><td style="padding:3px 8px;color:#555;font-size:12px;">On Hand Stock</td><td style="padding:3px 8px;font-size:13px;font-weight:bold;">${n(d.on_hand_stock)}</td></tr>
			</table>
			<div style="margin-top:10px;padding:8px 12px;background:#fff;border-radius:4px;font-size:13px;">
				<code style="color:#333;">On Hand Status = (${n(d.on_hand_stock)} / ${n(d.denominator)}) × 100 = <b>${e(d.on_hand_status)}</b></code>
			</div>
			<div style="margin-top:10px;display:flex;align-items:center;gap:12px;">
				<span style="font-size:13px;font-weight:bold;color:#333;">Colour:</span>
				${colour_badge(d.on_hand_colour)}
			</div>
		</div>`;

	frappe.msgprint({
		title: __("On Hand Status Calculator — {0}", [d.item_code]),
		message: info_html + qd_html + parent_html + final_html,
		wide: true,
	});
}

function show_priority_breakdown_dialog(d) {
	const e = s => frappe.utils.escape_html(String(s ?? ""));

	// ── Section 1: Item info ─────────────────────────────────────────────
	const info_rows = [
		["Item Code", `<b>${e(d.item_code)}</b>`],
		["SKU Type", e(d.sku_type)],
		["Level Formula", e(d.level_formula)],
		["Level", `<b>${d.level}</b>`],
	].map(([k, v]) =>
		`<tr><td style="padding:4px 10px;font-size:12px;color:#888;white-space:nowrap;">${k}</td>
		     <td style="padding:4px 10px;font-size:12px;">${v}</td></tr>`
	).join("");

	// ── Section 2: FIFO SO table ─────────────────────────────────────────
	const fifo_html = _fifo_table(d.fifo_detail);

	// ── Section 3: Own priority ──────────────────────────────────────────
	const own_html = d.own_priority
		? _priority_badge(d.own_priority)
		: `<span style="color:#aaa;">— (no open SOs)</span>`;

	// ── Section 4: Parent items ──────────────────────────────────────────
	let parents_html = "";
	if (d.parent_details && d.parent_details.length) {
		const p_hdrs = ["Parent Item", "SKU Type", "Stock", "WIP", "Open PO", "Level", "Own Priority"]
			.map(h => `<th style="padding:4px 8px;border-bottom:1px solid #ccc;font-size:11px;text-align:left;">${h}</th>`)
			.join("");
		const p_rows = d.parent_details.map(p => `<tr>
			<td style="padding:3px 8px;font-size:11px;"><b>${e(p.item_code)}</b></td>
			<td style="padding:3px 8px;font-size:11px;">${e(p.sku_type)}</td>
			<td style="padding:3px 8px;font-size:11px;">${p.stock}</td>
			<td style="padding:3px 8px;font-size:11px;">${p.wip}</td>
			<td style="padding:3px 8px;font-size:11px;">${p.open_po}</td>
			<td style="padding:3px 8px;font-size:11px;"><b>${p.level}</b></td>
			<td style="padding:3px 8px;font-size:11px;">${_priority_badge(p.priority)}</td>
		</tr>`).join("");
		parents_html = `
			<h4 style="margin:16px 0 6px;font-size:13px;color:#555;">BOM Parents (in this report)</h4>
			<table style="border-collapse:collapse;width:100%;background:#fafafa;">
				<thead><tr style="background:#eee;">${p_hdrs}</tr></thead>
				<tbody>${p_rows}</tbody>
			</table>
			<p style="font-size:11px;color:#888;margin-top:4px;">
				Final priority = worst colour among all parents' own priorities.
			</p>`;
	} else {
		parents_html = `<p style="color:#888;font-size:12px;margin-top:12px;">No BOM parents found — item is a root item.</p>`;
	}

	// ── Final priority ───────────────────────────────────────────────────
	const final_html = `
		<div style="margin-top:16px;padding:10px 14px;background:#f0f8ff;border-radius:6px;display:flex;align-items:center;gap:12px;">
			<span style="font-size:13px;font-weight:bold;color:#333;">Final Priority:</span>
			${_priority_badge(d.final_priority) || '<span style="color:#aaa;">— (no demand)</span>'}
			${d.parent_details && d.parent_details.length
			? `<span style="font-size:11px;color:#888;">(worst of parent priorities)</span>`
			: `<span style="font-size:11px;color:#888;">(own FIFO priority — no parents)</span>`}
		</div>`;

	const html = `
		<table style="margin-bottom:12px;">${info_rows}</table>
		<h4 style="margin:0 0 4px;font-size:13px;color:#555;">FIFO Sales Order Allocation</h4>
		${fifo_html}
		<h4 style="margin:14px 0 4px;font-size:13px;color:#555;">Own Priority (before propagation)</h4>
		<div style="padding:4px 0;">${own_html}</div>
		${parents_html}
		${final_html}`;

	frappe.msgprint({
		title: __("Priority Breakdown — {0}", [d.item_code]),
		message: html,
		wide: true,
	});
}
