frappe.pages["bb-tog"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "BB TOG",
		single_column: true,
	});

	const view_by_field = page.add_field({
		fieldname: "view_by",
		label: __("View By"),
		fieldtype: "Select",
		options: [
			"Sale Quantity",
			// "Sale Value",   // not yet implemented
			// "Throughput",   // not yet implemented
		],
		default: "Sale Quantity",
		change() { load_data(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="bbt-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	// ── HBT colour palette ────────────────────────────────────────────────────
	const HBT = {
		H: { bg: "#1a7a3f", fg: "#ffffff", light: "#e8f5ee", label: "H — High" },
		B: { bg: "#d4a000", fg: "#ffffff", light: "#fdf7e3", label: "B — Body" },
		T: { bg: "#c0152a", fg: "#ffffff", light: "#fdecea", label: "T — Tail" },
	};

	function hbt_badge(val) {
		if (!val || !HBT[val]) return `<span style="color:#ccc;">—</span>`;
		const c = HBT[val];
		return `<span style="display:inline-block;padding:2px 10px;border-radius:4px;
			background:${c.bg};color:${c.fg};font-weight:700;font-size:12px;
			letter-spacing:1px;">${val}</span>`;
	}

	function num_badge(val, hbt_key) {
		if (val === null || val === undefined) return `<span style="color:#ccc;">—</span>`;
		const n = parseFloat(val);
		if (!n) return `<span style="color:#bbb;">0</span>`;
		const c = HBT[hbt_key];
		return `<span style="display:inline-block;padding:1px 8px;border-radius:3px;
			background:${c.light};color:${c.bg};font-weight:600;font-size:12px;">${fmt_num(n)}</span>`;
	}

	function fmt_num(v, dec = 1) {
		if (v === null || v === undefined) return "—";
		return parseFloat(v).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
	}

	function fmt_pct(v) {
		if (v === null || v === undefined) return "—";
		return parseFloat(v).toFixed(1) + "%";
	}

	function esc(v) { return frappe.utils.escape_html(String(v ?? "")); }
	function dash() { return '<span style="color:#ccc;">—</span>'; }

	// ── Summary cards ─────────────────────────────────────────────────────────
	function render_summary(data) {
		const counts = { H: 0, B: 0, T: 0 };
		const totals = { H: 0, B: 0, T: 0 };
		data.forEach(r => {
			if (HBT[r.hbt]) {
				counts[r.hbt]++;
				totals[r.hbt] += r.total || 0;
			}
		});

		const cards = ["H", "B", "T"].map(k => {
			const c = HBT[k];
			return `
			<div style="flex:1;min-width:160px;border-radius:8px;overflow:hidden;
				box-shadow:0 1px 4px rgba(0,0,0,0.12);">
				<div style="background:${c.bg};color:${c.fg};padding:10px 16px;">
					<span style="font-size:22px;font-weight:800;letter-spacing:2px;">${k}</span>
					<span style="font-size:12px;margin-left:8px;opacity:0.85;">${k === "H" ? "High" : k === "B" ? "Body" : "Tail"}</span>
				</div>
				<div style="background:${c.light};padding:10px 16px;">
					<div style="font-size:24px;font-weight:700;color:${c.bg};">${counts[k]}</div>
					<div style="font-size:11px;color:#666;margin-top:2px;">items &nbsp;|&nbsp; ${fmt_num(totals[k], 0)} qty</div>
				</div>
			</div>`;
		}).join("");

		return `<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px;">${cards}</div>`;
	}

	// ── DataTable ─────────────────────────────────────────────────────────────
	let _dt = null;

	const COLS = [
		{
			name: "Item Code", id: "item_code", width: 200, align: "left",
			format: val => val
				? `<a href="/app/item/${encodeURIComponent(val)}" target="_blank"
					style="font-weight:500;">${esc(val)}</a>`
				: dash(),
		},
		{
			name: "Total Qty", id: "total", width: 130, align: "right",
			format: val => `<span style="font-weight:600;">${fmt_num(val, 1)}</span>`,
		},
		{
			name: "Contr%", id: "contr_pct", width: 90, align: "right",
			format: val => fmt_pct(val),
		},
		{
			name: "Cumu%", id: "cumu_pct", width: 90, align: "right",
			format: (val, _r, _c, d) => {
				const n = parseFloat(val);
				let color = "#c0152a";
				if (n <= 50) color = "#1a7a3f";
				else if (n <= 90) color = "#d4a000";
				return `<span style="font-weight:600;color:${color};">${fmt_pct(val)}</span>`;
			},
		},
		{
			name: "HBT", id: "hbt", width: 80, align: "center",
			format: val => hbt_badge(val),
		},
		{
			name: "Frequency", id: "frequency", width: 100, align: "right",
			format: val => (val !== null && val !== undefined) ? String(val) : dash(),
		},
		{
			name: "H Qty", id: "h", width: 130, align: "right",
			format: val => num_badge(val, "H"),
		},
		{
			name: "B Qty", id: "b", width: 130, align: "right",
			format: val => num_badge(val, "B"),
		},
		{
			name: "T Qty", id: "t", width: 130, align: "right",
			format: val => num_badge(val, "T"),
		},
		{
			name: "ADU", id: "adu", width: 110, align: "right",
			format: val => val !== null && val !== undefined ? fmt_num(val, 2) : dash(),
		},
		{
			name: "LT", id: "lt", width: 90, align: "right",
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "FOS", id: "fos", width: 100, align: "right",
			format: val => val !== null && val !== undefined ? fmt_num(val, 2) : dash(),
		},
		{
			name: "TOG", id: "tog", width: 100, align: "right",
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "Current TOG", id: "current_tog", width: 120, align: "right",
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
	];

	function build_datatable(data, period_label) {
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#bbt-root").html(`
			${render_summary(data)}
			<div style="font-size:12px;color:#888;margin-bottom:10px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
			</div>
			<div id="bbt-dt" style="overflow-x:auto;"></div>
		`);

		_dt = new DataTable(document.getElementById("bbt-dt"), {
			columns: COLS,
			data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No BB items found for the configured HBT period."),
			layout: "fixed",
			getRowHTML(cols, data_row) {
				const hbt = data_row.hbt;
				const bg = (HBT[hbt] && hbt !== "H") ? HBT[hbt].light : "";
				const cells = cols.map(col => {
					const val = data_row[col.id];
					const cell_val = col.format ? col.format(val, null, col, data_row) : (val ?? "");
					const align = col.align || "left";
					return `<td style="padding:6px 10px;text-align:${align};
						${bg ? `background:${bg};` : ""}">${cell_val}</td>`;
				});
				return `<tr>${cells.join("")}</tr>`;
			},
		});
	}

	// ── Load ──────────────────────────────────────────────────────────────────
	function load_data() {
		$("#bbt-root").html(`
			<div style="padding:24px;text-align:center;color:#888;">
				<div class="spinner" style="display:inline-block;width:20px;height:20px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:bbt-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;">Loading…</span>
			</div>
			<style>@keyframes bbt-spin { to { transform: rotate(360deg); } }</style>
		`);

		const view_by = view_by_field.get_value() || "Sale Quantity";

		frappe.call({
			method: "prakash_steel.prakash_steel.page.bb_tog.bb_tog.get_bb_tog_data",
			args: { view_by },
			callback(r) {
				if (!r.message) return;
				const { data, period_label } = r.message;
				if (!data || !data.length) {
					$("#bbt-root").html(`
						<div style="padding:32px;text-align:center;color:#888;">
							No BB items found for the configured HBT period.
						</div>`);
					return;
				}
				build_datatable(data, period_label || "");
			},
		});
	}

	load_data();
};
