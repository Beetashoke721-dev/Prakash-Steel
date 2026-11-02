// Copyright (c) 2026, Beetashoke Chakraborty and contributors
// For license information, please see license.txt

let _load_colour_rules = [];

const LOAD_COLOUR_STYLES = {
	Black: { bg: "#000000", fg: "#FFFFFF" },
	Red: { bg: "#FF0000", fg: "#FFFFFF" },
	Yellow: { bg: "#FFFF00", fg: "#000000" },
	Green: { bg: "#00C853", fg: "#FFFFFF" },
	White: { bg: "#FFFFFF", fg: "#000000", border: "1px solid #ccc" },
};

function get_load_colour(value, colour_rules) {
	if (value === null || value === undefined || value === "") return null;
	const v = parseFloat(value);
	if (isNaN(v)) return null;
	if (v === 0) return "Black";
	for (const rule of colour_rules) {
		if (v >= rule.from_days && v <= rule.to_days) return rule.colour;
	}
	// Greater than all defined ranges → White
	return "White";
}

function load_colour_badge(value, colour_rules) {
	const colour = get_load_colour(value, colour_rules);
	if (!colour) return value;
	const s = LOAD_COLOUR_STYLES[colour] || {};
	const border = s.border ? `border:${s.border};` : "";
	return `<div style="background:${s.bg};color:${s.fg};${border}padding:4px;text-align:center;font-weight:bold;border-radius:0px;">${value}</div>`;
}

