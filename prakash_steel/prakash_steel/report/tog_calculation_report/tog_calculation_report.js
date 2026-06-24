// Copyright (c) 2026, beetashok chakraborty and contributors
// For license information, please see license.txt

const TOG_ITEM_DEBUG_METHOD =
	"prakash_steel.prakash_steel.report.tog_calculation_report.tog_calculation_report.get_item_tog_debug";

// function tog_debug_item(item_code) {
// 	if (!item_code) return;
// 	console.info(`[Tog] Fetching debug for: ${item_code} …`);

// 	frappe.call({
// 		method: TOG_ITEM_DEBUG_METHOD,
// 		args: { item_code },
// 		callback: function (r) {
// 			const d = r && r.message;
// 			if (!d) {
// 				console.warn("[Tog] No data returned", r);
// 				return;
// 			}

// 			console.group(
// 				`%c[Tog] ═══ Debug: ${d.item_code} ═══`,
// 				"font-size:14px; font-weight:bold; color:#2196F3"
// 			);
// 			console.log(`Horizon: ${d.horizon_days} days  (${d.start_date} → ${d.end_date})`);
// 			console.log(`%cSell (direct)  = ${d.total_sell}`, "font-weight:bold; color:#4CAF50");
// 			console.log(
// 				`%cParent Sell    = ${d.total_parent_sell_raw.toFixed(4)}  →  ceiled in grid = ${d.total_parent_sell_ceiled}`,
// 				"font-weight:bold; color:#FF9800"
// 			);
// 			console.log(
// 				`%cMean (Sell / days) = ${d.total_sell} / ${d.horizon_days} = ${d.mean_daily_qty}`,
// 				"color:#9C27B0"
// 			);
// 			console.log(
// 				`%cSD = ${d.sd}   |   ADU = ${d.adu}   |   COV (SD/ADU) = ${d.cov !== null ? d.cov : "N/A"}`,
// 				"font-weight:bold; color:#E91E63"
// 			);

// 			// ── SELL: direct sales invoices ──────────────────────────────────
// 			console.group(
// 				`%c[SELL] "${d.item_code}" directly sold on ${d.direct_sells.length} invoice line(s)`,
// 				"color:#4CAF50; font-weight:bold"
// 			);
// 			if (d.direct_sells.length) {
// 				console.table(
// 					d.direct_sells.map((l) => ({
// 						Date: l.posting_date,
// 						"Sales Invoice": l.sales_invoice,
// 						"Sales Order": l.sales_order || "-",
// 						Qty: l.qty,
// 					}))
// 				);
// 			} else {
// 				console.log("No direct sales in this horizon.");
// 			}
// 			console.groupEnd();

// 			// ── PARENT SELL: BOM hops that pushed demand onto this item ───────
// 			console.group(
// 				`%c[PARENT SELL] ${d.parent_sell_contributions.length} BOM hop(s) pushed demand onto "${d.item_code}"`,
// 				"color:#FF9800; font-weight:bold"
// 			);
// 			console.log(
// 				"Formula per hop:  child_need = sold_qty × (bom_fg_qty ÷ bom_line_qty)\n" +
// 				"  path_total added to Parent Sell = path_cumul_before + child_need"
// 			);

// 			if (d.parent_sell_contributions.length) {
// 				// Group by invoice line
// 				const groups = {};
// 				for (const hop of d.parent_sell_contributions) {
// 					const key = `${hop.posting_date}  |  ${hop.sales_invoice}  |  Sold: ${hop.sold_item}  qty=${hop.sold_qty_this_line}`;
// 					if (!groups[key]) groups[key] = [];
// 					groups[key].push(hop);
// 				}

// 				for (const [label, hops] of Object.entries(groups)) {
// 					const h0 = hops[0];
// 					const ratio = h0.bom_fg_qty / h0.bom_line_qty;
// 					const fullLabel =
// 						`${label}  →  BOM ratio ${h0.bom_fg_qty}÷${h0.bom_line_qty}=${ratio.toFixed(4)}` +
// 						`  →  child_need = sold_qty × ${ratio.toFixed(4)}`;
// 					console.groupCollapsed(fullLabel);
// 					console.table(
// 						hops.map((h) => ({
// 							"BOM parent (from)": h.from_item,
// 							"This item (to)": h.to_item,
// 							BOM: h.bom,
// 							"bom_fg_qty (A)": h.bom_fg_qty,
// 							"bom_line_qty (B)": h.bom_line_qty,
// 							"ratio A/B": +(h.bom_fg_qty / h.bom_line_qty).toFixed(4),
// 							"sold_qty (Q)": h.sold_qty_this_line,
// 							"child_need = Q×(A/B)": +h.child_need.toFixed(4),
// 							"path_cumul_before": +h.path_cumulative_before_hop.toFixed(4),
// 							"path_total → added to Parent Sell": +h.path_total_accrued_to_to_item.toFixed(4),
// 						}))
// 					);
// 					console.groupEnd();
// 				}

