frappe.pages["rb-tog"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "RB TOG",
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
		options: ["", "RBMTA", "RBMTO", "BOTA", "BOTO", "TRMTA", "TRMTO"],
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
					custom_item_type: ["in", ["RB", "BO", "Traded"]],
					disabled: 0,
				},
			};
		},
		change() { apply_filter(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());

	$(`<div id="rbt-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	// ── HBT colour palette ────────────────────────────────────────────────────
	const HBT = {
		H: { bg: "#1a7a3f", fg: "#ffffff", light: "#e8f5ee" },
		B: { bg: "#d4a000", fg: "#ffffff", light: "#fdf7e3" },
		T: { bg: "#c0152a", fg: "#ffffff", light: "#fdecea" },
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
		if (val === null || val === undefined) {
			return `<span class="rbt-change-pct" data-idx="${idx}" style="color:#ccc;">—</span>`;
		}
		const n = parseFloat(val);
		const color = n > 0 ? "#1a7a3f" : n < 0 ? "#c0152a" : "#888";
		const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "";
		return `<span class="rbt-change-pct" data-idx="${idx}"
			style="font-weight:600;color:${color};">${Math.abs(n).toFixed(1)}% ${arrow}</span>`;
	}

	// ── DataTable ─────────────────────────────────────────────────────────────
	let _dt = null;
	let _dt_observer = null;
	let _all_data = [];
	let _raw_data = [];

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
		_dt = new DataTable(document.getElementById("rbt-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No items found."),
			layout: "fixed",
		});
		setup_dt_observer("rbt-dt");
		apply_table_styles("rbt-dt");
		bind_events();
	}

	const COLS = [
		{
			name: "Item Code", id: "item_code", width: 200, align: "left", editable: false,
			format: val => val
				? `<span class="rbt-item-link" data-item="${esc(val)}"
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
				const color = (d && HBT[d.hbt]) ? HBT[d.hbt].bg : "#c0152a";
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
				`<input type="number" class="rbt-fos-input" data-idx="${d._idx}" min="0" step="1"
					value="${val !== null && val !== undefined ? val : ""}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
					font-size:12px;width:80px;text-align:right;background:#fffbe6;">`,
		},
		{
			name: "TOG", id: "tog", width: 110, align: "right", editable: false,
			format: (val, _r, _c, d) =>
				`<input type="number" class="rbt-tog-input" data-idx="${d._idx}" min="0" step="1"
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
		{
			name: "Head Customer",
			id: "h", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "H"),
		},
		{
			name: "Body Customer",
			id: "b", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "B"),
		},
		{
			name: "Tail Customer",
			id: "t", width: 150, align: "right", editable: false,
			format: val => num_badge(val, "T"),
		},
	];

	function apply_row_colors(root_id = "rbt-dt") {
		const tbody = document.querySelector(`#${root_id} .dt-body`);
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

	function apply_hbt_header_colors(root_id = "rbt-dt") {
		COLS.forEach((col, idx) => {
			const hbt_key = { h: "H", b: "B", t: "T" }[col.id];
			if (!hbt_key) return;
			const { bg, fg } = HBT[hbt_key];
			document.querySelectorAll(`#${root_id} .dt-row-header .dt-cell--col-${idx}`).forEach(cell => {
				cell.style.backgroundColor = bg;
				cell.querySelectorAll(".dt-cell__content, .content").forEach(el => {
					el.style.backgroundColor = bg;
					el.style.color = fg;
					el.style.fontWeight = "700";
				});
			});
		});
	}

	function apply_table_styles(root_id = "rbt-dt") {
		apply_row_colors(root_id);
		apply_hbt_header_colors(root_id);
	}

	function setup_dt_observer(root_id = "rbt-dt") {
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		let _obs_timer = null;
		const dt_el = document.getElementById(root_id);
		if (!dt_el) return;
		_dt_observer = new MutationObserver(() => {
			clearTimeout(_obs_timer);
			_obs_timer = setTimeout(() => apply_table_styles(root_id), 30);
		});
		_dt_observer.observe(dt_el, { childList: true, subtree: true });
	}

	function recalc_change_pct(idx) {
		const row = _all_data[idx];
		const tog = row.tog;
		const current_tog = row.current_tog || 0;
		const change_pct = (tog !== null && tog !== undefined && !Number.isNaN(tog) && current_tog)
			? Math.round((tog - current_tog) / current_tog * 1000) / 10
			: null;
		row.change_pct = change_pct;
		const html = fmt_change_pct(change_pct, idx);
		const $el = $(`.rbt-change-pct[data-idx="${idx}"]`);
		if ($el.length) {
			$el.replaceWith(html);
			return;
		}
		// Fallback for cells already showing an untagged dash from before the fix
		const col_idx = COLS.findIndex(c => c.id === "change_pct");
		const $row = $(`.rbt-tog-input[data-idx="${idx}"]`).closest(".dt-row");
		if ($row.length && col_idx >= 0) {
			$row.find(`.dt-cell--col-${col_idx} .dt-cell__content, .dt-cell--col-${col_idx} .content`)
				.first()
				.html(html);
		}
	}

	function recalc_tog(idx) {
		const row = _all_data[idx];
		const fos = row.fos !== null && row.fos !== undefined ? row.fos : 25;
		const tog = Math.ceil((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
		row.tog = tog;
		$(`.rbt-tog-input[data-idx="${idx}"]`).val(tog);
		recalc_change_pct(idx);
	}

	function bind_events() {
		$(document).off("click", ".rbt-item-link").on("click", ".rbt-item-link", function () {
			const item = $(this).data("item");
			if (item) window.open(`/app/item/${encodeURIComponent(item)}`, "_blank");
		});

		$(document).off("input", ".rbt-fos-input").on("input", ".rbt-fos-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].fos = val === "" ? 0 : parseInt(val);
			recalc_tog(idx);
		});

		$(document).off("input", ".rbt-tog-input").on("input", ".rbt-tog-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].tog = val === "" ? null : parseInt(val);
			recalc_change_pct(idx);
		});
	}

	function build_datatable(data, period_label) {
		_raw_data = data;
		_all_data = data.map((row, idx) => ({ ...row, _idx: idx }));

		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#rbt-root").html(`
			<div style="font-size:12px;color:#888;margin-bottom:10px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
			</div>
			<div id="rbt-dt" style="overflow-x:auto;"></div>
		`);

		_dt = new DataTable(document.getElementById("rbt-dt"), {
			columns: COLS,
			data: _all_data,
			serialNoColumn: false,
			checkboxColumn: false,
			inlineFilters: true,
			clusterize: false,
			noDataMessage: __("No items found for the configured TOG period."),
			layout: "fixed",
		});

		setup_dt_observer("rbt-dt");
		apply_table_styles("rbt-dt");
		bind_events();
	}

	// ── Load ──────────────────────────────────────────────────────────────────
	function load_data() {
		$("#rbt-root").html(`
			<div style="padding:24px;text-align:center;color:#888;">
				<div class="spinner" style="display:inline-block;width:20px;height:20px;
					border:3px solid #ddd;border-top-color:#1a7a3f;border-radius:50%;
					animation:rbt-spin 0.8s linear infinite;"></div>
				<span style="margin-left:10px;">Loading…</span>
			</div>
			<style>@keyframes rbt-spin { to { transform: rotate(360deg); } }</style>
		`);

		const view_by = view_by_field.get_value() || "Sale Quantity";

		frappe.call({
			method: "prakash_steel.prakash_steel.page.rb_tog.rb_tog.get_rb_tog_data",
			args: { view_by },
			callback(r) {
				if (!r.message) return;
				const { data, period_label } = r.message;
				if (!data || !data.length) {
					$("#rbt-root").html(`
						<div style="padding:32px;text-align:center;color:#888;">
							No items found for the configured TOG period.
						</div>`);
					return;
				}
				build_datatable(data, period_label || "");
			},
		});
	}

	load_data();
};