function show_machine_breakdown(d) {
	if (!d || !d.machine) {
		frappe.msgprint(__("No data returned."));
		return;
	}

	const fmt = v => (v === null || v === undefined) ? "&mdash;" : v;

	// Machine summary card
	const summary = `
		<div style="display:flex;flex-wrap:wrap;gap:16px;margin-bottom:16px;font-size:13px;background:#f4f6fa;padding:12px 16px;border-radius:6px;border:1px solid #dde;">
			<span><b>Machine:</b> ${frappe.utils.escape_html(d.machine)}</span>
			<span><b>No of Machines:</b> ${fmt(d.no_of_machines)}</span>
			<span><b>Runtime (hrs/day):</b> ${fmt(d.runtime)}</span>
			<span><b>OEE (%):</b> ${fmt(d.oee)}</span>
			<span><b>Effective Runtime (hrs):</b> <span style="color:#1a6;">${fmt(d.effective_runtime)}</span></span>
		</div>`;

	// Formula explanation
	const formula = `
		<div style="font-size:12px;background:#fff8e1;border:1px solid #ffe082;padding:10px 14px;border-radius:6px;margin-bottom:16px;">
			<b>Formula:</b>&nbsp;
			Net Load (Days) = <code>(Total Qty &divide; Effective Runtime) &divide; No of Machines</code><br>
			<span style="color:#666;">Effective Runtime = Runtime &times; (OEE / 100)
			&nbsp;|&nbsp; <b>Net Prod Load</b> uses Production Order Rec (wip/mrq/moq applied)
			&nbsp;|&nbsp; <b>Net Order Load</b> uses Open SO &minus; Stock</span>
		</div>`;

	// Per-item table
	const hdrs = [
		"Item Code", "SKU Type", "Kg/Hr", "Open SO", "Stock", "WIP", "MRQ", "TOG",
		"Qual. Demand", "MOQ", "Batch Size", "Base OR", "Net OR", "Prod Hrs (OR/Kg·Hr)",
		"Order Req", "Order Hrs (Req/Kg·Hr)"
	].map(h => `<th style="padding:5px 8px;border-bottom:2px solid #ddd;white-space:nowrap;font-size:11px;text-align:right;">${h}</th>`).join("");

	const tbody = (d.items || []).map(r => {
		const sku_bg = r.sku_type === "BBMTA" ? "#e8f5e9" : "#e3f2fd";
		return `<tr style="border-bottom:1px solid #eee;">
			<td style="padding:4px 8px;font-size:12px;font-weight:bold;white-space:nowrap;">${frappe.utils.escape_html(r.item_code)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:center;"><span style="background:${sku_bg};padding:1px 6px;border-radius:3px;">${r.sku_type}</span></td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;font-weight:bold;">${fmt(r.kg_per_hour)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.open_so)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.stock)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.wip)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.mrq)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.tog)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.qualified_demand)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.moq)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;">${fmt(r.batch_size)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;color:#888;">${fmt(r.base_order_rec)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;font-weight:bold;">${fmt(r.net_order_rec)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;font-weight:bold;color:#1a6;">${fmt(r.prod_hours)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;font-weight:bold;">${fmt(r.order_req)}</td>
			<td style="padding:4px 8px;font-size:12px;text-align:right;font-weight:bold;color:#e65;">${fmt(r.order_hours)}</td>
		</tr>`;
	}).join("");

	// Totals row
	const totals_row = `
		<tr style="background:#f0f4ff;font-weight:bold;border-top:2px solid #aac;">
			<td colspan="13" style="padding:5px 8px;font-size:12px;text-align:right;">TOTAL HOURS</td>
			<td style="padding:5px 8px;font-size:12px;text-align:right;color:#1a6;">${fmt(d.total_prod_hours)}</td>
			<td style="padding:5px 8px;font-size:12px;text-align:right;"></td>
			<td style="padding:5px 8px;font-size:12px;text-align:right;color:#e65;">${fmt(d.total_order_hours)}</td>
		</tr>`;

	// Build colour reason explanation for a value
	function colour_reason(value, colour_rules) {
		const v = parseFloat(value);
		if (isNaN(v) || value === null || value === undefined) return "";
		const colour = get_load_colour(value, colour_rules);
		if (!colour) return "";
		const s = LOAD_COLOUR_STYLES[colour] || {};
		const badge = `<span style="display:inline-block;background:${s.bg};color:${s.fg};${s.border ? `border:${s.border};` : ""}padding:1px 8px;border-radius:3px;font-weight:bold;font-size:12px;">${colour}</span>`;
		let reason = "";
		if (v === 0) {
			reason = "Value = 0 → Black";
		} else {
			const matched = colour_rules.find(r => v >= r.from_days && v <= r.to_days);
			if (matched) {
				reason = `${v} days falls in range ${matched.from_days}–${matched.to_days} days`;
			} else {
				const max_rule = colour_rules.length ? colour_rules[colour_rules.length - 1] : null;
				reason = max_rule
					? `${v} days exceeds all ranges (max defined: ${max_rule.to_days} days) → White`
					: "No colour rules defined → White";
			}
		}
		return `<div style="margin-top:6px;font-size:11px;color:#555;">Colour: ${badge} &nbsp; <span style="color:#888;">${reason}</span></div>`;
	}

	// Colour rules table
	const rules = _load_colour_rules;
	const rules_rows = rules.map(r => {
		const s = LOAD_COLOUR_STYLES[r.colour] || {};
		return `<tr>
			<td style="padding:3px 10px;font-size:11px;text-align:center;">
				<span style="display:inline-block;background:${s.bg};color:${s.fg};${s.border ? `border:${s.border};` : ""}padding:1px 8px;border-radius:3px;font-weight:bold;">${r.colour}</span>
			</td>
			<td style="padding:3px 10px;font-size:11px;text-align:center;">${r.from_days}</td>
			<td style="padding:3px 10px;font-size:11px;text-align:center;">${r.to_days}</td>
		</tr>`;
	}).join("");
	const colour_table = rules.length ? `
		<div style="margin-top:14px;font-size:12px;">
			<b>Colour Rules (from Machine Load Colour Master):</b>
			<table style="margin-top:6px;border-collapse:collapse;border:1px solid #ddd;">
				<thead>
					<tr style="background:#f0f0f0;">
						<th style="padding:4px 10px;font-size:11px;">Colour</th>
						<th style="padding:4px 10px;font-size:11px;">From (days)</th>
						<th style="padding:4px 10px;font-size:11px;">To (days)</th>
					</tr>
				</thead>
				<tbody>${rules_rows}</tbody>
			</table>
			<div style="font-size:11px;color:#888;margin-top:4px;">Value = 0 → Black &nbsp;|&nbsp; Value > max range → White</div>
		</div>` : `<div style="margin-top:10px;font-size:11px;color:#999;">No colour rules loaded.</div>`;

	// Final calculation
	const calc = `
		<div style="display:flex;gap:24px;margin-top:16px;font-size:13px;flex-wrap:wrap;">
			<div style="background:#e8f5e9;padding:12px 20px;border-radius:6px;border:1px solid #a5d6a7;min-width:240px;">
				<div style="font-size:11px;color:#555;margin-bottom:4px;">NET PROD LOAD (Days)</div>
				<div style="font-size:22px;font-weight:bold;color:#2e7d32;">${fmt(d.net_prod_load)}</div>
				<div style="font-size:11px;color:#777;margin-top:4px;">(${fmt(d.total_prod_hours)} hrs &divide; ${fmt(d.effective_runtime)}) &divide; ${fmt(d.no_of_machines)}</div>
				${colour_reason(d.net_prod_load, rules)}
			</div>
			<div style="background:#fff3e0;padding:12px 20px;border-radius:6px;border:1px solid #ffcc80;min-width:240px;">
				<div style="font-size:11px;color:#555;margin-bottom:4px;">NET ORDER LOAD (Days)</div>
				<div style="font-size:22px;font-weight:bold;color:#e65100;">${fmt(d.net_order_load)}</div>
				<div style="font-size:11px;color:#777;margin-top:4px;">(${fmt(d.total_order_hours)} hrs &divide; ${fmt(d.effective_runtime)}) &divide; ${fmt(d.no_of_machines)}</div>
				${colour_reason(d.net_order_load, rules)}
			</div>
		</div>
		${colour_table}`;

	const html = summary + formula + `
		<div style="overflow-x:auto;">
			<table style="width:100%;border-collapse:collapse;">
				<thead><tr style="background:#f0f0f0;">${hdrs}</tr></thead>
				<tbody>${tbody}${totals_row}</tbody>
			</table>
		</div>` + calc;

	frappe.msgprint({
		title: __("Machine Load Debug — {0}", [d.machine]),
		message: html,
		wide: true,
	});
}

