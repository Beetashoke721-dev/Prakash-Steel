

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

		report.page.add_inner_button(__("On Hand Status Calculator"), function () {
			const d = new frappe.ui.Dialog({
				title: __("On Hand Status Calculator"),
				fields: [
					{
						label: __("Item Code"),
						fieldname: "item_code",
						fieldtype: "Link",
						options: "Item",
						reqd: 1,
					},
				],
				primary_action_label: __("Calculate"),
				primary_action({ item_code }) {
					if (!item_code) return;
					d.disable_primary_action();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.get_on_hand_status_breakdown",
						args: { item_code },
						callback(r) {
							d.enable_primary_action();
							if (!r.message) {
								frappe.msgprint(__("No data returned."));
								return;
							}
							show_on_hand_status_dialog(r.message);
						},
						error() { d.enable_primary_action(); },
					});
				},
			});
			d.show();
		});
		// ── Child Requirement Debugger button ─────────────────────────────
		report.page.add_inner_button(__("Child Requirement Debugger"), function () {
			const d = new frappe.ui.Dialog({
				title: __("Child Requirement Debugger"),
				fields: [
					{
						label: __("Parent Item Code"),
						fieldname: "item_code",
						fieldtype: "Link",
						options: "Item",
						reqd: 1,
					},
				],
				primary_action_label: __("Show Breakdown"),
				primary_action({ item_code }) {
					if (!item_code) return;
					d.disable_primary_action();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.get_child_requirement_breakdown",
						args: { item_code },
						callback(r) {
							d.enable_primary_action();
							if (!r.message) {
								frappe.msgprint(__("No data returned."));
								return;
							}
							show_child_requirement_dialog(r.message);
						},
						error() { d.enable_primary_action(); },
					});
				},
			});
			d.show();
		});

		// ── Production Qty Debugger button ────────────────────────────────
		report.page.add_inner_button(__("Production Qty Debugger"), function () {
			const dlg = new frappe.ui.Dialog({
				title: __("Production Qty Debugger"),
				fields: [
					{
						label: __("Item Code"),
						fieldname: "item_code",
						fieldtype: "Link",
						options: "Item",
						reqd: 1,
					},
				],
				primary_action_label: __("Show Breakdown"),
				primary_action({ item_code }) {
					if (!item_code) return;
					dlg.disable_primary_action();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.po_recomendation_for_psp.po_recomendation_for_psp.get_child_requirement_breakdown",
						args: { item_code },
						callback(r) {
							dlg.enable_primary_action();
							if (!r.message) { frappe.msgprint(__("No data returned.")); return; }
							const data = r.message;
							if (data.no_bom || !data.child_items || !data.child_items.length) {
								frappe.msgprint(__("No BOM or child items found for {0}", [item_code]));
								return;
							}
							// Build a row object for each child (same shape show_prod_qty_inline_dialog expects)
							// Using total stock (FIFO not applied here — for exact FIFO see the report row)
							data.child_items.forEach(c => {
								const or_val      = data.or_with_moq_batch_size || 0;
								const bom_qty_c   = c.bom_qty || 0;
								const bom_qty_of  = c.bom_quantity || 1;
								const pfcf        = bom_qty_c > 0 ? (bom_qty_of / bom_qty_c) : 0;
								const child_req   = c.child_requirement || 0;
								const c_stock     = c.child_stock || 0;
								const c_wip_po    = c.child_wip_open_po || 0;
								const alloc_stock = Math.min(child_req, c_stock);
								const stock_short = Math.max(0, child_req - alloc_stock);
								const alloc_wip   = Math.min(stock_short, c_wip_po);
								const wip_short   = Math.max(0, stock_short - alloc_wip);
								const prod_stock  = or_val > 0 ? Math.min(Math.ceil(alloc_stock * pfcf), Math.ceil(or_val)) : 0;
								const prod_wip    = or_val > 0 ? Math.min(Math.ceil((alloc_stock + alloc_wip) * pfcf), Math.ceil(or_val)) : 0;
								const kit_stock   = or_val === 0 ? null : stock_short === 0 ? "Full-kit" : alloc_stock === 0 ? "Pending" : "Partial";
								const kit_wip     = or_val === 0 ? null : wip_short  === 0 ? "Full-kit" : alloc_wip   === 0 ? "Pending" : "Partial";

								show_prod_qty_inline_dialog({
									item_code:    data.item_code,
									item_name:    data.item_name,
									child_item_code:  c.child_item_code,
									on_hand_status:   "",
									or_with_moq_batch_size: or_val,
									child_requirement:  child_req,
									child_stock:        c_stock,
									child_stock_soft_allocation_qty:    alloc_stock,
									child_stock_shortage:               stock_short,
									child_wip_open_po:                  c_wip_po,
									child_wip_open_po_soft_allocation_qty: alloc_wip,
									child_wip_open_po_shortage:         wip_short,
									child_bom_qty:      bom_qty_c,
									child_bom_quantity: bom_qty_of,
									production_qty_based_on_child_stock:             prod_stock,
									production_qty_based_on_child_stock_wip_open_po: prod_wip,
									child_full_kit_status:              kit_stock,
									child_wip_open_po_full_kit_status:  kit_wip,
								});
							});
						},
						error() { dlg.enable_primary_action(); },
					});
				},
			});
			dlg.show();
		});

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