// 				// Summary per sold item
// 				const by_sold = {};
// 				for (const hop of d.parent_sell_contributions) {
// 					by_sold[hop.sold_item] = (by_sold[hop.sold_item] || 0) + hop.path_total_accrued_to_to_item;
// 				}
// 				console.group("Contribution summary by sold item");
// 				console.table(
// 					Object.entries(by_sold).map(([item, total]) => ({
// 						"Sold Item": item,
// 						"Total added to Parent Sell": +total.toFixed(4),
// 					}))
// 				);
// 				console.groupEnd();
// 			} else {
// 				console.log(
// 					"No BOM hops found.\n" +
// 					"  • No parent item sold in this horizon has a BOM that includes this item\n" +
// 					"  • OR this item has item_type = RM (BOM traversal stops here)"
// 				);
// 			}

// 			console.groupEnd(); // PARENT SELL

// 			// ── SD: daily breakdown ───────────────────────────────────────────
// 			console.group(
// 				`%c[SD] Standard Deviation breakdown for "${d.item_code}"`,
// 				"color:#E91E63; font-weight:bold"
// 			);
// 			console.log(
// 				"Formula:\n" +
// 				"  mean     = total_sell / horizon_days\n" +
// 				"  variance = Σ( (daily_qty − mean)² ) / horizon_days\n" +
// 				"  SD       = √variance"
// 			);
// 			console.log(
// 				`  total_sell = ${d.total_sell}   horizon_days = ${d.horizon_days}` +
// 				`   mean = ${d.mean_daily_qty}   variance = ${d.variance}   SD = ${d.sd}`
// 			);

// 			if (d.sd_daily_breakdown && d.sd_daily_breakdown.length) {
// 				// Highlight only days that had sales
// 				const saleDays = d.sd_daily_breakdown.filter(row => row.qty > 0);
// 				const zeroDays = d.sd_daily_breakdown.filter(row => row.qty === 0);

// 				console.groupCollapsed(`Days WITH sales (${saleDays.length} day(s))`);
// 				console.table(
// 					saleDays.map(row => ({
// 						Date: row.date,
// 						"Daily Qty": row.qty,
// 						"Deviation (qty − mean)": row.deviation,
// 						"Squared Deviation": row.squared_deviation,
// 					}))
// 				);
// 				console.groupEnd();

// 				console.groupCollapsed(`Days with NO sales (${zeroDays.length} day(s))  — qty=0, deviation=${(-d.mean_daily_qty).toFixed(4)}`);
// 				console.table(
// 					zeroDays.map(row => ({
// 						Date: row.date,
// 						"Daily Qty": 0,
// 						"Deviation (0 − mean)": row.deviation,
// 						"Squared Deviation": row.squared_deviation,
// 					}))
// 				);
// 				console.groupEnd();

// 				// Full day-by-day table collapsed
// 				console.groupCollapsed("All days (full table)");
// 				console.table(
// 					d.sd_daily_breakdown.map(row => ({
// 						Date: row.date,
// 						"Daily Qty": row.qty,
// 						"Deviation": row.deviation,
// 						"Squared Deviation": row.squared_deviation,
// 					}))
// 				);
// 				console.groupEnd();
// 			} else {
// 				console.log("No sales data in horizon — SD = 0");
// 			}
// 			console.groupEnd(); // SD

// 			console.groupEnd(); // main group
// 		},
// 		error: function (err) {
// 			console.error(`[Tog] Request failed for "${item_code}"`, err);
// 		},
// 	});
// }

// ─── Report definition ────────────────────────────────────────────────────────
frappe.query_reports["Tog calculation report"] = {
	filters: [],

	onload: function (report) {
		report.page.add_inner_button(__("Debug Item"), function () {
			var d = new frappe.ui.Dialog({
				title: __("Debug Item — Tog Calculation"),
				fields: [
					{
						fieldtype: "Link",
						fieldname: "item_code",
						options: "Item",
						label: __("Item Code"),
						reqd: 1,
						description: __("Open DevTools Console (F12) before clicking Show"),
					},
				],
				primary_action_label: __("Show in Console"),
				primary_action: function (values) {
					d.hide();
					tog_debug_item(values.item_code);
				},
			});
			d.show();
		});
	},
};