function ensure_bold_headers() {
	if (document.getElementById("bright-machine-load-bold-headers")) return;
	const style = document.createElement("style");
	style.id = "bright-machine-load-bold-headers";
	style.innerHTML = `.dt-cell--header .dt-cell__content { font-weight: 700 !important; }`;
	document.head.appendChild(style);
}

frappe.query_reports["Bright Machine Load"] = {
	"filters": [],

	onload(report) {
		ensure_bold_headers();

		// Fetch colour rules once into module-level variable
		frappe.call({
			method: "prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load.get_machine_load_colours",
			callback(r) {
				_load_colour_rules = r.message || [];
			},
		});

		report.page.add_inner_button(__("Debug Machine Breakdown"), () => {
			const dlg = new frappe.ui.Dialog({
				title: __("Debug Machine Breakdown"),
				fields: [
					{
						label: __("Machine"),
						fieldname: "machine_group_name",
						fieldtype: "Link",
						options: "Bright Machine",
						reqd: 1,
					},
				],
				primary_action_label: __("Show Breakdown"),
				primary_action({ machine_group_name }) {
					if (!machine_group_name) return;
					dlg.disable_primary_action();
					frappe.call({
						method: "prakash_steel.prakash_steel.report.bright_machine_load.bright_machine_load.get_machine_breakdown",
						args: { machine_group_name },
						callback(r) {
							dlg.enable_primary_action();
							show_machine_breakdown(r.message || {});
						},
						error() {
							dlg.enable_primary_action();
						},
					});
				},
			});
			dlg.show();
		});
	},

	formatter(value, row, column, data, default_formatter) {
		if (column.fieldname === "no_of_machines" && data) {
			const v = data.no_of_machines;
			return `<div style="text-align:center;font-weight:bold;">${v === null || v === undefined ? "" : v}</div>`;
		}
		if (column.fieldname === "machine_name" && data) {
			const v = data.machine_name;
			return `<div style="font-weight:bold;">${v === null || v === undefined ? "" : frappe.utils.escape_html(v)}</div>`;
		}
		value = default_formatter(value, row, column, data);
		if (
			(column.fieldname === "net_prod_load" || column.fieldname === "net_order_load") &&
			data && value !== null && value !== undefined
		) {
			const rules = _load_colour_rules;
			return load_colour_badge(data[column.fieldname], rules);
		}
		return value;
	},
};