function show_prod_qty_inline_dialog(r) {
	const e  = v => frappe.utils.escape_html(String(v ?? "—"));
	const n  = v => (v === null || v === undefined || v === "") ? "—" : Number(v).toLocaleString();
	const nf = v => (v === null || v === undefined || v === "") ? 0  : Number(v);

	const or          = nf(r.or_with_moq_batch_size);
	const bom_qty     = nf(r.child_bom_qty);          // child qty needed per BOM run
	const bom_qty_of  = nf(r.child_bom_quantity) || 1; // how many parent units BOM produces
	const ratio       = bom_qty_of > 0 ? (bom_qty / bom_qty_of) : 0; // child units per 1 parent
	const pfcf        = ratio > 0 ? (1 / ratio) : 0;  // parent units per 1 child unit
	const child_req   = nf(r.child_requirement);
	const total_stock = nf(r.child_stock);
	const alloc_stock = nf(r.child_stock_soft_allocation_qty);
	const short_stock = nf(r.child_stock_shortage);
	const wip_po      = nf(r.child_wip_open_po);
	const alloc_wip   = nf(r.child_wip_open_po_soft_allocation_qty);
	const short_wip   = nf(r.child_wip_open_po_shortage);
	const prod_stock  = nf(r.production_qty_based_on_child_stock);
	const prod_wip    = nf(r.production_qty_based_on_child_stock_wip_open_po);

	const kit_badge = (status) => {
		if (!status) return "—";
		const cfg = { "Full-kit": ["#dcfce7","#166534"], "Partial": ["#fef9c3","#854d0e"], "Pending": ["#fef2f2","#9b1c1c"] };
		const [bg, fg] = cfg[status] || ["#f3f4f6","#374151"];
		return `<span style="background:${bg};color:${fg};padding:2px 10px;border-radius:10px;font-weight:600;font-size:12px;">${e(status)}</span>`;
	};

	const step = (num, title, content) => `
		<div style="margin-bottom:10px;padding:10px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;">
			<div style="font-size:12px;font-weight:600;color:#475569;margin-bottom:6px;">${num}. ${title}</div>
			${content}
		</div>`;

	const code_line = (expr, result, color) =>
		`<div style="font-family:monospace;font-size:13px;padding:4px 8px;background:#fff;border-radius:4px;margin-top:4px;">
			${e(expr)} = <b style="color:${color || "#1d4ed8"};">${n(result)}</b>
		</div>`;

	const html = `
		${step("①", `Parent Item: <b>${e(r.item_code)}</b>`,
			`<table style="border-collapse:collapse;width:100%;">
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;width:200px;">Child Item</td><td style="font-size:12px;font-weight:600;">${e(r.child_item_code)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">On Hand Status</td><td style="font-size:12px;">${e(r.on_hand_status)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">OR with MOQ/Batch</td><td style="font-size:14px;font-weight:bold;color:#1d4ed8;">${n(or)}</td></tr>
			</table>`
		)}

		${step("②", "BOM Ratio → Child Requirement",
			`<table style="border-collapse:collapse;width:100%;margin-bottom:4px;">
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;width:200px;">BOM: produces</td><td style="font-size:12px;">${n(bom_qty_of)} parent unit(s)</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">BOM: needs</td><td style="font-size:12px;">${n(bom_qty)} unit(s) of child</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">Ratio (child per parent)</td><td style="font-size:12px;">${bom_qty} / ${bom_qty_of} = <b>${ratio.toFixed(4)}</b></td></tr>
			</table>
			${code_line(`ceil(OR ${n(or)}  ×  ratio ${ratio.toFixed(4)})`, child_req, "#7c3aed")}
			<div style="font-size:11px;color:#888;margin-top:2px;padding-left:8px;">= <b>${n(child_req)}</b> units of child needed</div>`
		)}

		${step("③", "Child Stock — FIFO Allocation",
			`<table style="border-collapse:collapse;width:100%;margin-bottom:4px;">
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;width:200px;">Total child stock</td><td style="font-size:12px;font-weight:600;">${n(total_stock)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">FIFO allocated to this item</td><td style="font-size:13px;font-weight:bold;color:#0369a1;">${n(alloc_stock)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">Stock shortage</td><td style="font-size:12px;color:${short_stock > 0 ? '#9b1c1c' : '#166534'};">${n(short_stock)}</td></tr>
			</table>
			<div style="font-size:11px;color:#64748b;padding:4px 8px;background:#f0f9ff;border-radius:4px;">
				ℹ FIFO: parents with <b>lower on-hand %</b> (worse buffer status) get child stock first.
				This item got <b>${n(alloc_stock)}</b> of the <b>${n(total_stock)}</b> available.
			</div>`
		)}

		${step("④", `Production Qty (from child stock only) = <b style="color:#166534;">${n(prod_stock)}</b>`,
			`${code_line(`ceil(alloc ${n(alloc_stock)}  ×  factor ${pfcf.toFixed(4)})`, Math.ceil(alloc_stock * pfcf), "#166534")}
			${code_line(`capped at OR:  min(${Math.ceil(alloc_stock * pfcf)},  ${n(or)})`, prod_stock, "#166534")}
			<div style="font-size:11px;color:#888;margin-top:2px;padding-left:8px;">
				factor = bom_quantity / child_bom_qty = ${bom_qty_of} / ${bom_qty} = ${pfcf.toFixed(4)}
				&nbsp;(how many parent units 1 child unit can produce)
			</div>
			<div style="margin-top:6px;">${kit_badge(r.child_full_kit_status)}</div>`
		)}

		${step("⑤", `Production Qty (stock + WIP + Open PO) = <b style="color:#1d4ed8;">${n(prod_wip)}</b>`,
			`<table style="border-collapse:collapse;width:100%;margin-bottom:4px;">
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;width:200px;">Child WIP + Open PO</td><td style="font-size:12px;">${n(wip_po)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">FIFO allocated (WIP/PO)</td><td style="font-size:12px;font-weight:600;color:#0369a1;">${n(alloc_wip)}</td></tr>
				<tr><td style="padding:2px 8px;color:#888;font-size:12px;">WIP/PO shortage</td><td style="font-size:12px;color:${short_wip > 0 ? '#9b1c1c' : '#166534'};">${n(short_wip)}</td></tr>
			</table>
			${code_line(`ceil((stock_alloc ${n(alloc_stock)} + wip_alloc ${n(alloc_wip)})  ×  factor ${pfcf.toFixed(4)})`, Math.ceil((alloc_stock + alloc_wip) * pfcf), "#1d4ed8")}
			${code_line(`capped at OR:  min(${Math.ceil((alloc_stock + alloc_wip) * pfcf)},  ${n(or)})`, prod_wip, "#1d4ed8")}
			<div style="margin-top:6px;">${kit_badge(r.child_wip_open_po_full_kit_status)}</div>`
		)}`;

	frappe.msgprint({
		title: __("Production Qty Breakdown — {0} → {1}", [r.item_code, r.child_item_code || "?"]),
		message: html,
		wide: true,
	});
}

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

function show_child_requirement_dialog(d) {
	const e = v => frappe.utils.escape_html(String(v ?? "—"));
	const n = v => (v === null || v === undefined || v === "") ? "—" : Number(v).toLocaleString();
	const row = (label, val, bold) => `
		<tr>
			<td style="padding:4px 10px;color:#888;font-size:12px;width:230px;white-space:nowrap;">${label}</td>
			<td style="padding:4px 10px;font-size:${bold ? "13" : "12"}px;font-weight:${bold ? "bold" : "normal"};">${val}</td>
		</tr>`;

	const badge = (txt, bg, fg) =>
		`<span style="background:${bg};color:${fg};padding:1px 10px;border-radius:10px;font-weight:bold;font-size:12px;">${e(txt)}</span>`;

	// ── Section 1: Parent item info ────────────────────────────────────────
	const info_html = `
		<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
			<h4 style="margin:0 0 8px;font-size:13px;color:#334155;">① Parent Item</h4>
			<table style="width:100%;border-collapse:collapse;">
				${row("Item Code", `<b>${e(d.item_code)}</b> — ${e(d.item_name)}`)}
				${row("Buffer Flag / SKU Type", `${e(d.buffer_flag)} &nbsp;|&nbsp; <b>${e(d.sku_type)}</b>`)}
				${row("Item Type", e(d.item_type))}
				${row("TOG (Safety Stock)", n(d.tog))}
				${row("MOQ / Batch Size", d.moq > 0 ? `MOQ = ${n(d.moq)}` : d.batch_size > 0 ? `Batch = ${n(d.batch_size)}` : "None")}
			</table>
		</div>`;

	// ── Section 2: Demand & Order Recommendation ──────────────────────────
	const threshold_note = d.threshold_triggered
		? `<span style="color:#c0392b;font-size:11px;">⚠ Raw QD (${n(d.till_today + d.spike)}) &lt; Threshold (${n(d.spike_threshold_qty)}) → set to 0</span>`
		: d.buffer_flag === "Buffer"
			? `<span style="color:#27ae60;font-size:11px;">✓ Passes threshold (${n(d.spike_threshold_qty)})</span>`
			: `<span style="color:#888;font-size:11px;">N/A (Non-Buffer)</span>`;

	const spike_detail = d.spike_sos && d.spike_sos.length
		? `<details style="margin-top:6px;"><summary style="font-size:11px;color:#666;cursor:pointer;">Spike SO details (${d.spike_sos.length})</summary>
		   <table style="border-collapse:collapse;width:100%;margin-top:4px;">
		     <thead><tr style="background:#f1f5f9;"><th style="padding:2px 8px;font-size:11px;text-align:left;">SO</th><th style="padding:2px 8px;font-size:11px;text-align:left;">Delivery Date</th><th style="padding:2px 8px;font-size:11px;text-align:right;">Qty</th></tr></thead>
		     <tbody>${d.spike_sos.map(s => `<tr><td style="padding:2px 8px;font-size:11px;">${e(s.so_name)}</td><td style="padding:2px 8px;font-size:11px;">${e(s.delivery_date)}</td><td style="padding:2px 8px;font-size:11px;text-align:right;">${n(s.qty)}</td></tr>`).join("")}</tbody>
		   </table></details>` : "";

	const demand_html = `
		<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
			<h4 style="margin:0 0 8px;font-size:13px;color:#334155;">② Parent Order Recommendation</h4>
			<table style="width:100%;border-collapse:collapse;">
				${row("On Hand Stock", n(d.stock))}
				${row("WIP (Work Orders)", n(d.wip))}
				${row("Open PO", n(d.open_po))}
				${row("Open SO (all-time)", n(d.open_so))}
				${d.buffer_flag === "Buffer" ? row("Till Today (SO ≤ today)", n(d.till_today)) : ""}
				${d.buffer_flag === "Buffer" ? row(`Spike (next ${n(d.demand_horizon)} days)`, n(d.spike)) : ""}
				${d.buffer_flag === "Buffer" ? row("Threshold check", threshold_note) : ""}
				${row("Qualified Demand", `<b>${n(d.qualified_demand)}</b>`)}
				${spike_detail ? `<tr><td colspan="2">${spike_detail}</td></tr>` : ""}
			</table>
			<div style="margin-top:10px;padding:8px 12px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:4px;">
				<div style="font-size:11px;color:#555;margin-bottom:4px;">Base Order Rec Formula:</div>
				<code style="font-size:12px;color:#166534;">${e(d.order_rec_formula)} = <b>${n(d.base_order_rec)}</b></code>
			</div>
			<div style="margin-top:8px;padding:8px 12px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:4px;">
				<div style="font-size:11px;color:#555;margin-bottom:4px;">MOQ / Batch Size Adjustment:</div>
				<code style="font-size:12px;color:#1d4ed8;">${e(d.moq_batch_note)}</code>
			</div>
			<table style="width:100%;border-collapse:collapse;margin-top:8px;">
				${row("Net Order Rec (before ceil)", n(d.net_order_rec))}
				${row("OR with MOQ/Batch (ceil)", `<b style="font-size:15px;color:#1d4ed8;">${n(d.or_with_moq_batch_size)}</b>`, true)}
			</table>
		</div>`;

	// ── Section 3: BOM info ────────────────────────────────────────────────
	let bom_html;
	if (d.no_bom) {
		bom_html = `
			<div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
				<h4 style="margin:0 0 4px;font-size:13px;color:#334155;">③ BOM</h4>
				<p style="color:#c2410c;font-size:12px;margin:0;">⚠ No active default BOM found for this item. Child requirement cannot be computed.</p>
			</div>`;
	} else {
		bom_html = `
			<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
				<h4 style="margin:0 0 8px;font-size:13px;color:#334155;">③ BOM Details</h4>
				<table style="width:100%;border-collapse:collapse;">
					${row("BOM Name", e(d.bom_name))}
					${row("BOM Quantity (produces)", n(d.bom_quantity))}
					${row("Formula", `Child Req = ceil(OR × child_qty / bom_qty)`)}
				</table>
			</div>`;
	}

	// ── Section 4: Child items table ───────────────────────────────────────
	let child_html = "";
	if (!d.no_bom && d.child_items && d.child_items.length) {
		const child_rows = d.child_items.map(c => {
			const kit_stock_color  = c.full_kit_stock  === "Full Kit" ? "#166534" : "#9b1c1c";
			const kit_wip_color    = c.full_kit_wip_po === "Full Kit" ? "#166534" : "#9b1c1c";
			const kit_stock_bg     = c.full_kit_stock  === "Full Kit" ? "#dcfce7" : "#fef2f2";
			const kit_wip_bg       = c.full_kit_wip_po === "Full Kit" ? "#dcfce7" : "#fef2f2";

			return `<tr style="border-bottom:1px solid #f1f5f9;">
				<td style="padding:6px 8px;font-size:12px;font-weight:600;">${e(c.child_item_code)}</td>
				<td style="padding:6px 8px;font-size:11px;color:#666;">${e(c.item_type || "—")}</td>
				<td style="padding:6px 8px;font-size:11px;color:#666;">${e(c.sku_type || "—")}</td>
				<td style="padding:6px 8px;font-size:11px;text-align:right;">${n(c.bom_qty)} / ${n(c.bom_quantity)}<br><span style="color:#888;">(ratio ${n(c.normalized_ratio)})</span></td>
				<td style="padding:6px 8px;text-align:center;">
					<span style="background:#dbeafe;color:#1e40af;padding:2px 10px;border-radius:10px;font-weight:bold;font-size:13px;">${n(c.child_requirement)}</span>
					<br><span style="font-size:10px;color:#888;">${e(c.req_formula)}</span>
				</td>
				<td style="padding:6px 8px;font-size:12px;text-align:right;">${n(c.child_stock)}</td>
				<td style="padding:6px 8px;font-size:11px;text-align:right;color:#555;">${n(c.child_wip)}</td>
				<td style="padding:6px 8px;font-size:11px;text-align:right;color:#555;">${n(c.child_open_po)}</td>
				<td style="padding:6px 8px;font-size:11px;text-align:right;color:#555;">${n(c.child_wip_open_po)}</td>
				<td style="padding:6px 8px;text-align:center;">
					<span style="background:${kit_stock_bg};color:${kit_stock_color};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;">${e(c.full_kit_stock)}</span>
				</td>
				<td style="padding:6px 8px;text-align:center;">
					<span style="background:${kit_wip_bg};color:${kit_wip_color};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;">${e(c.full_kit_wip_po)}</span>
				</td>
			</tr>`;
		}).join("");

		child_html = `
			<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
				<h4 style="margin:0 0 8px;font-size:13px;color:#334155;">④ Child Requirement Breakdown</h4>
				<div style="overflow-x:auto;">
				<table style="border-collapse:collapse;width:100%;min-width:900px;">
					<thead>
						<tr style="background:#e9eef5;">
							<th style="padding:5px 8px;font-size:11px;text-align:left;">Child Item</th>
							<th style="padding:5px 8px;font-size:11px;text-align:left;">Type</th>
							<th style="padding:5px 8px;font-size:11px;text-align:left;">SKU</th>
							<th style="padding:5px 8px;font-size:11px;text-align:right;">BOM Qty / BOM Qty</th>
							<th style="padding:5px 8px;font-size:11px;text-align:center;">Child Req<br><span style="font-weight:normal;">(ceil(OR × ratio))</span></th>
							<th style="padding:5px 8px;font-size:11px;text-align:right;">Stock</th>
							<th style="padding:5px 8px;font-size:11px;text-align:right;">WIP</th>
							<th style="padding:5px 8px;font-size:11px;text-align:right;">Open PO</th>
							<th style="padding:5px 8px;font-size:11px;text-align:right;">WIP+PO</th>
							<th style="padding:5px 8px;font-size:11px;text-align:center;">vs Stock</th>
							<th style="padding:5px 8px;font-size:11px;text-align:center;">vs Stock+WIP+PO</th>
						</tr>
					</thead>
					<tbody>${child_rows}</tbody>
				</table>
				</div>
				<div style="margin-top:8px;padding:6px 12px;background:#fefce8;border-radius:4px;font-size:11px;color:#854d0e;">
					<b>How to read:</b> Child Req = ceil(OR with MOQ/Batch × normalized BOM ratio). "vs Stock" = can we produce from stock alone? "vs Stock+WIP+PO" = can we produce including inbound stock?
				</div>
			</div>`;
	} else if (!d.no_bom) {
		child_html = `
			<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:12px 16px;margin-bottom:12px;">
				<h4 style="margin:0;font-size:13px;color:#334155;">④ Child Items</h4>
				<p style="color:#aaa;font-size:12px;margin:6px 0 0;">No child items found in the BOM.</p>
			</div>`;
	}

	frappe.msgprint({
		title: __("Child Requirement Debugger — {0}", [d.item_code]),
		message: info_html + demand_html + bom_html + child_html,
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
