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

	const fos_field = page.add_field({
		fieldname: "global_fos",
		label: __("FOS %"),
		fieldtype: "Int",
		default: 25,
		change() { apply_global_fos(); },
	});

	page.add_inner_button(__("Refresh"), () => load_data());
	page.add_inner_button(__("Export to Excel"), () => export_to_xlsx());
	page.add_inner_button(__("Save"), () => save_selected());
	page.add_inner_button(__("Update TOG"), () => update_tog_selected());
	page.add_inner_button(__("Reset"), () => reset_selected());

	$(`<div id="bbt-root" style="padding:16px 4px 40px;"></div>`).appendTo(page.main);

	$(`<style>
		#bbt-dt .dt-row-header .dt-cell__content,
		#bbt-dt .dt-row-header .content { text-align: left !important; }
	</style>`).appendTo(document.head);

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
	function ceil1000(v) { return Math.ceil(v / 1000) * 1000; }


	function fmt_change_pct(val, idx) {
		if (val === null || val === undefined) {
			return `<span class="bbt-change-pct" data-idx="${idx}" style="color:#ccc;">—</span>`;
		}
		const n = parseFloat(val);
		const color = n > 0 ? "#1a7a3f" : n < 0 ? "#c0152a" : "#888";
		const arrow = n > 0 ? "▲" : n < 0 ? "▼" : "";
		return `<span class="bbt-change-pct" data-idx="${idx}"
			style="font-weight:600;color:${color};">${Math.abs(n).toFixed(1)}% ${arrow}</span>`;
	}

	function get_global_fos() {
		const v = parseInt(fos_field.get_value());
		return isNaN(v) ? 25 : v;
	}

	function apply_global_fos() {
		const fos = get_global_fos();
		_all_data.forEach(row => {
			row.fos = fos;
			row.tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			row.change_pct = current_tog
				? Math.round((row.tog - current_tog) / current_tog * 1000) / 10
				: null;
		});
		if (_dt) _dt.refresh(_all_data);
	}

	// ── DataTable ─────────────────────────────────────────────────────────────
	let _dt = null;
	let _dt_observer = null;
	let _all_data = [];
	let _raw_data = [];
	let _selected = new Set();

	function apply_filter() {
		const sku = sku_type_field.get_value();
		const item = item_code_field.get_value();
		const filtered = _raw_data.filter(r => {
			if (sku && r.sku_type !== sku) return false;
			if (item && r.item_code !== item) return false;
			return true;
		});
		const _gfos = get_global_fos();
		const _new_tog_map = {};
		_all_data.forEach(r => { _new_tog_map[r.item_code] = r.new_tog; });
		_all_data = filtered.map((row, idx) => {
			const fos = _gfos;
			const tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			const change_pct = current_tog ? Math.round((tog - current_tog) / current_tog * 1000) / 10 : null;
			return { ...row, _idx: idx, fos, tog, change_pct, new_tog: row.item_code in _new_tog_map ? _new_tog_map[row.item_code] : (row.new_tog ?? null) };
		});
		_selected.clear();
		_all_data.forEach((row, i) => { if (row.sku_type === "BBMTA") _selected.add(i); });
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
		setup_dt_observer("bbt-dt");
		apply_table_styles("bbt-dt");
		bind_events();
	}

	const COLS = [
		{
			name: "", id: "_select", width: 40, align: "center", editable: false,
			resizable: false, sortable: false,
			format: (_val, _r, _c, d) =>
				`<input type="checkbox" class="bbt-row-check" data-idx="${d._idx}" ${_selected.has(d._idx) ? "checked" : ""}>`,
		},
		{
			name: "", id: "_idx", width: 55, align: "center", editable: false,
			format: (_val, _r, _c, d) => `<span style="color:#888;font-size:12px;">${d._idx + 1}</span>`,
		},
		{
			name: "SKU Type", id: "sku_type", width: 110, align: "center", editable: false,
			format: val => val ? esc(val) : dash(),
		},
		{
			name: "Item Code", id: "item_code", width: 200, align: "center", editable: false,
			format: val => val
				? `<span class="bbt-item-link" data-item="${esc(val)}"
					style="color:#1a73e8;font-weight:500;cursor:pointer;">${esc(val)}</span>`
				: dash(),
		},
		{
			name: "Contr%", id: "contr_pct", width: 90, align: "center", editable: false,
			format: val => fmt_pct(val),
		},
		{
			name: "Cumu%", id: "cumu_pct", width: 90, align: "center", editable: false,
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
			name: "Frequency", id: "frequency", width: 100, align: "center", editable: false,
			format: val => (val !== null && val !== undefined) ? String(val) : dash(),
		},
		{
			name: "Total Qty", id: "total", width: 130, align: "center", editable: false,
			format: val => `<span style="font-weight:600;">${fmt_num(val, 0)}</span>`,
		},
		{
			name: "ADU", id: "adu", width: 110, align: "center", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "LT", id: "lt", width: 90, align: "center", editable: false,
			format: val => val !== null && val !== undefined ? fmt_num(val, 0) : dash(),
		},
		{
			name: "FOS", id: "fos", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) =>
				`<div style="display:flex;align-items:center;gap:2px;">
					<input type="number" class="bbt-fos-input" data-idx="${d._idx}" min="0" step="1"
						value="${val !== null && val !== undefined ? val : ""}"
						style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
						font-size:12px;width:calc(100% - 16px);box-sizing:border-box;text-align:center;background:#fffbe6;">
					<span style="font-size:12px;color:#666;flex-shrink:0;">%</span>
				</div>`,
		},
		{
			name: "Calc TOG", id: "tog", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) =>
				`<span class="bbt-calc-tog" data-idx="${d._idx}" style="font-weight:600;">${val != null ? val : "—"}</span>`,
		},
		{
			name: "New TOG", id: "new_tog", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) =>
				`<input type="number" class="bbt-new-tog-input" data-idx="${d._idx}" min="0" step="1"
					value="${val !== null && val !== undefined ? val : ""}"
					style="border:1px solid #d1d8e0;border-radius:3px;padding:3px 6px;
					font-size:12px;width:100%;box-sizing:border-box;text-align:center;background:#fffbe6;">`,
		},
		{
			name: "Current TOG", id: "current_tog", width: 120, align: "center", editable: false,
			format: val => val ? `<span style="font-weight:600;">${fmt_num(val, 0)}</span>` : dash(),
		},
		{
			name: "Change%", id: "change_pct", width: 110, align: "center", editable: false,
			format: (val, _r, _c, d) => fmt_change_pct(val, d._idx),
		},
		{
			name: "No of Customer", id: "no_of_customer", width: 130, align: "center", editable: false,
			format: val => val != null ? `<span style="font-weight:600;">${val}</span>` : dash(),
		},
		{
			name: "Head Customer", id: "h", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "H"),
		},
		{
			name: "Body Customer", id: "b", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "B"),
		},
		{
			name: "Tail Customer", id: "t", width: 150, align: "center", editable: false,
			format: val => num_badge(val, "T"),
		},
	];

	function apply_row_colors(root_id = "bbt-dt") {
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

	function apply_hbt_header_colors(root_id = "bbt-dt") {
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

	function apply_table_styles(root_id = "bbt-dt") {
		apply_row_colors(root_id);
		apply_hbt_header_colors(root_id);
	}

	function setup_dt_observer(root_id = "bbt-dt") {
		if (_dt_observer) { _dt_observer.disconnect(); _dt_observer = null; }
		let _obs_timer = null;
		const dt_el = document.getElementById(root_id);
		if (!dt_el) return;
		_dt_observer = new MutationObserver(() => {
			clearTimeout(_obs_timer);
			_obs_timer = setTimeout(() => {
				apply_table_styles(root_id);
				document.getElementById(root_id).querySelectorAll(".bbt-row-check").forEach(cb => {
					cb.checked = _selected.has(parseInt(cb.dataset.idx));
				});
			}, 30);
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
		const $el = $(`.bbt-change-pct[data-idx="${idx}"]`);
		if ($el.length) {
			$el.replaceWith(html);
			return;
		}
		// Fallback for cells already showing an untagged dash from before the fix
		const col_idx = COLS.findIndex(c => c.id === "change_pct");
		const $row = $(`.bbt-calc-tog[data-idx="${idx}"]`).closest(".dt-row");
		if ($row.length && col_idx >= 0) {
			$row.find(`.dt-cell--col-${col_idx} .dt-cell__content, .dt-cell--col-${col_idx} .content`)
				.first()
				.html(html);
		}
	}

	function recalc_tog(idx) {
		const row = _all_data[idx];
		const fos = row.fos !== null && row.fos !== undefined ? row.fos : 25;
		const adu = row.adu || 0;
		const lt = row.lt || 0;
		const tog = ceil1000(adu * lt * (1 + fos / 100));
		row.tog = tog;
		$(`.bbt-calc-tog[data-idx="${idx}"]`).text(tog);
		recalc_change_pct(idx);
	}

	function _get_selected_rows() {
		return _all_data.filter((_, i) => _selected.has(i));
	}

	function save_selected() {
		const selected = _get_selected_rows();
		if (!selected.length) {
			frappe.show_alert({ message: __("No rows selected."), indicator: "orange" });
			return;
		}
		const items = selected
			.filter(r => r.sku_type === "BBMTA")
			.map(r => ({ item_code: r.item_code, tog: r.new_tog != null ? r.new_tog : r.tog }));
		if (!items.length) {
			frappe.show_alert({ message: __("No MTA items selected. Only BBMTA items can be saved."), indicator: "orange" });
			return;
		}
		frappe.call({
			method: "prakash_steel.prakash_steel.page.bb_tog.bb_tog.save_tog",
			args: { items: JSON.stringify(items) },
			freeze: true,
			freeze_message: __("Saving TOG values…"),
			callback(r) {
				if (r.message) {
					frappe.show_alert({
						message: __(`${r.message.saved} item(s) saved successfully.`),
						indicator: "green",
					});
				}
			},
		});
	}
	function update_tog_selected() {}
	function reset_selected() {}

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

		$(document).off("input", ".bbt-new-tog-input").on("input", ".bbt-new-tog-input", function () {
			const idx = parseInt($(this).data("idx"));
			const val = $(this).val();
			_all_data[idx].new_tog = val === "" ? null : parseInt(val);
		});

		$(document).off("change", "#bbt-select-all").on("change", "#bbt-select-all", function () {
			if (this.checked) {
				_all_data.forEach((_, i) => _selected.add(i));
			} else {
				_selected.clear();
		_all_data.forEach((row, i) => { if (row.sku_type === "BBMTA") _selected.add(i); });
			}
			$(".bbt-row-check").prop("checked", this.checked);
		});

		$(document).off("change", ".bbt-row-check").on("change", ".bbt-row-check", function () {
			const idx = parseInt($(this).data("idx"));
			if (this.checked) _selected.add(idx);
			else _selected.delete(idx);
			const total = _all_data.length;
			$("#bbt-select-all")
				.prop("indeterminate", _selected.size > 0 && _selected.size < total)
				.prop("checked", _selected.size === total);
		});
	}

	function build_datatable(data, period_label) {
		_raw_data = data;
		const _gfos = get_global_fos();
		_all_data = data.map((row, idx) => {
			const fos = _gfos;
			const tog = ceil1000((row.adu || 0) * (row.lt || 0) * (1 + fos / 100));
			const current_tog = row.current_tog || 0;
			const change_pct = current_tog ? Math.round((tog - current_tog) / current_tog * 1000) / 10 : null;
			return { ...row, _idx: idx, fos, tog, change_pct, new_tog: row.new_tog ?? null };
		});

		_selected.clear();
		_all_data.forEach((row, i) => { if (row.sku_type === "BBMTA") _selected.add(i); });
		if (_dt) { try { _dt.destroy(); } catch (_) {} _dt = null; }

		$("#bbt-root").html(`
			<div style="font-size:12px;color:#888;margin-bottom:10px;padding-left:2px;">
				Period: <strong>${esc(period_label)}</strong>
				&nbsp;·&nbsp; ${data.length} items
			</div>
			<div style="padding:4px 2px 8px;display:flex;align-items:center;gap:8px;">
				<label style="font-size:12px;color:#555;cursor:pointer;display:flex;align-items:center;gap:6px;">
					<input type="checkbox" id="bbt-select-all">
					<span>Select All</span>
				</label>
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

		setup_dt_observer("bbt-dt");
		apply_table_styles("bbt-dt");
		bind_events();
	}

	// ── Export ───────────────────────────────────────────────────────────────
	function export_to_xlsx() {
		if (!_all_data || !_all_data.length) {
			frappe.msgprint(__("No data to export."));
			return;
		}
		const form = document.createElement("form");
		form.method = "POST";
		form.action = "/api/method/prakash_steel.prakash_steel.page.bb_tog.bb_tog.export_bb_tog_xlsx";
		form.style.display = "none";

		const add_field = (name, value) => {
			const input = document.createElement("input");
			input.type = "hidden";
			input.name = name;
			input.value = value;
			form.appendChild(input);
		};

		add_field("data", JSON.stringify(_all_data));
		add_field("filename", "BB_TOG");
		add_field("csrf_token", frappe.csrf_token);

		document.body.appendChild(form);
		form.submit();
		document.body.removeChild(form);
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
