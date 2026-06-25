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

	const sku_type_field = page.add_field({
		fieldname: "sku_type",
		label: __("SKU Type"),
		fieldtype: "Select",
		options: ["", "BBMTA", "BBMTO"],
		default: "",
		change() { apply_filter(); },
	});

	const item_code_field = page.add_field({
		fieldname: "item_code",
		label: __("Item Code"),
		fieldtype: "Link",
		options: "Item",
		get_query() {
			return {
				filters: {
					custom_sku_type: ["in", ["BBMTA", "BBMTO"]],
					disabled: 0,
				},
			};
		},
		change() { apply_filter(); },
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
			background:${c.light};color:${c.bg};font-weight:600;font-size:12px;">${fmt_num(n, 0)}</span>`;
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

	function fmt_change_pct(val, idx) {
		if (val === null || val === undefined) return dash();
		const n = parseFloat(val);
		const color = n > 0 ? "#1a7a3f" : n < 0 ? "#c0152a" : "#888";
		const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "";
		return `<span class="bbt-change-pct" data-idx="${idx}"
			style="font-weight:600;color:${color};">${Math.abs(n).toFixed(1)}% ${arrow}</span>`;
	}

	// ── DataTable ─────────────────────────────────────────────────────────────
	let _dt = null;
	let _dt_observer = null;
	let _all_data = [];
	let _raw_data = [];   // full unfiltered dataset

	function apply_filter() {
		const sku = sku_type_field.get_value();
		const item = item_code_field.get_value();
		const filtered = _raw_data.filter(r => {
			if (sku && r.sku_type !== sku) return false;
			if (item && r.item_code !== item) return false;
			return true;
		});
		_all_data = filtered.map((row, idx) => ({ ...row, _idx: idx }));
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }
		_dt = new DataTable(document.getElementById("bbt-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No BB items found."),
			layout: "fixed",
		});
		bind_events();
	}

	const COLS = [
		{
			name: "Item Code", id: "item_code", width: 200, align: "left", editable: false,
			format: val => val
				? `<span class="bbt-item-link" data-item="${esc(val)}"
					style="color:#1a73e8;font-weight:500;cursor:pointer;">${esc(val)}</span>`
				: dash(),
		},
		{
			name: "SKU Type", id: "sku_type", width: 110, align: "center", editable: false,
			format: val => val ? esc(val) : dash(),
		},
		{
			name: "Total Qty", id: "total", width: 130, align: "right", editable: false,
			format: val => `<span style="font-weight:600;">${fmt_num(val, 0)}</span>`,
		},
		{
			name: "Contr%", id: "contr_pct", width: 90, align: "right", editable: false,
			format: val => fmt_pct(val),
		},
		{
			name: "Cumu%", id: "cumu_pct", width: 90, align: "right", editable: false,
			format: (val, _r, _c, d) => {
				const n = parseFloat(val);
				let color = "#c0152a";
				if (n <= 50) color = "#1a7a3f";
				else if (n <= 90) color = "#d4a000";
				return `<span style="font-weight:600;color:${color};">${fmt_pct(val)}</span>`;
			},
		},
		{
			name: "HBT", id: "hbt", width: 80, align: "center", editable: false,
			format: val => hbt_badge(val),
		},
		{
			name: "Frequency", id: "frequency", width: 100, align: "right", editable: false,
			format: val => (val !== null && val !== undefined) ? String(val) : dash(),
		},
		{
			name: "Head Customer", id: "h", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "H"),
		},
		{
			name: "Body Customer", id: "b", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "B"),
		},
		{
			name: "Tail Customer", id: "t", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "T"),
		},
		{
			name: "ADU", id: "adu", width: 110, align: "right", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "LT", id: "lt", width: 90, align: "right", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "FOS", id: "fos", width: 110, align: "right", editable: false,
			format: (val, _r, _c, d) =>
				`<input type="number" class="bbt-fos-input" data-idx="${d._idx}" min="0" step="1"
					value="${val !== null && val !== undefined ? val : ""}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
					font-size:12px;width:80px;text-align:right;background:#fffbe6;">`,
		},
		{
			name: "TOG", id: "tog", width: 110, align: "right", editable: false,
			format: (val, _r, _c, d) =>
				`<input type="number" class="bbt-tog-input" data-idx="${d._idx}" min="0" step="1"
					value="${val !== null && val !== undefined ? val : ""}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
					font-size:12px;width:80px;text-align:right;background:#fffbe6;">`,
		},
		{
			name: "Current TOG", id: "current_tog", width: 120, align: "right", editable: false,
			format: val => val !== null && val !== undefined ? `<span style="font-weight:600;">${fmt_num(val, 0)}</span>` : dash(),
		},
		{
			name: "Change%", id: "change_pct", width: 110, align: "right", editable: false,
			format: (val, _r, _c, d) => fmt_change_pct(val, d._idx),
		},
	];

	function recalc_tog(idx) {
		const row = _all_data[idx];
		const fos = row.fos !== null && row.fos !== undefined ? row.fos : 25;
		const adu = row.adu || 0;
		const lt = row.lt || 0;
		const tog = Math.ceil(adu * lt * (1 + fos / 100));
		row.tog = tog;
		$(`.bbt-tog-input[data-idx="${idx}"]`).val(tog);

		const current_tog = row.current_tog || 0;
		const change_pct = current_tog ? Math.round((tog - current_tog) / current_tog * 1000) / 10 : null;
		row.change_pct = change_pct;
		$(`.bbt-change-pct[data-idx="${idx}"]`).replaceWith(fmt_change_pct(change_pct, idx));
	}

	function bind_events() {
		$(document).off("click", ".bbt-item-link").on("click", ".bbt-item-link", function () {
			const item = $(this).data("item");
			if (item) window.open(`/app/item/${encodeURIComponent(item)}`, "_blank");
		});

		$(document).off("input", ".bbt-fos-input").on("input", ".bbt-fos-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].fos = val === "" ? 0 : parseInt(val);
			recalc_tog(idx);
		});

		$(document).off("input", ".bbt-tog-input").on("input", ".bbt-tog-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].tog = val === "" ? null : parseInt(val);
		});
	}

	function build_datatable(data, period_label) {
		_raw_data = data;
		_all_data = data.map((row, idx) => ({ ...row, _idx: idx }));

		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#bbt-root").html(`
			<div style="font-size:12px;color:#888;margin-bottom:10px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
			</div>
			<div id="bbt-dt" style="overflow-x:auto;"></div>
		`);

		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }

		_dt = new DataTable(document.getElementById("bbt-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No BB items found for the configured HBT period."),
			layout: "fixed",
		});

		// Apply row background colors based on HBT after every render
		function apply_row_colors() {
			const tbody = document.querySelector("#bbt-dt .dt-body");
			if (!tbody) return;
			tbody.querySelectorAll(".dt-row").forEach(tr => {
				const idx = parseInt(tr.getAttribute("data-row-index"));
				if (isNaN(idx)) return;
				const row = _all_data[idx];
				if (!row) return;
				const bg = HBT[row.hbt] ? HBT[row.hbt].light : "";
				tr.querySelectorAll(".dt-cell").forEach(td => {
					td.style.backgroundColor = bg;
				});
			});
		}

		let _obs_timer = null;
		const dt_el = document.getElementById("bbt-dt");
		_dt_observer = new MutationObserver(() => {
			clearTimeout(_obs_timer);
			_obs_timer = setTimeout(apply_row_colors, 30);
		});
		_dt_observer.observe(dt_el, { childList: true, subtree: true });

		apply_row_colors();
		bind_events();
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
